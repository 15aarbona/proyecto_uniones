import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset
from sklearn.preprocessing import StandardScaler, LabelEncoder
from .config import (
    CATEGORICAL_FEATURES, NUMERIC_FEATURES, REGRESSION_ALWAYS, MASKED_COLUMNS,
    CATALOGO_BOLT, P_COLUMNS, N_Y, N_ALMA_CLASSES, N_CANTONERA_CLASSES,
    TARGET_CLS_N_ALMA, TARGET_CLS_N_CANTONERA, P_TRANSITION_TO_IDX,
    P_TRANSITION_UNUSED_IDX, secuencia_transiciones,
)

BOLT_TO_IDX = {value: idx for idx, value in enumerate(CATALOGO_BOLT)}

def bolt_nominal_mm(df):
    return df["Bolt"].astype(str).str.replace("M", "", regex=False).astype(int)

def transition_indices_from_counts(n_alma_values, n_cantonera_values, n_p=N_Y):
    na = np.asarray(n_alma_values, dtype=int)
    nc = np.asarray(n_cantonera_values, dtype=int)
    out = np.full((len(na), n_p), P_TRANSITION_UNUSED_IDX, dtype=np.int64)
    for row, (a, c) in enumerate(zip(na, nc)):
        transitions = secuencia_transiciones(a, c)
        if len(transitions) > n_p:
            raise ValueError(f"Row {row}: {len(transitions)} transitions exceed n_p={n_p}")
        for j, name in enumerate(transitions):
            out[row, j] = P_TRANSITION_TO_IDX[name]
    return out

def validate_connection_targets(df):
    p = df[P_COLUMNS].fillna(0.0).to_numpy(float)
    active = p > 0
    expected = df["n_alma"].astype(int).to_numpy() + df["n_cantonera"].astype(int).to_numpy() + 1
    expected_mask = np.arange(N_Y)[None, :] < expected[:, None]
    result = pd.DataFrame(index=df.index)
    result["expected_p_count"] = expected
    result["actual_p_count"] = active.sum(axis=1)
    result["count_valid"] = result["actual_p_count"].to_numpy() == expected
    result["prefix_valid"] = np.all(active == expected_mask, axis=1)
    result["valid"] = result["count_valid"] & result["prefix_valid"]
    return result

class Preprocessor:
    def fit(self, df):
        self.cat_encoders = {c: LabelEncoder().fit(df[c].astype(str)) for c in CATEGORICAL_FEATURES}
        self.num_scaler = StandardScaler().fit(df[NUMERIC_FEATURES].to_numpy())
        self.reg_always_scaler = StandardScaler().fit(df[REGRESSION_ALWAYS].to_numpy())
        self.standard_encoder = LabelEncoder().fit(df["standard"].astype(str))

        m = df[MASKED_COLUMNS].fillna(0.0).to_numpy(np.float64)
        self.masked_mean = np.zeros(m.shape[1], dtype=np.float64)
        self.masked_std = np.ones(m.shape[1], dtype=np.float64)
        self.masked_active_frac = np.zeros(m.shape[1], dtype=np.float64)
        for j in range(m.shape[1]):
            active = m[:, j] > 0
            self.masked_active_frac[j] = active.mean()
            if active.sum() > 1:
                self.masked_mean[j] = m[active, j].mean()
                self.masked_std[j] = max(m[active, j].std(), 1e-6)

        self.presence_pos_weight = np.ones(m.shape[1], dtype=np.float32)
        for j, frac in enumerate(self.masked_active_frac):
            self.presence_pos_weight[j] = max((1-frac)/max(frac, 1e-6), 1.0)

        self.count_class_weights = {
            TARGET_CLS_N_ALMA: self._count_weights(df[TARGET_CLS_N_ALMA], N_ALMA_CLASSES),
            TARGET_CLS_N_CANTONERA: self._count_weights(df[TARGET_CLS_N_CANTONERA], N_CANTONERA_CLASSES),
        }
        return self

    @staticmethod
    def _count_weights(values, n_classes):
        vals = np.asarray(values, dtype=int)
        counts = np.array([max((vals == c).sum(), 1) for c in range(n_classes)], float)
        weights = len(vals) / (n_classes * counts)
        return (weights / weights.mean()).astype(np.float32)

    @property
    def cat_cardinalities(self):
        return [len(self.cat_encoders[c].classes_) for c in CATEGORICAL_FEATURES]

    @property
    def n_standard_classes(self):
        return len(self.standard_encoder.classes_)

    def transform_features(self, df):
        x_cat = np.stack([self.cat_encoders[c].transform(df[c].astype(str)) for c in CATEGORICAL_FEATURES], axis=1)
        x_num = self.num_scaler.transform(df[NUMERIC_FEATURES].to_numpy()).astype(np.float32)
        return x_cat.astype(np.int64), x_num

    def transform_targets(self, df):
        standard_idx = self.standard_encoder.transform(df["standard"].astype(str)).astype(np.int64)
        bolt_mm = bolt_nominal_mm(df)
        bolt_idx = bolt_mm.map(BOLT_TO_IDX).to_numpy()
        if pd.isna(bolt_idx).any():
            raise ValueError("Bolt contains values outside CATALOGO_BOLT")
        slip = df["SlipCritical"].astype(str).str.upper().isin(["YES", "TRUE", "1"]).astype(np.float32).to_numpy()
        na = df["n_alma"].astype(int).to_numpy()
        nc = df["n_cantonera"].astype(int).to_numpy()
        reg = self.reg_always_scaler.transform(df[REGRESSION_ALWAYS].to_numpy()).astype(np.float32)
        real = df[MASKED_COLUMNS].fillna(0.0).to_numpy(np.float32)
        mask = (real > 0).astype(np.float32)
        values = ((real - self.masked_mean) / self.masked_std).astype(np.float32)
        transitions = transition_indices_from_counts(na, nc)
        return {
            "standard_idx": standard_idx,
            "bolt_idx": bolt_idx.astype(np.int64),
            "slip_critical": slip,
            "n_alma_idx": na.astype(np.int64),
            "n_cantonera_idx": nc.astype(np.int64),
            "reg_always": reg,
            "masked_value": values,
            "masked_mask": mask,
            "p_transition_idx": transitions,
        }

    def inverse_reg_always(self, standardized):
        return self.reg_always_scaler.inverse_transform(standardized)

    def inverse_masked(self, standardized):
        return standardized * self.masked_std + self.masked_mean

class ConnectionDataset(Dataset):
    def __init__(self, df, preprocessor):
        self.x_cat, self.x_num = preprocessor.transform_features(df)
        self.targets = preprocessor.transform_targets(df)
        self.n = len(df)

    def __len__(self):
        return self.n

    def __getitem__(self, idx):
        item = {
            "x_cat": torch.tensor(self.x_cat[idx], dtype=torch.long),
            "x_num": torch.tensor(self.x_num[idx], dtype=torch.float32),
        }
        long_keys = {"standard_idx", "bolt_idx", "n_alma_idx", "n_cantonera_idx", "p_transition_idx"}
        for key, values in self.targets.items():
            dtype = torch.long if key in long_keys else torch.float32
            item[key] = torch.tensor(values[idx], dtype=dtype)
        return item
