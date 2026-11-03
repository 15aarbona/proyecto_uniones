import numpy as np
import pandas as pd
from .config import (
    CATALOGO_BOLT,
    CATALOGO_g,
    CATALOGO_e,
    CATALOGO_d,
    CATALOGO_Bp,
    CATALOGO_tp,
    CATALOGO_tws,
    CATALOGO_ts,
    CATALOGO_tbs,
    CATALOGO_tst,
    REGRESSION_ALWAYS,
    P_COLUMNS,
    STIFFENER_COLUMNS,
    Y_GRID_STEP,
    N_Y,
    N_ALMA_CLASSES,
    N_CANTONERA_CLASSES,
    secuencia_transiciones,
)

CATALOGS = {
    "g": CATALOGO_g,
    "e": CATALOGO_e,
    "d": CATALOGO_d,
    "Bp": CATALOGO_Bp,
    "tp": CATALOGO_tp,
    "tws": CATALOGO_tws,
    "ts": CATALOGO_ts,
    "tbs": CATALOGO_tbs,
    "tst": CATALOGO_tst,
}


def snap_to_catalog(values, catalog):
    values = np.asarray(values, float)
    if catalog is None:
        return values
    arr = np.asarray(catalog, float)
    return arr[np.abs(values[:, None] - arr[None, :]).argmin(1)]


def _sigmoid(x):
    return 1 / (1 + np.exp(-np.clip(x, -30, 30)))


def geometry_counts(e, d, p, beam_d, beam_tf, lh=None, tolerance=0.5):
    """Conteos de filas a partir de e, d, p y la geometria de la viga.

    La fila 0 esta en y=e. Las filas siguientes son e + suma acumulada de las p
    activas. ``n_cantonera`` son las filas por debajo de la viga menos la fila
    inferior (la ultima fila suelta).
    """
    e = np.asarray(e, float).reshape(-1, 1)
    d = np.asarray(d, float).reshape(-1, 1)
    p = np.asarray(p, float)
    beam_d = np.asarray(beam_d, float).reshape(-1, 1)
    beam_tf = np.asarray(beam_tf, float).reshape(-1, 1)

    exists_p = p > 0
    rows = np.concatenate([e, e + np.cumsum(p, axis=1)], axis=1)
    exists = np.concatenate([np.ones_like(e, dtype=bool), exists_p], axis=1)

    top_out = e + d
    top_in = top_out + beam_tf
    bot_out = top_out + beam_d
    bot_in = bot_out - beam_tf

    in_alma = exists & (rows >= top_in - tolerance) & (rows <= bot_in + tolerance)
    n_alma = in_alma.sum(axis=1)
    if lh is None:
        below = exists & (rows > bot_out + tolerance)
        n_cantonera = np.maximum(below.sum(axis=1) - 1, 0)
    else:
        lh = np.asarray(lh, float).reshape(-1, 1)
        angle_bottom = bot_out + np.maximum(lh, 0.0)
        in_cantonera = (
            exists
            & (rows > bot_out + tolerance)
            & (rows < angle_bottom - tolerance)
        )
        n_cantonera = in_cantonera.sum(axis=1)
    return n_alma.astype(int), n_cantonera.astype(int)


def decode_predictions(
    reg_always_real,
    masked_value_real,
    masked_presence_prob,
    bolt_logits,
    n_alma_logits,
    n_cantonera_logits,
    standard_logits=None,
    standard_classes=None,
    slip_critical_logit=None,
    thresholds=None,
    n_rows_logits=None,
    beam_d_mm=None,
    beam_tf_mm=None,
    lh_mm=None,
):
    n = len(reg_always_real)
    if thresholds is None:
        thresholds = np.full(masked_value_real.shape[1], 0.5)
    out = {}
    for j, name in enumerate(REGRESSION_ALWAYS):
        out[name] = snap_to_catalog(reg_always_real[:, j], CATALOGS.get(name))

    p = np.maximum(
        np.round(masked_value_real[:, :N_Y] / Y_GRID_STEP) * Y_GRID_STEP, Y_GRID_STEP
    )

    if n_rows_logits is not None:
        n_rows = np.clip(np.asarray(n_rows_logits).argmax(1) - 1, 0, N_Y)
        active = np.arange(N_Y)[None, :] < n_rows[:, None]
        p = np.where(active, p, 0.0)
        if beam_d_mm is None:
            beam_d_mm = np.zeros(n, dtype=float)
        if beam_tf_mm is None:
            beam_tf_mm = np.zeros(n, dtype=float)
        idx_e = REGRESSION_ALWAYS.index("e")
        idx_d = REGRESSION_ALWAYS.index("d")
        if lh_mm is None and "Lh" in REGRESSION_ALWAYS:
            lh_mm = reg_always_real[:, REGRESSION_ALWAYS.index("Lh")]
        na, nc = geometry_counts(
            reg_always_real[:, idx_e],
            reg_always_real[:, idx_d],
            p,
            beam_d_mm,
            beam_tf_mm,
            lh=lh_mm,
        )
        na = np.clip(na, 0, N_ALMA_CLASSES - 1)
        nc = np.clip(nc, 0, N_CANTONERA_CLASSES - 1)
        k = na + nc + 1
        active = np.arange(N_Y)[None, :] < k[:, None]
        p = np.where(active, p, 0.0)
    else:
        na = n_alma_logits.argmax(1)
        nc = n_cantonera_logits.argmax(1)
        k = na + nc + 1
        active = np.arange(N_Y)[None, :] < k[:, None]
        p = np.where(active, p, 0.0)

    out["n_alma"], out["n_cantonera"] = na, nc
    for j, name in enumerate(P_COLUMNS):
        out[name] = p[:, j]

    probs = masked_presence_prob[:, N_Y:]
    vals = masked_value_real[:, N_Y:]
    for j, name in enumerate(STIFFENER_COLUMNS):
        snapped = snap_to_catalog(vals[:, j], CATALOGS[name])
        out[name] = np.where(probs[:, j] >= thresholds[N_Y + j], snapped, 0.0)

    bolt_idx = bolt_logits.argmax(1)
    out["Bolt"] = np.asarray(CATALOGO_BOLT)[bolt_idx]
    out["_bolt_nominal_mm"] = out["Bolt"].astype(int)
    if standard_logits is not None and standard_classes is not None:
        out["standard"] = np.asarray(standard_classes)[standard_logits.argmax(1)]
    if slip_critical_logit is not None:
        out["SlipCritical"] = np.where(
            _sigmoid(slip_critical_logit) >= 0.5, "YES", "NO"
        )

    for i in range(1, N_Y + 1):
        out[f"p{i}_transition"] = []
    for row in range(n):
        trans = secuencia_transiciones(int(na[row]), int(nc[row]))
        for j in range(N_Y):
            out[f"p{j + 1}_transition"].append(trans[j] if j < len(trans) else "UNUSED")
    return pd.DataFrame(out)


def derive_dependent_columns(df):
    out = df.copy().reset_index(drop=True)
    out["Hole"] = out["_bolt_nominal_mm"].astype(int) + 2
    out["num_filas_tornillos"] = (
        out["n_alma"].astype(int) + out["n_cantonera"].astype(int) + 2
    )
    out["tiene_cantonera"] = out["n_cantonera"].astype(int) > 0
    return out
