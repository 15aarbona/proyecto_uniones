import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.utils.class_weight import compute_class_weight

from .config import (
    CATEGORICAL_FEATURES, NUMERIC_FEATURES, REGRESSION_ALWAYS,
    MASKED_COLUMNS, CATALOGO_BOLT, Y_COLUMNS, P_COLUMNS,
    TARGET_CLS_N_ALMA, TARGET_CLS_N_CANTONERA,
    N_ALMA_CLASSES, N_CANTONERA_CLASSES, N_ROLE_CLASSES,
)

BOLT_TO_IDX = {v: i for i, v in enumerate(CATALOGO_BOLT)}
ROLE_IGNORE = -100   # ignore_index para la CE de rol en pasos inactivos


def roles_from_p(df):
    """
    Rol geométrico por paso (esquema zona-colapsado, 5 clases) usando fronteras a tf/2:
        0 TOP            : p1 (primer paso, al primer tornillo dentro de la viga)
        1 BEAM_INTERIOR  : aterriza dentro de la viga [y_beam_top, y_beam_bot]
        2 BOTTOM         : primer paso que aterriza por debajo de y_beam_bot
        3 HAUNCH         : aterriza por debajo en la zona de cartabón (Lh>0)
        4 SIN_CARTABON   : aterriza por debajo sin cartabón / más allá del cartabón
    Devuelve (N, N_Y) con ROLE_IGNORE en los pasos inactivos.
    """
    e = df["e"].values.astype(float)
    d = df["d"].values.astype(float)
    beam_d = df["BEAM_d_mm"].values.astype(float)
    tf = df["BEAM_tf_mm"].values.astype(float)
    lh = df["Lh"].values.astype(float)
    P = df[P_COLUMNS].fillna(0.0).values.astype(float)

    roles = np.full((len(df), P.shape[1]), ROLE_IGNORE, dtype=np.int64)
    for i in range(len(df)):
        y_top = e[i] + d[i] + tf[i] / 2.0
        y_bot = e[i] + d[i] + beam_d[i] - tf[i] / 2.0
        y_hau = y_bot + lh[i] if lh[i] > 0 else y_bot
        prev = e[i]
        first_below = True
        for j in range(P.shape[1]):
            p = P[i, j]
            if p <= 0:
                break
            end = prev + p
            if j == 0:
                role = 0
            elif end <= y_bot:
                role = 1
            elif first_below:
                role = 2
                first_below = False
            elif lh[i] > 0 and end <= y_hau:
                role = 3
            else:
                role = 4
            roles[i, j] = role
            prev = end
    return roles


def bolt_nominal_mm(df):
    """Bolt -> diámetro nominal en mm. Acepta int (16, 20, ...) o string ('M20'),
    incluido el dtype 'string' de pandas (Arrow)."""
    b = df["Bolt"]
    return b.astype(str).str.replace("M", "", regex=False).astype(int)


def ys_from_p(df):
    """
    Deriva las cotas acumuladas Y1..Y12 desde los pasos relativos p1..p12 + e (misma
    definición que variables.ipynb):
        Y_i = e + p1 + ... + p_i   si p_i > 0, y 0 en caso contrario
    (las Ys activas son siempre un prefijo). El dataset global persiste p1..p12; en
    post-proceso/evaluación se derivan las Ys desde las p predichas Verificado que p_i = Y_i - Y_{i-1}.
    """
    df = df.copy()
    P = df[P_COLUMNS].fillna(0.0).values.astype(float)
    e = df["e"].values.astype(float)
    cum = P.cumsum(axis=1) + e[:, None]
    Y = np.where(P > 0, cum, 0.0)
    for i, col in enumerate(Y_COLUMNS):
        df[col] = Y[:, i]
    return df


def counts_from_ys(df):
    """
    Deriva n_alma / n_cantonera / num_filas desde las cotas acumuladas Y1..Y12 + e + d +
    BEAM_d_mm (misma lógica que variables.ipynb, con las filas activas solamente):
      - fila 1 en cota e (no ocupa columna Y)
      - y_ala_sup = e + d, y_ala_inf = e + d + BEAM_d_mm
      - n_alma      = filas activas con y_ala_sup <= Y <= y_ala_inf
      - n_debajo    = filas activas con Y > y_ala_inf  (== 1 + n_cantonera)
      - num_filas   = 1 + nº de Ys activas = n_alma + n_cantonera + 2
    Para filas de entrenamiento ya vienen calculadas en el dataset; esta función se usa
    en evaluación y para validar el esquema.
    """
    Y = df[Y_COLUMNS].fillna(0.0).values
    active = Y > 0
    e = df["e"].values.astype(float)
    d = df["d"].values.astype(float)
    h = df["BEAM_d_mm"].values.astype(float)
    y_ala_sup = e + d
    y_ala_inf = e + d + h

    n_alma = ((Y >= y_ala_sup[:, None]) & (Y <= y_ala_inf[:, None]) & active).sum(axis=1)
    n_debajo = ((Y > y_ala_inf[:, None]) & active).sum(axis=1)
    n_cantonera = np.maximum(n_debajo - 1, 0)
    num_filas = 1 + active.sum(axis=1)
    return n_alma, n_cantonera, num_filas


def counts_from_p(df):
    """
    n_alma / n_cantonera / num_filas directamente desde p1..p12 + e + d + BEAM_d_mm.
    Misma lógica de transformar_topologia_y_cotas (variables.ipynb) pero SIN calcular
    ni guardar las cotas Yx (solo se usan internamente y no se persisten):
      - fila 1 en cota e (no ocupa columna p)
      - y_ala_sup = e + d, y_ala_inf = e + d + BEAM_d_mm
      - Y_i = e + cumsum(p)_i solo donde p_i > 0 (transitorio, no se guarda)
      - n_alma      = filas activas con y_ala_sup <= Y <= y_ala_inf
      - n_debajo    = filas activas con Y > y_ala_inf  (== 1 + n_cantonera)
      - num_filas   = 1 + nº de p activas = n_alma + n_cantonera + 2
    """
    P = df[P_COLUMNS].fillna(0.0).values.astype(float)
    e = df["e"].values.astype(float)
    d = df["d"].values.astype(float)
    h = df["BEAM_d_mm"].values.astype(float)
    y_ala_sup = e + d
    y_ala_inf = e + d + h

    Y = np.where(P > 0, P.cumsum(axis=1) + e[:, None], 0.0)
    n_alma = ((Y >= y_ala_sup[:, None]) & (Y <= y_ala_inf[:, None]) & (P > 0)).sum(axis=1)
    n_debajo = ((Y > y_ala_inf[:, None]) & (P > 0)).sum(axis=1)
    n_cantonera = np.maximum(n_debajo - 1, 0)
    num_filas = 1 + (P > 0).sum(axis=1)
    return n_alma.astype(int), n_cantonera.astype(int), num_filas.astype(int)


class Preprocessor:
    """Ajusta encoders/scalers SOLO con el split de train y los reutiliza en val/test/inferencia.
    Requiere el esquema v4 (p1..p12 directos como targets con máscara; n_alma, n_cantonera, standard, Bolt int)."""

    def fit(self, df):
        self.cat_encoders = {c: LabelEncoder().fit(df[c].astype(str)) for c in CATEGORICAL_FEATURES}
        self.num_scaler = StandardScaler().fit(df[NUMERIC_FEATURES].values)
        self.reg_always_scaler = StandardScaler().fit(df[REGRESSION_ALWAYS].values)
        self.standard_encoder = LabelEncoder().fit(df["standard"].astype(str))

        # Media/std de cada columna enmascarada (pasos p + rigidizadores) SOLO sobre sus
        # valores activos (>0): si se incluyeran los ceros, la media de columnas raras
        # como p11/p12 quedaría dominada por ceros y los valores reales caerían a
        # muchas sigmas.
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

        # Peso positivo de presencia por columna (frecuencia inversa) para el BCE
        # ponderado: compensa el desbalance de clase. tws es ~97% ceros -> el activo
        # recibe ~30x más peso en la pérdida de presencia (en vez de ahogarse en ceros).
        self.presence_pos_weight = np.ones(m.shape[1])
        for j in range(m.shape[1]):
            frac = self.masked_active_frac[j]
            self.presence_pos_weight[j] = max((1.0 - frac) / max(frac, 1e-6), 1.0)

        # Pesos de clase (frecuencia inversa, normalizados a media 1) para los conteos
        # desbalanceados n_alma / n_cantonera: los valores altos son raros y sin peso
        # la CE ignoraría esas clases.
        self.count_class_weights = {
            TARGET_CLS_N_ALMA: self._count_weights(df[TARGET_CLS_N_ALMA], N_ALMA_CLASSES),
            TARGET_CLS_N_CANTONERA: self._count_weights(df[TARGET_CLS_N_CANTONERA], N_CANTONERA_CLASSES),
        }

        # Pesos de clase para el rol auxiliar (frecuencia inversa, media 1).
        role_vals = roles_from_p(df).reshape(-1)
        role_vals = role_vals[role_vals >= 0]
        counts = np.array([max((role_vals == c).sum(), 1) for c in range(N_ROLE_CLASSES)], dtype=float)
        w = len(role_vals) / (N_ROLE_CLASSES * counts)
        self.role_class_weights = (w / w.mean()).astype(np.float32)
        return self

    @staticmethod
    def _count_weights(values, n_classes):
        vals = np.asarray(values).astype(int)
        classes = np.arange(n_classes)
        # clases ausentes en train: peso mínimo (solo evita div/0; nunca se predicen bien)
        counts = np.array([max((vals == c).sum(), 1) for c in classes])
        w = len(vals) / (n_classes * counts)
        return (w / w.mean()).astype(np.float32)

    @property
    def cat_cardinalities(self):
        return [len(self.cat_encoders[c].classes_) for c in CATEGORICAL_FEATURES]

    @property
    def n_standard_classes(self):
        return len(self.standard_encoder.classes_)

    def transform_features(self, df):
        x_cat = np.stack([self.cat_encoders[c].transform(df[c].astype(str)) for c in CATEGORICAL_FEATURES], axis=1)
        x_num = self.num_scaler.transform(df[NUMERIC_FEATURES].values).astype(np.float32)
        return x_cat.astype(np.int64), x_num

    def transform_targets(self, df):
        standard_idx = self.standard_encoder.transform(df["standard"].astype(str))
        bolt_idx = bolt_nominal_mm(df).map(BOLT_TO_IDX).values
        slip = df["SlipCritical"].astype(str).str.upper().isin(["YES", "TRUE", "1"]).astype(np.float32).values
        n_alma_idx = df["n_alma"].astype(int).values
        n_cant_idx = df["n_cantonera"].astype(int).values

        reg_always = self.reg_always_scaler.transform(df[REGRESSION_ALWAYS].values).astype(np.float32)

        m = df[MASKED_COLUMNS].fillna(0.0).values.astype(np.float32)
        masked_mask = (m > 0.0).astype(np.float32)
        masked_value = ((m - self.masked_mean) / self.masked_std).astype(np.float32)

        role_idx = roles_from_p(df)

        return {
            "standard_idx": standard_idx.astype(np.int64),
            "bolt_idx": bolt_idx.astype(np.int64),
            "slip_critical": slip,
            "n_alma_idx": n_alma_idx,
            "n_cantonera_idx": n_cant_idx,
            "reg_always": reg_always,
            "masked_value": masked_value,
            "masked_mask": masked_mask,
            "role_idx": role_idx,
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
