import numpy as np, pandas as pd
from sklearn.metrics import (
    accuracy_score,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)
from config import REGRESSION_ALWAYS, P_COLUMNS, P_LABEL_COLUMNS, STIFFENER_COLUMNS


def evaluate(real, pred):
    cls = {
        c: accuracy_score(real[c].astype(str), pred[c].astype(str))
        for c in ["DrawingCode", "Bolt", "SlipCritical"]
    }
    labels = {
        c: accuracy_score(real[c].fillna("UNUSED").astype(str), pred[c].astype(str))
        for c in P_LABEL_COLUMNS
    }
    rows = []
    for c in REGRESSION_ALWAYS + P_COLUMNS + STIFFENER_COLUMNS:
        y = real[c].fillna(0).astype(float).to_numpy()
        yp = pred[c].astype(float).to_numpy()
        m = np.ones(len(y), bool) if c in REGRESSION_ALWAYS else y > 0
        if not m.any():
            continue
        rows.append(
            {
                "Variable": c,
                "N": int(m.sum()),
                "MAE": mean_absolute_error(y[m], yp[m]),
                "RMSE": mean_squared_error(y[m], yp[m]) ** 0.5,
                "R2": r2_score(y[m], yp[m])
                if m.sum() > 1 and y[m].std() > 0
                else np.nan,
                "% <=5mm": 100 * np.mean(abs(y[m] - yp[m]) <= 5),
                "% <=15mm": 100 * np.mean(abs(y[m] - yp[m]) <= 15),
            }
        )
    structure = {
        "secuencia_labels_exacta": float(
            np.mean(
                np.all(
                    real[P_LABEL_COLUMNS].fillna("UNUSED").astype(str).to_numpy()
                    == pred[P_LABEL_COLUMNS].astype(str).to_numpy(),
                    axis=1,
                )
            )
        ),
        "cantonera_accuracy": accuracy_score(
            real["tiene_cantonera"].astype(str), pred["tiene_cantonera"].astype(str)
        ),
    }
    return cls, pd.Series(labels, name="accuracy"), pd.DataFrame(rows), structure
