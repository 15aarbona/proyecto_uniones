import numpy as np
import torch
from torch.utils.data import Dataset
from sklearn.preprocessing import StandardScaler, LabelEncoder

from config import (
    CATEGORICAL_FEATURES, NUMERIC_FEATURES, REGRESSION_ALWAYS,
    MASKED_COLUMNS, CATALOGO_BOLT,
)
from geometry import gaps_from_p

BOLT_TO_IDX = {v: i for i, v in enumerate(CATALOGO_BOLT)}


def add_geometry_targets(df):
    """
    Deriva E-S, D_1..D_5, I-C, C_1..C_5, E-C a partir de p1..p12 + e + d + BEAM_d_mm y los
    añade al dataframe. Necesario porque train/test.parquet solo tienen p1..p12 (no hay
    columna C_i real: es un concepto nuevo). Llamar UNA vez, antes de Preprocessor.fit /
    ConnectionDataset, sobre train_df/val_df/test_df.
    """
    df = df.copy()
    geom = gaps_from_p(df)
    for c in geom.columns:
        df[c] = geom[c]
    return df


class Preprocessor:
    """Ajusta encoders/scalers SOLO con el split de train y los reutiliza en val/test/inferencia.
    Requiere que el df ya tenga las columnas de add_geometry_targets (E-S, D_*, I-C, C_*, E-C)."""

    def fit(self, df):
        self.cat_encoders = {c: LabelEncoder().fit(df[c].astype(str)) for c in CATEGORICAL_FEATURES}
        self.num_scaler = StandardScaler().fit(df[NUMERIC_FEATURES].values)
        self.reg_always_scaler = StandardScaler().fit(df[REGRESSION_ALWAYS].values)
        self.drawing_code_encoder = LabelEncoder().fit(df["DrawingCode"].astype(str))

        # Media/std de cada columna enmascarada (geometría + rigidizadores) SOLO sobre sus
        # valores activos (>0): si se incluyeran los ceros, la media de columnas raras como
        # C_4/C_5 quedaría dominada por ceros y los valores reales caerían a muchas sigmas.
        m = df[MASKED_COLUMNS].fillna(0.0).values.astype(np.float64)
        self.masked_mean = np.zeros(m.shape[1])
        self.masked_std = np.ones(m.shape[1])
        self.masked_active_frac = np.zeros(m.shape[1])
        for j in range(m.shape[1]):
            act = m[:, j] > 0
            self.masked_active_frac[j] = act.mean()
            if act.sum() > 1:
                self.masked_mean[j] = m[act, j].mean()
                self.masked_std[j] = max(m[act, j].std(), 1e-6)
        return self

    @property
    def cat_cardinalities(self):
        return [len(self.cat_encoders[c].classes_) for c in CATEGORICAL_FEATURES]

    @property
    def n_drawing_codes(self):
        return len(self.drawing_code_encoder.classes_)

    def transform_features(self, df):
        x_cat = np.stack([self.cat_encoders[c].transform(df[c].astype(str)) for c in CATEGORICAL_FEATURES], axis=1)
        x_num = self.num_scaler.transform(df[NUMERIC_FEATURES].values).astype(np.float32)
        return x_cat.astype(np.int64), x_num

    def transform_targets(self, df):
        drawing_idx = self.drawing_code_encoder.transform(df["DrawingCode"].astype(str))
        bolt_nominal = df["Bolt"].astype(str).str.replace("M", "", regex=False).astype(int)
        bolt_idx = bolt_nominal.map(BOLT_TO_IDX).values
        slip = (df["SlipCritical"].astype(str) == "YES").astype(np.float32).values

        reg_always = self.reg_always_scaler.transform(df[REGRESSION_ALWAYS].values).astype(np.float32)

        m = df[MASKED_COLUMNS].fillna(0.0).values.astype(np.float32)
        masked_mask = (m > 0.0).astype(np.float32)
        masked_value = ((m - self.masked_mean) / self.masked_std).astype(np.float32)

        return {
            "drawing_code_idx": drawing_idx.astype(np.int64),
            "bolt_idx": bolt_idx.astype(np.int64),
            "slip_critical": slip,
            "reg_always": reg_always,
            "masked_value": masked_value,
            "masked_mask": masked_mask,
        }

    def inverse_reg_always(self, standardized):
        return self.reg_always_scaler.inverse_transform(standardized)

    def inverse_masked(self, standardized):
        return standardized * self.masked_std + self.masked_mean


class ConnectionDataset(Dataset):
    def __init__(self, df, preprocessor: Preprocessor):
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
        for k, v in self.targets.items():
            item[k] = torch.tensor(v[idx])
        return item
