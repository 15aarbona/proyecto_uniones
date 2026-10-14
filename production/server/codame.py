"""Mapeo input + diseno -> 63 columnas de CODAME (`Tabla_MOMENT_M1`), con imputacion.

Vive en el servidor (fuente unica para todos los modelos) y usa `catalogo` (datos en
`production/server/data`). Devuelve todas las columnas del esquema CODAME con su tipo y
formato correctos; `codame_schema.fill_missing` actua como red de seguridad.

Referencia: `doc/codame/mapeo_columnas_codame.md`.

Reglas con criterio de ingenieria PROVISIONAL (marcadas con "PROVISIONAL"): ancho de
chapa, Bws/Lws y largo de cantonera. Estan aisladas en funciones y constantes para
poder ajustarlas sin tocar el resto.
"""
import logging
import math

from catalogo import ACERO_TABLE, DEFAULT_GRADO_ACERO, DEFAULT_CLASE_TORNILLO, get_profile
from externos import tablapernos

log = logging.getLogger("ai-server")

# ---------------------------------------------------------------------------
# Valores por defecto de la tabla CODAME (Cambios_a_aplicar.txt)
# ---------------------------------------------------------------------------
DEFAULT_WELD_MM = 6.0             # wf, ww, w3, w4, wh
DEFAULT_PR_PORCEN = 50
DEFAULT_TRACCION = True
DEFAULT_ELECTRODE = "E49XX"
DEFAULT_SISUNI = True             # SisUniBoltSI, SisUniPlateSI
DEFAULT_DESIGNATION = "Tekla19"
DEFAULT_E_MPA = 200000.0
DEFAULT_HAUNCH_ANGLE_DEG = 60.0   # solo si hay cantonera (Lh > 0)
DEFAULT_HAUNCH_FACTOR = 0.7       # solo si hay cantonera (Lh > 0)

# Red de seguridad: pfi minimo (mm) que se garantiza aqui si el modelo entrega un
# p1 incoherente. El minimo "de diseno" lo aplica el adaptador del modelo (PFI_MIN_MM).
PFI_MIN_SEGURIDAD = 5.0

# PROVISIONAL: holgura (mm) entre la placa del alma de la columna y los acuerdos / rigidizadores.
WEB_PLATE_GAP_MM = 5.0


def _num(v, default=0.0):
    try:
        f = float(v)
        return default if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return default


def _mm_text(v) -> str:
    """CODAME guarda espesores como texto: '20mm'."""
    return f"{int(round(_num(v)))}mm"


def _ceil5(x: float) -> float:
    return math.ceil(round(x, 6) / 5.0) * 5.0


def _floor5(x: float) -> float:
    return math.floor(round(x, 6) / 5.0) * 5.0


def _pct_int(ratio) -> int:
    """Ratio 0-1 -> porcentaje entero (sin decimales ni ruido de coma flotante)."""
    return int(round(_num(ratio) * 100.0))


def _infer_source(beam) -> str:
    return "Canadian" if str(beam).strip().upper().startswith("W") else "European"


def _n_years() -> int:
    return 12


def _geom(profile, col, default=0.0):
    return _num(profile.get(col), default) if profile is not None else default


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


def _plate_width(bp, g, bolt, bf_beam, bf_col, uid) -> float:
    """b_ep: ancho de la chapa. PROVISIONAL.

    Se respeta lo que predice el modelo salvo que incumpla:
      - minimo por distancia al borde: g + 2*Le_min del tornillo,
      - minimo por geometria: ancho del ala de la viga (acotado al ala del pilar),
      - maximo: ancho del ala del pilar.
    Si el minimo por tornillos ya no cabe en el ala del pilar, se deja el valor del modelo.
    """
    try:
        le_min = tablapernos.DATOS_PERNOS[int(bolt)]["Le_min"]
    except (KeyError, TypeError, ValueError):
        le_min = 0.0
    lo_bolts = g + 2.0 * le_min
    hi = bf_col if bf_col > 0 else math.inf
    lo = max(lo_bolts, min(bf_beam, hi) if bf_beam > 0 else 0.0)

    if lo_bolts > hi:
        log.warning("b_ep: no cabe g + 2*Le_min = %.0f en el ala del pilar (%.0f); "
                    "se mantiene el valor del modelo (UNICODE=%s)", lo_bolts, hi, uid)
        return bp
    new = float(math.ceil(min(max(bp, lo), hi)))
    if new != bp:
        log.info("b_ep %.0f -> %.0f (min %.0f, max %.0f) (UNICODE=%s)", bp, new, lo, hi, uid)
    return new


def _web_plate_dims(col, beam_d, beam_tf, t_stiff):
    """(Bws, Lws) de la placa del alma de la columna. PROVISIONAL.

    Hipotesis: placa paralela al alma, entre las alas de la columna.
      Bws = alma libre entre acuerdos: d_col - 2*tf_col - 2*r_col, menos holgura a cada lado.
      Lws = entre rigidizadores transversales (a la altura de las alas de la viga):
            (d_viga - tf_viga) - t_rigidizador, menos holgura a cada lado.
    No tiene en cuenta los tornillos (por confirmar).
    """
    if col is None:
        return 0.0, 0.0
    hw = _geom(col, "d_mm") - 2.0 * _geom(col, "tf_mm") - 2.0 * _geom(col, "r1_mm")
    bws = _floor5(hw - 2.0 * WEB_PLATE_GAP_MM)
    lws = _floor5(beam_d - beam_tf - t_stiff - 2.0 * WEB_PLATE_GAP_MM)
    return max(bws, 0.0), max(lws, 0.0)


def _haunch_length(p, e, d, beam_d, n_cantonera) -> float:
    """Lh: largo (proyeccion horizontal) de la cantonera. PROVISIONAL.

    Canto de la cantonera = lo que la chapa sobresale por debajo de la viga:
        H = sum(p) + e - (d + canto_viga)      (el origen es la primera fila de tornillos)
    Con angulo de 60 grados medido desde la horizontal: Lh = H / tan(60).
    Si la geometria no da canto positivo se usan las ultimas `n_cantonera` separaciones.
    """
    if n_cantonera <= 0:
        return 0.0
    depth = sum(p.values()) + e - (d + beam_d)
    if depth <= 0:
        active = [v for _, v in sorted(p.items()) if v > 0]
        depth = sum(active[-n_cantonera:]) + e
    return _ceil5(depth / math.tan(math.radians(DEFAULT_HAUNCH_ANGLE_DEG)))


def to_codame(input_row: dict, design_row: dict) -> dict:
    """Input + diseno -> fila de CODAME (todas las columnas, imputadas)."""
    inp = input_row or {}
    d = design_row or {}
    uid = inp.get("UNICODE")

    beam = str(inp.get("BEAM", "")).strip()
    column = str(inp.get("COLUMN", "")).strip()
    geom = get_profile(beam)
    col_geom = get_profile(column)
    tf = _geom(geom, "tf_mm")
    beam_d = _geom(geom, "d_mm")

    e = _num(d.get("e"))
    g = _num(d.get("g"))
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

    pfo = _num(d.get("d"))

    # pfi = p1 - pfo - tf debe ser siempre positivo. Si el modelo entrega un p1
    # incoherente se corrige aqui (red de seguridad) y se deja constancia en el log.
    if p[1] <= 0:
        log.error("p1 ausente o 0 en el diseno (UNICODE=%s): pfi no es fiable", uid)
    elif p[1] - pfo - tf < PFI_MIN_SEGURIDAD:
        nuevo_p1 = math.ceil((pfo + tf + PFI_MIN_SEGURIDAD) / 5.0) * 5.0
        log.warning("pfi=%.1f < %.1f; p1 %.1f -> %.1f (UNICODE=%s)",
                    p[1] - pfo - tf, PFI_MIN_SEGURIDAD, p[1], nuevo_p1, uid)
        p[1] = nuevo_p1
    p1 = p[1]
    pfi = p1 - pfo - tf

    # Lp = suma de todas las p + 2e (e = distancia del primer y ultimo tornillo al borde).
    lp = 2.0 * e + sum(p.values())

    # ts y tst son siempre iguales: se toma tst (su catalogo {0,10,15,20} esta contenido
    # en el de ts) y se copia. Si un modelo antiguo solo trae ts, se usa ese.
    t_stiff = _num(d["tst"]) if "tst" in d else _num(d.get("ts"))

    b_ep = _plate_width(
        _num(d.get("Bp")), g, bolt,
        _geom(geom, "bf_mm"), _geom(col_geom, "bf_mm"), uid,
    )

    tws = _num(d.get("tws"))
    bws, lws = _web_plate_dims(col_geom, beam_d, tf, t_stiff) if tws > 0 else (0.0, 0.0)

    n_cantonera = int(_num(d.get("n_cantonera")))
    lh = _haunch_length(p, e, pfo, beam_d, n_cantonera)
    has_haunch = lh > 0

    row = {
        "Unicode": uid if uid is not None else "",
        "Normativas": inp.get("Normativas", ""),
        "BEAM": beam,
        "COLUMN": column,
        "MzEd_Porcen": _pct_int(inp.get("ratio_moment")),
        "FyEd_Porcen": _pct_int(inp.get("ratio_shear")),
        "FxEd_Porcen": _pct_int(inp.get("ratio_axial")),
        "Pr_Porcen": DEFAULT_PR_PORCEN,
        "Traccion": DEFAULT_TRACCION,
        "MzEd_PanelZone": 0.0,
        "Vgra": 0.0,
        "Havg": 0.0,
        "BoltName_ep": bolt_name,
        "p2_ep": g,
        "ThicknessName_t_webstiff": _mm_text(tws),
        "Bws": bws,
        "Lws": lws,
        "b_ep": b_ep,
        "Lp": lp,
        "ThicknessName_t_ep": _mm_text(d.get("tp")),
        "Lh": lh,
        "AnguloCantonera": DEFAULT_HAUNCH_ANGLE_DEG if has_haunch else 0.0,
        "dev": e,
        "p12_Outer": 0.0,
        "pfo": pfo,
        "pfi": pfi,
        "pb": p[2],
        "ThicknessName_t_compstiff": _mm_text(t_stiff),
        "ThicknessName_t_BeamHcompstiff": _mm_text(d.get("tbs")),
        "ThicknessName_t_tenstiff": _mm_text(t_stiff),
        "wf": DEFAULT_WELD_MM,
        "ww": DEFAULT_WELD_MM,
        "w3": DEFAULT_WELD_MM,
        "w4": DEFAULT_WELD_MM,
        "wh": DEFAULT_WELD_MM,
        "FactorCantoCantonera": DEFAULT_HAUNCH_FACTOR if has_haunch else 0.0,
        "ntensionrows": _tension_rows({**d, "p1": p1}, beam_d),
        "fy": fy,
        "fu": fu,
        "fyp": fy,
        "fup": fu,
        "E": DEFAULT_E_MPA,
        "BoltGrade": str(inp.get("clase_tornillo") or DEFAULT_CLASE_TORNILLO).strip(),
        "BoltThreads": True,
        "Electrode": DEFAULT_ELECTRODE,
        "yieldmethod": True,
        "WeldFactor": 1,
        "BoltsInTensionFactor": 2,
        "SisUniBoltSI": DEFAULT_SISUNI,
        "SisUniPlateSI": DEFAULT_SISUNI,
        "Source": _infer_source(beam),
        "Designation": DEFAULT_DESIGNATION,
    }
    for n in range(3, _n_years() + 1):
        row[f"p{n}"] = p[n]
    return row