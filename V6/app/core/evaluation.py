"""
Evaluación del modelo.

Incluye:

    - regresiones globales;
    - separaciones activas;
    - estructura de filas;
    - coherencia del prefijo;
    - error por canto;
    - error y sesgo por transición;
    - comparación entre topología real y predicha.
"""

import numpy as np
import pandas as pd

from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)

from .config import (
    REGRESSION_ALWAYS,
    MASKED_COLUMNS,
    P_COLUMNS,
    N_Y,
)


def preparar_para_evaluar(
    test_df,
    full_design,
):
    """
    Extrae las columnas numéricas comunes.
    """
    columns = (
        REGRESSION_ALWAYS
        + MASKED_COLUMNS
    )

    real_df = (
        test_df[columns]
        .apply(
            pd.to_numeric,
            errors="coerce",
        )
        .fillna(0.0)
        .reset_index(drop=True)
    )

    predicted_df = (
        full_design[columns]
        .apply(
            pd.to_numeric,
            errors="coerce",
        )
        .fillna(0.0)
        .reset_index(drop=True)
    )

    if len(real_df) != len(
        predicted_df
    ):
        raise ValueError(
            f"Número de filas diferente: "
            f"{len(real_df)} reales frente a "
            f"{len(predicted_df)} predichas."
        )

    return real_df, predicted_df


def evaluar_predicciones(
    df_real,
    df_pred,
    tol_taller=(5.0, 10.0),
):
    """
    Evalúa MAE, RMSE, R² y tolerancias por columna.

    Las columnas enmascaradas sin ninguna muestra activa se omiten.
    """
    tolerance_a, tolerance_b = (
        tol_taller
    )

    common_columns = [
        column
        for column in df_real.columns
        if column in df_pred.columns
    ]

    real = (
        df_real[common_columns]
        .reset_index(drop=True)
    )

    predicted = (
        df_pred[common_columns]
        .reset_index(drop=True)
    )

    masked_columns = [
        column
        for column in common_columns
        if column in MASKED_COLUMNS
    ]

    results = []

    for column in common_columns:
        y_true = real[
            column
        ].to_numpy()

        y_pred = predicted[
            column
        ].to_numpy()

        if column in masked_columns:
            active = y_true > 0.0

            if active.sum() == 0:
                continue

            y_true = y_true[active]
            y_pred = y_pred[active]

        absolute_error = np.abs(
            y_true - y_pred
        )

        mae = mean_absolute_error(
            y_true,
            y_pred,
        )

        rmse = np.sqrt(
            mean_squared_error(
                y_true,
                y_pred,
            )
        )

        if (
            len(y_true) > 1
            and np.std(y_true) > 0.0
        ):
            r2 = r2_score(
                y_true,
                y_pred,
            )
        else:
            r2 = np.nan

        results.append(
            {
                "Variable": column,
                "N (Muestras)": len(
                    y_true
                ),
                "MAE (mm)": round(
                    mae,
                    2,
                ),
                "RMSE (mm)": round(
                    rmse,
                    2,
                ),
                "R2 Score": (
                    round(r2, 3)
                    if np.isfinite(r2)
                    else np.nan
                ),
                "% Exacto (Catálogo)": round(
                    100
                    * np.mean(
                        absolute_error
                        <= 0.5
                    ),
                    1,
                ),
                f"% <= {tolerance_a:g}mm (Taller)": round(
                    100
                    * np.mean(
                        absolute_error
                        <= tolerance_a
                    ),
                    1,
                ),
                f"% <= {tolerance_b:g}mm (Taller)": round(
                    100
                    * np.mean(
                        absolute_error
                        <= tolerance_b
                    ),
                    1,
                ),
            }
        )

    result_df = pd.DataFrame(
        results
    )

    print("=" * 105)
    print(
        " " * 20
        + "EVALUACIÓN INTEGRAL DE "
        "PREDICCIONES Y TOLERANCIAS"
    )
    print("=" * 105)

    print(
        result_df.to_string(
            index=False
        )
    )

    return result_df


def evaluar_estructura(
    test_df,
    full_design,
):
    """
    Evalúa los conteos y el número total de filas.
    """
    real_n_alma = (
        test_df["n_alma"]
        .astype(int)
        .to_numpy()
    )

    real_n_cantonera = (
        test_df["n_cantonera"]
        .astype(int)
        .to_numpy()
    )

    real_n_filas = (
        real_n_alma
        + real_n_cantonera
        + 2
    )

    predicted_n_alma = (
        full_design["n_alma"]
        .astype(int)
        .to_numpy()
    )

    predicted_n_cantonera = (
        full_design["n_cantonera"]
        .astype(int)
        .to_numpy()
    )

    predicted_n_filas = (
        full_design[
            "num_filas_tornillos"
        ]
        .astype(int)
        .to_numpy()
    )

    metrics = {
        "n_alma_exacto": float(
            np.mean(
                real_n_alma
                == predicted_n_alma
            )
        ),
        "n_cantonera_exacto": float(
            np.mean(
                real_n_cantonera
                == predicted_n_cantonera
            )
        ),
        "num_filas_exacto": float(
            np.mean(
                real_n_filas
                == predicted_n_filas
            )
        ),
        "num_filas_mas_menos_1": float(
            np.mean(
                np.abs(
                    real_n_filas
                    - predicted_n_filas
                ) <= 1
            )
        ),
    }

    print("=" * 70)
    print("ESTRUCTURA DE FILAS DE TORNILLOS")
    print("=" * 70)

    print(
        "n_alma exacto (%)              : "
        f"{100 * metrics['n_alma_exacto']:.1f}"
    )

    print(
        "n_cantonera exacto (%)         : "
        f"{100 * metrics['n_cantonera_exacto']:.1f}"
    )

    print(
        "num_filas exacto (%)           : "
        f"{100 * metrics['num_filas_exacto']:.1f}"
    )

    print(
        "num_filas ±1 (%)               : "
        f"{100 * metrics['num_filas_mas_menos_1']:.1f}"
    )

    confusion = pd.crosstab(
        pd.Series(
            real_n_filas,
            name="real",
        ),
        pd.Series(
            predicted_n_filas,
            name="predicho",
        ),
    )

    print(
        "\nNúmero de filas: real frente "
        "a predicho:"
    )

    print(
        confusion.to_string()
    )

    return metrics, confusion


def evaluar_coherencia_prefijo(
    full_design,
):
    """
    Comprueba que las p activas forman exactamente el prefijo
    definido por los conteos.
    """
    p_values = (
        full_design[P_COLUMNS]
        .fillna(0.0)
        .to_numpy(dtype=float)
    )

    active = p_values > 0.0

    expected_count = (
        full_design["n_alma"]
        .astype(int)
        .to_numpy()
        + full_design[
            "n_cantonera"
        ]
        .astype(int)
        .to_numpy()
        + 1
    )

    expected_mask = (
        np.arange(N_Y)[None, :]
        < expected_count[:, None]
    )

    prefix_valid = np.all(
        active == expected_mask,
        axis=1,
    )

    result = {
        "fraccion_prefijo_correcto": float(
            prefix_valid.mean()
        ),
    }

    print(
        "Prefijo de p correcto: "
        f"{100 * result['fraccion_prefijo_correcto']:.2f}%"
    )

    return result


def error_p_por_canto(
    test_df,
    full_design,
    n_bins=4,
):
    """
    MAE de las p activas por cuantiles del canto de la viga.
    """
    real = (
        test_df[P_COLUMNS]
        .fillna(0.0)
        .to_numpy(dtype=float)
    )

    predicted = (
        full_design[P_COLUMNS]
        .fillna(0.0)
        .to_numpy(dtype=float)
    )

    active = real > 0.0

    error = np.full_like(
        real,
        np.nan,
        dtype=float,
    )

    error[active] = np.abs(
        real[active]
        - predicted[active]
    )

    beam_depth = pd.to_numeric(
        test_df["BEAM_d_mm"],
        errors="coerce",
    )

    depth_groups = pd.qcut(
        beam_depth,
        q=n_bins,
        duplicates="drop",
    )

    error_df = pd.DataFrame(
        error,
        columns=P_COLUMNS,
        index=test_df.index,
    )

    table = (
        error_df
        .groupby(
            depth_groups,
            observed=True,
        )
        .mean()
        .round(2)
    )

    table["N_conexiones"] = (
        pd.Series(
            depth_groups,
            index=test_df.index,
        )
        .groupby(
            depth_groups,
            observed=True,
        )
        .size()
        .reindex(table.index)
        .to_numpy()
    )

    print(
        "MAE de las p activas por canto:"
    )

    print(
        table.to_string()
    )

    return table


def evaluar_sesgo_p(
    test_df,
    full_design,
):
    """
    Evalúa el error firmado de cada p.
    """
    results = []

    for column in P_COLUMNS:
        real = (
            pd.to_numeric(
                test_df[column],
                errors="coerce",
            )
            .fillna(0.0)
            .to_numpy(dtype=float)
        )

        predicted = (
            pd.to_numeric(
                full_design[column],
                errors="coerce",
            )
            .fillna(0.0)
            .to_numpy(dtype=float)
        )

        active = real > 0.0

        if active.sum() == 0:
            continue

        error = (
            predicted[active]
            - real[active]
        )

        negative_errors = error[
            error < 0.0
        ]

        results.append(
            {
                "Variable": column,
                "N": int(active.sum()),
                "Real media (mm)": (
                    real[active].mean()
                ),
                "Pred media (mm)": (
                    predicted[active].mean()
                ),
                "MAE (mm)": (
                    np.abs(error).mean()
                ),
                "Sesgo (mm)": (
                    error.mean()
                ),
                "% subestimadas": (
                    100
                    * np.mean(error < 0.0)
                ),
                "% subestimadas > 5 mm": (
                    100
                    * np.mean(error < -5.0)
                ),
                "% subestimadas > 10 mm": (
                    100
                    * np.mean(error < -10.0)
                ),
                "Subestimación media (mm)": (
                    -negative_errors.mean()
                    if len(negative_errors) > 0
                    else 0.0
                ),
            }
        )

    result = pd.DataFrame(
        results
    )

    return result


def evaluar_por_transicion(
    test_df,
    full_design,
):
    """
    Evalúa las separaciones agrupadas por transición geométrica real.

    Si test_df no contiene pX_transition, utiliza las transiciones
    producidas en full_design, pero para una evaluación rigurosa es
    preferible que test_df tenga las transiciones reales.
    """
    records = []

    for position in range(
        1,
        N_Y + 1,
    ):
        p_column = f"p{position}"

        transition_column = (
            f"p{position}_transition"
        )

        real = (
            pd.to_numeric(
                test_df[p_column],
                errors="coerce",
            )
            .fillna(0.0)
            .to_numpy(dtype=float)
        )

        predicted = (
            pd.to_numeric(
                full_design[p_column],
                errors="coerce",
            )
            .fillna(0.0)
            .to_numpy(dtype=float)
        )

        if transition_column in test_df.columns:
            transitions = (
                test_df[
                    transition_column
                ]
                .fillna("UNUSED")
                .astype(str)
                .to_numpy()
            )
        else:
            transitions = (
                full_design[
                    transition_column
                ]
                .fillna("UNUSED")
                .astype(str)
                .to_numpy()
            )

        active_indices = np.where(
            real > 0.0
        )[0]

        for row_index in active_indices:
            error = (
                predicted[row_index]
                - real[row_index]
            )

            records.append(
                {
                    "numero_p": position,
                    "transicion": (
                        transitions[row_index]
                    ),
                    "real_mm": (
                        real[row_index]
                    ),
                    "pred_mm": (
                        predicted[row_index]
                    ),
                    "error_mm": error,
                    "error_absoluto_mm": (
                        abs(error)
                    ),
                }
            )

    detail = pd.DataFrame(
        records
    )

    if detail.empty:
        return pd.DataFrame(), detail

    summary = (
        detail
        .groupby(
            "transicion",
            dropna=False,
        )
        .agg(
            N=("error_mm", "size"),
            real_media_mm=(
                "real_mm",
                "mean",
            ),
            pred_media_mm=(
                "pred_mm",
                "mean",
            ),
            MAE_mm=(
                "error_absoluto_mm",
                "mean",
            ),
            sesgo_mm=(
                "error_mm",
                "mean",
            ),
            dentro_10_pct=(
                "error_absoluto_mm",
                lambda values: (
                    100
                    * (values <= 10.0).mean()
                ),
            ),
            subestimadas_pct=(
                "error_mm",
                lambda values: (
                    100
                    * (values < 0.0).mean()
                ),
            ),
            subestimadas_mas_10_pct=(
                "error_mm",
                lambda values: (
                    100
                    * (values < -10.0).mean()
                ),
            ),
        )
        .reset_index()
        .sort_values(
            [
                "dentro_10_pct",
                "MAE_mm",
            ],
            ascending=[
                True,
                False,
            ],
        )
    )

    return summary, detail