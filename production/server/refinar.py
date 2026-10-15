"""Ajuste automatico de las placas tras la prediccion del modelo.

El modelo propone espesores que a veces no pasan la comprobacion AISC 360-10. Aqui se usa
el propio comprobador (`checker`) como oraculo: mientras algun ratio (sin contar soldaduras
ni tornillos) supere 1, se sube UN escalon del catalogo el espesor de la placa responsable
y se vuelve a comprobar. Asi se obtiene el espesor minimo que cumple.

  ratio que falla                                   -> variable que se sube
  ------------------------------------------------------------------------------------
  End plate (yield line / rotura) / cortante placa  -> tp   (espesor de la chapa frontal)
  Column flange / web crippling / rigid. transv.    -> tst  (= ts, rigidizadores del pilar)
  Column panel zone / Web doubler plate             -> tws  (placa del alma; recalcula Bws/Lws)
  Beam web yielding / Haunch web stiffeners         -> tbs  (rigidizador del alma de la viga)

No toca tornillos, geometria ni soldaduras (las define el usuario). Si una variable llega al
final del catalogo y el ratio sigue > 1, la fila se devuelve con lo conseguido y se avisa en el log.

Despues quita los elementos que sobran (rigidizadores / placa del alma con residuo <= 0) y
busca el mayor porcentaje de carga que la union aguanta (AI_MAXIMIZE_LOAD=0 lo desactiva).

Desactivar con la variable de entorno AI_AUTO_REFINE=0.
"""
import logging
import multiprocessing
import os
import threading
from concurrent.futures import ProcessPoolExecutor
from typing import Any, Dict, List, Optional, Tuple

import codame
from catalogo import get_profile
from checker import calcular_ratios_row, check_single_row

log = logging.getLogger("ai-server")

ENABLED = os.environ.get("AI_AUTO_REFINE", "1").strip().lower() not in ("0", "false", "no")
TARGET_RATIO = 1.0
MAX_STEPS = 50

# Catalogos de espesores (mm). Mantener alineados con los del modelo (core/config.py).
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


def _mm(v) -> int:
    try:
        return int(round(float(str(v).lower().replace("mm", "").strip() or 0)))
    except ValueError:
        return 0


def _next(catalog: List[int], value: int) -> Optional[int]:
    return next((c for c in catalog if c > value), None)


def _eval(row: Dict[str, Any]) -> Tuple[Dict[str, float], Any]:
    """(ratios {descripcion: valor}, calculador). Via rapida: sin el resultado completo."""
    return calcular_ratios_row(dict(row))


def _ratios(row: Dict[str, Any]) -> Dict[str, float]:
    return {k: float(v) for k, v in _eval(row)[0].items() if v is not None and v == v}


def _variable_for(ratio_name: str) -> Optional[str]:
    if "Weld" in ratio_name:
        return None
    for prefixes, var in _REMEDY:
        if ratio_name.startswith(prefixes):
            return var
    return None


def _apply(row: Dict[str, Any], var: str) -> Optional[str]:
    """Sube un escalon `var`. Devuelve la descripcion del cambio o None si no hay mas catalogo."""
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


# Elementos que SOBRAN cuando la demanda residual es <= 0 (el perfil solo ya aguanta):
#   atributo del calculador -> (nombre, columnas de espesor que se ponen a 0)
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
    """Pone a 0 los elementos con residuo <= 0, siempre que sin ellos no falle nada nuevo.

    `rs` y `res` son los ratios y residuos de `work`. Devuelve (quitados, ratios de la fila resultante).
    """
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
            work.clear(); work.update(prueba); rs = rs_p
            quitados.append(f"{nombre} quitados")
    return quitados, rs


# ---------------------------------------------------------------------------
# Maximizar la carga. Con la union ya definida (placas ajustadas) se suben las cargas por
# fases y se queda el mayor valor que respeta los limites:
#   1) cortante (FyEd): Bolts in Shear y Bolts in combined tension/shear
#   2) axil + momento (FxEd, MzEd, escalados juntos): tornillos a traccion, chapa frontal,
#      cortante de la chapa (flange tension force), ala de la columna y el combinado
# Cada ratio de esas familias puede llegar como mucho a RATIO_TOPE; si ya estaba por encima,
# no puede empeorar (en la practica su carga no sube). Los demas ratios (sin soldaduras) no
# pueden pasar de 1 ni empeorar si ya estaban por encima. La busqueda avanza a saltos (1, 2, 4...
# puntos) y afina por biseccion, calculando cada valor una sola vez.
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
    """Limites a partir de los ratios iniciales: (por familia, por ratio suelto)."""
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
    """Sube `keys` (porcentajes de carga, escalados juntos) hasta el mayor valor que cumple.

    Busqueda por saltos (1, 2, 4, 8... puntos) y despues biseccion entre el ultimo valor que
    cumple y el primero que falla; cada valor se calcula una sola vez. `rs` son los ratios de
    `work`. Devuelve (cambio | None, ratios de la fila resultante).
    """
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
    while ko is not None and ko - ok > 1:         # biseccion entre ok (cumple) y ko (falla)
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


def refine(row: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """Fila CODAME -> (fila ajustada, lista de cambios). Nunca lanza: ante un error devuelve la original.

    Cada comprobacion se hace una sola vez: los ratios de un paso se reutilizan en el siguiente.
    """
    uid = row.get("Unicode")
    changes: List[str] = []
    try:
        work = dict(row)
        blocked = set()
        rs, calc = _eval(work)
        res = _residuos(calc)
        for _ in range(MAX_STEPS):
            failing = {k: v for k, v in rs.items()
                       if v > TARGET_RATIO and _variable_for(k) and k not in blocked}
            if not failing:
                break
            worst = max(failing, key=failing.get)
            change = _apply(work, _variable_for(worst))
            if change is None:
                blocked.add(worst)
                log.warning("refinar %s: %s sigue en %.2f (sin mas catalogo)",
                            uid, worst, failing[worst])
                continue
            changes.append(change)
            rs, _calc = _eval(work)
        quitados, rs = _quitar_sobrantes(work, rs, res)
        changes += quitados
        if MAXIMIZE_LOAD:
            changes += _maximize_load(work, rs)
        if changes:
            log.info("refinar %s: %s", uid, _resumen(changes))
        return work, changes
    except Exception:  # noqa: BLE001
        log.exception("refinar fallo (UNICODE=%s); se deja la fila sin ajustar", uid)
        return row, []


# ---------------------------------------------------------------------------
# Paralelo. El calculo es Python puro (limitado por el GIL), asi que los hilos no
# acelerarian nada: se reparte una union por proceso. Variables de entorno:
#   AI_REFINE_WORKERS=N   procesos (por defecto: nucleos, maximo 8; 1 = sin paralelo)
# Con pocas filas se calcula en el propio proceso para no pagar el arranque del pool.
# ---------------------------------------------------------------------------
WORKERS = int(os.environ.get("AI_REFINE_WORKERS", "0") or 0) or min(8, os.cpu_count() or 1)
PARALLEL_MIN_ROWS = 4

_pool: Optional[ProcessPoolExecutor] = None
_pool_lock = threading.Lock()


def _init_worker() -> None:
    """Los procesos hijos no heredan el logging: escriben en el mismo archivo de sesion."""
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


def refine_and_check(row: Dict[str, Any], with_check: bool = True) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    """Ajusta una fila y, si se pide, devuelve ademas su comprobacion final (None si fallo)."""
    new, _ = refine(row)
    if not with_check:
        return new, None
    try:
        return new, check_single_row(dict(new))
    except Exception:  # noqa: BLE001  (el llamador la repite y deja constancia del error)
        return new, None


def _get_pool() -> ProcessPoolExecutor:
    global _pool
    with _pool_lock:
        if _pool is None:
            # "spawn": arranque limpio (el proceso principal ya tiene torch y varios hilos).
            _pool = ProcessPoolExecutor(
                max_workers=WORKERS, mp_context=multiprocessing.get_context("spawn"),
                initializer=_init_worker,
            )
        return _pool


def _reset_pool() -> None:
    global _pool
    with _pool_lock:
        if _pool is not None:
            _pool.shutdown(wait=False, cancel_futures=True)
            _pool = None


def refine_many(rows: List[Dict[str, Any]], with_check: bool = True):
    """[(fila ajustada, comprobacion | None)] en el mismo orden; en paralelo si compensa."""
    if not ENABLED:
        return [(r, None) for r in rows]
    if WORKERS > 1 and len(rows) >= PARALLEL_MIN_ROWS:
        try:
            flags = [with_check] * len(rows)
            return list(_get_pool().map(refine_and_check, rows, flags, chunksize=1))
        except Exception:  # noqa: BLE001  (pool roto, sin recursos...): se sigue en serie
            log.exception("refinar en paralelo fallo; se calcula en serie")
            _reset_pool()
    return [refine_and_check(r, with_check) for r in rows]