"""
Traductor: input+output del modelo (formato V_num) -> fila de Tabla_MOMENT_M1.

Replica el mapeo de VBA__AI_Client.bas (WriteResponseToSheet). No hace COM: es
puro Python, se testea sin Excel.

Entradas:
  input_row : dict con las columnas de produccion
              (UNICODE, BEAM, COLUMN, Capacity_* [y/o *_Percentage],
               grado_acero, clase_tornillo, yieldmethod opcional)
  design_row: dict con el output del modelo (store.predict_df -> result_df):
              g, e, d, Bp, tp, p1..p12, tws, ts, tbs, tst, [Lh],
              Bolt, standard, SlipCritical, n_alma, n_cantonera
  feats_row : dict con features ricas del perfil/material (store.predict_df -> feats_df):
              BEAM_tf_mm (obligatorio para pfi), fy_acero_mpa, fu_acero_mpa

Salida: dict {columna_excel: valor} listo para escribir en Tabla_MOMENT_M1.
"""
from __future__ import annotations

import math

try:
    from core.config import P_COLUMNS, STIFFENER_COLUMNS
except Exception:  # cuando se importa fuera de V_num/app
    P_COLUMNS = [f"p{i}" for i in range(1, 13)]
    STIFFENER_COLUMNS = ["tws", "ts", "tbs", "tst"]


def _num(v, default=0.0):
    if v is None:
        return default
    try:
        f = float(v)
        return default if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return default


def mm_text(v):
    """CODAME guarda espesores como texto: '20mm'."""
    return f"{int(round(_num(v)))}mm"


def _pct(input_row, name, absolute_name):
    """Porcentaje de capacidad: usa *_Percentage si está; si no, 0."""
    if name in input_row and input_row[name] is not None:
        return _num(input_row[name])
    return _num(input_row.get(absolute_name), 0.0) if False else 0.0


def model_to_row(input_row: dict, design_row: dict, feats_row: dict | None = None) -> dict:
    d = design_row
    f = feats_row or {}

    bolt = d.get("Bolt")
    try:
        bolt_name = f"M{int(bolt)}" if bolt is not None else ""
    except (TypeError, ValueError):
        bolt_name = str(bolt or "")

    pfo = _num(d.get("d"))
    p1 = _num(d.get("p1"))
    tf = _num(f.get("BEAM_tf_mm"), None) if f.get("BEAM_tf_mm") is not None else None
    pfi = (p1 - pfo - tf) if (tf is not None) else None

    lh = _num(d.get("Lh"), 0.0)
    fy = _num(f.get("fy_acero_mpa"), input_row.get("fy_acero_mpa", 0.0))
    fu = _num(f.get("fu_acero_mpa"), input_row.get("fu_acero_mpa", 0.0))

    # Lp: si el modelo no lo da, geometría estándar Lp = 2e + sum(p)
    if d.get("Lp") is not None:
        Lp = _num(d.get("Lp"))
    else:
        Sp = sum(_num(d.get(c)) for c in P_COLUMNS)
        Lp = 2.0 * _num(d.get("e")) + Sp

    row = {
        # identificacion / demanda
        "Unicode": input_row.get("UNICODE", input_row.get("Unicode", "")),
        "Standards": d.get("standard", input_row.get("standard", "")),
        "BEAM": input_row.get("BEAM", ""),
        "COLUMN": input_row.get("COLUMN", ""),
        "MzEd_Porcen": _pct(input_row, "Capacity_Moment_Percentage", "Capacity_Moment"),
        "FyEd_Porcen": _pct(input_row, "Capacity_Shear_Percentage", "Capacity_Shear"),
        "FxEd_Porcen": _pct(input_row, "Capacity_Axial_Percentage", "Capacity_Axial"),
        "Pr_Porcen": _num(input_row.get("Pr_Porcen"), 0.0),
        "MzEd_PanelZone": _num(input_row.get("MzEd_PanelZone"), 0.0),
        "Vgra": _num(input_row.get("Vgra"), 0.0),
        "Havg": _num(input_row.get("Havg"), 0.0),
        # tornillos
        "BoltName_ep": bolt_name,
        "BoltGrade": input_row.get("clase_tornillo", input_row.get("BOLT STANDARD", "")),
        "BoltThreads": True,
        "BoltsInTensionFactor": 2,
        # chapa / cartabon
        "p2_ep": _num(d.get("g")),            # separacion entre columnas de tornillos
        "b_ep": _num(d.get("Bp")),
        "Lp": Lp,
        "ThicknessName_t_ep": mm_text(d.get("tp")),
        "dev": _num(d.get("e")),
        "p12_Outer": 0.0,
        "Lh": lh,
        "AnguloCantonera": 60.0 if lh > 0 else 0.0,
        # pasos (el modelo da pasos relativos)
        "pfo": pfo,
        "pfi": pfi,
        # rigidizadores
        "ThicknessName_t_webstiff": mm_text(d.get("tws")),
        "ThicknessName_t_compstiff": mm_text(d.get("ts")),
        "ThicknessName_t_BeamHcompstiff": mm_text(d.get("tbs")),
        "ThicknessName_t_tenstiff": mm_text(d.get("tst")),
        "Bws": 0.0, "Lws": 0.0,
        # soldadura / material
        "wf": 0.0, "ww": 0.0, "w3": 0.0, "w4": 0.0, "wh": 0.0,
        "fy": fy, "fyp": fy, "fu": fu, "fup": fu,
        "Electrode": input_row.get("Electrode", input_row.get("WELDING ELECTRODE", "")),
        "yieldmethod": input_row.get("yieldmethod", True),
        "WeldFactor": 1,
    }
    # p2..p12 desde el modelo (p1 va implícito en pfi)
    for c in P_COLUMNS:
        if c == "p1":
            continue
        row[c] = _num(d.get(c))
    return row
