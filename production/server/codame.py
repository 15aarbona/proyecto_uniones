"""Mapeo input + diseno -> 63 columnas de CODAME (`Tabla_MOMENT_M1`), con imputacion.

Vive en el servidor (fuente unica para todos los modelos) y usa `catalogo` (datos en
`production/server/data`). Devuelve todas las columnas del esquema CODAME con su tipo y
formato correctos; `codame_schema.fill_missing` actua como red de seguridad.

Referencia: `doc/codame/mapeo_columnas_codame.md`.
"""
import logging
import math

from catalogo import ACERO_TABLE, DEFAULT_GRADO_ACERO, DEFAULT_CLASE_TORNILLO, get_profile

log = logging.getLogger("ai-server")

# Red de seguridad: pfi minimo (mm) que se garantiza aqui si el modelo entrega un
# p1 incoherente. El minimo "de diseno" lo aplica el adaptador del modelo (PFI_MIN_MM).
PFI_MIN_SEGURIDAD = 5.0


def _num(v, default=0.0):
    try:
        f = float(v)
        return default if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return default


def _mm_text(v) -> str:
    """CODAME guarda espesores como texto: '20mm'."""
    return f"{int(round(_num(v)))}mm"


def _infer_source(beam) -> str:
    return "Canadian" if str(beam).strip().upper().startswith("W") else "European"


def _n_years() -> int:
    return 12


def _tension_rows(design_row: dict, beam_d_mm: float) -> int:
    """ntensionrows: 3 si hay >=2 filas en [d, d+BEAM_d], si no 2 (logica del cliente)."""
    d = _num(design_row.get("d"))
    finish = d + _num(beam_d_mm)
    position = 0.0
    rows_inside = 0
    if d <= position <= finish:
        rows_inside += 1
    for n in range(1, _n_years() + 1):
        p = _num(design_row.get(f"p{n}"))
        if p == 0.0:
            break
        position += p
        if d <= position <= finish:
            rows_inside += 1
    return 3 if rows_inside >= 2 else 2


def to_codame(input_row: dict, design_row: dict) -> dict:
    """Input + diseno -> fila de CODAME (todas las columnas, imputadas)."""
    inp = input_row or {}
    d = design_row or {}

    beam = str(inp.get("BEAM", "")).strip()
    geom = get_profile(beam)
    tf = _num(geom.get("tf_mm")) if geom is not None else 0.0
    beam_d = _num(geom.get("d_mm")) if geom is not None else 0.0

    e = _num(d.get("e"))
    p = {n: _num(d.get(f"p{n}")) for n in range(1, _n_years() + 1)}

    grado = str(inp.get("grado_acero") or DEFAULT_GRADO_ACERO).strip()
    acero = ACERO_TABLE.get(grado, ACERO_TABLE[DEFAULT_GRADO_ACERO])
    fy = _num(inp.get("fy_acero_mpa", acero["fy_acero_mpa"]))
    fu = _num(inp.get("fu_acero_mpa", acero["fu_acero_mpa"]))

    bolt = d.get("Bolt")
    try:
        bolt_name = f"M{int(bolt)}" if bolt is not None else ""
    except (TypeError, ValueError):
        bolt_name = str(bolt or "")

    lh = _num(d.get("Lh"))  # V11 no predice Lh -> 0
    pfo = _num(d.get("d"))

    # pfi = p1 - pfo - tf debe ser siempre positivo. Si el modelo entrega un p1
    # incoherente se corrige aqui (red de seguridad) y se deja constancia en el log.
    if p[1] <= 0:
        log.error("p1 ausente o 0 en el diseno (UNICODE=%s): pfi no es fiable",
                  inp.get("UNICODE"))
    elif p[1] - pfo - tf < PFI_MIN_SEGURIDAD:
        nuevo_p1 = math.ceil((pfo + tf + PFI_MIN_SEGURIDAD) / 5.0) * 5.0
        log.warning("pfi=%.1f < %.1f; p1 %.1f -> %.1f (UNICODE=%s)",
                    p[1] - pfo - tf, PFI_MIN_SEGURIDAD, p[1], nuevo_p1, inp.get("UNICODE"))
        p[1] = nuevo_p1
    p1 = p[1]
    pfi = p1 - pfo - tf
    lp = 2.0 * e + sum(p.values())

    row = {
        "Unicode": inp.get("UNICODE", ""),
        "Standards": inp.get("Normativas", ""),
        "BEAM": beam,
        "COLUMN": inp.get("COLUMN", ""),
        "MzEd_Porcen": _num(inp.get("ratio_moment")) * 100.0,
        "FyEd_Porcen": _num(inp.get("ratio_shear")) * 100.0,
        "FxEd_Porcen": _num(inp.get("ratio_axial")) * 100.0,
        "Pr_Porcen": 0.0,
        "Traccion": "",
        "MzEd_PanelZone": 0.0,
        "Vgra": 0.0,
        "Havg": 0.0,
        "BoltName_ep": bolt_name,
        "p2_ep": _num(d.get("g")),
        "ThicknessName_t_webstiff": _mm_text(d.get("tws")),
        "Bws": 0.0,
        "Lws": 0.0,
        "b_ep": _num(d.get("Bp")),
        "Lp": lp,
        "ThicknessName_t_ep": _mm_text(d.get("tp")),
        "Lh": lh,
        "AnguloCantonera": 60.0 if lh != 0 else 0.0,
        "dev": e,
        "p12_Outer": 0.0,
        "pfo": pfo,
        "pfi": pfi,
        "pb": p[2],
        "ThicknessName_t_compstiff": _mm_text(d.get("ts")),
        "ThicknessName_t_BeamHcompstiff": _mm_text(d.get("tbs")),
        "ThicknessName_t_tenstiff": _mm_text(d.get("tst")),
        "wf": 0.0,
        "ww": 0.0,
        "w3": 0.0,
        "w4": 0.0,
        "wh": 0.0,
        "FactorCantoCantonera": 0.7 if lh != 0 else 0.0,
        "ntensionrows": _tension_rows({**d, "p1": p1}, beam_d),
        "fy": fy,
        "fu": fu,
        "fyp": fy,
        "fup": fu,
        "E": 0.0,
        "BoltGrade": str(inp.get("clase_tornillo") or DEFAULT_CLASE_TORNILLO).strip(),
        "BoltThreads": True,
        "Electrode": "",
        "yieldmethod": True,
        "WeldFactor": 1,
        "BoltsInTensionFactor": 2,
        "SisUniBoltSI": "",
        "SisUniPlateSI": "",
        "Source": _infer_source(beam),
        "Designation": "",
        "Estado_IA": "",
    }
    for n in range(3, _n_years() + 1):
        row[f"p{n}"] = p[n]
    return row