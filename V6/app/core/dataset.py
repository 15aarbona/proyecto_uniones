import numpy as np
import pandas as pd
import torch

from torch.utils.data import Dataset
from sklearn.preprocessing import (
    StandardScaler,
    LabelEncoder,
)

from .config import (
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    REGRESSION_ALWAYS,
    MASKED_COLUMNS,
    CATALOGO_BOLT,
    Y_COLUMNS,
    P_COLUMNS,
    P_LABEL_COLUMNS,
    TARGET_CLS_N_ALMA,
    TARGET_CLS_N_CANTONERA,
    N_ALMA_CLASSES,
    N_CANTONERA_CLASSES,
    N_Y,
    P_TRANSITION_TO_IDX,
    P_TRANSITION_UNUSED_IDX,
    P_TRANSITION_CLASSES,
    etiquetas_zona,
    secuencia_zonas_tornillos,
    secuencia_transiciones,
)


# ---------------------------------------------------------------------------
# TORNILLOS
# ---------------------------------------------------------------------------

BOLT_TO_IDX = {
    valor: indice
    for indice, valor
    in enumerate(CATALOGO_BOLT)
}


def bolt_nominal_mm(df):
    """
    Convierte Bolt a diámetro nominal en mm.

    Acepta:
        20
        "20"
        "M20"
    """
    bolt = df["Bolt"]

    return (
        bolt
        .astype(str)
        .str.replace(
            "M",
            "",
            regex=False,
        )
        .astype(int)
    )


# ---------------------------------------------------------------------------
# COORDENADAS ACUMULADAS
# ---------------------------------------------------------------------------

def ys_from_p(df):
    """
    Deriva las cotas acumuladas Y1...Y12 desde e y p1...p12.

    Definición:
        Y1 = e + p1
        Y2 = e + p1 + p2
        ...
        Yi = e + sum(p1...pi)

    Si pi no está activa, Yi se establece en cero.
    """
    resultado = df.copy()

    p = (
        resultado[P_COLUMNS]
        .fillna(0.0)
        .to_numpy(dtype=float)
    )

    e = (
        resultado["e"]
        .to_numpy(dtype=float)
    )

    acumulado = (
        p.cumsum(axis=1)
        + e[:, None]
    )

    y = np.where(
        p > 0.0,
        acumulado,
        0.0,
    )

    for indice, columna in enumerate(
        Y_COLUMNS
    ):
        resultado[columna] = y[:, indice]

    return resultado


# ---------------------------------------------------------------------------
# CONTEOS DERIVADOS
# ---------------------------------------------------------------------------

def counts_from_ys(df):
    """
    Deriva n_alma, n_cantonera y número total de filas desde Y.

    Límites de la viga:
        ala superior = e + d
        ala inferior = e + d + BEAM_d_mm

    Se considera que una fila está dentro de la viga cuando:
        ala superior <= Y <= ala inferior

    Las filas por debajo del ala inferior contienen:
        n_cantonera + fila inferior exterior
    """
    y = (
        df[Y_COLUMNS]
        .fillna(0.0)
        .to_numpy(dtype=float)
    )

    active = y > 0.0

    e = df["e"].to_numpy(dtype=float)
    d = df["d"].to_numpy(dtype=float)

    beam_depth = (
        df["BEAM_d_mm"]
        .to_numpy(dtype=float)
    )

    y_ala_superior = e + d

    y_ala_inferior = (
        e
        + d
        + beam_depth
    )

    n_alma = (
        (
            y >= y_ala_superior[:, None]
        )
        & (
            y <= y_ala_inferior[:, None]
        )
        & active
    ).sum(axis=1)

    n_debajo = (
        (
            y > y_ala_inferior[:, None]
        )
        & active
    ).sum(axis=1)

    n_cantonera = np.maximum(
        n_debajo - 1,
        0,
    )

    numero_filas = (
        1
        + active.sum(axis=1)
    )

    return (
        n_alma.astype(int),
        n_cantonera.astype(int),
        numero_filas.astype(int),
    )


def counts_from_p(df):
    """
    Deriva n_alma, n_cantonera y número total de filas directamente
    desde e, d, BEAM_d_mm y p1...p12.
    """
    p = (
        df[P_COLUMNS]
        .fillna(0.0)
        .to_numpy(dtype=float)
    )

    e = df["e"].to_numpy(dtype=float)
    d = df["d"].to_numpy(dtype=float)

    beam_depth = (
        df["BEAM_d_mm"]
        .to_numpy(dtype=float)
    )

    y_ala_superior = e + d

    y_ala_inferior = (
        e
        + d
        + beam_depth
    )

    y = np.where(
        p > 0.0,
        p.cumsum(axis=1) + e[:, None],
        0.0,
    )

    active = p > 0.0

    n_alma = (
        (
            y >= y_ala_superior[:, None]
        )
        & (
            y <= y_ala_inferior[:, None]
        )
        & active
    ).sum(axis=1)

    n_debajo = (
        (
            y > y_ala_inferior[:, None]
        )
        & active
    ).sum(axis=1)

    n_cantonera = np.maximum(
        n_debajo - 1,
        0,
    )

    numero_filas = (
        1
        + active.sum(axis=1)
    )

    return (
        n_alma.astype(int),
        n_cantonera.astype(int),
        numero_filas.astype(int),
    )


# ---------------------------------------------------------------------------
# TRANSICIONES GEOMÉTRICAS
# ---------------------------------------------------------------------------

def transition_indices_from_counts(
    n_alma_values,
    n_cantonera_values,
    n_p=N_Y,
):
    """
    Construye los índices de transición geométrica para cada muestra.

    Parameters
    ----------
    n_alma_values:
        Array con el número de filas dentro de la viga.

    n_cantonera_values:
        Array con el número de filas dentro de la cantonera.

    n_p:
        Número máximo de separaciones.

    Returns
    -------
    numpy.ndarray
        Matriz de shape (n_muestras, n_p).

    Las posiciones posteriores al prefijo activo reciben UNUSED.
    """
    n_alma_values = np.asarray(
        n_alma_values,
        dtype=int,
    )

    n_cantonera_values = np.asarray(
        n_cantonera_values,
        dtype=int,
    )

    if len(n_alma_values) != len(
        n_cantonera_values
    ):
        raise ValueError(
            "n_alma_values y n_cantonera_values "
            "deben tener la misma longitud."
        )

    resultado = np.full(
        shape=(
            len(n_alma_values),
            n_p,
        ),
        fill_value=P_TRANSITION_UNUSED_IDX,
        dtype=np.int64,
    )

    for fila_idx, (
        n_alma,
        n_cantonera,
    ) in enumerate(
        zip(
            n_alma_values,
            n_cantonera_values,
        )
    ):
        transiciones = secuencia_transiciones(
            n_alma=n_alma,
            n_cantonera=n_cantonera,
        )

        if len(transiciones) > n_p:
            raise ValueError(
                f"La muestra {fila_idx} tiene "
                f"{len(transiciones)} transiciones, "
                f"pero el máximo permitido es {n_p}."
            )

        for posicion, transicion in enumerate(
            transiciones
        ):
            if transicion not in P_TRANSITION_TO_IDX:
                raise ValueError(
                    "Transición desconocida: "
                    f"{transicion}"
                )

            resultado[
                fila_idx,
                posicion,
            ] = P_TRANSITION_TO_IDX[
                transicion
            ]

    return resultado


def transition_names_from_counts(
    n_alma_values,
    n_cantonera_values,
    n_p=N_Y,
):
    """
    Versión legible de transition_indices_from_counts.

    Devuelve una matriz de strings con nombres de transición.
    """
    indices = transition_indices_from_counts(
        n_alma_values=n_alma_values,
        n_cantonera_values=n_cantonera_values,
        n_p=n_p,
    )

    clases = np.asarray(
        P_TRANSITION_CLASSES,
        dtype=object,
    )

    return clases[indices]


# ---------------------------------------------------------------------------
# VALIDACIÓN DEL DATASET
# ---------------------------------------------------------------------------

def validate_connection_targets(df):
    """
    Comprueba la coherencia entre:

      - p activas
      - n_alma
      - n_cantonera
      - estructura de prefijo

    Relación esperada:
        número de p activas = n_alma + n_cantonera + 1
    """
    p_values = (
        df[P_COLUMNS]
        .fillna(0.0)
        .to_numpy(dtype=float)
    )

    p_active = p_values > 0.0

    expected_count = (
        df["n_alma"]
        .astype(int)
        .to_numpy()
        + df["n_cantonera"]
        .astype(int)
        .to_numpy()
        + 1
    )

    actual_count = p_active.sum(axis=1)

    positions = np.arange(
        len(P_COLUMNS)
    )[None, :]

    expected_mask = (
        positions
        < expected_count[:, None]
    )

    prefix_valid = np.all(
        p_active == expected_mask,
        axis=1,
    )

    validation = pd.DataFrame(
        {
            "expected_p_count": expected_count,
            "actual_p_count": actual_count,
            "count_valid": (
                actual_count == expected_count
            ),
            "prefix_valid": prefix_valid,
        },
        index=df.index,
    )

    validation["valid"] = (
        validation["count_valid"]
        & validation["prefix_valid"]
    )

    return validation


# ---------------------------------------------------------------------------
# PREPROCESADOR
# ---------------------------------------------------------------------------

class Preprocessor:
    """
    Ajusta encoders y escaladores únicamente con el split de train.

    Después reutiliza esos objetos en:
        validación
        test
        inferencia
    """

    def fit(self, df):
        # ---------------------------------------------------------------
        # Encoders categóricos de entrada
        # ---------------------------------------------------------------

        self.cat_encoders = {
            columna: LabelEncoder().fit(
                df[columna].astype(str)
            )
            for columna in CATEGORICAL_FEATURES
        }

        # ---------------------------------------------------------------
        # Escalador de variables numéricas de entrada
        # ---------------------------------------------------------------

        self.num_scaler = StandardScaler().fit(
            df[NUMERIC_FEATURES].to_numpy()
        )

        # ---------------------------------------------------------------
        # Escalador de regresiones siempre activas
        # ---------------------------------------------------------------

        self.reg_always_scaler = (
            StandardScaler().fit(
                df[
                    REGRESSION_ALWAYS
                ].to_numpy()
            )
        )

        # ---------------------------------------------------------------
        # Encoder de normativa
        # ---------------------------------------------------------------

        self.standard_encoder = (
            LabelEncoder().fit(
                df["standard"].astype(str)
            )
        )

        # ---------------------------------------------------------------
        # Encoder legacy de p_label
        # ---------------------------------------------------------------

        if all(
            columna in df.columns
            for columna in P_LABEL_COLUMNS
        ):
            etiquetas = pd.concat(
                [
                    df[columna].astype(str)
                    for columna
                    in P_LABEL_COLUMNS
                ],
                ignore_index=True,
            )

            self.p_label_encoder = (
                LabelEncoder().fit(etiquetas)
            )

        else:
            self.p_label_encoder = None

        # ---------------------------------------------------------------
        # Estadísticas de las columnas con máscara
        # ---------------------------------------------------------------

        masked_values = (
            df[MASKED_COLUMNS]
            .fillna(0.0)
            .to_numpy(dtype=np.float64)
        )

        n_masked = masked_values.shape[1]

        self.masked_mean = np.zeros(
            n_masked,
            dtype=np.float64,
        )

        self.masked_std = np.ones(
            n_masked,
            dtype=np.float64,
        )

        self.masked_active_frac = np.zeros(
            n_masked,
            dtype=np.float64,
        )

        for columna_idx in range(n_masked):
            active = (
                masked_values[:, columna_idx]
                > 0.0
            )

            self.masked_active_frac[
                columna_idx
            ] = active.mean()

            if active.sum() > 1:
                values_active = masked_values[
                    active,
                    columna_idx,
                ]

                self.masked_mean[
                    columna_idx
                ] = values_active.mean()

                self.masked_std[
                    columna_idx
                ] = max(
                    values_active.std(),
                    1e-6,
                )

        # ---------------------------------------------------------------
        # Pesos positivos para presencia
        # ---------------------------------------------------------------

        self.presence_pos_weight = np.ones(
            n_masked,
            dtype=np.float32,
        )

        for columna_idx in range(n_masked):
            active_fraction = (
                self.masked_active_frac[
                    columna_idx
                ]
            )

            self.presence_pos_weight[
                columna_idx
            ] = max(
                (
                    1.0
                    - active_fraction
                )
                / max(
                    active_fraction,
                    1e-6,
                ),
                1.0,
            )

        # ---------------------------------------------------------------
        # Pesos de los conteos
        # ---------------------------------------------------------------

        self.count_class_weights = {
            TARGET_CLS_N_ALMA: (
                self._count_weights(
                    df[TARGET_CLS_N_ALMA],
                    N_ALMA_CLASSES,
                )
            ),
            TARGET_CLS_N_CANTONERA: (
                self._count_weights(
                    df[
                        TARGET_CLS_N_CANTONERA
                    ],
                    N_CANTONERA_CLASSES,
                )
            ),
        }

        return self

    @staticmethod
    def _count_weights(
        values,
        n_classes,
    ):
        """
        Calcula pesos inversamente proporcionales a la frecuencia.

        Los pesos se normalizan para que tengan media uno.
        """
        values = np.asarray(
            values,
            dtype=int,
        )

        classes = np.arange(
            n_classes
        )

        counts = np.array(
            [
                max(
                    (values == clase).sum(),
                    1,
                )
                for clase in classes
            ],
            dtype=float,
        )

        weights = (
            len(values)
            / (
                n_classes
                * counts
            )
        )

        return (
            weights
            / weights.mean()
        ).astype(np.float32)

    @property
    def cat_cardinalities(self):
        return [
            len(
                self.cat_encoders[
                    columna
                ].classes_
            )
            for columna
            in CATEGORICAL_FEATURES
        ]

    @property
    def n_standard_classes(self):
        return len(
            self.standard_encoder.classes_
        )

    @property
    def p_label_classes(self):
        if (
            getattr(
                self,
                "p_label_encoder",
                None,
            )
            is not None
        ):
            return list(
                self.p_label_encoder.classes_
            )

        return None

    @property
    def p_transition_classes(self):
        return list(
            P_TRANSITION_CLASSES
        )

    def _encode_p_labels(self, df):
        """
        Codifica las columnas legacy p1_label...p12_label.

        Si las columnas no existen, devuelve una matriz de ceros.
        """
        encoder = getattr(
            self,
            "p_label_encoder",
            None,
        )

        labels_available = all(
            columna in df.columns
            for columna in P_LABEL_COLUMNS
        )

        if (
            encoder is not None
            and labels_available
        ):
            encoded = np.stack(
                [
                    encoder.transform(
                        df[columna].astype(str)
                    )
                    for columna
                    in P_LABEL_COLUMNS
                ],
                axis=1,
            )

            return encoded.astype(
                np.int64
            )

        return np.zeros(
            shape=(
                len(df),
                len(P_LABEL_COLUMNS),
            ),
            dtype=np.int64,
        )

    def transform_features(self, df):
        """
        Transforma las entradas categóricas y numéricas.
        """
        x_cat = np.stack(
            [
                self.cat_encoders[
                    columna
                ].transform(
                    df[columna].astype(str)
                )
                for columna
                in CATEGORICAL_FEATURES
            ],
            axis=1,
        )

        x_num = self.num_scaler.transform(
            df[NUMERIC_FEATURES].to_numpy()
        )

        return (
            x_cat.astype(np.int64),
            x_num.astype(np.float32),
        )

    def transform_targets(self, df):
        """
        Transforma todos los targets del modelo.
        """
        standard_idx = (
            self.standard_encoder.transform(
                df["standard"].astype(str)
            )
        )

        bolt_mm = bolt_nominal_mm(df)

        bolt_idx = (
            bolt_mm
            .map(BOLT_TO_IDX)
            .to_numpy()
        )

        if pd.isna(bolt_idx).any():
            unknown_bolts = sorted(
                set(
                    bolt_mm[
                        pd.isna(bolt_idx)
                    ]
                )
            )

            raise ValueError(
                "Existen tornillos fuera de "
                f"CATALOGO_BOLT: {unknown_bolts}"
            )

        slip_critical = (
            df["SlipCritical"]
            .astype(str)
            .str.upper()
            .isin(
                [
                    "YES",
                    "TRUE",
                    "1",
                ]
            )
            .astype(np.float32)
            .to_numpy()
        )

        n_alma_idx = (
            df["n_alma"]
            .astype(int)
            .to_numpy()
        )

        n_cantonera_idx = (
            df["n_cantonera"]
            .astype(int)
            .to_numpy()
        )

        if (
            (n_alma_idx < 0).any()
            or (
                n_alma_idx
                >= N_ALMA_CLASSES
            ).any()
        ):
            raise ValueError(
                "n_alma contiene valores fuera "
                f"del rango 0...{N_ALMA_CLASSES - 1}."
            )

        if (
            (n_cantonera_idx < 0).any()
            or (
                n_cantonera_idx
                >= N_CANTONERA_CLASSES
            ).any()
        ):
            raise ValueError(
                "n_cantonera contiene valores fuera "
                f"del rango 0...{N_CANTONERA_CLASSES - 1}."
            )

        reg_always = (
            self.reg_always_scaler.transform(
                df[
                    REGRESSION_ALWAYS
                ].to_numpy()
            )
            .astype(np.float32)
        )

        masked_real = (
            df[MASKED_COLUMNS]
            .fillna(0.0)
            .to_numpy(dtype=np.float32)
        )

        masked_mask = (
            masked_real > 0.0
        ).astype(np.float32)

        masked_value = (
            (
                masked_real
                - self.masked_mean
            )
            / self.masked_std
        ).astype(np.float32)

        p_label_idx = (
            self._encode_p_labels(df)
        )

        p_transition_idx = (
            transition_indices_from_counts(
                n_alma_values=n_alma_idx,
                n_cantonera_values=(
                    n_cantonera_idx
                ),
                n_p=N_Y,
            )
        )

        return {
            "standard_idx": (
                standard_idx.astype(
                    np.int64
                )
            ),
            "bolt_idx": (
                bolt_idx.astype(
                    np.int64
                )
            ),
            "slip_critical": (
                slip_critical
            ),
            "n_alma_idx": (
                n_alma_idx.astype(
                    np.int64
                )
            ),
            "n_cantonera_idx": (
                n_cantonera_idx.astype(
                    np.int64
                )
            ),
            "reg_always": (
                reg_always
            ),
            "masked_value": (
                masked_value
            ),
            "masked_mask": (
                masked_mask
            ),
            "p_label_idx": (
                p_label_idx
            ),
            "p_transition_idx": (
                p_transition_idx
            ),
        }

    def inverse_reg_always(
        self,
        standardized,
    ):
        """
        Desestandariza g, e, d, Bp y tp.
        """
        return (
            self.reg_always_scaler
            .inverse_transform(
                standardized
            )
        )

    def inverse_masked(
        self,
        standardized,
    ):
        """
        Desestandariza p1...p12 y rigidizadores.
        """
        return (
            standardized
            * self.masked_std
            + self.masked_mean
        )


# ---------------------------------------------------------------------------
# DATASET DE PYTORCH
# ---------------------------------------------------------------------------

class ConnectionDataset(Dataset):
    """
    Dataset PyTorch para el modelo de diseño de conexiones.
    """

    def __init__(
        self,
        df,
        preprocessor: Preprocessor,
    ):
        self.x_cat, self.x_num = (
            preprocessor.transform_features(df)
        )

        self.targets = (
            preprocessor.transform_targets(df)
        )

        self.n = len(df)

    def __len__(self):
        return self.n

    def __getitem__(self, idx):
        item = {
            "x_cat": torch.tensor(
                self.x_cat[idx],
                dtype=torch.long,
            ),
            "x_num": torch.tensor(
                self.x_num[idx],
                dtype=torch.float32,
            ),
        }

        for nombre, valores in (
            self.targets.items()
        ):
            valor = valores[idx]

            if nombre in {
                "standard_idx",
                "bolt_idx",
                "n_alma_idx",
                "n_cantonera_idx",
                "p_label_idx",
                "p_transition_idx",
            }:
                dtype = torch.long

            else:
                dtype = torch.float32

            item[nombre] = torch.tensor(
                valor,
                dtype=dtype,
            )

        return item