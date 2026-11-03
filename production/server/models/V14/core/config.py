"""Constantes del modelo PINN (catalogos alineados con V11 / refinar.py)."""

RAW_INPUT_COLUMNS = [
    "UNICODE", "Normativas", "BEAM", "COLUMN",
    "ratio_moment", "ratio_shear", "ratio_axial",
    "grado_acero", "clase_tornillo",
]
OPTIONAL_INPUT_COLUMNS = ["Normativas", "grado_acero", "clase_tornillo"]
NORMATIVAS = ["EN 1993-1-8", "AISC-360-05/10", "CSA S16-09"]

CATEGORICAL_FEATURES = ["grado_acero", "clase_tornillo"]

# Entrada de 21 variables del notebook (en este orden exacto). Se construye a partir de
# estas columnas del dataframe de features (ver dataset.Preprocessor.transform).
GEOMETRY_COLUMNS = [
    "BEAM_d_mm", "BEAM_b_mm", "BEAM_tf_mm", "BEAM_tw_mm", "BEAM_r1_mm",
    "COLUMN_d_mm", "COLUMN_b_mm", "COLUMN_tf_mm", "COLUMN_tw_mm", "COLUMN_r1_mm",
]
INPUT_DIM = 21

# Valores por defecto del notebook si el perfil no trae el dato
GEOM_DEFAULTS = {
    "BEAM_d_mm": 300.0, "BEAM_b_mm": 150.0, "BEAM_tf_mm": 10.7, "BEAM_tw_mm": 7.1, "BEAM_r1_mm": 15.0,
    "COLUMN_d_mm": 260.0, "COLUMN_b_mm": 260.0, "COLUMN_tf_mm": 12.5, "COLUMN_tw_mm": 7.5, "COLUMN_r1_mm": 24.0,
}

N_Y = 12
BOLT_DIAMETERS = [16, 20, 22, 24, 27, 30, 36]
ROWS_CHOICES = [2, 3, 4, 5, 6]          # cabeza num_rows: 5 clases

CATALOGO_BOLT = BOLT_DIAMETERS
CATALOGO_g = list(range(80, 171, 5))
CATALOGO_e = list(range(35, 76, 5))
CATALOGO_Bp = list(range(140, 400))
CATALOGO_tp = [12, 15, 20, 25, 30, 35, 40, 45, 50, 60]

PFI_MIN_MM = 5.0        # pfi = p1 - pfo - tf debe ser >= 5 (codame.PFI_MIN_SEGURIDAD)
PFO_MIN_MM = 25.0
PFO_MAX_MM = 100.0