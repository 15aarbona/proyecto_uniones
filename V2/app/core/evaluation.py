"""
Evaluación de predicciones (v3, geometría con nombre en vez de p1..p12).
  - evaluar_predicciones   : tu función (misma tabla), ahora enmascara TODAS las
                             MASKED_COLUMNS (geometría + rigidizadores), no solo p_*.
  - preparar_para_evaluar  : adapta (test_df, full_design) a lo que espera evaluar_predicciones;
                             la verdad de la geometría se deriva de p1..p12 con
                             geometry.gaps_from_p (no existe columna C_i real).
  - evaluar_estructura     : acierto de num_filas_tornillos y tiene_cantonera, y presencia
                             por columna (lo que el MAE por columna no ve).
  - error_geom_por_canto   : error de la geometría según el canto de la viga.
  - diagnostico_geometria  : ¿Lp = 2e + Σp y Σp = h + 2d en el dataset? (sobre p1..p12 crudo).
  - verificar_reversibilidad: gaps_from_p + p_from_named debe reproducir el p real -- confirma
                             que pasar a E-S/D_i/I-C/C_i/E-C no pierde información.
"""
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from .config import REGRESSION_ALWAYS, MASKED_COLUMNS, GEOM_COLUMNS, STIFFENER_COLUMNS, P_COLUMNS
from .geometry import gaps_from_p, check_reversibility


def _ensure_geometry(df):
    if "E-S" in df.columns:
        return df
    df = df.copy()
    geom = gaps_from_p(df)
    for c in geom.columns:
        df[c] = geom[c]
    return df


def preparar_para_evaluar(test_df, full_design):
    """
    Solo columnas numéricas que predice la red (REGRESSION_ALWAYS + MASKED_COLUMNS).
    test_df no necesita traer ya la geometría con nombre: si falta, se deriva aquí de
    p1..p12 (única fuente de verdad disponible, no hay columna C_i real en los datos).
    """
    test_df = _ensure_geometry(test_df)
    cols = REGRESSION_ALWAYS + MASKED_COLUMNS
    df_real = test_df[cols].apply(pd.to_numeric, errors="coerce").fillna(0.0).reset_index(drop=True)
    df_pred = full_design[cols].apply(pd.to_numeric, errors="coerce").fillna(0.0).reset_index(drop=True)
    assert len(df_real) == len(df_pred), f"{len(df_real)} vs {len(df_pred)}"
    return df_real, df_pred


def evaluar_predicciones(df_real, df_pred, tol_taller=(5.0, 10.0)):
    """
    Compara dos DataFrames columna por columna evaluando MAE, RMSE, R2 Score
    y porcentajes de tolerancia constructiva.
    Filtra columnas inactivas (MASKED_COLUMNS: geometría E-S/D_i/I-C/C_i/E-C + rigidizadores)
    para evitar la inflación artificial de aciertos en ceros.
    tol_taller: las dos tolerancias (mm) de las columnas "% <= Xmm (Taller)".
    """
    tol_a, tol_b = tol_taller
    cols_comunes = [c for c in df_real.columns if c in df_pred.columns]
    df_r = df_real[cols_comunes].reset_index(drop=True)
    df_p = df_pred[cols_comunes].reset_index(drop=True)

    masked_cols = [c for c in cols_comunes if c in MASKED_COLUMNS]
    resultados = []

    for col in cols_comunes:
        y_true = df_r[col].values
        y_pred = df_p[col].values

        if col in masked_cols:
            mask_activo = y_true > 0
            if mask_activo.sum() > 0:
                y_true = y_true[mask_activo]
                y_pred = y_pred[mask_activo]

        if len(y_true) == 0:
            continue

        error_abs = np.abs(y_true - y_pred)

        mae = mean_absolute_error(y_true, y_pred)
        rmse = np.sqrt(mean_squared_error(y_true, y_pred))
        r2 = r2_score(y_true, y_pred) if len(y_true) > 1 and np.std(y_true) > 0 else 1.0

        acierto_exacto = (error_abs <= 0.5).mean() * 100
        pct_dentro_a = (error_abs <= tol_a).mean() * 100
        pct_dentro_b = (error_abs <= tol_b).mean() * 100

        resultados.append({
            'Variable': col,
            'N (Muestras)': len(y_true),
            'MAE (mm)': round(mae, 2),
            'RMSE (mm)': round(rmse, 2),
            'R2 Score': round(r2, 3),
            '% Exacto (Catálogo)': round(acierto_exacto, 1),
            f'% <= {tol_a:g}mm (Taller)': round(pct_dentro_a, 1),
            f'% <= {tol_b:g}mm (Taller)': round(pct_dentro_b, 1),
        })

    df_res = pd.DataFrame(resultados)
    print("=" * 105)
    print(" " * 20 + "EVALUACIÓN INTEGRAL DE PREDICCIONES Y TOLERANCIAS")
    print("=" * 105)
    print(df_res.to_string(index=False))

    return df_res


def evaluar_estructura(test_df, full_design):
    """
    Lo que el MAE por columna no ve: acierto de num_filas_tornillos y tiene_cantonera,
    y precisión de presencia por columna de geometría (falsos positivos incluidos).
    """
    test_df = _ensure_geometry(test_df)
    real_n = (1 + (test_df[GEOM_COLUMNS].fillna(0.0) > 0).sum(axis=1)).values
    pred_n = full_design["num_filas_tornillos"].values
    real_cant = test_df["tiene_cantonera"].astype(bool).values
    pred_cant = full_design["tiene_cantonera"].astype(bool).values

    print("=" * 60)
    print(" " * 10 + "ESTRUCTURA: num_filas_tornillos / tiene_cantonera")
    print("=" * 60)
    print(f"num_filas_tornillos exacto (%) : {100*np.mean(real_n == pred_n):5.1f}")
    print(f"num_filas_tornillos ±1 (%)     : {100*np.mean(np.abs(real_n - pred_n) <= 1):5.1f}")
    print(f"tiene_cantonera acierto (%)    : {100*np.mean(real_cant == pred_cant):5.1f}")

    print("\nPresencia por columna de geometría (acierto de existe/no existe):")
    pres = {c: round(100 * np.mean((test_df[c].fillna(0).values > 0) == (full_design[c].values > 0)), 1)
            for c in GEOM_COLUMNS}
    print(pd.Series(pres).to_string())

    conf = pd.crosstab(pd.Series(real_n, name="real"), pd.Series(pred_n, name="pred"))
    print("\nnum_filas_tornillos, real (filas) vs predicho (columnas):")
    print(conf.to_string())
    return {"num_filas_exacto": float(np.mean(real_n == pred_n)),
            "cantonera_acierto": float(np.mean(real_cant == pred_cant))}, conf


def error_geom_por_canto(test_df, full_design, n_bins=4):
    """MAE de la geometría activa (E-S/D_i/I-C/C_i/E-C) por cuartiles del canto de la viga."""
    test_df = _ensure_geometry(test_df)
    real = test_df[GEOM_COLUMNS].fillna(0.0).values
    pred = full_design[GEOM_COLUMNS].values.astype(float)
    act = real > 0
    err = np.where(act, np.abs(real - pred), np.nan)
    canto = pd.qcut(test_df["BEAM_d_mm"].values, n_bins, duplicates="drop")
    tab = pd.DataFrame(err, columns=GEOM_COLUMNS).groupby(canto, observed=True).mean().round(1)
    tab.insert(0, "N", pd.Series(canto).value_counts().sort_index().values)
    print("MAE (mm) de la geometría activa por canto de viga:")
    print(tab.to_string())
    return tab


def diagnostico_geometria(df, tol=1.0):
    """¿Lp = 2e + Σp y Σp = BEAM_d + 2d en el dataset? (sobre p1..p12 crudo, no la geometría con nombre)."""
    S = df[P_COLUMNS].fillna(0.0).sum(axis=1)
    r1 = df["Lp"] - 2 * df["e"] - S
    r2 = S - (df["BEAM_d_mm"] + 2 * df["d"])
    print(f"Lp - (2e + Σp)      : {100*(r1.abs() <= tol).mean():5.1f}% de filas dentro de ±{tol:g} mm | mediana={r1.median():.1f}")
    print(f"Σp - (h_viga + 2d)  : {100*(r2.abs() <= tol).mean():5.1f}% de filas dentro de ±{tol:g} mm | mediana={r2.median():.1f}")
    return r1, r2


def verificar_reversibilidad(df):
    """
    Confirma que pasar de p1..p12 a E-S/D_i/I-C/C_i/E-C no pierde información: reconstruir
    p desde la geometría con nombre debe reproducir el p1..p12 original. Es la prueba de
    que la descomposición (incluida la extracción de C_i, sin ground truth propio) es
    correcta antes de fiarse de las métricas de más arriba.
    """
    return check_reversibility(df)