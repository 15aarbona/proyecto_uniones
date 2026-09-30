"""
Post-proceso de las salidas de la red (v4, esquema train_v3.parquet):
  1) snap_to_catalog: proyecta cada valor continuo al cat¡logo comercial; los pasos p1..p12 se
     snapean a la rejilla de Y_GRID_STEP mm (multiples de 5, como las Ys).
  2) decode_predictions: junta clasificacin (standard, Bolt, SlipCritical), conteos
     (n_alma, n_cantonera), regresin (g, e, d, Bp, tp, Lh) y columnas con m¡scara
     (Y1..Y12 + rigidizadores) en un dise±o concreto. El nº de p activas se fuerza al
     prefijo determinado por los conteos: k = n_alma + n_cantonera + 1 (las p que
     desaparecen son siempre las del final), y tambin se rellena por delante si la
     m¡scara dej menos p activas de las que tocan.
  3) derive_dependent_columns: Hole = Bolt + 2, num_filas_tornillos = n_alma +
     n_cantonera + 2, tiene_cantonera = n_cantonera > 0, y (opcional) las Ys acumuladas se derivan de
     de las p activas: Y1 = e + p1,  Y_i = e + p1 + ... + p_i).
"""
import numpy as np
import pandas as pd

from .config import (
    CATALOGO_BOLT, CATALOGO_g, CATALOGO_e, CATALOGO_d, CATALOGO_Bp, CATALOGO_tp,
    CATALOGO_tws, CATALOGO_ts, CATALOGO_tbs, CATALOGO_tst,
    REGRESSION_ALWAYS, MASKED_COLUMNS, P_COLUMNS, P_LABEL_COLUMNS, Y_COLUMNS,
    STIFFENER_COLUMNS, Y_GRID_STEP, N_Y,
)

CATALOGS = {
    "g": CATALOGO_g, "e": CATALOGO_e, "d": CATALOGO_d, "Bp": CATALOGO_Bp, "tp": CATALOGO_tp,
    "tws": CATALOGO_tws, "ts": CATALOGO_ts, "tbs": CATALOGO_tbs, "tst": CATALOGO_tst,
}


def snap_to_catalog(values: np.ndarray, catalog) -> np.ndarray:
    if catalog is None:
        return values
    arr = np.asarray(catalog, dtype=float)
    idx = np.abs(values[:, None] - arr[None, :]).argmin(axis=1)
    return arr[idx]


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30.0, 30.0)))


def decode_predictions(reg_always_real: np.ndarray, masked_value_real: np.ndarray,
                       masked_presence_prob: np.ndarray, bolt_logits: np.ndarray,
                       n_alma_logits: np.ndarray, n_cantonera_logits: np.ndarray,
                       standard_logits: np.ndarray = None, standard_classes=None,
                       slip_critical_logit: np.ndarray = None,
                       p_label_logits: np.ndarray = None, p_label_classes=None,
                       thresholds=None) -> pd.DataFrame:
    """
    reg_always_real / masked_value_real: ya des-estandarizados (mm).
    masked_* siguen el orden de config.MASKED_COLUMNS = P_COLUMNS + STIFFENER_COLUMNS.
    p_label_logits: (B, 12, C) logits de zona por paso; p_label_classes: nombres de clase.
    Devuelve un DataFrame (una fila por muestra) ANTES de calcular las columnas derivadas.
    """
    n = reg_always_real.shape[0]
    if thresholds is None:
        thresholds = np.full(masked_value_real.shape[1], 0.5)

    out = {}
    for j, name in enumerate(REGRESSION_ALWAYS):
        vals = reg_always_real[:, j]
        out[name] = snap_to_catalog(vals, CATALOGS.get(name))

    masked_names = P_COLUMNS + STIFFENER_COLUMNS
    active = masked_presence_prob >= thresholds[None, :]
    for j, name in enumerate(masked_names):
        vals = masked_value_real[:, j]
        if name in P_COLUMNS:
            # pasos relativos: rejilla de Y_GRID_STEP mm, siempre > 0 si activas
            vals = np.maximum(np.round(vals / Y_GRID_STEP) * Y_GRID_STEP, Y_GRID_STEP)
        elif name in CATALOGS:
            vals = snap_to_catalog(vals, CATALOGS[name])
        out[name] = np.where(active[:, j], vals, 0.0)

# ---- conteos -> estructura de las p (prefijo forzado)) ----
    n_alma = n_alma_logits.argmax(axis=1)
    n_cantonera = n_cantonera_logits.argmax(axis=1)
    k_target = n_alma + n_cantonera +  1          # n de p activas que debe haber
    # se recalcula el prefijo sobre las p ya decodificadas:
    P_pred = np.stack([out[name] for name in P_COLUMNS], axis=1)
    for i in range(n):
        k = int(k_target[i])
        for j in range(N_Y):
            if j >= k:        # sobran p al final: se anulan
                P_pred[i, j] =  0.0
            elif P_pred[i, j] <=  0.0:  # faltaba: paso minimo de la rejilla
                P_pred[i, j] = Y_GRID_STEP
    for j, name in enumerate(P_COLUMNS):
        out[name] = P_pred[:, j]

    out["n_alma"] = n_alma
    out["n_cantonera"] = n_cantonera

    bolt_idx = bolt_logits.argmax(axis=1)
    out["Bolt"] = np.array([CATALOGO_BOLT[i] for i in bolt_idx])   # di¡metro nominal (int, sin 'M')
    out["_bolt_nominal_mm"] = out["Bolt"].astype(int)

    if standard_logits is not None and standard_classes is not None:
        out["standard"] = np.array(standard_classes)[standard_logits.argmax(axis=1)]

    if slip_critical_logit is not None:
        out["SlipCritical"] = np.where(_sigmoid(slip_critical_logit) >= 0.5, "YES", "NO")

    # zona de cada paso p: argmax de la cabeza correspondiente
    if p_label_logits is not None and p_label_classes is not None:
        p_label_idx = p_label_logits.argmax(axis=-1)   # (B, 12)
        for j, name in enumerate(P_LABEL_COLUMNS):
            out[name] = np.array(p_label_classes)[p_label_idx[:, j]]

    return pd.DataFrame(out)


def derive_dependent_columns(design_df: pd.DataFrame) -> pd.DataFrame:
    """
    Columnas derivadas por aritmtica pura sobre lo ya predicho:
      - Hole = Bolt + 2
      - num_filas_tornillos = n_alma + n_cantonera + 2  (fila en cota e + ºltima fila,
        ambas siempre presentes; ver config.py)
      - tiene_cantonera = n_cantonera > 0
      - (las Ys desaparecen del output: no se derivan; solo p1..p12)
        (las p son el target real del modelo)
    """
    design_df = design_df.copy().reset_index(drop=True)
    bolt_mm = design_df["_bolt_nominal_mm"].values.astype(int)
    out = pd.DataFrame({
        "Hole": bolt_mm + 2,
        "num_filas_tornillos": design_df["n_alma"].astype(int) + design_df["n_cantonera"].astype(int) + 2,
        "tiene_cantonera": (design_df["n_cantonera"].astype(int) > 0).values,
    })
    res = pd.concat([design_df, out], axis=1)

    return res
