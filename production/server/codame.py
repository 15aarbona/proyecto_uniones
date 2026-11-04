"""Mapeo input + diseno -> 63 columnas de CODAME (`Tabla_MOMENT_M1`), con imputacion.
Vive en el servidor y utiliza el módulo `catalogo`.
"""
import logging
import math

from catalogo import ACERO_TABLE, DEFAULT_GRADO_ACERO, DEFAULT_CLASE_TORNILLO, get_profile
from externos import Externos, tablapernos, tablaplaca

log = logging.getLogger("ai-server")

DEFAULT_WELD_MM = 6.0
DEFAULT_PR_PORCEN = 50
DEFAULT_TRACCION = True
DEFAULT_ELECTRODE = "E49XX"
DEFAULT_SISUNI = True
DEFAULT_DESIGNATION = "Tekla19"
DEFAULT_E_MPA = 200000.0
DEFAULT_HAUNCH_ANGLE_DEG = 60.0
DEFAULT_HAUNCH_FACTOR = 0.7
PFI_MIN_SEGURIDAD = 5.0
WEB_PLATE_GAP_MM = 5.0

_SEP_KEYS = ("pb", "p3", "p4", "p5", "p6", "p7", "p8", "p9", "p10", "p11", "p12")


def _num(v, default=0.0):
    try:
        f = float(v)
        return default if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return default


def _mm_text(v) -> str:
    return f"{int(round(_num(v)))}mm"


def _ceil5(x: float) -> float:
    return math.ceil(round(x, 6) / 5.0) * 5.0


def _floor5(x: float) -> float:
    return math.floor(round(x, 6) / 5.0) * 5.0


def _round5(x: float) -> float:
    return round(x / 5.0) * 5.0


def _redond5(x: float) -> float:
    """Mismo redondeo que `moduloauxiliar.redond_mult(x, 5.0)` del calculador."""
    return _round5(x)


def _pct_int(ratio) -> int:
    return int(round(_num(ratio) * 100.0))


def _infer_source(beam) -> str:
    return "Canadian" if str(beam).strip().upper().startswith("W") else "European"


def _n_years() -> int:
    return 12


def _geom(profile, col, default=0.0):
    return _num(profile.get(col), default) if profile is not None else default


def diametro_tornillo(nombre, default: float = 24.0) -> float:
    """'M24' -> 24.0 (mismo criterio que el calculador: solo los digitos del nombre)."""
    digitos = "".join(ch for ch in str(nombre or "") if ch.isdigit())
    return float(digitos) if digitos else default


def _web_plate_dims(col, beam_d: float, beam_tf: float, t_stiff: float):
    """(Bws, Lws) de la placa de refuerzo del alma del pilar. El llamador decide si hay placa (tws > 0)."""
    hw = _geom(col, "d_mm") - 2.0 * _geom(col, "tf_mm") - 2.0 * _geom(col, "r1_mm")
    bws = max(_floor5(hw - 2.0 * WEB_PLATE_GAP_MM), 0.0)
    lws = max(_floor5(beam_d - beam_tf - t_stiff - 2.0 * WEB_PLATE_GAP_MM), 0.0)
    return bws, lws


def ajustar_cantonera_y_chapa(work: dict, lim: dict) -> bool:
    """Patron vertical de tornillos por debajo de la fila 1, en posiciones ABSOLUTAS.

    - Ninguna fila puede caer sobre el ala inferior de la viga ni sobre el ala de la cantonera.
      Zona prohibida de una cara y: (min(y - tf - holgura_fisica, y - holgura_herramienta),
      y + holgura_herramienta), igual que `calcular_geometria`.
    - Una fila prohibida se mueve al borde valido mas cercano que respete el paso minimo y
      maximo con la fila anterior. Las filas siguientes NO se desplazan.
    - UNA sola fila por debajo de viga/cantonera (la exterior); las sobrantes se eliminan y,
      si no habia, se anade. `Lh` no se toca. Las filas 0 (dev) y 1 (dev + c) no se tocan.

    `lim` trae los limites del calculador: clearance, minsp, maxsp, c.
    Modifica `work` (pb, p3..p12) y devuelve True si cambio algo.
    """
    beam = get_profile(str(work.get("BEAM", "")).strip())
    d, tf = _geom(beam, "d_mm"), _geom(beam, "tf_mm")
    c = _num(lim.get("c"))
    if d <= 0 or tf <= 0 or c <= 0:
        return False

    angulo = _num(work.get("AnguloCantonera"))
    factor = _num(work.get("FactorCantoCantonera"))
    h_h = factor * d / math.sin(math.radians(angulo)) if angulo != 0.0 else 0.0

    dev = _num(work.get("dev"), 50.0)
    pfo = _num(work.get("pfo"), 50.0)
    minsp = max(_num(lim.get("minsp")), 1.0)
    maxsp = _num(lim.get("maxsp")) or float("inf")
    m_tool = _num(lim.get("clearance"))
    wf = _num(work.get("wf")) or DEFAULT_WELD_MM
    m_fis = diametro_tornillo(work.get("BoltName_ep")) / 2.0 + wf + 5.0
    eps = 1e-6

    ys = [dev, dev + c]
    for k in _SEP_KEYS:
        v = _num(work.get(k))
        if v > 0:
            ys.append(ys[-1] + v)

    y_viga = dev + pfo + d               # cara inferior del ala inferior de la viga
    y_bot = y_viga + h_h                 # cara inferior de viga o del ala de la cantonera

    def zona(y_cara):
        return (min(y_cara - tf - m_fis, y_cara - m_tool), y_cara + m_tool)

    zonas = [zona(y_viga)] + ([zona(y_bot)] if h_h > 0 else [])
    zone_hi = zonas[-1][1]

    def prohibido(y):
        return any(lo + eps < y < hi - eps for lo, hi in zonas)

    def candidatos(y):
        cands = {y}
        for lo, hi in zonas:
            cands.add(float(math.floor(round(lo, 6))))
            cands.add(float(math.ceil(round(hi, 6))))
        return sorted(cands, key=lambda v: abs(v - y))

    nuevas = ys[:2]
    for y in ys[2:]:
        prev = nuevas[-1]
        y = max(y, prev + minsp)
        validos = [v for v in candidatos(y) if v >= prev + minsp - 1e-9 and not prohibido(v)]
        elegido = next((v for v in validos if v - prev <= maxsp + 1e-9), None)
        if elegido is None:              # sin opcion dentro del paso maximo: se prioriza no chocar
            elegido = validos[0] if validos else y
        nuevas.append(elegido)

    resto = nuevas[2:]
    dentro = nuevas[:2] + [y for y in resto if y < zone_hi - 1e-9]
    fuera = [y for y in resto if y >= zone_hi - 1e-9]

    y_min = max(zone_hi, dentro[-1] + minsp)
    if fuera and fuera[0] >= y_min - 1e-9:
        y_ext = fuera[0]
    else:
        y_ext = _ceil5(y_min)

    finales = dentro + [y_ext]
    seps = [round(finales[i + 1] - finales[i], 6) for i in range(1, len(finales) - 1)]
    if len(seps) > len(_SEP_KEYS):
        return False
    seps += [0.0] * (len(_SEP_KEYS) - len(seps))

    cambiado = False
    for k, v in zip(_SEP_KEYS, seps):
        if abs(_num(work.get(k)) - v) > 1e-9:
            work[k] = v
            cambiado = True
    return cambiado


def _plate_width(bp, g, bolt, bf_beam, bf_col, uid) -> float:
    try:
        le_min = tablapernos.DATOS_PERNOS[int(bolt)]["Le_min"]
    except (KeyError, TypeError, ValueError):
        le_min = 35.0

    ancho_min_tornillos = g + 2.0 * le_min
    ancho_min_viga = bf_beam + 10.0 if bf_beam > 0 else 0.0
    ancho_minimo = _ceil5(max(ancho_min_tornillos, ancho_min_viga))
    ancho_maximo = bf_col if bf_col > 0 else (ancho_minimo + 100.0)

    if ancho_minimo > ancho_maximo:
        return float(math.ceil(ancho_minimo))

    if ancho_minimo <= bp <= ancho_maximo:
        return float(math.ceil(_round5(bp)))

    b_ep_opt = min(max(ancho_minimo, _round5(bf_beam + 20.0)), ancho_maximo)
    return float(math.ceil(b_ep_opt))


def to_codame(input_row: dict, design_row: dict, apply_adjustments: bool = True) -> dict:
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
    if apply_adjustments and p[1] > 0 and (p[1] - pfo - tf < PFI_MIN_SEGURIDAD):
        p[1] = math.ceil((pfo + tf + PFI_MIN_SEGURIDAD) / 5.0) * 5.0

    p1 = p[1]
    pfi = p1 - pfo - tf
    lp = 2.0 * e + sum(p.values())
    t_stiff = _num(d["tst"]) if "tst" in d else _num(d.get("ts"))

    b_ep = (
        _plate_width(_num(d.get("Bp")), g, bolt, _geom(geom, "b_mm") or _geom(geom, "bf_mm"), _geom(col_geom, "b_mm") or _geom(col_geom, "bf_mm"), uid)
        if apply_adjustments else _num(d.get("Bp"))
    )

    tws = _num(d.get("tws"))
    bws, lws = _web_plate_dims(col_geom, beam_d, tf, t_stiff) if tws > 0 else (0.0, 0.0)

    n_cantonera = int(_num(d.get("n_cantonera")))
    lh = _num(d.get("Lh")) if (n_cantonera > 0 and _num(d.get("Lh")) > 0) else (DEFAULT_HAUNCH_FACTOR * beam_d / math.sin(math.radians(DEFAULT_HAUNCH_ANGLE_DEG)) if n_cantonera > 0 else 0.0)

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
        "ThicknessName_t_webstiff": _mm_text(tws) if tws > 0 else "0mm",
        "Bws": bws,
        "Lws": lws,
        "b_ep": b_ep,
        "Lp": lp,
        "ThicknessName_t_ep": _mm_text(d.get("tp")),
        "Lh": lh,
        "AnguloCantonera": DEFAULT_HAUNCH_ANGLE_DEG if lh > 0 else 0.0,
        "dev": e,
        "p12_Outer": 0.0,
        "pfo": pfo,
        "pfi": pfi,
        "pb": p[2],
        "ThicknessName_t_compstiff": _mm_text(t_stiff) if t_stiff > 0 else "0mm",
        "ThicknessName_t_BeamHcompstiff": _mm_text(d.get("tbs")) if _num(d.get("tbs")) > 0 else "0mm",
        "ThicknessName_t_tenstiff": _mm_text(t_stiff) if t_stiff > 0 else "0mm",
        "wf": DEFAULT_WELD_MM,
        "ww": DEFAULT_WELD_MM,
        "w3": DEFAULT_WELD_MM,
        "w4": DEFAULT_WELD_MM,
        "wh": DEFAULT_WELD_MM,
        "FactorCantoCantonera": DEFAULT_HAUNCH_FACTOR if lh > 0 else 0.0,
        "ntensionrows": 3 if sum(1 for n in range(1, _n_years() + 1) if d.get("d", 0) <= sum(_num(d.get(f"p{k}")) for k in range(1, n + 1)) <= d.get("d", 0) + beam_d) >= 2 else 2,
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