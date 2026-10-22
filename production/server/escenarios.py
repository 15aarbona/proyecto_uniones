"""Escenarios de carga: de una fila de entrada a 3 diseños de referencia.

Flujo:
  1. Se predice la fila tal cual llega (paso 0): modelo -> CODAME -> ajuste -> comprobacion.
  2. Se suben las cargas (ratio_moment, ratio_shear, ratio_axial) un `incremento` (5 %) y se
     vuelve a predecir, paso a paso (k = 1, 2, 3 ...), hasta que el diseno deja de cumplir.
     Ninguna carga supera el 100 % (1.0): se topan y, cuando todas llegan al tope, se para.
  3. Del historial se extraen 3 disenos (todos deben CUMPLIR la comprobacion AISC):
       E1  mayor carga SIN cantonera   (Lh == 0 y n_cantonera == 0)
       E2  primer diseno CON cantonera (el de menor carga)
       E3  mayor carga CON cantonera

Sobre el ajuste: en este flujo NO se maximiza la carga (`maximize_load=False`), porque
`refinar._maximize_load` reescribe MzEd_Porcen/FyEd_Porcen/FxEd_Porcen y falsearia el
escalon de carga que se esta evaluando. Si se ajustan geometria y espesores.

Este modulo no depende del modelo ni del servidor: recibe `predict_fn` (inyeccion), por lo
que se puede probar sin pesos. `run()` lo conecta con `predictor.predict_detailed`.
"""
from __future__ import annotations

import logging
import math
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger("ai-server")

LOAD_KEYS = ("ratio_moment", "ratio_shear", "ratio_axial")

# Maximos de carga vistos en el dataset de entrenamiento (datos_modelo.parquet).
# Por encima el modelo extrapola: el escenario se marca `fuera_rango_entrenamiento`.
RANGO_ENTRENAMIENTO = {"ratio_moment": 1.21, "ratio_shear": 1.0, "ratio_axial": 0.49}

CARGA_MAX = 1.0            # las cargas nunca pasan del 100 %
INCREMENTO = 0.05          # +5 % por paso
MAX_PASOS = 40             # 1.05**40 ~ x7
MAX_FALLOS_SEGUIDOS = 3    # pasos seguidos que no cumplen antes de parar (x2 si aun no hay cantonera valida)
LOTE = 8                   # pasos que se predicen a la vez (en paralelo en el pool de refinar)

NOMBRES = {
    "E1": "Mayor carga sin cantonera",
    "E2": "Primer diseño con cantonera",
    "E3": "Mayor carga con cantonera",
}


def _num(v, default=0.0) -> float:
    try:
        f = float(v)
        return default if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return default


def _find_key(row: Dict[str, Any], name: str) -> Optional[str]:
    for k in row:
        if str(k).strip().lower() == name.lower():
            return k
    return None


def _cargas_base(row: Dict[str, Any]) -> Dict[str, float]:
    """{clave_real_en_la_fila: valor} de las 3 cargas. ratio_moment es obligatorio."""
    out: Dict[str, float] = {}
    for name in LOAD_KEYS:
        key = _find_key(row, name)
        if key is None or row[key] is None or str(row[key]).strip() == "":
            if name == "ratio_moment":
                raise ValueError("Falta ratio_moment: es necesario para generar los escenarios de carga")
            continue
        out[key] = _num(str(row[key]).replace(",", "."))
    if not any(v > 0 for v in out.values()):
        raise ValueError("Todas las cargas son 0: no hay nada que aumentar")
    return out


def _fila_paso(row: Dict[str, Any], base: Dict[str, float], k: int, incremento: float, compuesto: bool):
    """Fila de entrada del paso k. Cargas = base * f, redondeadas a 2 decimales (1 % de
    resolucion, la misma que usa CODAME en `_pct_int`) y TOPADAS en 1.0 (100 %).
    Devuelve (fila, factor efectivo sobre ratio_moment)."""
    f = (1.0 + incremento) ** k if compuesto else 1.0 + incremento * k
    new = dict(row)
    for key, v in base.items():
        new[key] = round(min(1.0, v * f), 2)
    ukey = _find_key(row, "unicode") or "UNICODE"
    new[ukey] = f"{row.get(ukey, 'UNI')}_E{k:02d}"
    mkey = _find_key(row, "ratio_moment")
    f_ef = new[mkey] / base[mkey] if base.get(mkey, 0) > 0 else f
    return new, f_ef


def _filas_tornillos(row: Dict[str, Any]) -> int:
    seps = [row.get("pfi"), row.get("pb")] + [row.get(f"p{i}") for i in range(3, 13)]
    return sum(1 for s in seps if _num(s) > 0) + 1


def _registro(k: int, factor: float, entrada: Dict[str, Any], res: Dict[str, Any]) -> Dict[str, Any]:
    row = res.get("row") or {}
    chk = res.get("check") or {}
    lh = _num(row.get("Lh"))
    ncan = int(_num(res.get("n_cantonera")))
    cargas = {n: _num(entrada.get(_find_key(entrada, n))) for n in LOAD_KEYS}
    fuera = [n for n, lim in RANGO_ENTRENAMIENTO.items() if cargas.get(n, 0.0) > lim + 1e-9]
    return {
        "paso": k,
        "factor_carga": round(factor, 4),
        "ratio_moment": cargas["ratio_moment"],
        "ratio_shear": cargas["ratio_shear"],
        "ratio_axial": cargas["ratio_axial"],
        "cumple": bool(chk.get("cumple")),
        "ratio_pesimo": chk.get("ratio_pesimo"),
        "descripcion_ratio_pesimo": chk.get("descripcion_ratio_pesimo"),
        "Lh": lh,
        "n_cantonera": ncan,
        "con_cantonera": lh > 0 or ncan > 0,
        "fuera_rango_entrenamiento": fuera,
        "_res": res,            # fila CODAME + check completos (se quitan del historial publico)
    }


def seleccionar(historial: List[Dict[str, Any]]) -> Dict[str, Optional[Dict[str, Any]]]:
    """E1/E2/E3 a partir de los pasos que CUMPLEN."""
    ok = [r for r in historial if r["cumple"]]
    sin = [r for r in ok if not r["con_cantonera"]]
    con = [r for r in ok if r["con_cantonera"]]
    return {
        "E1": max(sin, key=lambda r: r["paso"]) if sin else None,
        "E2": min(con, key=lambda r: r["paso"]) if con else None,
        "E3": max(con, key=lambda r: r["paso"]) if con else None,
    }


def _motivo(clave: str, historial: List[Dict[str, Any]]) -> str:
    ok = [r for r in historial if r["cumple"]]
    if not ok:
        return "Ningun paso (ni el de partida) cumple la comprobacion AISC."
    if clave == "E1":
        return "El diseno de partida ya lleva cantonera, o no hay ningun diseno sin cantonera que cumpla."
    return "Ningun diseno con cantonera cumple en el rango de cargas explorado."


def generar_escenarios(
    row: Dict[str, Any],
    predict_fn: Callable[[List[Dict[str, Any]]], List[Dict[str, Any]]],
    incremento: float = INCREMENTO,
    max_pasos: int = MAX_PASOS,
    max_fallos_seguidos: int = MAX_FALLOS_SEGUIDOS,
    lote: int = LOTE,
    compuesto: bool = True,
) -> Dict[str, Any]:
    """`predict_fn(filas_entrada) -> [{"row", "check", "n_cantonera"}]` (mismo orden)."""
    if incremento <= 0:
        raise ValueError("incremento debe ser > 0")
    base = _cargas_base(row)
    avisos: List[str] = []
    if any(v > CARGA_MAX for v in base.values()):
        avisos.append("Alguna carga de entrada superaba el 100 %: se ha limitado al 100 %.")
        base = {k_: min(CARGA_MAX, v) for k_, v in base.items()}
    historial: List[Dict[str, Any]] = []
    fallos, hay_cantonera_valida, parada = 0, False, None
    previas, techo, k = None, False, 0
    while parada is None and not techo and k <= max_pasos:
        pasos, entradas, factores = [], [], []
        for kk in range(k, min(k + max(1, lote), max_pasos + 1)):
            ent, f = _fila_paso(row, base, kk, incremento, compuesto)
            cargas = tuple(ent[key] for key in base)
            if cargas == previas:          # todas las cargas ya estan al 100 %: no hay mas escalones
                techo = True
                break
            previas = cargas
            pasos.append(kk); entradas.append(ent); factores.append(f)
        if entradas:
            resultados = predict_fn(entradas)
            for kk, ent, f, res in zip(pasos, entradas, factores, resultados):
                reg = _registro(kk, f, ent, res)
                historial.append(reg)
                if reg["cumple"]:
                    fallos = 0
                    hay_cantonera_valida = hay_cantonera_valida or reg["con_cantonera"]
                else:
                    fallos += 1
                tolerancia = max_fallos_seguidos * (1 if hay_cantonera_valida else 2)
                if fallos >= tolerancia:
                    parada = f"{fallos} pasos seguidos sin cumplir (paso {kk})"
                    break
        k += max(1, lote)
    if parada is None:
        parada = "cargas al 100 %" if techo else f"alcanzado max_pasos={max_pasos}"

    elegidos = seleccionar(historial)
    if historial and not historial[0]["cumple"]:
        avisos.append("El diseno con las cargas de partida (paso 0) NO cumple la comprobacion.")
    escenarios, rows, checks, rows_raw = [], [], [], []
    for clave in ("E1", "E2", "E3"):
        r = elegidos[clave]
        if r is None:
            escenarios.append({"id": clave, "escenario": NOMBRES[clave], "encontrado": False,
                               "motivo": _motivo(clave, historial)})
            continue
        res = r["_res"]
        etiqueta = f"{clave} - {NOMBRES[clave]}"
        if r["fuera_rango_entrenamiento"]:
            avisos.append(f"{clave}: cargas fuera del rango de entrenamiento "
                          f"({', '.join(r['fuera_rango_entrenamiento'])}); el modelo extrapola.")
        escenarios.append({
            "id": clave, "escenario": NOMBRES[clave], "encontrado": True,
            **{x: r[x] for x in ("paso", "factor_carga", "ratio_moment", "ratio_shear", "ratio_axial",
                                 "cumple", "ratio_pesimo", "descripcion_ratio_pesimo", "Lh",
                                 "n_cantonera", "fuera_rango_entrenamiento")},
            "row": res.get("row"),                      # solo para la tabla (se quita abajo)
        })
        # Mismas estructuras y nombres que devolvia /predict, con la clave "Escenario" anadida.
        rows.append({**(res.get("row") or {}), "Escenario": etiqueta})
        checks.append({**(res.get("check") or {}), "Escenario": etiqueta})
        rows_raw.append({**(res.get("raw") or {}), "Escenario": etiqueta})
    if elegidos["E2"] is not None and elegidos["E2"] is elegidos["E3"]:
        avisos.append("E2 y E3 coinciden: solo un paso cumple con cantonera.")

    tabla = [_fila_tabla(e) for e in escenarios]
    return {
        # --- igual que /predict (model_name lo anade el servidor) ---
        "rows": rows,
        "checks": checks,
        "rows_raw": rows_raw,
        # --- escenarios ---
        "escenarios": [{k_: v for k_, v in e.items() if k_ != "row"} for e in escenarios],
        "tabla": tabla,
        "tabla_markdown": tabla_markdown(tabla),
        "historial": [{k_: v for k_, v in r.items() if k_ != "_res"} for r in historial],
        "parada": parada,
        "avisos": avisos,
        "parametros": {"incremento": incremento, "compuesto": compuesto, "max_pasos": max_pasos,
                       "max_fallos_seguidos": max_fallos_seguidos, "carga_max": CARGA_MAX},
    }


# ---------------------------------------------------------------------------
# Tabla
# ---------------------------------------------------------------------------
TABLA_COLUMNAS = [
    "Escenario", "Paso", "Factor carga", "Mz %", "Fy %", "Fx %", "Cumple", "Ratio pésimo",
    "Cantonera (Lh mm)", "n_cantonera", "Viga", "Pilar", "Tornillo", "Clase", "tp (placa)",
    "g", "b_ep", "Lp", "Filas tornillos", "Rig. col.", "Placa alma", "Rig. cartela", "Fuera de rango",
]


def _fila_tabla(e: Dict[str, Any]) -> Dict[str, Any]:
    out = {c: None for c in TABLA_COLUMNAS}
    out["Escenario"] = f"{e['id']} - {e['escenario']}"
    if not e["encontrado"]:
        out["Cumple"] = "No encontrado"
        out["Ratio pésimo"] = e.get("motivo")
        return out
    r = e["row"] or {}
    pct = lambda v: int(round(_num(v) * 100))  # noqa: E731
    out.update({
        "Paso": e["paso"], "Factor carga": e["factor_carga"],
        "Mz %": pct(e["ratio_moment"]), "Fy %": pct(e["ratio_shear"]), "Fx %": pct(e["ratio_axial"]),
        "Cumple": "Sí" if e["cumple"] else "No",
        "Ratio pésimo": f"{_num(e['ratio_pesimo']):.2f} ({str(e['descripcion_ratio_pesimo']).strip()})",
        "Cantonera (Lh mm)": round(e["Lh"], 1), "n_cantonera": e["n_cantonera"],
        "Viga": r.get("BEAM"), "Pilar": r.get("COLUMN"), "Tornillo": r.get("BoltName_ep"),
        "Clase": r.get("BoltGrade"), "tp (placa)": r.get("ThicknessName_t_ep"),
        "g": r.get("p2_ep"), "b_ep": r.get("b_ep"), "Lp": r.get("Lp"),
        "Filas tornillos": _filas_tornillos(r),
        "Rig. col.": r.get("ThicknessName_t_tenstiff"), "Placa alma": r.get("ThicknessName_t_webstiff"),
        "Rig. cartela": r.get("ThicknessName_t_BeamHcompstiff"),
        "Fuera de rango": ", ".join(e["fuera_rango_entrenamiento"]) or "No",
    })
    return out


def tabla_markdown(tabla: List[Dict[str, Any]]) -> str:
    def cel(v):
        return "" if v is None else str(v).replace("|", "/")
    lineas = ["| " + " | ".join(TABLA_COLUMNAS) + " |", "|" + "---|" * len(TABLA_COLUMNAS)]
    lineas += ["| " + " | ".join(cel(f[c]) for c in TABLA_COLUMNAS) + " |" for f in tabla]
    return "\n".join(lineas)


# ---------------------------------------------------------------------------
# Conexion con el servidor
# ---------------------------------------------------------------------------
def run(model_name: str, row: Dict[str, Any], **opciones) -> Dict[str, Any]:
    """Escenarios con el modelo real (usa `predictor.predict_detailed`, sin maximizar carga)."""
    import predictor

    def predict_fn(filas):
        return predictor.predict_detailed(model_name, filas, maximize_load=False)

    return generar_escenarios(row, predict_fn, **opciones)