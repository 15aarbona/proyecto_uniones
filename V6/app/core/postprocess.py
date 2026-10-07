"""
Postproceso de las predicciones.

La existencia de las separaciones p se determina exclusivamente mediante:

    k = n_alma + n_cantonera + 1

La cabeza de presencia solo controla la existencia de rigidizadores.
"""

import numpy as np
import pandas as pd

from .config import (
    CATALOGO_BOLT,
    CATALOGO_g,
    CATALOGO_e,
    CATALOGO_d,
    CATALOGO_Bp,
    CATALOGO_tp,
    CATALOGO_tws,
    CATALOGO_ts,
    CATALOGO_tbs,
    CATALOGO_tst,
    REGRESSION_ALWAYS,
    P_COLUMNS,
    STIFFENER_COLUMNS,
    Y_GRID_STEP,
    N_Y,
    secuencia_transiciones,
)


CATALOGS = {
    "g": CATALOGO_g,
    "e": CATALOGO_e,
    "d": CATALOGO_d,
    "Bp": CATALOGO_Bp,
    "tp": CATALOGO_tp,
    "tws": CATALOGO_tws,
    "ts": CATALOGO_ts,
    "tbs": CATALOGO_tbs,
    "tst": CATALOGO_tst,
}


def snap_to_catalog(
    values,
    catalog,
):
    """
    Proyecta cada valor al elemento más cercano del catálogo.
    """
    values = np.asarray(
        values,
        dtype=float,
    )

    if catalog is None:
        return values

    catalog_array = np.asarray(
        catalog,
        dtype=float,
    )

    indices = np.abs(
        values[:, None]
        - catalog_array[None, :]
    ).argmin(axis=1)

    return catalog_array[indices]


def _sigmoid(x):
    return 1.0 / (
        1.0
        + np.exp(
            -np.clip(
                x,
                -30.0,
                30.0,
            )
        )
    )


def decode_predictions(
    reg_always_real,
    masked_value_real,
    masked_presence_prob,
    bolt_logits,
    n_alma_logits,
    n_cantonera_logits,
    standard_logits=None,
    standard_classes=None,
    slip_critical_logit=None,
    thresholds=None,
):
    """
    Convierte las salidas desestandarizadas en un DataFrame de diseño.
    """
    n_samples = reg_always_real.shape[0]

    n_masked = masked_value_real.shape[1]

    if thresholds is None:
        thresholds = np.full(
            n_masked,
            0.5,
            dtype=float,
        )

    thresholds = np.asarray(
        thresholds,
        dtype=float,
    )

    if len(thresholds) != n_masked:
        raise ValueError(
            "thresholds debe tener la misma longitud "
            "que masked_value_real."
        )

    output = {}

    # ------------------------------------------------------------------
    # Regresiones siempre activas
    # ------------------------------------------------------------------

    for column_index, column_name in enumerate(
        REGRESSION_ALWAYS
    ):
        values = reg_always_real[
            :,
            column_index,
        ]

        output[column_name] = (
            snap_to_catalog(
                values,
                CATALOGS.get(column_name),
            )
        )

    # ------------------------------------------------------------------
    # Conteos
    # ------------------------------------------------------------------

    n_alma = n_alma_logits.argmax(
        axis=1
    )

    n_cantonera = (
        n_cantonera_logits.argmax(
            axis=1
        )
    )

    output["n_alma"] = n_alma
    output["n_cantonera"] = n_cantonera

    n_p_activas = (
        n_alma
        + n_cantonera
        + 1
    )

    # ------------------------------------------------------------------
    # Separaciones p
    # ------------------------------------------------------------------

    p_raw = masked_value_real[
        :,
        :N_Y,
    ].copy()

    p_snapped = np.maximum(
        np.round(
            p_raw / Y_GRID_STEP
        ) * Y_GRID_STEP,
        Y_GRID_STEP,
    )

    positions = np.arange(
        N_Y
    )[None, :]

    p_active_mask = (
        positions
        < n_p_activas[:, None]
    )

    p_final = np.where(
        p_active_mask,
        p_snapped,
        0.0,
    )

    for column_index, column_name in enumerate(
        P_COLUMNS
    ):
        output[column_name] = (
            p_final[:, column_index]
        )

    # ------------------------------------------------------------------
    # Rigidizadores
    # ------------------------------------------------------------------

    rigidizer_start = N_Y

    rigidizer_values = masked_value_real[
        :,
        rigidizer_start:,
    ]

    rigidizer_probabilities = (
        masked_presence_prob[
            :,
            rigidizer_start:,
        ]
    )

    rigidizer_thresholds = thresholds[
        rigidizer_start:
    ]

    for column_index, column_name in enumerate(
        STIFFENER_COLUMNS
    ):
        values = rigidizer_values[
            :,
            column_index,
        ]

        values = snap_to_catalog(
            values,
            CATALOGS[column_name],
        )

        active = (
            rigidizer_probabilities[
                :,
                column_index,
            ]
            >= rigidizer_thresholds[
                column_index
            ]
        )

        output[column_name] = np.where(
            active,
            values,
            0.0,
        )

    # ------------------------------------------------------------------
    # Tornillo
    # ------------------------------------------------------------------

    bolt_indices = bolt_logits.argmax(
        axis=1
    )

    bolt_values = np.asarray(
        CATALOGO_BOLT,
        dtype=int,
    )[bolt_indices]

    output["Bolt"] = bolt_values

    output["_bolt_nominal_mm"] = (
        bolt_values.astype(int)
    )

    # ------------------------------------------------------------------
    # Normativa
    # ------------------------------------------------------------------

    if (
        standard_logits is not None
        and standard_classes is not None
    ):
        standard_classes = np.asarray(
            standard_classes
        )

        output["standard"] = (
            standard_classes[
                standard_logits.argmax(
                    axis=1
                )
            ]
        )

    # ------------------------------------------------------------------
    # Slip critical
    # ------------------------------------------------------------------

    if slip_critical_logit is not None:
        output["SlipCritical"] = np.where(
            _sigmoid(
                slip_critical_logit
            ) >= 0.5,
            "YES",
            "NO",
        )

    # ------------------------------------------------------------------
    # Transiciones derivadas
    # ------------------------------------------------------------------

    transition_columns = {
        f"p{i}_transition": []
        for i in range(
            1,
            N_Y + 1,
        )
    }

    for sample_index in range(
        n_samples
    ):
        transitions = secuencia_transiciones(
            n_alma=int(
                n_alma[sample_index]
            ),
            n_cantonera=int(
                n_cantonera[
                    sample_index
                ]
            ),
        )

        for position in range(N_Y):
            column_name = (
                f"p{position + 1}_transition"
            )

            if position < len(transitions):
                value = transitions[position]
            else:
                value = "UNUSED"

            transition_columns[
                column_name
            ].append(value)

    output.update(
        transition_columns
    )

    return pd.DataFrame(output)


def derive_dependent_columns(
    design_df,
):
    """
    Añade columnas derivadas.
    """
    result = (
        design_df
        .copy()
        .reset_index(drop=True)
    )

    bolt_mm = (
        result["_bolt_nominal_mm"]
        .to_numpy(dtype=int)
    )

    result["Hole"] = (
        bolt_mm + 2
    )

    result["num_filas_tornillos"] = (
        result["n_alma"].astype(int)
        + result[
            "n_cantonera"
        ].astype(int)
        + 2
    )

    result["tiene_cantonera"] = (
        result[
            "n_cantonera"
        ].astype(int)
        > 0
    )

    return result