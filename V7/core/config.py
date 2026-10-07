"""Central configuration for the autoregressive connection model."""
RAW_INPUT_COLUMNS = [
    "UNICODE", "BEAM", "COLUMN", "Capacity_Moment", "Capacity_Shear",
    "Capacity_Axial", "grado_acero", "clase_tornillo",
]

CATEGORICAL_FEATURES = [
    "BEAM_type", "COLUMN_type", "grado_acero", "clase_tornillo",
]

# Only the profile depths are retained from beam and column geometry.
NUMERIC_FEATURES = [
    "BEAM_d_mm", "COLUMN_d_mm",
    "fy_acero_mpa", "fu_acero_mpa",
    "fy_tornillo_mpa", "fu_tornillo_mpa", "fv_tornillo_mpa",
    "Capacity_Moment", "Capacity_Shear", "Capacity_Axial",
]
FEATURE_COLUMNS = CATEGORICAL_FEATURES + NUMERIC_FEATURES

TARGET_CLS_STANDARD = "standard"
TARGET_CLS_BOLT = "Bolt"
TARGET_CLS_SLIP_CRITICAL = "SlipCritical"
TARGET_CLS_N_ALMA = "n_alma"
TARGET_CLS_N_CANTONERA = "n_cantonera"

N_Y = 12
P_COLUMNS = [f"p{i}" for i in range(1, N_Y + 1)]
Y_COLUMNS = [f"Y{i}" for i in range(1, N_Y + 1)]
N_ALMA_CLASSES = 7
N_CANTONERA_CLASSES = 6

REGRESSION_ALWAYS = ["g", "e", "d", "Bp", "tp"]
STIFFENER_COLUMNS = ["tws", "ts", "tbs", "tst"]
MASKED_COLUMNS = P_COLUMNS + STIFFENER_COLUMNS

CATALOGO_BOLT = [16, 20, 22, 24, 27, 30, 36]
CATALOGO_g = list(range(80, 171, 5))
CATALOGO_e = list(range(35, 76, 5))
CATALOGO_d = None
CATALOGO_Bp = list(range(140, 400))
CATALOGO_tp = [12, 15, 20, 25, 30, 35, 40, 45, 50, 60]
CATALOGO_tws = [0, 6, 8, 10, 12, 15, 20]
CATALOGO_ts = [0, 10, 12, 15, 20, 25, 30, 35, 40]
CATALOGO_tbs = [0, 10, 12, 15, 20, 25, 30, 35, 40]
CATALOGO_tst = [0, 10, 15, 20]
Y_GRID_STEP = 5

UNUSED_TRANSITION = "UNUSED"

def etiquetas_zona(nombre_zona, cantidad):
    """Classifies rows from top to bottom within one zone."""
    cantidad = int(cantidad)
    if cantidad <= 0:
        return []
    if cantidad == 1:
        return [f"{nombre_zona} centro"]
    if cantidad == 2:
        return [f"{nombre_zona} primero", f"{nombre_zona} inferior"]
    labels = [f"{nombre_zona} primero"]
    for pos in range(1, cantidad - 1):
        rel = pos / (cantidad - 1)
        if rel < 0.5:
            label = f"{nombre_zona} centro superior"
        elif rel == 0.5:
            label = f"{nombre_zona} centro"
        else:
            label = f"{nombre_zona} centro inferior"
        labels.append(label)
    labels.append(f"{nombre_zona} inferior")
    return labels

def secuencia_zonas_tornillos(n_alma, n_cantonera):
    zones = ["superior"]
    zones += etiquetas_zona("cantonera", n_cantonera)
    zones += etiquetas_zona("viga", n_alma)
    zones.append("inferior")
    return zones

def secuencia_transiciones(n_alma, n_cantonera):
    zones = secuencia_zonas_tornillos(n_alma, n_cantonera)
    return [f"{a}__{b}" for a, b in zip(zones[:-1], zones[1:])]

def crear_catalogo_transiciones():
    values = {UNUSED_TRANSITION}
    for na in range(N_ALMA_CLASSES):
        for nc in range(N_CANTONERA_CLASSES):
            values.update(secuencia_transiciones(na, nc))
    return [UNUSED_TRANSITION] + sorted(x for x in values if x != UNUSED_TRANSITION)

P_TRANSITION_CLASSES = crear_catalogo_transiciones()
P_TRANSITION_TO_IDX = {name: idx for idx, name in enumerate(P_TRANSITION_CLASSES)}
P_TRANSITION_UNUSED_IDX = P_TRANSITION_TO_IDX[UNUSED_TRANSITION]
N_P_TRANSITION_CLASSES = len(P_TRANSITION_CLASSES)
