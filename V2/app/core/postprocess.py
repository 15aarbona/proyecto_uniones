"""
Post-proceso de las salidas de la red (v3):
  1) snap_to_catalog / snap_grid: proyecta cada valor continuo al catálogo comercial o a
     la rejilla de GEOM_GRID_STEP mm.
  2) decode_predictions: junta clasificación + regresión + geometría (E-S, D_i, I-C, C_i,
     E-C) + rigidizadores en un diseño concreto.
  3) derive_dependent_columns: Hole, num_filas_tornillos y tiene_cantonera, aritmética pura
     sobre las columnas anteriores (geometry.assemble_from_named) -- YA NO hace falta
     recorrer p1..p12, porque el modelo predice directamente la geometría con nombre.
  4) reconstruct_p (opcional): p1..p12 desde la geometría con nombre, solo para comparar
     contra el p real en evaluación o exportar a sistemas que aún esperen p1..p12.
"""
import numpy as np
import pandas as pd

from .config import (
    CATALOGO_BOLT, CATALOGO_g, CATALOGO_e, CATALOGO_d, CATALOGO_Bp, CATALOGO_tp,
    CATALOGO_tws, CATALOGO_ts, CATALOGO_tbs, CATALOGO_tst,
    REGRESSION_ALWAYS, GEOM_COLUMNS, STIFFENER_COLUMNS, GEOM_GRID_STEP,
)
from .geometry import assemble_from_named, p_from_named

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
                       drawing_code_logits: np.ndarray = None, drawing_code_classes=None,
                       slip_critical_logit: np.ndarray = None,
                       thresholds=None) -> pd.DataFrame:
    """
    reg_always_real / masked_value_real: ya des-estandarizados (mm).
    masked_* siguen el orden de config.MASKED_COLUMNS = GEOM_COLUMNS + STIFFENER_COLUMNS.
    Devuelve un DataFrame (una fila por muestra) ANTES de calcular las columnas derivadas.
    """
    n = reg_always_real.shape[0]
    if thresholds is None:
        thresholds = np.full(masked_value_real.shape[1], 0.5)

    out = {}
    for j, name in enumerate(REGRESSION_ALWAYS):
        out[name] = snap_to_catalog(reg_always_real[:, j], CATALOGS.get(name))

    masked_names = GEOM_COLUMNS + STIFFENER_COLUMNS
    active = masked_presence_prob >= thresholds[None, :]
    for j, name in enumerate(masked_names):
        vals = masked_value_real[:, j]
        if name in CATALOGS:
            vals = snap_to_catalog(vals, CATALOGS[name])
        else:  # geometría: sin catálogo propio, se snapea a la rejilla de GEOM_GRID_STEP mm
            vals = np.round(vals / GEOM_GRID_STEP) * GEOM_GRID_STEP
        out[name] = np.where(active[:, j], vals, 0.0)

    bolt_idx = bolt_logits.argmax(axis=1)
    out["Bolt"] = np.array([f"M{CATALOGO_BOLT[i]}" for i in bolt_idx])
    out["_bolt_nominal_mm"] = np.array([CATALOGO_BOLT[i] for i in bolt_idx])

    if drawing_code_logits is not None and drawing_code_classes is not None:
        out["DrawingCode"] = np.array(drawing_code_classes)[drawing_code_logits.argmax(axis=1)]

    if slip_critical_logit is not None:
        out["SlipCritical"] = np.where(_sigmoid(slip_critical_logit) >= 0.5, "YES", "NO")

    return pd.DataFrame(out)


def derive_dependent_columns(design_df: pd.DataFrame, beam_d_mm: np.ndarray = None,
                             reconstruct_p: bool = False) -> pd.DataFrame:
    """
    Hole, num_filas_tornillos, tiene_cantonera: aritmética pura sobre GEOM_COLUMNS
    (geometry.assemble_from_named). beam_d_mm ya no hace falta aquí (solo se usaba para
    ubicar el ala inferior al derivar DESDE p; ahora la red predice la geometría
    directamente), se acepta por compatibilidad de firma y se ignora si se pasa.
    reconstruct_p=True añade p1..p12 reconstruidas (geometry.p_from_named), útil para
    comparar contra el p real en evaluación o para exportar a sistemas que aún lo esperen.
    """
    design_df = design_df.copy().reset_index(drop=True)
    derived = assemble_from_named(design_df, design_df["_bolt_nominal_mm"].values)
    out = pd.concat([design_df, derived], axis=1)
    if reconstruct_p:
        out = pd.concat([out, p_from_named(design_df)], axis=1)
    return out
