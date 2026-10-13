"""Traduccion de filas servidas (CODAME + extras) al esquema de reentreno y persistencia.

- `to_train_row(row)`: fila servida -> columnas `train_schema.TRAIN_COLUMNS` (con tipo y
  NULL cuando falta el dato).
- `append_to_parquet(rows)`: anade al parquet unificado reemplazando `Unicode` duplicados.
"""
from __future__ import annotations

import math
import threading
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

import config
from catalogo import ACERO_TABLE, TORNILLO_TABLE, get_profile
from train_schema import BOOL_COLUMNS, NUMERIC_COLUMNS, TEXT_COLUMNS, TRAIN_COLUMNS

_LOCK = threading.Lock()


def _num(v):
    try:
        f = float(v)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return None


def _text(v):
    if v is None:
        return None
    s = str(v).strip()
    return s if s and s.lower() not in ("nan", "none") else None


def _bool(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    s = str(v).strip().upper()
    if s in ("TRUE", "YES", "1", "Y"):
        return True
    if s in ("FALSE", "NO", "0", "N"):
        return False
    return None


def _parse_mm(v):
    """'20mm' / '20' -> 20.0 ; vacio/'0mm' -> 0.0/None segun valor."""
    if v is None:
        return None
    s = str(v).strip().lower().replace("mm", "").replace("t", "").strip()
    if s == "":
        return None
    return _num(s)


def _bolt_int(v):
    """'M20' / 20 -> 20."""
    if v is None:
        return None
    s = str(v).strip().upper().replace("M", "")
    return _num(s)


def to_train_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Fila servida (CODAME + extras) -> dict con las columnas de TRAIN_COLUMNS."""
    r = row or {}

    beam = _text(r.get("BEAM"))
    column = _text(r.get("COLUMN"))
    geom_b = get_profile(beam) if beam else None
    geom_c = get_profile(column) if column else None

    def g(geom, col):
        if geom is None:
            return None
        return _num(geom.get(col))

    pfo = _num(r.get("pfo"))
    pfi = _num(r.get("pfi"))
    tf_b = g(geom_b, "tf_mm")
    p1 = None
    if pfo is not None and pfi is not None:
        p1 = pfo + pfi + (tf_b or 0.0)

    bolt = _bolt_int(r.get("BoltName_ep") or r.get("Bolt"))
    hole = (bolt + 2) if bolt is not None else None

    grado = _text(r.get("AceroEstructural") or r.get("grado_acero"))
    fy = _num(r.get("fy"))
    fu = _num(r.get("fu"))
    if grado is None and fy is not None:
        for k, v in ACERO_TABLE.items():
            if abs(v["fy_acero_mpa"] - fy) < 1e-6:
                grado = k
                break
    clase = _text(r.get("BoltGrade") or r.get("EstandarTornillos"))
    tornillo = TORNILLO_TABLE.get(clase, {}) if clase else {}

    out = {
        # demanda
        "Capacity_Moment_Percentage": _num(r.get("MzEd_Porcen")),
        "Capacity_Moment": _num(r.get("Capacity_Moment")),
        "Capacity_Shear_Percentage": _num(r.get("FyEd_Porcen")),
        "Capacity_Shear": _num(r.get("Capacity_Shear")),
        "Capacity_Axial_Percentage": _num(r.get("FxEd_Porcen")),
        "Capacity_Axial": _num(r.get("Capacity_Axial")),
        # diseno
        "g": _num(r.get("p2_ep")),
        "tws": _parse_mm(r.get("ThicknessName_t_webstiff")),
        "Bp": _num(r.get("b_ep")),
        "Lp": _num(r.get("Lp")),
        "tp": _parse_mm(r.get("ThicknessName_t_ep")),
        "Lh": _num(r.get("Lh")),
        "e": _num(r.get("dev")),
        "d": pfo,
        "p1": p1,
        "p2": _num(r.get("pb")),
        "ts": _parse_mm(r.get("ThicknessName_t_compstiff")),
        "tbs": _parse_mm(r.get("ThicknessName_t_BeamHcompstiff")),
        "tst": _parse_mm(r.get("ThicknessName_t_tenstiff")),
        "Hole": hole,
        # identificacion / metadatos
        "Unicode": _text(r.get("Unicode")),
        "BEAM": beam,
        "COLUMN": column,
        "DrawingCode": _text(r.get("DrawingCode")),
        "Bolt": bolt,
        "SlipCritical": _bool(r.get("SlipCritical")),
        "Normativas": _text(r.get("Standards")),
        "AceroEstructural": grado,
        "EstandarTornillos": clase,
        "Source": _text(r.get("Source")),
        "National_Annex": _text(r.get("National_Annex")),
        "standard": _text(r.get("standard")),
        # geometria viga
        "BEAM_d_mm": g(geom_b, "d_mm"),
        "BEAM_bf_mm": g(geom_b, "bf_mm"),
        "BEAM_tw_mm": g(geom_b, "tw_mm"),
        "BEAM_tf_mm": tf_b,
        "BEAM_A_mm": g(geom_b, "A_mm"),
        "BEAM_w_kgm": g(geom_b, "w_kgm"),
        "BEAM_iy_mm": g(geom_b, "iy_mm"),
        "BEAM_iz_mm": g(geom_b, "iz_mm"),
        "BEAM_wely_mm": g(geom_b, "wely_mm"),
        "BEAM_welz_mm": g(geom_b, "welz_mm"),
        # geometria columna
        "COLUMN_d_mm": g(geom_c, "d_mm"),
        "COLUMN_bf_mm": g(geom_c, "bf_mm"),
        "COLUMN_tw_mm": g(geom_c, "tw_mm"),
        "COLUMN_tf_mm": g(geom_c, "tf_mm"),
        "COLUMN_A_mm": g(geom_c, "A_mm"),
        "COLUMN_w_kgm": g(geom_c, "w_kgm"),
        "COLUMN_iy_mm": g(geom_c, "iy_mm"),
        "COLUMN_iz_mm": g(geom_c, "iz_mm"),
        "COLUMN_wely_mm": g(geom_c, "wely_mm"),
        "COLUMN_welz_mm": g(geom_c, "welz_mm"),
        # materiales
        "fy_acero_mpa": fy,
        "fu_acero_mpa": fu,
        "fy_tornillo_mpa": _num(tornillo.get("fy_tornillo_mpa")),
        "fu_tornillo_mpa": _num(tornillo.get("fu_tornillo_mpa")),
        "fv_tornillo_mpa": _num(tornillo.get("fv_tornillo_mpa")),
        # conteos
        "n_alma": _num(r.get("n_alma")),
        "n_cantonera": _num(r.get("n_cantonera")),
    }
    for n in range(3, 13):
        out[f"p{n}"] = _num(r.get(f"p{n}"))

    # Coercion final por tipo.
    for c in NUMERIC_COLUMNS:
        out[c] = _num(out.get(c))
    for c in BOOL_COLUMNS:
        out[c] = _bool(out.get(c))
    for c in TEXT_COLUMNS:
        out[c] = _text(out.get(c))

    return {c: out.get(c) for c in TRAIN_COLUMNS}


def append_to_parquet(rows: List[Dict[str, Any]], path: Path = None) -> Dict[str, Any]:
    """Traduce `rows`, reemplaza `Unicode` duplicados y guarda el parquet unificado."""
    path = Path(path or config.DATASET_PATH)
    new_df = pd.DataFrame([to_train_row(r) for r in rows], columns=TRAIN_COLUMNS)

    with _LOCK:
        if path.exists():
            current = pd.read_parquet(path).reindex(columns=TRAIN_COLUMNS)
        else:
            current = pd.DataFrame(columns=TRAIN_COLUMNS)

        existing = set(current["Unicode"].dropna().astype(str))
        incoming = set(new_df["Unicode"].dropna().astype(str))
        added = len(incoming - existing)
        updated = len(incoming & existing)

        combined = pd.concat([current, new_df], ignore_index=True)
        if not combined.empty and combined["Unicode"].notna().any():
            combined = combined.drop_duplicates(subset="Unicode", keep="last")

        path.parent.mkdir(parents=True, exist_ok=True)
        combined.to_parquet(path, index=False)

    return {"added": added, "updated": updated, "total_rows": int(len(combined))}
