"""
Definición central de columnas, catálogos, targets y roles.

Representación de las filas de tornillos
----------------------------------------

- La primera fila de tornillos está situada en la cota `e`.

- p1...p12 son las distancias relativas entre filas consecutivas:

      p1 = Y1 - e
      p2 = Y2 - Y1
      ...
      pi = Yi - Y(i-1)

- Las p activas siempre forman un prefijo:

      p1, p2, ..., pk

  Las p posteriores son cero.

- La estructura de una conexión cumple:

      numero_filas = n_alma + n_cantonera + 2

      numero_p_activas = numero_filas - 1
                       = n_alma + n_cantonera + 1

- La primera y la última fila siempre existen:

      superior
      ...
      inferior

- n_alma es el número de filas de tornillos dentro de la viga.

- n_cantonera es el número de filas de tornillos dentro de la
  cantonera.

Las posiciones Y no se almacenan como targets. Se pueden derivar:

    Y1 = e + p1
    Y2 = e + p1 + p2
    ...
"""

# ---------------------------------------------------------------------------
# INPUT REAL DE PRODUCCIÓN
# ---------------------------------------------------------------------------

RAW_INPUT_COLUMNS = [
    "UNICODE",
    "BEAM",
    "COLUMN",
    "Capacity_Moment",
    "Capacity_Shear",
    "Capacity_Axial",
    "grado_acero",
    "clase_tornillo",
]


# ---------------------------------------------------------------------------
# FEATURES DEL MODELO
# ---------------------------------------------------------------------------

CATEGORICAL_FEATURES = [
    "BEAM_type",
    "COLUMN_type",
    "grado_acero",
    "clase_tornillo",
]


NUMERIC_FEATURES = [
    # Geometría de la viga
    "BEAM_d_mm",

    # Geometría de la columna
    "COLUMN_d_mm",

    # Propiedades mecánicas del acero
    "fy_acero_mpa",
    "fu_acero_mpa",

    # Propiedades mecánicas del tornillo
    "fy_tornillo_mpa",
    "fu_tornillo_mpa",
    "fv_tornillo_mpa",

    # Capacidades requeridas
    "Capacity_Moment",
    "Capacity_Shear",
    "Capacity_Axial",
]


FEATURE_COLUMNS = (
    CATEGORICAL_FEATURES
    + NUMERIC_FEATURES
)


# ---------------------------------------------------------------------------
# TARGETS DE CLASIFICACIÓN
# ---------------------------------------------------------------------------

TARGET_CLS_STANDARD = "standard"
TARGET_CLS_BOLT = "Bolt"
TARGET_CLS_SLIP_CRITICAL = "SlipCritical"
TARGET_CLS_N_ALMA = "n_alma"
TARGET_CLS_N_CANTONERA = "n_cantonera"


# ---------------------------------------------------------------------------
# NÚMERO MÁXIMO DE SEPARACIONES
# ---------------------------------------------------------------------------

N_Y = 12

P_COLUMNS = [
    f"p{i}"
    for i in range(1, N_Y + 1)
]

Y_COLUMNS = [
    f"Y{i}"
    for i in range(1, N_Y + 1)
]


# ---------------------------------------------------------------------------
# ETIQUETAS LEGACY DE p
# ---------------------------------------------------------------------------
#
# Se conservan temporalmente para mantener compatibilidad con el modelo
# anterior. La nueva arquitectura utilizará p_transition_idx.
#
# Estas columnas pueden continuar existiendo en el dataset aunque su peso
# en la loss sea cero.
# ---------------------------------------------------------------------------

P_LABEL_COLUMNS = [
    f"p{i}_label"
    for i in range(1, N_Y + 1)
]

# Valor legacy. Si las etiquetas reales tienen otro número de clases,
# esta cabeza debería desactivarse con w_p_label=0.
N_P_LABEL_CLASSES = 11


# ---------------------------------------------------------------------------
# RANGOS DE LOS CONTEOS
# ---------------------------------------------------------------------------

N_ALMA_CLASSES = 7
N_CANTONERA_CLASSES = 6


CLASSIFICATION_TARGETS = [
    TARGET_CLS_STANDARD,
    TARGET_CLS_BOLT,
    TARGET_CLS_SLIP_CRITICAL,
    TARGET_CLS_N_ALMA,
    TARGET_CLS_N_CANTONERA,
] + P_LABEL_COLUMNS


# ---------------------------------------------------------------------------
# TARGETS DE REGRESIÓN
# ---------------------------------------------------------------------------

REGRESSION_ALWAYS = [
    "g",
    "e",
    "d",
    "Bp",
    "tp",
]


STIFFENER_COLUMNS = [
    "tws",
    "ts",
    "tbs",
    "tst",
]


MASKED_COLUMNS = (
    P_COLUMNS
    + STIFFENER_COLUMNS
)


REGRESSION_TARGETS = (
    REGRESSION_ALWAYS
    + MASKED_COLUMNS
)


ALL_TARGETS = (
    CLASSIFICATION_TARGETS
    + REGRESSION_TARGETS
)


MAX_NUM_FILAS = 1 + N_Y


# ---------------------------------------------------------------------------
# CLASIFICACIÓN GEOMÉTRICA DE LOS TORNILLOS
# ---------------------------------------------------------------------------

UNUSED_TRANSITION = "UNUSED"


def etiquetas_zona(nombre_zona, cantidad):
    """
    Clasifica las filas de tornillos de una zona, de arriba hacia abajo.

    Ejemplos
    --------

    1 fila:
        centro

    2 filas:
        primero
        inferior

    3 filas:
        primero
        centro
        inferior

    4 filas:
        primero
        centro superior
        centro inferior
        inferior

    5 filas:
        primero
        centro superior
        centro
        centro inferior
        inferior

    6 filas:
        primero
        centro superior
        centro superior
        centro inferior
        centro inferior
        inferior
    """
    cantidad = int(cantidad)

    if cantidad <= 0:
        return []

    if cantidad == 1:
        return [
            f"{nombre_zona} centro"
        ]

    if cantidad == 2:
        return [
            f"{nombre_zona} primero",
            f"{nombre_zona} inferior",
        ]

    etiquetas = [
        f"{nombre_zona} primero"
    ]

    for posicion in range(1, cantidad - 1):
        posicion_relativa = (
            posicion
            / (cantidad - 1)
        )

        if posicion_relativa < 0.5:
            etiqueta = (
                f"{nombre_zona} centro superior"
            )

        elif posicion_relativa == 0.5:
            etiqueta = (
                f"{nombre_zona} centro"
            )

        else:
            etiqueta = (
                f"{nombre_zona} centro inferior"
            )

        etiquetas.append(etiqueta)

    etiquetas.append(
        f"{nombre_zona} inferior"
    )

    return etiquetas


def secuencia_zonas_tornillos(
    n_alma,
    n_cantonera,
):
    """
    Construye la secuencia completa de tornillos de arriba hacia abajo.

    Orden:
        superior
        tornillos de cantonera
        tornillos de viga
        inferior
    """
    secuencia = ["superior"]

    secuencia += etiquetas_zona(
        nombre_zona="cantonera",
        cantidad=n_cantonera,
    )

    secuencia += etiquetas_zona(
        nombre_zona="viga",
        cantidad=n_alma,
    )

    secuencia.append("inferior")

    return secuencia


def secuencia_transiciones(
    n_alma,
    n_cantonera,
):
    """
    Devuelve las transiciones correspondientes a p1...pk.

    Cada p representa la transición entre dos tornillos consecutivos.
    """
    zonas = secuencia_zonas_tornillos(
        n_alma=n_alma,
        n_cantonera=n_cantonera,
    )

    return [
        f"{zona_superior}__{zona_inferior}"
        for zona_superior, zona_inferior
        in zip(
            zonas[:-1],
            zonas[1:],
        )
    ]


def crear_catalogo_transiciones():
    """
    Obtiene todas las transiciones posibles recorriendo todas las
    combinaciones válidas de n_alma y n_cantonera.
    """
    transiciones = {
        UNUSED_TRANSITION
    }

    for n_alma in range(N_ALMA_CLASSES):
        for n_cantonera in range(
            N_CANTONERA_CLASSES
        ):
            transiciones.update(
                secuencia_transiciones(
                    n_alma=n_alma,
                    n_cantonera=n_cantonera,
                )
            )

    # UNUSED primero para que tenga índice cero.
    transiciones_ordenadas = [
        UNUSED_TRANSITION
    ]

    transiciones_ordenadas += sorted(
        transicion
        for transicion in transiciones
        if transicion != UNUSED_TRANSITION
    )

    return transiciones_ordenadas


P_TRANSITION_CLASSES = (
    crear_catalogo_transiciones()
)


P_TRANSITION_TO_IDX = {
    nombre: indice
    for indice, nombre
    in enumerate(P_TRANSITION_CLASSES)
}


P_TRANSITION_UNUSED_IDX = (
    P_TRANSITION_TO_IDX[
        UNUSED_TRANSITION
    ]
)


N_P_TRANSITION_CLASSES = len(
    P_TRANSITION_CLASSES
)


# ---------------------------------------------------------------------------
# COLUMNAS DERIVADAS
# ---------------------------------------------------------------------------

DERIVED_COLUMNS = [
    "Hole",
    "num_filas_tornillos",
    "tiene_cantonera",
]


# ---------------------------------------------------------------------------
# CATÁLOGOS COMERCIALES
# ---------------------------------------------------------------------------

CATALOGO_BOLT = [
    16,
    20,
    22,
    24,
    27,
    30,
    36,
]


CATALOGO_g = list(
    range(80, 171, 5)
)


CATALOGO_e = list(
    range(35, 76, 5)
)


CATALOGO_Bp = list(
    range(140, 400, 1)
)


CATALOGO_tp = [
    12,
    15,
    20,
    25,
    30,
    35,
    40,
    45,
    50,
    60,
]


CATALOGO_d = None


CATALOGO_tws = [
    0,
    6,
    8,
    10,
    12,
    15,
    20,
]


CATALOGO_ts = [
    0,
    10,
    12,
    15,
    20,
    25,
    30,
    35,
    40,
]


CATALOGO_tbs = [
    0,
    10,
    12,
    15,
    20,
    25,
    30,
    35,
    40,
]


CATALOGO_tst = [
    0,
    10,
    15,
    20,
]


# Las p se ajustan a una rejilla de 5 mm.
Y_GRID_STEP = 5


# ---------------------------------------------------------------------------
# TABLAS DE MATERIALES
# ---------------------------------------------------------------------------

ACERO_TABLE = {
    "S275JR": {
        "fy_acero_mpa": 275.0,
        "fu_acero_mpa": 430.0,
    },
    "S355JR": {
        "fy_acero_mpa": 355.0,
        "fu_acero_mpa": 490.0,
    },
}


TORNILLO_TABLE = {
    "8.8": {
        "fy_tornillo_mpa": 640.0,
        "fu_tornillo_mpa": 800.0,
        "fv_tornillo_mpa": 480.0,
    },
    "10.9": {
        "fy_tornillo_mpa": 900.0,
        "fu_tornillo_mpa": 1000.0,
        "fv_tornillo_mpa": 500.0,
    },
    "A325M": {
        "fy_tornillo_mpa": 660.0,
        "fu_tornillo_mpa": 830.0,
        "fv_tornillo_mpa": 372.0,
    },
}