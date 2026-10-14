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

Desactivar con la variable de entorno AI_AUTO_REFINE=0.
"""
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import codame
from catalogo import get_profile
from checker import check_single_row

log = logging.getLogger("ai-server")

ENABLED = os.environ.get("AI_AUTO_REFINE", "1").strip().lower() not in ("0", "false", "no")
TARGET_RATIO = 1.0
MAX_STEPS = 20

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


def _ratios(row: Dict[str, Any]) -> Dict[str, float]:
    res = check_single_row(dict(row))
    out = {}
    for f in res["ratios"]:
        v = f.get("ratio")
        if v is not None and v == v:
            out[str(f["descripcion"]).strip()] = float(v)
    return out


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


def refine(row: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """Fila CODAME -> (fila ajustada, lista de cambios). Nunca lanza: ante un error devuelve la original."""
    uid = row.get("Unicode")
    changes: List[str] = []
    try:
        work = dict(row)
        blocked = set()
        for _ in range(MAX_STEPS):
            failing = {k: v for k, v in _ratios(work).items()
                       if v > TARGET_RATIO and _variable_for(k) and k not in blocked}
            if not failing:
                break
            worst = max(failing, key=failing.get)
            change = _apply(work, _variable_for(worst))
            if change is None:
                blocked.add(worst)
                log.warning("refinar: %s sigue en %.2f y no hay mas catalogo (UNICODE=%s)",
                            worst, failing[worst], uid)
                continue
            changes.append(change)
        if changes:
            log.info("refinar (UNICODE=%s): %s", uid, ", ".join(changes))
        return work, changes
    except Exception:  # noqa: BLE001
        log.exception("refinar fallo (UNICODE=%s); se deja la fila sin ajustar", uid)
        return row, []