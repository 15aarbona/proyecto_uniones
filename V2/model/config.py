"""
Definición central de columnas, catálogos y roles.
v3: p1..p12 deja de ser un target del modelo. Se sustituye por variables con significado
    fijo (E-S, D_1..D_5, I-C, C_1..C_5, E-C) derivadas de p1..p12+e+d+BEAM_d_mm mediante
    geometry.gaps_from_p, tratadas como regresión con máscara igual que los rigidizadores
    (ver geometry.py / model.py / losses.py). p_k mezclaba roles distintos según la
    topología (a veces D, a veces I-C, a veces cantonera) y eso lo volvía multimodal;
    cada variable nombrada tiene un único rol en todas las muestras.

Corrige los desajustes detectados en model2.ipynb:
 - Bolt catalog incompleto (faltaba M22)
 - Targets incompletos (faltaban Lp, Hole, ts, tbs, tst, DrawingCode, SlipCritical)
 - D_1..D_5 / E-S / E-C / I-C / num_filas_tornillos / tiene_cantonera NO son features
   independientes: son 100% derivables de (p1..p12, e, d, BEAM_d_mm). No se modelan,
   se recalculan en post-proceso con la misma lógica de variables.ipynb (ver postprocess.py).
 - Hole es prácticamente Bolt + 2 mm -> se deriva, no se modela como target propio
   (se deja como chequeo de consistencia, no como salida de red).
"""

# ---------------------------------------------------------------------------
# INPUT REAL DE PRODUCCIÓN
# ---------------------------------------------------------------------------
# NOTA: fictional.csv traía Capacity_*_Percentage, pero se decidió entrenar con las
# capacidades ABSOLUTAS (ya presentes en train/test.parquet). El input de producción
# tendrá que traer Capacity_Moment/Shear/Axial en vez de los porcentajes.
RAW_INPUT_COLUMNS = [
    "UNICODE", "BEAM", "COLUMN",
    "Capacity_Moment", "Capacity_Shear", "Capacity_Axial",
    "grado_acero", "clase_tornillo",
]

# ---------------------------------------------------------------------------
# FEATURES QUE ALIMENTAN LA RED (tras el paso de lookup/feature engineering)
# ---------------------------------------------------------------------------
CATEGORICAL_FEATURES = [
    "BEAM_type", "COLUMN_type",   # HE/W/IPE/HI - derivable del propio código de perfil
    "grado_acero",                  # p.ej. S275JR / S355JR (viene directo del input)
    "clase_tornillo",               # p.ej. 8.8 / 10.9 / A325M (viene directo del input)
]

NUMERIC_FEATURES = [
    # Geometría de viga (lookup por BEAM)
    "BEAM_d_mm", "BEAM_bf_mm", "BEAM_tw_mm", "BEAM_tf_mm", "BEAM_r1_mm", "BEAM_wely_mm", "BEAM_w_kgm",
    # Geometría de columna (lookup por COLUMN)
    "COLUMN_d_mm", "COLUMN_bf_mm", "COLUMN_tw_mm", "COLUMN_tf_mm", "COLUMN_r1_mm", "COLUMN_wely_mm", "COLUMN_w_kgm",
    # Propiedades mecánicas (lookup por grado_acero / clase_tornillo)
    "fy_acero_mpa", "fu_acero_mpa", "fy_tornillo_mpa", "fu_tornillo_mpa", "fv_tornillo_mpa",
    # Demanda: capacidades ABSOLUTAS (decisión: se usan en vez de los porcentajes)
    "Capacity_Moment", "Capacity_Shear", "Capacity_Axial",
]

FEATURE_COLUMNS = CATEGORICAL_FEATURES + NUMERIC_FEATURES

# ---------------------------------------------------------------------------
# TARGETS REALES A PREDECIR (todo lo que hay que diseñar)
# ---------------------------------------------------------------------------

# Clasificación
TARGET_CLS_DRAWING_CODE = "DrawingCode"          # plantilla/topología de la unión (MLE, MHE, ...)
TARGET_CLS_BOLT = "Bolt"                          # diámetro nominal del tornillo
TARGET_CLS_SLIP_CRITICAL = "SlipCritical"        # YES/NO

CLASSIFICATION_TARGETS = [TARGET_CLS_DRAWING_CODE, TARGET_CLS_BOLT, TARGET_CLS_SLIP_CRITICAL]

# Regresión SIEMPRE activa (no dependen de si hay o no cierta fila/rigidizador)
REGRESSION_ALWAYS = ["g", "e", "d", "Bp", "Lp", "tp"]

# Regresión CON MÁSCARA (pueden valer 0 = "no existe esa fila/rigidizador")
P_COLUMNS = [f"p{i}" for i in range(1, 13)]
STIFFENER_COLUMNS = ["tws", "ts", "tbs", "tst"]
REGRESSION_MASKED = P_COLUMNS + STIFFENER_COLUMNS

REGRESSION_TARGETS = REGRESSION_ALWAYS + REGRESSION_MASKED

ALL_TARGETS = CLASSIFICATION_TARGETS + REGRESSION_TARGETS

# Columnas que NO se modelan porque son 100% derivables (ver postprocess.py)
# v3: D_1..D_5, E-S, I-C, C_1..C_5, E-C pasan a MODELARSE (ver GEOM_COLUMNS más abajo).
# Solo quedan como derivadas puramente aritméticas (ver geometry.assemble_from_named):
DERIVED_COLUMNS = ["Hole", "num_filas_tornillos", "tiene_cantonera"]

# ---------------------------------------------------------------------------
# CATÁLOGOS COMERCIALES (corregidos contra los valores reales del dataset)
# ---------------------------------------------------------------------------
CATALOGO_BOLT = [16, 20, 22, 24, 27, 30, 36]          # antes faltaba 22 en model2.ipynb
MAX_D = 5   # nº máx. de D_i modelados (huecos interiores dentro de la viga)
MAX_C = 5   # nº máx. de C_i modelados (huecos interiores dentro de la cantonera) -- NUEVO
D_COLUMNS = [f"D_{i}" for i in range(1, MAX_D + 1)]
C_COLUMNS = [f"C_{i}" for i in range(1, MAX_C + 1)]
GEOM_COLUMNS = ["E-S"] + D_COLUMNS + ["I-C"] + C_COLUMNS + ["E-C"]
GEOM_GRID_STEP = 5   # los huecos observados son múltiplos de 5 mm; se snapea en postproceso

CATALOGO_g = list(range(80, 171, 5))
CATALOGO_e = list(range(35, 76, 5))
CATALOGO_Bp = list(range(140, 400, 1))
CATALOGO_Lp = None                                      # continuo, muy variable (250..1820), no snap
CATALOGO_tp = [12, 15, 20, 25, 30, 35, 40, 45, 50, 60]
# d hoy NO se ajusta a catálogo (sale como 50.0079, etc.). Si en train es siempre múltiplo de 5
# (el notebook lo comprueba en la sección 3), poner p.ej. list(range(35, 101, 5)); afecta a
# la posición del ala inferior en derive_dependent_columns.
CATALOGO_d = None
CATALOGO_tws = [0, 6, 8, 10, 12, 15, 20]
CATALOGO_ts = [0, 10, 12, 15, 20, 25, 30, 35, 40]
CATALOGO_tbs = [0, 10, 12, 15, 20, 25, 30, 35, 40]
CATALOGO_tst = [0, 10, 15, 20]

# grado_acero -> (fy, fu) MPa  (idéntico a variables.ipynb, cell "AÑADIR RESISTENCIAS")
ACERO_TABLE = {
    "S275JR": {"fy_acero_mpa": 275.0, "fu_acero_mpa": 430.0},
    "S355JR": {"fy_acero_mpa": 355.0, "fu_acero_mpa": 490.0},
}

# clase_tornillo -> (fy, fu, fv) MPa (idéntico a variables.ipynb)
TORNILLO_TABLE = {
    "8.8":   {"fy_tornillo_mpa": 640.0, "fu_tornillo_mpa": 800.0, "fv_tornillo_mpa": 480.0},
    "10.9":  {"fy_tornillo_mpa": 900.0, "fu_tornillo_mpa": 1000.0, "fv_tornillo_mpa": 500.0},
    "A325M": {"fy_tornillo_mpa": 660.0, "fu_tornillo_mpa": 830.0, "fv_tornillo_mpa": 372.0},
}


# ---------------------------------------------------------------------------
# p1..p12 como clasificación sobre rejilla (v2)
# ---------------------------------------------------------------------------
N_P = len(P_COLUMNS)          # 12 huecos como máximo
N_ROWS_CLASSES = N_P + 1      # nº de pasos activos: 0..12
P_STEP = 5                    # paso de la rejilla en mm (los p reales son múltiplos de 5)
P_SOFT_SIGMA = 1.0            # suavizado de etiquetas en nº de clases (1.0 = ±5 mm)

# Objetivos de regresión con máscara (v3): geometría con significado fijo + rigidizadores.
# p1..p12 ya NO es un target del modelo; sigue existiendo como dato de entrada crudo (para
# derivar GEOM_COLUMNS en entrenamiento, vía geometry.gaps_from_p) y como salida opcional
# reconstruida (geometry.p_from_named) para compatibilidad con sistemas aguas abajo.
MASKED_COLUMNS = GEOM_COLUMNS + STIFFENER_COLUMNS
