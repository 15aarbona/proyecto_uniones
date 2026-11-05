"""Ajuste automático de geometría y placas tras la predicción del modelo.

El modelo propone geometría y espesores que a veces no pasan la comprobación AISC 360-10.
Aquí se usa el propio comprobador (`checker`) como oráculo:

1. REAJUSTE GEOMÉTRICO ITERATIVO (`_ajustar_geometria`):
   Cada comprobación geométrica de `calcular_geometria` tiene un remedio asignado (`_FIXERS`).
   Se repite evaluar -> aplicar el remedio de cada comprobación que falla -> reevaluar hasta
   que todo da OK. Se prioriza mantener los valores predichos: solo se cambia lo imprescindible.
   Si la chapa no cabe con el tornillo actual, se baja el diámetro (mínimo BOLT_MIN).
   El patrón vertical de filas lo reconstruye `codame.ajustar_cantonera_y_chapa`.

2. REAJUSTE DE ESPESORES DE PLACAS Y TORNILLOS:
   Mientras algún ratio (sin contar soldaduras) supere 1, se aplica UN remedio y se vuelve a
   comprobar. Placas: se sube un escalón del catálogo (tp, tst, tws, tbs). Tornillos: según
   el ratio y el término que gobierna (dev, tp o diámetro). La clase de tornillo y el grado de
   acero los impone el cliente y NUNCA se tocan. Tras esta fase se repasa la geometría.

3. OPTIMIZACIÓN:
   Quita elementos sobrantes con demanda residual <= 0, compacta chapas desproporcionadas
   (vigas pequeñas con placas enormes) y busca el mayor porcentaje de carga.

Desactivar con la variable de entorno AI_AUTO_REFINE=0.
"""

import logging
import math
import multiprocessing
import os
import threading
import time
from concurrent.futures import ProcessPoolExecutor
from typing import Any, Dict, List, Optional, Tuple

import codame
import config
from calculador import CalculadorAISC36010
from catalogo import get_profile
from checker import calcular_ratios_row, check_single_row, row_to_conexion_input
from externos import tablapernos

log = logging.getLogger("ai-server")

ENABLED = os.environ.get("AI_AUTO_REFINE", "1").strip().lower() not in ("0", "false", "no")
TARGET_RATIO = 1.0
MAX_STEPS = 50

# Catálogos de espesores (mm). Mantener alineados con los del modelo (core/config.py).
CAT_TP = [12, 15, 20, 25, 30, 35, 40, 45, 50, 60]
CAT_TST = [0, 10, 12, 15, 20, 25, 30, 35, 40]          # ts = tst
CAT_TWS = [0, 6, 8, 10, 12, 15, 20]
CAT_TBS = [0, 10, 12, 15, 20, 25, 30, 35, 40]

# prefijo del ratio -> variable a subir
_REMEDY = (
    (("End plate", "Shear yielding", "Shear rupture"), "tp"),
    (("Column flange", "Column web crippling", "Transverse stiffeners"), "tst"),
    (("Column panel zone", "Web doubler"), "tws"),
    (("Beam web yielding", "Haunch web"), "tbs"),
)

# Ratios que se corrigen con remedios de tornillos (ver `_apply_bolt`)
_BOLT_RATIOS = ("Bolts in Tension", "Bolts in Shear", "Bolts in combined", "Slip Resistance")


def _mm(v) -> int:
    try:
        return int(round(float(str(v).lower().replace("mm", "").strip() or 0)))
    except ValueError:
        return 0


def _next(catalog: List[int], value: int) -> Optional[int]:
    return next((c for c in catalog if c > value), None)


def _eval(row: Dict[str, Any]) -> Tuple[Dict[str, float], Any]:
    """(ratios {descripción: valor}, calculador). Vía rápida: sin el resultado completo."""
    return calcular_ratios_row(dict(row))


def _ratios(row: Dict[str, Any]) -> Dict[str, float]:
    return {k: float(v) for k, v in _eval(row)[0].items() if v is not None and v == v}


def _variable_for(ratio_name: str) -> Optional[str]:
    if "Weld" in ratio_name:
        return None
    if ratio_name.startswith(_BOLT_RATIOS):
        return "bolt"
    for prefixes, var in _REMEDY:
        if ratio_name.startswith(prefixes):
            return var
    return None


def _apply(row: Dict[str, Any], var: str) -> Optional[str]:
    """Sube un escalón `var`. Devuelve la descripción del cambio o None si no hay más catálogo."""
    if var == "tp":
        old = _mm(row["ThicknessName_t_ep"]); new = _next(CAT_TP, old)
        if new is None:
            return None
        row["ThicknessName_t_ep"] = f"{new}mm"
    elif var == "tst":
        old = _mm(row["ThicknessName_t_tenstiff"]); new = _next(CAT_TST, old)
        if new is None:
            return None
        row["ThicknessName_t_tenstiff"] = row["ThicknessName_t_compstiff"] = f"{new}mm"
    elif var == "tws":
        old = _mm(row["ThicknessName_t_webstiff"]); new = _next(CAT_TWS, old)
        if new is None:
            return None
        row["ThicknessName_t_webstiff"] = f"{new}mm"
    elif var == "tbs":
        old = _mm(row["ThicknessName_t_BeamHcompstiff"]); new = _next(CAT_TBS, old)
        if new is None:
            return None
        row["ThicknessName_t_BeamHcompstiff"] = f"{new}mm"
    else:
        return None

    if var in ("tws", "tst"):   # Bws/Lws dependen de tws (y de los rigidizadores)
        _refresh_web_plate(row)
    return f"{var} {old}->{new}"


def _refresh_web_plate(row: Dict[str, Any]) -> None:
    if _mm(row["ThicknessName_t_webstiff"]) <= 0:
        row["Bws"], row["Lws"] = 0.0, 0.0
        return
    beam, col = get_profile(row["BEAM"]), get_profile(row["COLUMN"])
    row["Bws"], row["Lws"] = codame._web_plate_dims(
        col, codame._geom(beam, "d_mm"), codame._geom(beam, "tf_mm"), _mm(row["ThicknessName_t_tenstiff"])
    )


# ---------------------------------------------------------------------------
# Reescalado y ajuste geométrico iterativo
# ---------------------------------------------------------------------------
SEP_KEYS = ("pb", "p3", "p4", "p5", "p6", "p7", "p8", "p9", "p10", "p11", "p12")
CLAVES_GEO = ("p2_ep", "b_ep", "dev", "pfo", "pfi") + SEP_KEYS + ("FactorCantoCantonera", "BoltName_ep")
_FALLOS_PLACA = {"PRMIN", "PRMAX", "DEH_MIN", "DEH_MAX", "bep&bb", "bep&bepmin", "bep&bc"}
BOLT_MIN = "M16"   # si la chapa no cabe en el ala del pilar con M20, M16 es la única salida


def _n(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _c5(x: float) -> float:
    return math.ceil(round(x, 6) / 5.0) * 5.0


def _f5(x: float) -> float:
    return math.floor(round(x, 6) / 5.0) * 5.0


def _r5(x: float) -> float:
    return round(x / 5.0) * 5.0


def _cambiado(a, b) -> bool:
    try:
        return abs(float(a) - float(b)) > 1e-9
    except (TypeError, ValueError):
        return str(a) != str(b)


def _fmt(v) -> str:
    try:
        return f"{float(v):g}"
    except (TypeError, ValueError):
        return str(v)


def _evaluar_geometria(work: Dict[str, Any]):
    """(calculador ya ejecutado, {descripción: texto REVISAR}). El calculador trae los límites
    (MINedge, MAXedge, MINspacing, MAXspacing, c_, De_...) que NO están en ConexionInput."""
    calc = CalculadorAISC36010(inp=row_to_conexion_input(work))
    return calc, calc.calcular_geometria()


# --- placa: gramil p2_ep y ancho b_ep -------------------------------------
def _candidatos_g(pilar, g0: float) -> List[float]:
    """g válidos respecto a PRMIN/PRMAX: rejilla de 5 mm, extremos enteros y el g predicho si cabe."""
    lo = pilar.Prmin if pilar.Prmin > 0 else 5.0
    hi = pilar.Prmax if pilar.Prmax > 0 else pilar.b
    eps = 1e-9
    cands = {float(math.ceil(lo)), float(math.floor(hi))}
    g = _c5(lo)
    while g <= hi + eps:
        cands.add(g)
        g += 5.0
    if lo - eps <= g0 <= hi + eps:
        cands.add(g0)
    out = sorted(c for c in cands if lo - eps <= c <= hi + eps)
    return out or [round((lo + hi) / 2.0)]


def _placa_viable(viga, pilar, le: float, mx: float) -> bool:
    """¿Existe g y b_ep que cumplan PRMIN/PRMAX, DEH_MIN/MAX, bep&bb, bep&bepmin y bep&bc?"""
    bep_min = _c5(viga.b + 20.0)
    for g in _candidatos_g(pilar, 0.0):
        if max(viga.b, bep_min, g + 2.0 * le) <= min(pilar.b, g + 2.0 * mx):
            return True
    return False


def _max_perno_viable(work: Dict[str, Any], calc) -> Optional[int]:
    """Mayor diámetro del catálogo (>= BOLT_MIN) cuya chapa cabe entre viga y ala del pilar."""
    tp = _mm(work.get("ThicknessName_t_ep"))
    mx = min(12.0 * tp, 150.0) if tp > 0 else 150.0
    mejor = None
    for d in config.CATALOGO_BOLT:
        if d < int(BOLT_MIN[1:]):
            continue
        le = tablapernos.DATOS_PERNOS.get(d, {}).get("Le_min", 1.25 * d)
        if _placa_viable(calc.viga, calc.pilar, le, mx):
            mejor = d
    return mejor


def _limitar_tornillo(work: Dict[str, Any], calc) -> bool:
    """Baja el diámetro al mayor que permite una chapa viable (o a BOLT_MIN si ninguno lo permite)."""
    tope = _max_perno_viable(work, calc)
    if tope is None:
        tope = int(BOLT_MIN[1:])
    d = int(codame.diametro_tornillo(work.get("BoltName_ep")))
    if d <= tope:
        return False
    work["BoltName_ep"] = f"M{tope}"
    return True


def _ajustar_placa(work: Dict[str, Any], calc) -> bool:
    """g en [Prmin, Prmax] SIEMPRE. Devuelve True si además existe b_ep que cumpla todo;
    False si no (el llamador debe bajar el diámetro), pero g ya queda corregido."""
    pilar, viga = calc.pilar, calc.viga
    mn, mx = calc.MINedge, calc.MAXedge
    g0 = _n(work.get("p2_ep"), 100.0)
    b0 = _n(work.get("b_ep"), 200.0)
    bep_min = _c5(viga.b + 20.0)

    def rango(g):
        lo = max(viga.b, bep_min, g + 2.0 * mn)
        hi = min(pilar.b, g + 2.0 * mx)
        return lo, hi

    cands = _candidatos_g(pilar, g0)
    completos = [g for g in cands if rango(g)[0] <= rango(g)[1]]
    ok = bool(completos)
    if ok:
        g = min(completos, key=lambda v: abs(v - g0))
    else:                                   # el que menos viola; a igualdad, el más cercano al predicho
        g = min(cands, key=lambda v: (max(0.0, rango(v)[0] - rango(v)[1]), abs(v - g0)))

    lo, hi = rango(g)
    if ok:
        lo_r = _c5(lo) if _c5(lo) <= hi else math.ceil(lo)
        hi_r = _f5(hi) if _f5(hi) >= lo_r else math.floor(hi)
        b = min(max(b0, lo_r), hi_r)
        if b >= pilar.b or b <= viga.b:     # preferencia: estrictamente entre ambas alas
            b = min(max(_r5((viga.b + pilar.b) / 2.0), lo_r), hi_r)
    else:
        b = min(b0, _f5(hi))                # al menos ni pasar del pilar ni de DEH_MAX

    if _cambiado(g, g0):
        work["p2_ep"] = g
    if _cambiado(b, b0):
        work["b_ep"] = b
    return ok


# --- distancia al borde superior dev ---------------------------------------
def _ajustar_dev(work: Dict[str, Any], calc) -> None:
    dev = _n(work.get("dev"), 50.0)
    new = dev
    if dev < calc.MINedge:
        new = _c5(calc.MINedge)
    elif dev > calc.MAXedge:
        new = _f5(calc.MAXedge)
    if _cambiado(new, dev):
        work["dev"] = new


# --- separaciones entre filas ----------------------------------------------
def _ajustar_separaciones(work: Dict[str, Any], calc) -> None:
    """La 1ª separación entre filas es c = redondeo5(pfo + pfi + tf): se corrige con pfi.
    El resto (pb, p3..p12) se corrigen directamente."""
    mn, mx = calc.MINspacing, calc.MAXspacing
    for k in SEP_KEYS:
        v = _n(work.get(k))
        if 0.0 < v < mn:
            work[k] = _c5(mn)
        elif v > mx:
            work[k] = _f5(mx)

    c = calc.c_
    pfo, pfi, tf = _n(work.get("pfo"), 50.0), _n(work.get("pfi"), 30.0), calc.viga.tf
    if c < mn:
        nuevo = _c5(mn) - pfo - tf
        if nuevo > pfi:
            work["pfi"] = nuevo
    elif c > mx:
        nuevo = _f5(mx) - pfo - tf
        if nuevo > 0:
            work["pfi"] = nuevo


# --- colisiones de filas de tornillos con las caras de las alas ------------
def _margen(calc) -> float:
    digitos = "".join(ch for ch in str(calc.BoltName_ep) if ch.isdigit())
    return tablapernos.DATOS_PERNOS.get(int(digitos), {}).get("clearance", 0.0) if digitos else 0.0


# --- reconstrucción del patrón vertical: filas, cantonera, último tornillo, Lp ---
def _ajustar_cantonera(work: Dict[str, Any], calc) -> bool:
    """Reglas de `codame.ajustar_cantonera_y_chapa` con los límites reales del calculador."""
    lim = {"clearance": _margen(calc), "minsp": calc.MINspacing,
           "maxsp": calc.MAXspacing, "c": calc.c_}
    return codame.ajustar_cantonera_y_chapa(work, lim)


# --- último recurso: tornillo de menor diámetro ----------------------------
def _bajar_tornillo(work: Dict[str, Any]) -> bool:
    nombre = str(work.get("BoltName_ep") or "").strip().upper()
    if not nombre or nombre == BOLT_MIN:
        return False
    nuevo = str(tablapernos().NombreTornilloAnterior(nombre) or "").strip().upper()
    if not nuevo or nuevo == nombre:
        return False
    work["BoltName_ep"] = nuevo
    return True


def _actualizar_lp(work: Dict[str, Any], calc) -> None:
    """Lp (informativo en CODAME) = última fila de tornillos + db/2 + e, con las cotas finales."""
    if "Lp" not in work:
        return
    dev = _n(work.get("dev"))
    c = codame._redond5(_n(work.get("pfo")) + _n(work.get("pfi")) + calc.viga.tf)
    db = codame.diametro_tornillo(work.get("BoltName_ep"))
    y_ult = dev + c + sum(_n(work.get(k)) for k in SEP_KEYS)
    work["Lp"] = _c5(y_ult + db / 2.0 + dev)


# --- un remedio por comprobación geométrica ---------------------------------
def _fix_placa(work, calc):          # PRMIN, PRMAX, DEH_MIN, DEH_MAX, bep&bb, bep&bepmin, bep&bc
    _ajustar_placa(work, calc)


def _fix_dev(work, calc):            # DEV_MIN, DEV_MAX
    _ajustar_dev(work, calc)


def _fix_separaciones(work, calc):   # SPACING_MIN, SPACING_MAX
    _ajustar_separaciones(work, calc)
    _ajustar_cantonera(work, calc)


def _fix_filas(work, calc):          # los 6 ENTER_*: se reconstruye el patrón vertical
    _ajustar_cantonera(work, calc)


def _fix_ninguno(work, calc):        # bc&bb: viga más ancha que el ala del pilar, sin remedio geométrico
    pass


_FIXERS = {
    "bc&bb": _fix_ninguno,
    "PRMIN": _fix_placa, "PRMAX": _fix_placa, "DEH_MIN": _fix_placa, "DEH_MAX": _fix_placa,
    "bep&bb": _fix_placa, "bep&bepmin": _fix_placa, "bep&bc": _fix_placa,
    "DEV_MIN": _fix_dev, "DEV_MAX": _fix_dev,
    "SPACING_MIN": _fix_separaciones, "SPACING_MAX": _fix_separaciones,
    "ENTER_TOP_FLANGE_TOP": _fix_filas, "ENTER_TOP_FLANGE_LOW": _fix_filas,
    "ENTER_LOW_FLANGE_TOP": _fix_filas, "ENTER_LOW_FLANGE_LOW": _fix_filas,
    "ENTER_HAUNCH_FLANGE_TOP": _fix_filas, "ENTER_HAUNCH_FLANGE_LOW": _fix_filas,
}
_ORDEN_FALLOS = tuple(_FIXERS)   # placa -> dev -> separaciones -> filas (las filas van siempre al final)


def _ajustar_geometria(work: Dict[str, Any], max_iter: int = 40) -> List[str]:
    """Repite: evaluar -> aplicar el remedio de cada comprobación que falla -> reevaluar,
    hasta que todo esté OK, no haya más cambios posibles o se detecte una oscilación."""
    changes: List[str] = []
    vistos = set()
    calc, fallos = None, {}

    for _ in range(max_iter):
        calc, fallos = _evaluar_geometria(work)
        if not fallos:
            break
        estado = tuple(str(work.get(k)) for k in CLAVES_GEO)
        if estado in vistos:
            break
        vistos.add(estado)
        antes = dict(work)

        if not _limitar_tornillo(work, calc):          # chapa inviable con este tornillo -> se baja
            aplicados = []
            for key in _ORDEN_FALLOS:
                fix = _FIXERS[key]
                if key in fallos and fix not in aplicados:
                    fix(work, calc)
                    aplicados.append(fix)
            sin_cambio = not any(_cambiado(work.get(k), antes.get(k)) for k in CLAVES_GEO)
            if sin_cambio and (_FALLOS_PLACA & set(fallos)):
                _bajar_tornillo(work)                  # último recurso

        cambios_iter = [k for k in CLAVES_GEO if _cambiado(work.get(k), antes.get(k))]
        if not cambios_iter:
            break
        for k in cambios_iter:
            changes.append(f"{k} {_fmt(antes.get(k))}->{_fmt(work.get(k))}")
    else:
        calc, fallos = _evaluar_geometria(work)

    if fallos and calc is not None:
        log.warning("refinar %s: geometria sin resolver: %s", work.get("Unicode"), sorted(fallos))
    if changes and calc is not None:
        _actualizar_lp(work, calc)
    return changes


# ---------------------------------------------------------------------------
# Remedios de tornillos (la clase de tornillo y el acero los impone el cliente: no se tocan)
# ---------------------------------------------------------------------------
def _gobierna_cortante(calc) -> str:
    """Qué limita la resistencia por tornillo en 'Bolts in Shear':
    'tornillo' (Fnv*A), 'Vr1' (aplastamiento chapa), 'Vr2' (aplastamiento ala pilar),
    'Vr3' (desgarro por borde, depende de dev y tp) o 'Vr4' (entre filas, depende de c y tp)."""
    vmin = calc.VrminAME_
    if abs(vmin - calc.FnvAME_) <= 1e-9:
        return "tornillo"
    for nombre, v in (("Vr1", calc.Vr1_), ("Vr2", calc.Vr2_), ("Vr3", calc.Vr3_), ("Vr4", calc.Vr4_)):
        if abs(vmin - v) <= 1e-9:
            return nombre
    return "tornillo"


def _subir_diametro(work: Dict[str, Any]) -> Optional[List[str]]:
    """Sube un diámetro del catálogo (sin pasar de lo que cabe en el ala del pilar) y reajusta
    la geometría (los mínimos de borde, paso y holgura crecen con el diámetro). Si con el nuevo
    diámetro la geometría queda peor que antes (o el ajuste lo vuelve a bajar), se deshace y
    devuelve None."""
    d = int(codame.diametro_tornillo(work.get("BoltName_ep")))
    nuevo = next((c for c in config.CATALOGO_BOLT if c > d), None)
    if nuevo is None:
        return None
    calc, fallos_antes_dict = _evaluar_geometria(work)
    tope = _max_perno_viable(work, calc)
    if tope is None or nuevo > tope:
        return None
    antes = dict(work)
    fallos_antes = set(fallos_antes_dict)
    work["BoltName_ep"] = f"M{nuevo}"
    cambios = [f"BoltName_ep M{d}->M{nuevo}"] + _ajustar_geometria(work)
    if work.get("BoltName_ep") != f"M{nuevo}" or not set(_evaluar_geometria(work)[1]) <= fallos_antes:
        work.clear()
        work.update(antes)
        return None
    return cambios


def _apply_bolt(work: Dict[str, Any], ratio_name: str, calc) -> Optional[List[str]]:
    """Remedio para un ratio de tornillos. Devuelve la lista de cambios o None si no queda ninguno.
      - Slip Resistance: Tb solo depende del diámetro -> diámetro.
      - Bolts in Shear: según el término que gobierna (dev -> tp -> diámetro).
      - Bolts in Tension / combined: diámetro o subdivisión de vano si ya no se puede subir."""
    if ratio_name.startswith("Slip"):
        return _subir_diametro(work)

    if ratio_name.startswith("Bolts in Shear"):
        g = _gobierna_cortante(calc)
        if g == "Vr3":                                   # borde: primero dev, luego tp
            dev = _n(work.get("dev"), 50.0)
            if dev + 5.0 <= calc.MAXedge:
                work["dev"] = dev + 5.0
                _actualizar_lp(work, calc)
                return [f"dev {_fmt(dev)}->{_fmt(dev + 5.0)}"]
        if g in ("Vr1", "Vr3", "Vr4"):
            c = _apply(work, "tp")
            return [c] if c else _subir_diametro(work)
        return _subir_diametro(work)                     # 'Vr2' o cortante del propio tornillo

    # Tracción / Combinado (Bolts in Tension / Bolts in combined)
    res_diam = _subir_diametro(work)
    if res_diam is not None:
        return res_diam

    # Si ya no se puede subir el diámetro y sigue fallando por combinado/tracción:
    # subdividir el paso vertical libre más grande para meter una fila extra de pernos.
    min_sp = calc.MINspacing if (calc and hasattr(calc, "MINspacing") and calc.MINspacing > 0) else 60.0
    for k in ("pb", "p3", "p4", "p5"):
        val = _n(work.get(k))
        if val >= 2.0 * min_sp:
            nuevo_paso = _c5(val / 2.0)
            work[k] = nuevo_paso
            idx = 2 if k == "pb" else int(k.replace("p", ""))
            for i in range(12, idx, -1):
                prev_k = f"p{i-1}" if i > 3 else "pb"
                curr_k = f"p{i}"
                work[curr_k] = _n(work.get(prev_k))
            work[f"p{idx+1}"] = nuevo_paso
            _ajustar_geometria(work)
            return [f"Insertada fila intermedia en {k} ({_fmt(val)}->{_fmt(nuevo_paso)})"]

    return None


# Elementos que SOBRAN cuando la demanda residual es <= 0 (el perfil solo ya aguanta):
_SOBRANTES = (
    ("Ffts_", "rigidizadores transversales", ("ThicknessName_t_tenstiff", "ThicknessName_t_compstiff")),
    ("Vfdp_", "placa de refuerzo del alma", ("ThicknessName_t_webstiff",)),
    ("C1wsAME_", "rigidizadores de cartela", ("ThicknessName_t_BeamHcompstiff",)),
)


def _residuos(calc) -> Dict[str, float]:
    """Residuos del calculador (no dependen de los espesores, solo de perfiles y cargas)."""
    return {attr: float(getattr(calc, attr)) for attr, _, _ in _SOBRANTES}


def _fallan(rs: Dict[str, float]) -> set:
    return {k for k, v in rs.items() if _variable_for(k) and v > TARGET_RATIO}


def _quitar_sobrantes(work: Dict[str, Any], rs: Dict[str, float], res: Dict[str, float]):
    """Pone a 0 los elementos con residuo <= 0, siempre que sin ellos no falle nada nuevo."""
    quitados: List[str] = []
    presentes = [(a, n, c) for a, n, c in _SOBRANTES if any(_mm(work.get(x)) > 0 for x in c)]
    if not presentes:
        return quitados, rs
    candidatos = [(n, c) for a, n, c in presentes if res[a] <= 0]
    for nombre, cols in candidatos:
        prueba = dict(work)
        for c in cols:
            prueba[c] = "0mm"
        _refresh_web_plate(prueba)
        rs_p = _ratios(prueba)
        if _fallan(rs_p) <= _fallan(rs):
            work.clear()
            work.update(prueba)
            rs = rs_p
            quitados.append(f"{nombre} quitados")
    return quitados, rs


# ---------------------------------------------------------------------------
# Compactar chapas desproporcionadas (vigas pequeñas con placas enormes)
# ---------------------------------------------------------------------------
REALISTIC = os.environ.get("AI_REALISTIC_PLATE", "1").strip().lower() not in ("0", "false", "no")
PFO_MAX_DB = 2.5        # pfo <= 2.5*db     (M20 -> 50)
DEV_MAX_DB = 2.0        # dev <= 2.0*db     (M20 -> 40)
BEP_EXTRA_MAX = 50.0    # b_ep <= ancho ala viga + 50


def _topes_realistas(calc, work):
    db = codame.diametro_tornillo(work.get("BoltName_ep"))
    pfo_cap = max(_c5(PFO_MAX_DB * db), _c5(_margen(calc)))     # nunca por debajo de la holgura de herramienta
    dev_cap = max(_c5(DEV_MAX_DB * db), _c5(calc.MINedge))      # nunca por debajo del borde mínimo
    b_cap = _c5(calc.viga.b + BEP_EXTRA_MAX)
    return pfo_cap, dev_cap, b_cap


def _compactar_ancho(work, calc, b_cap):
    """Reduce b_ep (y mueve g lo mínimo) hasta b_cap, o hasta el mínimo geométrico si este es mayor."""
    pilar, viga = calc.pilar, calc.viga
    mn, mx = calc.MINedge, calc.MAXedge
    g0, b0 = _n(work.get("p2_ep"), 100.0), _n(work.get("b_ep"), 200.0)
    if b0 <= b_cap:
        return {}
    bep_min = _c5(viga.b + 20.0)
    viables = []
    for g in _candidatos_g(pilar, g0):
        lo = max(viga.b, bep_min, g + 2.0 * mn)
        hi = min(pilar.b, g + 2.0 * mx)
        if lo <= hi:
            viables.append((g, lo, hi))
    if not viables:
        return {}
    cabe = [m for m in viables if m[1] <= b_cap]
    g, lo, hi = min(cabe, key=lambda m: abs(m[0] - g0)) if cabe else min(viables, key=lambda m: m[1])
    lo_r = _c5(lo) if _c5(lo) <= hi else math.ceil(lo)
    hi_r = _f5(hi) if _f5(hi) >= lo_r else math.floor(hi)
    b = min(max(min(b0, b_cap), lo_r), hi_r)
    return {"p2_ep": g, "b_ep": b}


def _compactar_placa(work: Dict[str, Any], rs: Dict[str, float]):
    """Acerca la chapa a proporciones reales. Devuelve (cambios, ratios actualizados).
    Solo actúa sobre una geometría ya válida y no admite fallos nuevos de geometría ni de resistencia."""
    cambios: List[str] = []
    try:
        calc, fallos = _evaluar_geometria(work)
        if fallos:
            return cambios, rs
        pfo_cap, dev_cap, b_cap = _topes_realistas(calc, work)

        pasos = (
            ("pfo", lambda w, c: {"pfo": pfo_cap} if _n(w.get("pfo")) > pfo_cap + 1e-9 else {}),
            ("dev", lambda w, c: {"dev": dev_cap} if _n(w.get("dev")) > dev_cap + 1e-9 else {}),
            ("ancho", lambda w, c: _compactar_ancho(w, c, b_cap)),
        )
        for nombre, paso in pasos:
            calc, _ = _evaluar_geometria(work)
            cambio = paso(work, calc)
            if not cambio:
                continue
            prueba = dict(work)
            prueba.update(cambio)
            calc_p, _ = _evaluar_geometria(prueba)
            _ajustar_cantonera(prueba, calc_p)       # reconstruye filas y Lp con las nuevas cotas
            _ajustar_geometria(prueba)
            if _evaluar_geometria(prueba)[1]:        # la geometría no puede quedar peor
                continue
            rs_p = _ratios(prueba)
            if _fallan(rs_p) <= _fallan(rs):         # ni un fallo de resistencia nuevo
                for k in CLAVES_GEO:
                    if _cambiado(prueba.get(k), work.get(k)):
                        cambios.append(f"{k} {_fmt(work.get(k))}->{_fmt(prueba.get(k))} (compactar)")
                work.clear()
                work.update(prueba)
                rs = rs_p
    except Exception:  # noqa: BLE001
        log.exception("refinar: compactacion fallo; se deja la chapa como estaba")
    return cambios, rs


# ---------------------------------------------------------------------------
# Maximizar la carga
# ---------------------------------------------------------------------------
MAXIMIZE_LOAD = os.environ.get("AI_MAXIMIZE_LOAD", "1").strip().lower() not in ("0", "false", "no")
RATIO_TOPE = 0.85
LOAD_MAX_PCT = 100

_COMBINADO = "Bolts in combined"
_FAM_CORTANTE = ("Bolts in Shear", _COMBINADO)
_FAM_AXIL_MOMENTO = ("Bolts in Tension", "End plate", "Shear yielding", "Shear rupture",
                     "Column flange", _COMBINADO)


def _pct(v) -> int:
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return 0


def _limites(base: Dict[str, float], familias) -> Tuple[Dict[str, float], Dict[str, float]]:
    """Límites a partir de los ratios iniciales: (por familia, por ratio suelto)."""
    fam = {f: max(RATIO_TOPE, _fam_max(base, f)) for f in familias}
    resto = {k: max(1.0, v) for k, v in base.items()
             if "Weld" not in k and not k.startswith(tuple(familias))}
    return fam, resto


def _fam_max(rs: Dict[str, float], prefijo: str) -> float:
    return max([v for k, v in rs.items() if k.startswith(prefijo)] or [0.0])


def _cumple(rs: Dict[str, float], fam: Dict[str, float], resto: Dict[str, float]) -> bool:
    eps = 1e-9
    if any(_fam_max(rs, f) > lim + eps for f, lim in fam.items()):
        return False
    return all(v <= resto.get(k, 1.0) + eps for k, v in rs.items()
               if k in resto or ("Weld" not in k and not k.startswith(tuple(fam))))


def _subir(work: Dict[str, Any], keys, familias, rs: Dict[str, float]):
    """Sube `keys` (porcentajes de carga, escalados juntos) hasta el mayor valor que cumple."""
    ini = {k: _pct(work.get(k)) for k in keys}
    base = max(ini.values())
    if base <= 0 or base >= LOAD_MAX_PCT:
        return None, rs
    fam, resto = _limites(rs, familias)
    cache: Dict[int, Optional[Dict[str, float]]] = {}

    def probar(s: int) -> bool:
        if s not in cache:
            prueba = dict(work)
            prueba.update({k: min(LOAD_MAX_PCT, int(round(v * s / base))) for k, v in ini.items()})
            r = _ratios(prueba)
            cache[s] = r if _cumple(r, fam, resto) else None
        return cache[s] is not None

    ok, paso = base, 1
    ko = None
    while ok < LOAD_MAX_PCT:                      # fase de saltos
        s = min(LOAD_MAX_PCT, ok + paso)
        if probar(s):
            ok, paso = s, paso * 2
        else:
            ko = s
            break
    while ko is not None and ko - ok > 1:         # bisección entre ok (cumple) y ko (falla)
        mid = (ok + ko) // 2
        if probar(mid):
            ok = mid
        else:
            ko = mid
    if ok == base:
        return None, rs
    work.update({k: min(LOAD_MAX_PCT, int(round(v * ok / base))) for k, v in ini.items()})
    return ("/".join(str(ini[k]) for k in keys) + "->" + "/".join(str(_pct(work[k])) for k in keys)), cache[ok]


def _maximize_load(work: Dict[str, Any], rs: Dict[str, float]) -> List[str]:
    """Fase 1: cortante. Fase 2: axil + momento. Devuelve los cambios hechos."""
    out: List[str] = []
    c, rs = _subir(work, ("FyEd_Porcen",), _FAM_CORTANTE, rs)
    if c:
        out.append(f"cortante {c}")
    c, rs = _subir(work, ("MzEd_Porcen", "FxEd_Porcen"), _FAM_AXIL_MOMENTO, rs)
    if c:
        out.append(f"momento/axil {c}")
    return out


def _resumen(changes: List[str]) -> str:
    """Agrupa los cambios por variable: 'tp 12->15' + 'tp 15->20' -> 'tp 12->20'."""
    out: List[str] = []
    seen: Dict[str, int] = {}
    for c in changes:
        var, _, rng = c.partition(" ")
        if "->" in rng and var in seen and out[seen[var]].startswith(var + " "):
            ini = out[seen[var]].split(" ", 1)[1].split("->", 1)[0]
            out[seen[var]] = f"{var} {ini}->{rng.split('->', 1)[1]}"
        else:
            seen[var] = len(out)
            out.append(c)
    return " | ".join(out)


def refine(row: Dict[str, Any], maximize_load: Optional[bool] = None) -> Tuple[Dict[str, Any], List[str]]:
    """Fila CODAME -> (fila ajustada, lista de cambios). Nunca lanza: ante un error devuelve la original."""
    uid = row.get("Unicode")
    changes: List[str] = []
    try:
        work = dict(row)

        # 1. Corrección geométrica iterativa
        try:
            changes.extend(_ajustar_geometria(work))
        except Exception:  # noqa: BLE001
            log.exception("refinar %s: ajuste geometrico fallo; se sigue sin el", uid)

        # 2. Ajuste de espesores de placas y de tornillos (dev / tp / diametro)
        blocked = set()
        rs, calc = _eval(work)
        res = _residuos(calc)
        for _ in range(MAX_STEPS):
            failing = {k: v for k, v in rs.items()
                       if v > TARGET_RATIO and _variable_for(k) and k not in blocked}
            if not failing:
                break
            worst = max(failing, key=failing.get)
            var = _variable_for(worst)
            if var == "bolt":
                cambios = _apply_bolt(work, worst, calc)
            else:
                c = _apply(work, var)
                cambios = [c] if c else None
            if not cambios:
                blocked.add(worst)
                log.warning("refinar %s: %s sigue en %.2f (sin mas remedios)",
                            uid, worst, failing[worst])
                continue
            changes.extend(cambios)
            rs, calc = _eval(work)

        # Pase final de seguridad: los cambios de tp/tornillo pueden alterar MAXedge,
        # MAXspacing, MINedge... y dejar un fallo geométrico nuevo.
        try:
            changes.extend(_ajustar_geometria(work))
            rs, calc = _eval(work)
        except Exception:  # noqa: BLE001
            log.exception("refinar %s: pase final de geometria fallo", uid)

        # 3. Quitar sobrantes, compactar la chapa y maximizar cargas
        quitados, rs = _quitar_sobrantes(work, rs, res)
        changes += quitados
        if REALISTIC:
            compactados, rs = _compactar_placa(work, rs)
            changes += compactados
        if (MAXIMIZE_LOAD if maximize_load is None else maximize_load):
            changes += _maximize_load(work, rs)

        if changes:
            log.info("refinar %s: %s", uid, _resumen(changes))
        return work, changes
    except Exception:  # noqa: BLE001
        log.exception("refinar fallo (UNICODE=%s); se deja la fila sin ajustar", uid)
        return row, []


# ---------------------------------------------------------------------------
# Paralelismo
# ---------------------------------------------------------------------------
WORKERS = int(os.environ.get("AI_REFINE_WORKERS", "0") or 0) or min(8, os.cpu_count() or 1)
PARALLEL_MIN_ROWS = 4


def _init_worker() -> None:
    """Los procesos hijos no heredan el logging: escriben en el mismo archivo de sesión."""
    try:
        import config
        destino = os.environ.get("AI_LOG_FILE") or str(config.LOG_PATH)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
            handlers=[logging.FileHandler(destino, encoding="utf-8")],
        )
    except Exception:  # noqa: BLE001
        pass
    try:
        import catalogo
        catalogo.profile_lookup()
    except Exception:  # noqa: BLE001
        log.exception("refinar: no se pudo precargar el catalogo en el worker")


def refine_and_check(row: Dict[str, Any], with_check: bool = True,
                     maximize_load: Optional[bool] = None) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    """Ajusta una fila y, si se pide, devuelve además su comprobación final (None si falló)."""
    new, _ = refine(row, maximize_load)
    if not with_check:
        return new, None
    try:
        return new, check_single_row(dict(new))
    except Exception:  # noqa: BLE001
        return new, None


class RefineTimeout(TimeoutError):
    """El refinado paralelo superó AI_REFINE_TIMEOUT_S."""


class RefineBackend:
    name = "base"

    def start(self) -> None:
        pass

    def map_refine(self, rows: List[Dict[str, Any]], with_check: bool,
                   maximize_load: Optional[bool] = None):
        raise NotImplementedError

    def reset(self) -> None:
        pass

    def close(self) -> None:
        pass


class SerialBackend(RefineBackend):
    name = "serial"

    def map_refine(self, rows: List[Dict[str, Any]], with_check: bool,
                   maximize_load: Optional[bool] = None):
        return [refine_and_check(r, with_check, maximize_load) for r in rows]


class ProcessPoolBackend(RefineBackend):
    name = "process"

    def __init__(self) -> None:
        self._executor: Optional[ProcessPoolExecutor] = None
        self._lock = threading.RLock()

    def start(self) -> None:
        with self._lock:
            if self._executor is None:
                self._executor = ProcessPoolExecutor(
                    max_workers=WORKERS,
                    mp_context=multiprocessing.get_context("spawn"),
                    initializer=_init_worker,
                )
                log.info("refinar: pool de procesos iniciado (%d workers)", WORKERS)

    def _get(self) -> ProcessPoolExecutor:
        if self._executor is None:
            self.start()
        return self._executor

    def _drop(self) -> None:
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None

    def reset(self) -> None:
        with self._lock:
            self._drop()

    def _drop_if_current(self, executor: ProcessPoolExecutor) -> None:
        with self._lock:
            if self._executor is executor:
                self._drop()

    def map_refine(self, rows: List[Dict[str, Any]], with_check: bool,
                   maximize_load: Optional[bool] = None):
        if not rows:
            return []
        with self._lock:
            executor = self._get()
            futures = [
                executor.submit(refine_and_check, row, with_check, maximize_load)
                for row in rows
            ]
        rondas = math.ceil(len(rows) / max(1, WORKERS))
        timeout_s = max(1.0, config.REFINE_TIMEOUT_S) + max(0.0, config.REFINE_TIMEOUT_PER_ROW_S) * rondas
        deadline = time.monotonic() + timeout_s
        out = []
        try:
            for fut in futures:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError
                out.append(fut.result(timeout=remaining))
            return out
        except TimeoutError:
            pendientes = sum(1 for fut in futures if fut.cancel())
            log.error(
                "refinar: timeout de %.0fs para %d filas (%d sin empezar canceladas); pool conservado",
                timeout_s, len(rows), pendientes,
            )
            raise RefineTimeout(
                f"El refinado supero {timeout_s:.0f}s para {len(rows)} filas"
            )
        except Exception:
            for fut in futures:
                fut.cancel()
            self._drop_if_current(executor)
            raise

    def close(self) -> None:
        with self._lock:
            if self._executor is not None:
                log.info("refinar: cerrando pool de procesos")
                self._executor.shutdown(wait=True, cancel_futures=True)
                self._executor = None


_BACKEND: Optional[RefineBackend] = None
_BACKEND_LOCK = threading.Lock()


def _make_backend() -> RefineBackend:
    kind = (config.REFINE_BACKEND or "process").lower()
    if kind == "serial":
        return SerialBackend()
    if kind == "process":
        return ProcessPoolBackend()
    log.warning("AI_REFINE_BACKEND=%s no soportado; se usa 'process'", kind)
    return ProcessPoolBackend()


def get_backend() -> RefineBackend:
    global _BACKEND
    with _BACKEND_LOCK:
        if _BACKEND is None:
            _BACKEND = _make_backend()
        return _BACKEND


def start_backend() -> None:
    get_backend().start()


def shutdown_backend() -> None:
    global _BACKEND
    with _BACKEND_LOCK:
        if _BACKEND is not None:
            try:
                _BACKEND.close()
            finally:
                _BACKEND = None


def refine_many(
    rows: List[Dict[str, Any]],
    with_check: bool = True,
    maximize_load: Optional[bool] = None,
):
    if not ENABLED:
        return [(r, None) for r in rows]
    if not rows:
        return []

    backend = get_backend()
    if backend.name == "process" and (WORKERS <= 1 or len(rows) < PARALLEL_MIN_ROWS):
        return [refine_and_check(r, with_check, maximize_load) for r in rows]

    try:
        return backend.map_refine(rows, with_check, maximize_load)
    except RefineTimeout:
        raise
    except Exception:  # noqa: BLE001
        log.exception("refinar en %s fallo; se calcula en serie", backend.name)
        backend.reset()
        return [refine_and_check(r, with_check, maximize_load) for r in rows]