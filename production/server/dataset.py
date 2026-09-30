import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset
from sklearn.preprocessing import LabelEncoder, StandardScaler

from config import (
    CATEGORICAL_FEATURES, NUMERIC_FEATURES, REGRESSION_ALWAYS,
    MASKED_COLUMNS, CATALOGO_BOLT, Y_COLUMNS, P_COLUMNS,
    P_LABEL_COLUMNS, N_P_LABEL_CLASSES,
    TARGET_CLS_N_ALMA, TARGET_CLS_N_CANTONERA,
    N_ALMA_CLASSES, N_CANTONERA_CLASSES,
    ACERO_TABLE, TORNILLO_TABLE,
)

BOLT_TO_IDX = {v: i for i, v in enumerate(CATALOGO_BOLT)}


def bolt_nominal_mm(df):
    """Bolt -> diámetro nominal en mm. Tolera 'Bolt' o 'bolt' y valores nulos/NaN."""
    col = None
    if "Bolt" in df.columns:
        col = df["Bolt"]
    elif "bolt" in df.columns:
        col = df["bolt"]

    if col is None:
        return pd.Series(20, index=df.index, dtype=int)

    # Limpieza robusta de NaNs, 'M' y textos no numéricos
    s = (
        col.fillna(20)
        .astype(str)
        .str.replace("M", "", regex=False)
        .str.replace("nan", "20", regex=False)
        .str.replace("None", "20", regex=False)
    )
    return pd.to_numeric(s, errors="coerce").fillna(20).astype(int)


def ys_from_p(df):
    df = df.copy()
    P = df[P_COLUMNS].fillna(0.0).values.astype(float)
    e = df["e"].fillna(50.0).values.astype(float) if "e" in df.columns else np.full(len(df), 50.0)
    cum = P.cumsum(axis=1) + e[:, None]
    Y = np.where(P > 0, cum, 0.0)
    for i, col in enumerate(Y_COLUMNS):
        df[col] = Y[:, i]
    return df


def counts_from_ys(df):
    Y = df[Y_COLUMNS].fillna(0.0).values
    active = Y > 0
    e = df["e"].fillna(50.0).values.astype(float)
    d = df["d"].fillna(50.0).values.astype(float)
    h = df["BEAM_d_mm"].fillna(300.0).values.astype(float)
    y_ala_sup = e + d
    y_ala_inf = e + d + h

    n_alma = ((Y >= y_ala_sup[:, None]) & (Y <= y_ala_inf[:, None]) & active).sum(axis=1)
    n_debajo = ((Y > y_ala_inf[:, None]) & active).sum(axis=1)
    n_cantonera = np.maximum(n_debajo - 1, 0)
    num_filas = 1 + active.sum(axis=1)
    return n_alma, n_cantonera, num_filas


def counts_from_p(df):
    P = df[P_COLUMNS].fillna(0.0).values.astype(float)
    e = df["e"].fillna(50.0).values.astype(float)
    d = df["d"].fillna(50.0).values.astype(float)
    h = df["BEAM_d_mm"].fillna(300.0).values.astype(float)
    y_ala_sup = e + d
    y_ala_inf = e + d + h

    Y = np.where(P > 0, P.cumsum(axis=1) + e[:, None], 0.0)
    n_alma = ((Y >= y_ala_sup[:, None]) & (Y <= y_ala_inf[:, None]) & (P > 0)).sum(axis=1)
    n_debajo = ((Y > y_ala_inf[:, None]) & (P > 0)).sum(axis=1)
    n_cantonera = np.maximum(n_debajo - 1, 0)
    num_filas = 1 + (P > 0).sum(axis=1)
    return n_alma.astype(int), n_cantonera.astype(int), num_filas.astype(int)


class Preprocessor:
    """Ajusta encoders/scalers sanitizando valores faltantes o etiquetas no vistas."""

    def _enrich_materials(self, df):
        """Auto-rellena fy/fu de acero y tornillos si faltan y se dispone de grado/clase."""
        df = df.copy()

        if "grado_acero" in df.columns:
            for idx in df.index:
                grado = str(df.at[idx, "grado_acero"]).strip() if pd.notna(df.at[idx, "grado_acero"]) else ""
                if grado in ACERO_TABLE:
                    for k, v in ACERO_TABLE[grado].items():
                        if k not in df.columns or pd.isna(df.at[idx, k]) or df.at[idx, k] == 0:
                            df.at[idx, k] = v

        if "clase_tornillo" in df.columns:
            for idx in df.index:
                clase = str(df.at[idx, "clase_tornillo"]).strip() if pd.notna(df.at[idx, "clase_tornillo"]) else ""
                if clase in TORNILLO_TABLE:
                    for k, v in TORNILLO_TABLE[clase].items():
                        if k not in df.columns or pd.isna(df.at[idx, k]) or df.at[idx, k] == 0:
                            df.at[idx, k] = v

        return df

    def fit(self, df):
        df = self._enrich_materials(df)

        self.cat_encoders = {}
        for c in CATEGORICAL_FEATURES:
            s = df[c].fillna("UNKNOWN").astype(str) if c in df.columns else pd.Series(["UNKNOWN"] * len(df), index=df.index)
            self.cat_encoders[c] = LabelEncoder().fit(s)

        df_num = df.reindex(columns=NUMERIC_FEATURES, fill_value=0.0)
        num_vals = df_num[NUMERIC_FEATURES].apply(pd.to_numeric, errors="coerce").fillna(0.0).values
        self.num_scaler = StandardScaler().fit(num_vals)

        df_reg = df.reindex(columns=REGRESSION_ALWAYS, fill_value=0.0)
        reg_vals = df_reg[REGRESSION_ALWAYS].apply(pd.to_numeric, errors="coerce").fillna(0.0).values
        self.reg_always_scaler = StandardScaler().fit(reg_vals)

        std_s = df["standard"].fillna("AISC 360-16").astype(str) if "standard" in df.columns else pd.Series(["AISC 360-16"] * len(df), index=df.index)
        self.standard_encoder = LabelEncoder().fit(std_s)

        if all(c in df.columns for c in P_LABEL_COLUMNS):
            # Las etiquetas ausentes (NaN) NO se convierten en 'UNUSED': se ignoran en el entrenamiento.
            p_concat = pd.concat([df[c] for c in P_LABEL_COLUMNS], ignore_index=True).dropna().astype(str)
            p_concat = pd.concat([p_concat, pd.Series(["UNUSED"])], ignore_index=True)
            self.p_label_encoder = LabelEncoder().fit(p_concat)
        else:
            self.p_label_encoder = None

        df_masked = df.reindex(columns=MASKED_COLUMNS, fill_value=0.0)
        m = df_masked[MASKED_COLUMNS].apply(pd.to_numeric, errors="coerce").fillna(0.0).values.astype(np.float64)

        self.masked_mean = np.zeros(m.shape[1])
        self.masked_std = np.ones(m.shape[1])
        self.masked_active_frac = np.zeros(m.shape[1])
        for j in range(m.shape[1]):
            act = m[:, j] > 0
            self.masked_active_frac[j] = act.mean()
            if act.sum() > 1:
                self.masked_mean[j] = m[act, j].mean()
                self.masked_std[j] = max(m[act, j].std(), 1e-6)

        n_alma_s = df[TARGET_CLS_N_ALMA] if TARGET_CLS_N_ALMA in df.columns else pd.Series(2, index=df.index)
        n_cant_s = df[TARGET_CLS_N_CANTONERA] if TARGET_CLS_N_CANTONERA in df.columns else pd.Series(0, index=df.index)

        self.count_class_weights = {
            TARGET_CLS_N_ALMA: self._count_weights(n_alma_s, N_ALMA_CLASSES),
            TARGET_CLS_N_CANTONERA: self._count_weights(n_cant_s, N_CANTONERA_CLASSES),
        }
        return self

    @staticmethod
    def _count_weights(values, n_classes):
        vals = pd.to_numeric(values, errors="coerce").fillna(0).clip(0, n_classes - 1).astype(int).values
        classes = np.arange(n_classes)
        counts = np.array([max((vals == c).sum(), 1) for c in classes])
        w = len(vals) / (n_classes * counts)
        return (w / w.mean()).astype(np.float32)

    @property
    def cat_cardinalities(self):
        return [len(self.cat_encoders[c].classes_) for c in CATEGORICAL_FEATURES]

    @property
    def n_standard_classes(self):
        return len(self.standard_encoder.classes_)

    def _encode_p_labels(self, df):
        """Índices de clase por paso p. -100 = etiqueta ausente/desconocida (ignorada por la CE)."""
        n = len(df)
        if getattr(self, "p_label_encoder", None) is None:
            return np.full((n, len(P_LABEL_COLUMNS)), -100, dtype=np.int64)
        mapping = {c: i for i, c in enumerate(self.p_label_encoder.classes_)}
        cols = []
        for c in P_LABEL_COLUMNS:
            if c not in df.columns:
                cols.append(np.full(n, -100, dtype=np.int64))
            else:
                cols.append(
                    df[c].map(lambda x: mapping.get(str(x), -100) if pd.notna(x) else -100)
                    .astype(np.int64).values
                )
        return np.stack(cols, axis=1)

    @property
    def p_label_classes(self):
        if getattr(self, "p_label_encoder", None) is not None:
            return list(self.p_label_encoder.classes_)
        return None

    def transform_features(self, df):
        df = self._enrich_materials(df)

        encoded_cols = []
        for c in CATEGORICAL_FEATURES:
            encoder = self.cat_encoders[c]
            known = set(encoder.classes_)
            fallback = encoder.classes_[0]
            s = df[c].fillna(fallback).astype(str) if c in df.columns else pd.Series([fallback] * len(df), index=df.index)
            s_clean = s.map(lambda x: x if x in known else fallback)
            encoded_cols.append(encoder.transform(s_clean))

        x_cat = np.stack(encoded_cols, axis=1)

        # Reindexación segura para evitar KeyError cuando faltan columnas numéricas en Excel
        df_num = df.reindex(columns=NUMERIC_FEATURES, fill_value=0.0)
        num_vals = df_num[NUMERIC_FEATURES].apply(pd.to_numeric, errors="coerce").fillna(0.0).values
        x_num = self.num_scaler.transform(num_vals).astype(np.float32)
        return x_cat.astype(np.int64), x_num

    def transform_targets(self, df):
        std_s = df["standard"].fillna("AISC 360-16").astype(str) if "standard" in df.columns else pd.Series(["AISC 360-16"] * len(df), index=df.index)
        known_std = set(self.standard_encoder.classes_)
        fallback_std = self.standard_encoder.classes_[0]
        std_clean = std_s.map(lambda x: x if x in known_std else fallback_std)
        standard_idx = self.standard_encoder.transform(std_clean)

        bolt_s = bolt_nominal_mm(df)
        bolt_idx = bolt_s.map(BOLT_TO_IDX).fillna(0).astype(int).values

        slip_col = df["SlipCritical"] if "SlipCritical" in df.columns else (df["slip_critical"] if "slip_critical" in df.columns else "NO")
        slip = pd.Series(slip_col, index=df.index).fillna("NO").astype(str).str.upper().isin(["YES", "TRUE", "1"]).astype(np.float32).values

        n_alma_col = df["n_alma"] if "n_alma" in df.columns else 2
        n_cant_col = df["n_cantonera"] if "n_cantonera" in df.columns else 0
        n_alma_idx = pd.to_numeric(n_alma_col, errors="coerce").fillna(2).clip(0, N_ALMA_CLASSES - 1).astype(int).values
        n_cant_idx = pd.to_numeric(n_cant_col, errors="coerce").fillna(0).clip(0, N_CANTONERA_CLASSES - 1).astype(int).values

        df_reg = df.reindex(columns=REGRESSION_ALWAYS, fill_value=0.0)
        reg_vals = df_reg[REGRESSION_ALWAYS].apply(pd.to_numeric, errors="coerce").fillna(0.0).values
        reg_always = self.reg_always_scaler.transform(reg_vals).astype(np.float32)

        df_masked = df.reindex(columns=MASKED_COLUMNS, fill_value=0.0)
        m = df_masked[MASKED_COLUMNS].apply(pd.to_numeric, errors="coerce").fillna(0.0).values.astype(np.float32)
        masked_mask = (m > 0.0).astype(np.float32)
        masked_value = ((m - self.masked_mean) / self.masked_std).astype(np.float32)

        p_label_idx = self._encode_p_labels(df)

        return {
            "standard_idx": standard_idx.astype(np.int64),
            "bolt_idx": bolt_idx.astype(np.int64),
            "slip_critical": slip,
            "n_alma_idx": n_alma_idx,
            "n_cantonera_idx": n_cant_idx,
            "reg_always": reg_always,
            "masked_value": masked_value,
            "masked_mask": masked_mask,
            "p_label_idx": p_label_idx,
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