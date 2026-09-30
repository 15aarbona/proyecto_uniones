"""
Descomposición geométrica de p1..p12 en variables con significado fijo, en vez de huecos
posicionales cuyo significado cambia según la topología:

    E-S    : hueco fila 1 -> fila 2 (extensión superior)          = antiguo p1
    D_1..5 : huecos interiores entre la fila 2 y la fila que       = antiguos D_1..D_5,
             contiene el ala inferior de la viga                    ya derivados en v1/v2
    I-C    : hueco que contiene el ala inferior de la viga         = antiguo I-C
    C_1..5 : huecos interiores DENTRO de la cantonera, entre I-C   = NUEVO. Antes se
             y el último hueco                                       perdían (v1: solo se
                                                                       guardaba el último)
    E-C    : último hueco (extensión inferior / cantonera)         = antiguo E-C

No existe columna C_i real en train/test.parquet (es un concepto nuevo), así que los
objetivos de entrenamiento de TODAS estas variables se derivan aquí mismo a partir de
p1..p12 + e + d + BEAM_d_mm, con la misma lógica que ya usaba derive_dependent_columns.
Esto no añade información nueva: es una reparametrización, pensada para que cada variable
tenga una única semántica y deje de ser multimodal.

gaps_from_p       : p1..p12 (+ e, d, BEAM_d_mm) -> E-S, D_1..5, I-C, C_1..5, E-C   (para targets)
assemble_from_named: E-S, D_1..5, I-C, C_1..5, E-C (+ Bolt) -> Hole, num_filas_tornillos,
                      tiene_cantonera                                              (para postproceso)
p_from_named      : reconstruye p1..p12 desde las variables nombradas (solo para
                      comparar contra el p real y para exportar a sistemas que aún
                      esperen p1..p12; el modelo YA NO necesita predecir p)
check_reversibility: gaps_from_p seguido de p_from_named debe devolver el p original.
                      Es la prueba de que la descomposición no pierde información.
"""

import numpy as np
import pandas as pd

from .config import P_COLUMNS, MAX_D, MAX_C, D_COLUMNS, C_COLUMNS, GEOM_COLUMNS


def _gaps_row(pasos, e, d, h_beam):
    res = {"E-S": np.nan, "I-C": np.nan, "E-C": np.nan, "tiene_cantonera": False}
    res.update({c: np.nan for c in D_COLUMNS})
    res.update({c: np.nan for c in C_COLUMNS})
    if len(pasos) < 1:
        return res

    Y = [e]
    for p in pasos:
        Y.append(Y[-1] + p)
    y_ala_inf = e + d + h_beam

    idx_IC = None
    for k in range(1, len(Y)):
        if Y[k - 1] <= y_ala_inf <= Y[k]:
            idx_IC = k - 1
            break

    res["E-S"] = pasos[0]
    if idx_IC is not None:
        # Caso borde (vigas poco profundas): el ala inferior cae ya en el PRIMER hueco, así
        # que I-C coincidiría con E-S (mismo hueco físico). No se etiqueta dos veces -- si no,
        # ese hueco se contaría el doble en num_filas_tornillos y en la reconstrucción de p.
        if idx_IC > 0:
            res["I-C"] = pasos[idx_IC]
        for i, val in enumerate(pasos[1:idx_IC][:MAX_D], start=1):
            res[f"D_{i}"] = val
        tail = pasos[idx_IC + 1 :]
        if len(tail) >= 1:
            res["tiene_cantonera"] = True
            res["E-C"] = tail[-1]
            for i, val in enumerate(tail[:-1][:MAX_C], start=1):
                res[f"C_{i}"] = val
    else:
        # Ala inferior más allá de la última fila modelada (placa corta / input inconsistente):
        # no hay I-C ni cantonera; se listan como D_i todos los huecos restantes (limitación
        # heredada: se pierden si superan MAX_D, igual que antes con D_1..D_5).
        for i, val in enumerate(pasos[1:][:MAX_D], start=1):
            res[f"D_{i}"] = val

    return res


def gaps_from_p(df: pd.DataFrame) -> pd.DataFrame:
    """df con p1..p12, e, d, BEAM_d_mm -> DataFrame con GEOM_COLUMNS + tiene_cantonera."""

    def _row(row):
        pasos = [row[c] for c in P_COLUMNS if pd.notna(row[c]) and row[c] > 0]
        return pd.Series(_gaps_row(pasos, row["e"], row["d"], row["BEAM_d_mm"]))

    return df.apply(_row, axis=1)


def assemble_from_named(named: pd.DataFrame, bolt_nominal_mm) -> pd.DataFrame:
    """
    named: DataFrame con GEOM_COLUMNS (predichos o reales, 0/NaN = no existe).
    Recalcula, sin volver a tocar p1..p12: Hole, num_filas_tornillos, tiene_cantonera.
    num_filas_tornillos = 1 (fila inicial) + nº de huecos activos (cada hueco activo añade
    una fila), igual que antes con len(pasos)+FILAS_OFFSET, pero contado sobre las variables
    nombradas en vez de sobre p.
    """
    active = named[GEOM_COLUMNS].fillna(0.0) > 0
    n_huecos = active.sum(axis=1)
    out = pd.DataFrame(
        {
            "Hole": np.asarray(bolt_nominal_mm) + 2,
            "num_filas_tornillos": (1 + n_huecos).values,
            "tiene_cantonera": (active[C_COLUMNS].any(axis=1) | active["E-C"]).values,
        },
        index=named.index,
    )
    return out


def p_from_named(named: pd.DataFrame) -> pd.DataFrame:
    """
    Reconstruye p1..p12 concatenando, por fila, los huecos activos en orden:
    E-S, D_1..D_5 (activos), I-C, C_1..C_5 (activos), E-C. Solo para comparar contra el
    p real (evaluación) o exportar a un sistema aguas abajo que todavía espere p1..p12;
    el modelo no necesita esto para predecir.
    """
    order = ["E-S"] + D_COLUMNS + ["I-C"] + C_COLUMNS + ["E-C"]
    out = np.zeros((len(named), len(P_COLUMNS)))
    vals = named[order].fillna(0.0).values
    for i in range(len(named)):
        row = vals[i]
        activos = row[row > 0]
        out[i, : min(len(activos), len(P_COLUMNS))] = activos[: len(P_COLUMNS)]
    return pd.DataFrame(out, columns=P_COLUMNS, index=named.index)


def check_reversibility(df: pd.DataFrame, tol=1e-6) -> dict:
    """
    Prueba de que la descomposición no pierde información: gaps_from_p + p_from_named
    debe devolver el p1..p12 original. Si no coincide, o bien hay más de MAX_D/MAX_C
    huecos en algún tramo (truncamiento) o hay un caso "idx_IC is None" sin cantonera.
    """
    named = gaps_from_p(df)
    p_true = df[P_COLUMNS].fillna(0.0).values
    p_rec = p_from_named(named).values
    ok = np.all(np.abs(p_true - p_rec) <= tol, axis=1)
    n_pasos = (df[P_COLUMNS].fillna(0.0) > 0).sum(axis=1)
    print(
        f"Reconstrucción p exacta: {100 * ok.mean():.1f}% de las filas "
        f"({(~ok).sum()} de {len(df)} no coinciden)"
    )
    if (~ok).any():
        print(
            "  nº de pasos en las filas que fallan (sospecha: > MAX_D+MAX_C+3 huecos, "
            f"o ala inferior fuera de rango):\n{n_pasos[~ok].value_counts().sort_index().to_string()}"
        )
    return {"frac_exacto": float(ok.mean()), "n_fallos": int((~ok).sum())}
