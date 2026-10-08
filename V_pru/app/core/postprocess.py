"""
Post-proceso de las salidas de la red.

  decode_predictions: clasificación (standard, Bolt, SlipCritical), conteos
  (n_alma, n_cantonera), regresión siempre activa (g,e,d,Bp,tp) y columnas con máscara
  MASKED_COLUMNS = p1..p12, tws, ts, tbs, tst, Lh.

  Para las p (salto entre filas) NO se trunca por conteos. Sólo:
    - gating por presencia (p_j = 0 si prob. de presencia < umbral),
    - positividad (max(0, ·)),
    - prefijo por presencia: desde el primer p inactivo, los siguientes se anulan.
  El número de filas lo determina la presencia. n_alma / n_cantonera se RECALCULAN desde la
  geometría de las p emitidas (fronteras a tf/2), para que sean coherentes con las filas.

  derive_dependent_columns: Hole = Bolt + 2, num_filas_tornillos = n_alma + n_cantonera + 2,
  tiene_cantonera = n_cantonera > 0.
"""
import numpy as np
import pandas as pd

from .config import (
    CATALOGO_BOLT, CATALOGO_g, CATALOGO_e, CATALOGO_d, CATALOGO_Bp, CATALOGO_tp,
    CATALOGO_tws, CATALOGO_ts, CATALOGO_tbs, CATALOGO_tst,
    REGRESSION_ALWAYS, MASKED_COLUMNS, P_COLUMNS, STIFFENER_COLUMNS, N_Y,
)

CATALOGS = {
    "g": CATALOGO_g, "e": CATALOGO_e, "d": CATALOGO_d, "Bp": CATALOGO_Bp, "tp": CATALOGO_tp,
    "tws": CATALOGO_tws, "ts": CATALOGO_ts, "tbs": CATALOGO_tbs, "tst": CATALOGO_tst,
}

LH_MIN = 20.0


def snap_to_catalog(values: np.ndarray, catalog) -> np.ndarray:
    if catalog is None:
        return values
    arr = np.asarray(catalog, dtype=float)
    idx = np.abs(values[:, None] - arr[None, :]).argmin(axis=1)
    return arr[idx]


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30.0, 30.0)))


def _min_nonzero(catalog):
    if not catalog:
        return 0.0
    pos = [v for v in catalog if v > 0]
    return float(min(pos)) if pos else 0.0


def _prefix_by_presence(P, active):
    """Fuerza que los p activos sean un prefijo: desde el primer inactivo, todo a 0."""
    keep = np.ones_like(P, dtype=bool)
    for i in range(P.shape[0]):
        inact = np.where(~active[i])[0]
        if len(inact) > 0:
            keep[i, inact[0]:] = False
    return np.where(keep, P, 0.0)


def _counts_from_p(P, e, d, beam_d, tf):
    """n_alma / n_cantonera desde la geometría (fronteras a tf/2), forzando la identidad
    n_alma + n_cantonera + 1 == nº de p activas (coherencia con las filas emitidas)."""
    y_top = e + d + tf / 2.0
    y_bot = e + d + beam_d - tf / 2.0
    Y = np.where(P > 0, P.cumsum(axis=1) + e[:, None], 0.0)
    active = P > 0
    m = active.sum(axis=1)
    n_alma_geo = ((Y >= y_top[:, None]) & (Y <= y_bot[:, None]) & active).sum(axis=1)
    n_alma = np.minimum(n_alma_geo, np.maximum(m - 1, 0))
    n_cantonera = np.maximum(m - 1 - n_alma, 0)
    return n_alma.astype(int), n_cantonera.astype(int)


def decode_predictions(reg_always_real: np.ndarray, masked_value_real: np.ndarray,
                       masked_presence_prob: np.ndarray, bolt_logits: np.ndarray,
                       n_alma_logits: np.ndarray, n_cantonera_logits: np.ndarray,
                       standard_logits: np.ndarray = None, standard_classes=None,
                       slip_critical_logit: np.ndarray = None,
                       thresholds=None,
                       beam_d=None, beam_tf=None) -> pd.DataFrame:
    """
    reg_always_real / masked_value_real: ya des-estandarizados (mm).
    masked_* siguen el orden de config.MASKED_COLUMNS = P_COLUMNS + STIFFENER_COLUMNS + Lh.
    beam_d / beam_tf (opcional): geometría de viga (mm) para recomputar los conteos a tf/2.
    Devuelve un DataFrame ANTES de calcular las columnas derivadas.
    """
    n = reg_always_real.shape[0]
    if thresholds is None:
        thresholds = np.full(masked_value_real.shape[1], 0.5)

    out = {}
    for j, name in enumerate(REGRESSION_ALWAYS):
        out[name] = snap_to_catalog(reg_always_real[:, j], CATALOGS.get(name))

    active = masked_presence_prob >= thresholds[None, :]

    # --- p: gating + positividad + prefijo por presencia (sin truncado por conteos) ---
    P = np.maximum(masked_value_real[:, :N_Y], 0.0)
    P = np.where(active[:, :N_Y], P, 0.0)
    P = _prefix_by_presence(P, active[:, :N_Y])
    for j, name in enumerate(P_COLUMNS):
        out[name] = P[:, j]

    # --- rigidizadores: si activan y el catálogo deja 0, subir al mínimo no-cero ---
    for name in STIFFENER_COLUMNS:
        j = MASKED_COLUMNS.index(name)
        vals = snap_to_catalog(masked_value_real[:, j], CATALOGS[name])
        floor = _min_nonzero(CATALOGS[name])
        vals = np.where(active[:, j] & (vals <= 0.0), floor, vals)
        out[name] = np.where(active[:, j], vals, 0.0)

    # --- Lh (cartabón): con máscara; si activa, longitud > 0 ---
    lh_idx = MASKED_COLUMNS.index("Lh")
    lh_vals = np.where(active[:, lh_idx] & (masked_value_real[:, lh_idx] <= 0.0),
                       LH_MIN, masked_value_real[:, lh_idx])
    out["Lh"] = np.where(active[:, lh_idx], lh_vals, 0.0)

    # --- conteos: predichos (cabezas) o recalculados desde la geometría de las p ---
    e_arr = out["e"].astype(float)
    d_arr = out["d"].astype(float)
    if beam_d is not None and beam_tf is not None:
        n_alma, n_cantonera = _counts_from_p(
            P, e_arr, d_arr, np.asarray(beam_d, dtype=float), np.asarray(beam_tf, dtype=float))
    else:
        n_alma = n_alma_logits.argmax(axis=1)
        n_cantonera = n_cantonera_logits.argmax(axis=1)
    out["n_alma"] = n_alma
    out["n_cantonera"] = n_cantonera

    bolt_idx = bolt_logits.argmax(axis=1)
    out["Bolt"] = np.array([CATALOGO_BOLT[i] for i in bolt_idx])
    out["_bolt_nominal_mm"] = out["Bolt"].astype(int)

    if standard_logits is not None and standard_classes is not None:
        out["standard"] = np.array(standard_classes)[standard_logits.argmax(axis=1)]

    if slip_critical_logit is not None:
        out["SlipCritical"] = np.where(_sigmoid(slip_critical_logit) >= 0.5, "YES", "NO")

    return pd.DataFrame(out)


def derive_dependent_columns(design_df: pd.DataFrame) -> pd.DataFrame:
    """Columnas derivadas por aritmética pura sobre lo ya predicho."""
    design_df = design_df.copy().reset_index(drop=True)
    bolt_mm = design_df["_bolt_nominal_mm"].values.astype(int)
    out = pd.DataFrame({
        "Hole": bolt_mm + 2,
        "num_filas_tornillos": design_df["n_alma"].astype(int) + design_df["n_cantonera"].astype(int) + 2,
        "tiene_cantonera": (design_df["n_cantonera"].astype(int) > 0).values,
    })
    return pd.concat([design_df, out], axis=1)
