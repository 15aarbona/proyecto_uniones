"""
Definición central de columnas, catálogos y roles.

- p1..p12 : PASOS RELATIVOS entre filas de tornillos consecutivas ( p_i = Y_i - Y_{i-1},
              con p1 = Y1 - e). Las p activas son SIEMPRE un prefijo p1..p_k (p=0 =>
              "no existe esa fila"); el nº de p activas = n_alma + n_cantonera + 1 (las que
              desaparecen son las del final). El modelo LAS PREDICE DIRECTAMENTE (con máscara
              de presencia); las Ys ya NO se derivan ni se persisten:
              desaparecen del schema persistido y del output del modelo).
  - p1_label..p12_label : (ELIMINADO) ya no se predicen las clases de zona; la
              confusión de roles la manejan n_alma / n_cantonera + el clamp de post-proceso.
  - n_alma,n_cantonera : nº de filas de tornillos entre las alas de la viga y nº de
              filas en la cantonera(por debajo del ala inferior].
              Relación exacta verificada en el dataset:
                  num_filas = n_alma + n_cantonera + 2
                  nº de p activas = num_filas -  1 = n_alma + n_cantonera + 1
              n_sup (fila 1, cota e) y n_inf (última fila, bajo el ala inferior) son
              siempre 1, por eso el +2. Ambos conteos están DESBALANCEADOS (los valores
              altos son mucho menos probables): la loss usa CE ponderada.
  - standard (normativa, 4 valores) sustituye a DrawingCode como head de clasificación.
  - La máscara de presencia por columna se mantiene (BCE), aunque el nº real de Ys
    activas queda determinado por n_alma + n_cantonera: en post-proceso el prefijo se
    fuerza con los conteos predichos.

INPUT REAL DE PRODUCCIÓN (sin cambios): UNICODE, BEAM, COLUMN, Capacity_Moment,
Capacity_Shear, Capacity_Axial, grado_acero, clase_tornillo. Features = esas columnas
más las derivadas directamente de ellas (lookup Tekla de BEAM/COLUMN y tablas de
resistencias de grado_acero/clase_tornillo).
"""

# ---------------------------------------------------------------------------
# INPUT REAL DE PRODUCCIÓN
# ---------------------------------------------------------------------------
RAW_INPUT_COLUMNS = [
    "UNICODE", "BEAM", "COLUMN",
    "Capacity_Moment", "Capacity_Shear", "Capacity_Axial",
    "grado_acero", "clase_tornillo",
]

# ---------------------------------------------------------------------------
# FEATURES QUE ALIMENTAN LA RED (tras lookup/feature engineering)
# ---------------------------------------------------------------------------
CATEGORICAL_FEATURES = [
    "BEAM_type", "COLUMN_type",   # HE/W/IPE/HI - derivable del propio código de perfil
    "grado_acero",                  # p.ej. S275JR / S355JR (viene directo del input)
    "clase_tornillo",               # p.ej. 8.8 / 10.9 / A325M (viene directo del input)
]

NUMERIC_FEATURES = [
    # Geometría de viga (lookup por BEAM)
    "BEAM_d_mm", "BEAM_bf_mm", "BEAM_tw_mm", "BEAM_tf_mm", # investigar quitar tw
    # Geometría de columna (lookup por COLUMN)
    "COLUMN_d_mm", "COLUMN_bf_mm", "COLUMN_tw_mm", "COLUMN_tf_mm",
    # Propiedades mecánicas (lookup por grado_acero / clase_tornillo)
    "fy_acero_mpa", "fu_acero_mpa", "fy_tornillo_mpa", "fu_tornillo_mpa", "fv_tornillo_mpa",
    # Demanda: capacidades ABSOLUTAS (decisión: se usan en vez de los porcentajes)
    "Capacity_Moment", "Capacity_Shear", "Capacity_Axial",
    "Capacity_Moment_Percentage", "Capacity_Shear_Percentage", "Capacity_Axial_Percentage"
]

FEATURE_COLUMNS = CATEGORICAL_FEATURES + NUMERIC_FEATURES

# ---------------------------------------------------------------------------
# TARGETS REALES A PREDECIR (todo lo que hay que diseñar)
# ---------------------------------------------------------------------------

# Clasificación
TARGET_CLS_STANDARD = "standard"                  # normativa (AISC-360-05/10, EN 1993-1-8, ...)
TARGET_CLS_BOLT = "Bolt"                          # diámetro nominal del tornillo (int, sin 'M')
TARGET_CLS_SLIP_CRITICAL = "SlipCritical"        # bool
TARGET_CLS_N_ALMA = "n_alma"                      # nº filas entre las alas (0..6)  -- NUEVO
TARGET_CLS_N_CANTONERA = "n_cantonera"            # nº filas en cantonera (0..5)  -- NUEVO

N_Y = 12

CLASSIFICATION_TARGETS = [
    TARGET_CLS_STANDARD, TARGET_CLS_BOLT, TARGET_CLS_SLIP_CRITICAL,
    TARGET_CLS_N_ALMA, TARGET_CLS_N_CANTONERA,
]

# Regresión SIEMPRE activa: g, e, d, Bp, tp. (Lp NO se predice ni se infiere; estaba
# determinado por 2e + sum(p). Lh se trata con máscara, ver MASKED_COLUMNS.)
REGRESSION_ALWAYS = ["g", "e", "d", "Bp", "tp"]

# Regresión CON MÁSCARA (0 = "no existe esa fila/rigidizador/cartabón"). Pasos p1..p12
# primero, luego rigidizadores y por último Lh (longitud del cartabón; con máscara para
# separar "tiene cartabón" de "longitud del cartabón").
N_Y = 12
Y_COLUMNS = [f"Y{i}" for i in range(1, N_Y + 1)]      # cotas acumuladas DERIVADAS en post-proceso
P_COLUMNS = [f"p{i}" for i in range(1, N_Y + 1)]       # pasos relativos:TARGETS CON MÁSCARA
STIFFENER_COLUMNS = ["tws", "ts", "tbs", "tst"]
MASKED_COLUMNS = P_COLUMNS + STIFFENER_COLUMNS + ["Lh"]

# Pasos relativos entre filas de tornillos (representación persistida en el dataset
# global; las p se predican DESDE EL MODELO (con máscara); las Ys se derivan en post-proceso):
#   Y1 = e + p1,  Y_i = e + p1 + ... + p_i   (0 si p_i = 0),  p_i = Y_i - Y_{i-1}

REGRESSION_TARGETS = REGRESSION_ALWAYS + MASKED_COLUMNS
ALL_TARGETS = CLASSIFICATION_TARGETS + REGRESSION_TARGETS

# nº máximo de filas de tornillos = 1 (cota e) + nº máx. de Ys = 13
MAX_NUM_FILAS = 1 + N_Y

# Rangos de clases para los conteos (observados en train_v3; los valores altos son
# muy poco frecuentes -> CE ponderada por frecuencia inversa).
N_ALMA_CLASSES = 7        # 0..6
N_CANTONERA_CLASSES = 6   # 0..5

# Rol geométrico por paso (esquema zona-colapsado). Fronteras a tf/2 (mitad del ala) para
# proyectar las zonas físicas reales y evitar errores en transiciones (soldadura/radio).
ROLE_CLASSES = ["TOP", "BEAM_INTERIOR", "BOTTOM", "HAUNCH", "SIN_CARTABON"]
N_ROLE_CLASSES = len(ROLE_CLASSES)

# Columnas derivadas 100% por aritmética en post-proceso (no tienen cabeza):
#   Hole    = Bolt + 2
#   num_filas_tornillos = n_alma + n_cantonera + 2
#   tiene_cantonera = n_cantonera > 0
#   p1..p12 son TARGETS (ver MASKED_COLUMNS); Y1..Y12 derivadas = e + cumsum(p) (opcional, para sistemas aguas abajo)
DERIVED_COLUMNS = ["Hole", "num_filas_tornillos", "tiene_cantonera"]

# ---------------------------------------------------------------------------
# CATÁLOGOS COMERCIALES (corregidos contra los valores reales del dataset)
# ---------------------------------------------------------------------------
CATALOGO_BOLT = [16, 20, 22, 24, 27, 30, 36]

CATALOGO_g = list(range(80, 171, 5))
CATALOGO_e = list(range(35, 76, 5))
CATALOGO_Bp = list(range(140, 400, 1))
CATALOGO_tp = [12, 15, 20, 25, 30, 35, 40, 45, 50, 60]
# d hoy NO se ajusta a catálogo (sale como 50.0079, etc.). Si en train es siempre múltiplo de 5,
# poner p.ej. list(range(35, 101, 5)); afecta a la coherencia con e/Y1.
CATALOGO_d = None
CATALOGO_Lh = None                                      # continuo (40..715), no snap
CATALOGO_tws = [0, 6, 8, 10, 12, 15, 20] # hay un caso de 5
CATALOGO_ts = [0, 10, 12, 15, 20, 25, 30, 35, 40]
CATALOGO_tbs = [0, 10, 12, 15, 20, 25, 30, 35, 40]
CATALOGO_tst = [0, 10, 15, 20]

# Ys: cotas acumuladas; e y los p subyacentes son (casi siempre) múltiplos de 5 mm.
# En post-proceso se snapean a esta rejilla.
Y_GRID_STEP = 5

# --- Regla 2: constructabilidad de los pasos p (post-proceso) ---------------------
# En el dataset real los pasos activos van de 45 a ~301 mm (98% múltiplos de 5).
# Si el modelo predice una fila (presencia activa) pero el valor decodificado queda
# por debajo de P_MIN_PITCH, esa fila se ELIMINA (no se inventa una distancia),
# recortando el prefijo para que el nº de filas quede coherente.
P_MIN_PITCH = 40.0
P_MAX_PITCH = 350.0
# Holgura mínima al cruzar el ala inferior: BEAM_tf_mm + BEAM_r1_mm + margen.
FLANGE_CLEARANCE_MARGIN = 10.0
# Reconciliación del prefijo: si los conteos (n_alma+n_cantonera) se quedan cortos pero
# la cabeza de presencia del siguiente paso es alta y su valor es plausible, se EXTIENDE
# el prefijo (evita poner a 0 pasos reales -> quita outliers negativos grandes).
P_EXTEND_THRESHOLD = 0.5
P_EXTEND_MAX = 0

# grado_acero -> (fy, fu) MPa
ACERO_TABLE = {
    "S275JR": {"fy_acero_mpa": 275.0, "fu_acero_mpa": 430.0},
    "S355JR": {"fy_acero_mpa": 355.0, "fu_acero_mpa": 490.0},
}

# clase_tornillo -> (fy, fu, fv) MPa
TORNILLO_TABLE = {
    "8.8":   {"fy_tornillo_mpa": 640.0, "fu_tornillo_mpa": 800.0, "fv_tornillo_mpa": 480.0},
    "10.9":  {"fy_tornillo_mpa": 900.0, "fu_tornillo_mpa": 1000.0, "fv_tornillo_mpa": 500.0},
    "A325M": {"fy_tornillo_mpa": 660.0, "fu_tornillo_mpa": 830.0, "fv_tornillo_mpa": 372.0},
}
