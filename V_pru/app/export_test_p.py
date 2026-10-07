"""
Exporta a CSV la tabla completa de resultados por variable en el TEST:
  - Regresión siempre activa: g, e, d, Bp, tp
  - Con máscara: p1..p12 (pasos predichos), tws, ts, tbs, tst y Lh
  - Clasificación: standard, Bolt, SlipCritical, n_alma, n_cantonera

El test es el split de data_final.csv:
    df_train, df_test = train_test_split(df_resultado, test_size=0.2, random_state=2)

Las columnas con máscara y las p se evalúan solo en muestras activas (valor real > 0).

Uso:  python export_test_p.py [salida.csv]
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

import store
from core.config import P_COLUMNS, STIFFENER_COLUMNS, REGRESSION_ALWAYS
from core.training import forward_numpy, outputs_to_design

CSV_PATH = store.DATA_DIR / "data_final.csv"


def _reg_row(col, y_true, y_pred, tipo, tol=(5.0, 10.0)):
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    act = y_true > 0
    if col in REGRESSION_ALWAYS:          # siempre activa: usa todas las filas
        act = np.ones_like(act, dtype=bool)
    y_true, y_pred = y_true[act], y_pred[act]
    if len(y_true) == 0:
        return None
    err = np.abs(y_true - y_pred)
    r2 = r2_score(y_true, y_pred) if len(y_true) > 1 and np.std(y_true) > 0 else 1.0
    return {
        "Variable": col, "Tipo": tipo, "N": len(y_true),
        "MAE (mm)": round(mean_absolute_error(y_true, y_pred), 2),
        "RMSE (mm)": round(np.sqrt(mean_squared_error(y_true, y_pred)), 2),
        "SD Error (mm)": round(float(err.std()), 2),
        "Max Error (mm)": round(float(err.max()), 2),
        "R2 Score": round(r2, 3),
        "% Exacto (0.5mm)": round((err <= 0.5).mean() * 100, 1),
        "% <= 5mm": round((err <= tol[0]).mean() * 100, 1),
        "% <= 10mm": round((err <= tol[1]).mean() * 100, 1),
        "Accuracy": "",
    }


def _cls_row(col, real, pred, tipo):
    real = np.asarray(real).ravel()
    pred = np.asarray(pred).ravel()
    n = len(real)
    return {
        "Variable": col, "Tipo": tipo, "N": n,
        "MAE (mm)": "", "RMSE (mm)": "", "SD Error (mm)": "", "Max Error (mm)": "", "R2 Score": "",
        "% Exacto (0.5mm)": "", "% <= 5mm": "", "% <= 10mm": "",
        "Accuracy": round(float((real == pred).mean()), 4),
    }


def main(out_path):
    bundle = store.load_model_bundle()
    if bundle is None:
        raise SystemExit("No hay modelo entrenado.")
    model, pre, device = bundle

    df_resultado = store.build_global_structure_from_final(pd.read_csv(CSV_PATH, sep=";"))
    _, df_test = train_test_split(df_resultado, test_size=0.2, random_state=2)

    x_cat, x_num = pre.transform_features(df_test)
    outputs = forward_numpy(model, x_cat, x_num, device)
    design = outputs_to_design(outputs, pre, geom=df_test).reset_index(drop=True)
    real = df_test.reset_index(drop=True)

    filas = []
    for col in REGRESSION_ALWAYS:
        filas.append(_reg_row(col, real[col], design[col], "Regresión"))
    for col in STIFFENER_COLUMNS + ["Lh"]:
        filas.append(_reg_row(col, real[col], design[col], "Máscara"))
    for col in P_COLUMNS:
        filas.append(_reg_row(col, real[col], design[col], "p (predicha)"))

    # Clasificación (cabezas globales)
    filas.append(_cls_row("standard", real["standard"].astype(str), design["standard"].astype(str), "Clasificación"))
    filas.append(_cls_row("Bolt", real["Bolt"].astype(int), design["Bolt"].astype(int), "Clasificación"))
    slip_real = real["SlipCritical"].astype(str).str.upper().map(
        {"TRUE": "YES", "FALSE": "NO", "YES": "YES", "NO": "NO"})
    filas.append(_cls_row("SlipCritical", slip_real, design["SlipCritical"].astype(str), "Clasificación"))
    filas.append(_cls_row("n_alma", real["n_alma"].astype(int), design["n_alma"].astype(int), "Clasificación"))
    filas.append(_cls_row("n_cantonera", real["n_cantonera"].astype(int), design["n_cantonera"].astype(int), "Clasificación"))

    res = pd.DataFrame([f for f in filas if f is not None])
    res.to_csv(out_path, index=False)
    print(res.to_string(index=False))
    print(f"\nGuardado en: {out_path}")


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else (store.APP_DIR / "resultados_test.csv")
    main(out)
