"""
Evaluación de predicciones (v4, esquema train_v3.parquet: pasos p1..p12 + conteos).
  - evaluar_predicciones   : tabla MAE/RMSE/R2/tolerancias por columna; enmascara TODAS las
                             MASKED_COLUMNS (Ys + rigidizadores), no solo p_*.
  - preparar_para_evaluar  : adapta (test_df, full_design) a lo que espera evaluar_predicciones.
  - counts_from_ys (en dataset.py) : verdad de n_alma/n_cantonera/num_filas desde Ys + e + d.
  - evaluar_estructura     : acierto de n_alma, n_cantonera y num_filas_tornillos, y presencia
                             por columna (lo que el MAE por columna no ve).
  - error_ys_por_canto     : error de las Ys activas según el canto de la viga.
"""
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from .config import REGRESSION_ALWAYS, MASKED_COLUMNS, P_COLUMNS, P_LABEL_COLUMNS, Y_COLUMNS
from .dataset import ys_from_p


def preparar_para_evaluar(test_df, full_design):
    """
    Solo columnas numéricas que predice la red (REGRESSION_ALWAYS + MASKED_COLUMNS).
    El esquema v4 trae las Ys reales directamente (no hay que derivar nada de p1..p12).
    """
    cols = REGRESSION_ALWAYS + MASKED_COLUMNS
    df_real = test_df[cols].apply(pd.to_numeric, errors="coerce").fillna(0.0).reset_index(drop=True)
    df_pred = full_design[cols].apply(pd.to_numeric, errors="coerce").fillna(0.0).reset_index(drop=True)
    assert len(df_real) == len(df_pred), f"{len(df_real)} vs {len(df_pred)}"
    return df_real, df_pred


def evaluar_predicciones(df_real, df_pred, tol_taller=(5.0, 10.0)):
    """
    Compara dos DataFrames columna por columna evaluando MAE, RMSE, R2 Score
    y porcentajes de tolerancia constructiva.
    Filtra columnas inactivas (MASKED_COLUMNS: p1..p12 + rigidizadores)
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
    Lo que el MAE por columna no ve: acierto de n_alma, n_cantonera y num_filas_tornillos
    (la verdad viene directa en n_alma/n_cantonera), y precisión de presencia
    por columna (falsos positivos incluidos).
    """
    real_n_alma = test_df["n_alma"].astype(int).values
    real_n_can = test_df["n_cantonera"].astype(int).values
    real_n_filas = real_n_alma + real_n_can + 2
    pred_n_alma = full_design["n_alma"].astype(int).values
    pred_n_can = full_design["n_cantonera"].astype(int).values
    pred_n_filas = full_design["num_filas_tornillos"].astype(int).values

    print("=" * 60)
    print(" " * 10 + "ESTRUCTURA: n_alma / n_cantonera / num_filas_tornillos")
    print("=" * 60)
    print(f"n_alma exacto (%)            : {100*np.mean(real_n_alma == pred_n_alma):5.1f}")
    print(f"n_cantonera exacto (%)       : {100*np.mean(real_n_can == pred_n_can):5.1f}")
    print(f"num_filas_tornillos exacto (%) : {100*np.mean(real_n_filas == pred_n_filas):5.1f}")
    print(f"num_filas_tornillos ±1 (%)     : {100*np.mean(np.abs(real_n_filas - pred_n_filas) <= 1):5.1f}")

    print("\nPresencia por columna (acierto de existe/no existe):")
    pres = {c: round(100 * np.mean((test_df[c].fillna(0).values > 0) == (full_design[c].values > 0)), 1)
            for c in P_COLUMNS}
    print(pd.Series(pres).to_string())

    conf = pd.crosstab(pd.Series(real_n_filas, name="real"), pd.Series(pred_n_filas, name="pred"))
    print("\nnum_filas_tornillos, real (filas) vs predicho (columnas):")
    print(conf.to_string())
    return {"n_alma_exacto": float(np.mean(real_n_alma == pred_n_alma)),
            "n_cantonera_exacto": float(np.mean(real_n_can == pred_n_can)),
            "num_filas_exacto": float(np.mean(real_n_filas == pred_n_filas))}, conf


def error_p_por_canto(test_df, full_design, n_bins=4):
    """MAE de las p activas por cuartiles del canto de la viga."""
    real = test_df[P_COLUMNS].fillna(0.0).values
    pred = full_design[P_COLUMNS].values.astype(float)
    act = real > 0
    err = np.nan + np.zeros_like(real)
    err[act] = np.abs(real[act] - pred[act])
    canto = pd.qcut(test_df["BEAM_d_mm"].values)
    tab = pd.DataFrame(err).groupby(canto).mean().round(1)
    tab["N"] = canto.value_counts().sort_index().values
    print("MAE (mm) de las p activas por canto de viga:")
    print(tab.to_string())
    return tab


def evaluar_p_labels(test_df, full_design):
    """
    Acierto de la zona predicha por paso (p1_label..p12_label). Para pasos inactivos
    (p real = 0) la clase esperada es UNUSED; se evalua el acierto global y, aparte,
    el acierto SOLO en pasos activos (excluye UNUSED real).
    """
    res = []
    for c in P_LABEL_COLUMNS:
        real = test_df[c].astype(str).values
        pred = full_design[c].astype(str).values
        acc = float(np.mean(real == pred))
        act = test_df[P_COLUMNS[P_LABEL_COLUMNS.index(c)]].fillna(0.0).values > 0
        acc_act = float(np.mean(real[act] == pred[act])) if act.sum() > 0 else float("nan")
        res.append({"Variable": c, "N": int(len(real)), "Accuracy": round(acc, 4),
                    "Accuracy (activos)": round(acc_act, 4) if act.sum() > 0 else ""})
    tab = pd.DataFrame(res)
    print("Acierto por p_label (global / solo pasos activos):")
    print(tab.to_string(index=False))
    return tab
