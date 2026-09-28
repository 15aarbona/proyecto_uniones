"""Configuración del modelo V3 basado en p1_label..p12_label."""
CATEGORICAL_FEATURES = [
    "BEAM_type", "COLUMN_type", "grado_acero", "clase_tornillo", "Source", "standard",
]
NUMERIC_FEATURES = [
    "BEAM_d_mm", "BEAM_bf_mm", "BEAM_tw_mm", "BEAM_tf_mm", "BEAM_r1_mm", "BEAM_wely_mm", "BEAM_w_kgm",
    "COLUMN_d_mm", "COLUMN_bf_mm", "COLUMN_tw_mm", "COLUMN_tf_mm", "COLUMN_r1_mm", "COLUMN_wely_mm", "COLUMN_w_kgm",
    "fy_acero_mpa", "fu_acero_mpa", "fy_tornillo_mpa", "fu_tornillo_mpa", "fv_tornillo_mpa",
    "Capacity_Moment", "Capacity_Shear", "Capacity_Axial",
]
ID_COLUMNS = ["BEAM", "COLUMN"]
P_COLUMNS = [f"p{i}" for i in range(1, 13)]
P_LABEL_COLUMNS = [f"p{i}_label" for i in range(1, 13)]
REGRESSION_ALWAYS = ["g", "Bp", "Lp", "tp", "e", "d"]
STIFFENER_COLUMNS = ["tws", "ts", "tbs", "tst"]
MASKED_VALUE_COLUMNS = P_COLUMNS + STIFFENER_COLUMNS
CLASSIFICATION_TARGETS = ["DrawingCode", "Bolt", "SlipCritical"]
CATALOGO_BOLT = [16, 20, 22, 24, 27, 30, 36]
CATALOGS = {
    "g": list(range(80, 171, 5)), "Bp": list(range(140, 401)),
    "Lp": None, "tp": [12, 15, 20, 25, 30, 35, 40, 45, 50, 60],
    "e": list(range(35, 76, 5)), "d": None,
    "tws": [0, 6, 8, 10, 12, 15, 20], "ts": [0, 10, 12, 15, 20, 25, 30, 35, 40],
    "tbs": [0, 10, 12, 15, 20, 25, 30, 35, 40], "tst": [0, 10, 15, 20],
}
REQUIRED_COLUMNS = CATEGORICAL_FEATURES + NUMERIC_FEATURES + P_COLUMNS + P_LABEL_COLUMNS + REGRESSION_ALWAYS + STIFFENER_COLUMNS + CLASSIFICATION_TARGETS
