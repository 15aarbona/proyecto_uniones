"""Preprocesador del PINN (se serializa en artifacts/preprocessor.joblib).

Convierte el dataframe de features (ya enriquecido con la geometria de los perfiles) en
el vector de 21 entradas del notebook. El modelo se entreno SIN normalizar.

Ojo: la clase se serializa como `core.dataset.Preprocessor`; no moverla ni renombrarla.
"""
import math

import numpy as np
import pandas as pd

from .config import GEOM_DEFAULTS, INPUT_DIM


def _f(v, default=0.0) -> float:
    try:
        x = float(v)
        return default if math.isnan(x) else x
    except (TypeError, ValueError):
        return default


class Preprocessor:
    def __init__(self):
        self.input_dim = INPUT_DIM
        self.version = 1

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        out = []
        for _, r in df.iterrows():
            rm, rv, rn = (_f(r.get(k)) for k in ("ratio_moment", "ratio_shear", "ratio_axial"))
            # el notebook interpreta valores > 5 como porcentajes
            rm, rv, rn = [x / 100.0 if x > 5.0 else x for x in (rm, rv, rn)]
            g = {k: _f(r.get(k), d) for k, d in GEOM_DEFAULTS.items()}
            beam = [g["BEAM_d_mm"], g["BEAM_b_mm"], g["BEAM_tf_mm"], g["BEAM_tw_mm"], g["BEAM_r1_mm"]]
            col = [g["COLUMN_d_mm"], g["COLUMN_b_mm"], g["COLUMN_tf_mm"], g["COLUMN_tw_mm"], g["COLUMN_r1_mm"]]
            fy, fu = _f(r.get("fy_acero_mpa")), _f(r.get("fu_acero_mpa"))
            out.append([
                rm, rv, rn, *beam, *col,
                fy, fu, fy, fu, fy,
                _f(r.get("fy_tornillo_mpa")), _f(r.get("fu_tornillo_mpa")), _f(r.get("fv_tornillo_mpa")),
            ])
        arr = np.asarray(out, dtype=np.float32)
        if arr.shape[1] != self.input_dim:
            raise ValueError(f"Vector de entrada de {arr.shape[1]} columnas; se esperaban {self.input_dim}")
        return arr