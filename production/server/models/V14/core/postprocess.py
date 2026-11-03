"""Salidas de la PINN -> diseno en claves canonicas (las que consume codame.to_codame).

Interpretacion geometrica (coherente con la loss del notebook):
  e1       = distancia del 1er tornillo al borde superior de la chapa      -> e (dev)
  e_x1     = chapa por encima de la cara superior del ala de la viga
  pfo (d)  = e_x1 - e1  (1er tornillo a la cara exterior del ala)
  p1_mat   = separaciones entre filas (4 valores); p1 = pfo + pfi + tf (CODAME)
  b_p, e2  = ancho de chapa y distancia lateral del tornillo              -> g = b_p - 2*e2
La red NO predice rigidizadores (tws, tst, tbs = 0) ni cantonera (n_cantonera = 0): el
refinado (refinar.py) los anade/crea si la comprobacion AISC lo exige.
"""
import numpy as np
import pandas as pd

from .config import (
    CATALOGO_Bp, CATALOGO_e, CATALOGO_g, CATALOGO_tp, BOLT_DIAMETERS, N_Y,
    PFI_MIN_MM, PFO_MAX_MM, PFO_MIN_MM, ROWS_CHOICES,
)


def _c5(x):
    return np.ceil(np.round(x, 6) / 5.0) * 5.0


def _r5(x):
    return np.round(x / 5.0) * 5.0


def snap_nearest(values, catalog):
    arr = np.asarray(catalog, float)
    v = np.asarray(values, float)
    return arr[np.abs(v[:, None] - arr[None, :]).argmin(1)]


def snap_up(values, catalog):
    """Primer valor del catalogo >= value (el espesor no se reduce al ajustar)."""
    arr = np.sort(np.asarray(catalog, float))
    idx = np.searchsorted(arr, np.asarray(values, float) - 1e-9)
    return arr[np.minimum(idx, len(arr) - 1)]


def decode_predictions(out: dict, geom: dict, bolt_idx, rows_idx, tf_beam) -> pd.DataFrame:
    """Todos los argumentos son arrays numpy (out/geom: dicts de arrays)."""
    n = len(bolt_idx)
    tf = np.asarray(tf_beam, float)
    bolt = np.asarray(BOLT_DIAMETERS)[bolt_idx]
    n_rows = np.asarray(ROWS_CHOICES)[rows_idx]

    e = snap_nearest(geom["e1"], CATALOGO_e)
    pfo = np.clip(_r5(geom["e_x1"] - geom["e1"]), PFO_MIN_MM, PFO_MAX_MM)
    bp = np.clip(np.ceil(geom["b_p"]), CATALOGO_Bp[0], CATALOGO_Bp[-1])
    g = snap_nearest(bp - 2.0 * geom["e2"], CATALOGO_g)
    tp = snap_up(geom["t_p"], CATALOGO_tp)

    pm = geom["p1_matrix"]
    p1 = np.maximum(_c5(pm[:, 0]), _c5(pfo + tf + PFI_MIN_MM))     # pfi = p1 - pfo - tf >= 5
    gaps = np.stack([p1, _c5(pm[:, 1]), _c5(pm[:, 2]), _c5(pm[:, 3]), _c5(pm[:, 3])], axis=1)
    n_gaps = n_rows - 1                                            # 1..5 separaciones activas
    p = np.zeros((n, N_Y))
    for j in range(gaps.shape[1]):
        p[:, j] = np.where(j < n_gaps, gaps[:, j], 0.0)

    d = {"Bolt": bolt, "d": pfo, "e": e, "g": g, "Bp": bp, "tp": tp,
         "tws": 0.0, "ts": 0.0, "tbs": 0.0, "tst": 0.0,
         "n_cantonera": 0, "n_alma": np.maximum(1, n_rows - 2),
         "num_filas_tornillos": n_rows, "tiene_cantonera": False,
         "Hole": bolt + 2, "SlipCritical": "NO", "standard": ""}
    for j in range(N_Y):
        d[f"p{j + 1}"] = p[:, j]
    return pd.DataFrame(d)