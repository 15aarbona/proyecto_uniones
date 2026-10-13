"""Esquema del dataset de reentreno (columnas de `data/data_final.csv`).

`TRAIN_COLUMNS` es el orden exacto del parquet unificado; el tipo de cada columna se usa
para coercionar al traducir. Referencia: `data/data_final.csv`.
"""

TRAIN_COLUMNS = [
    # demanda
    "Capacity_Moment_Percentage", "Capacity_Moment",
    "Capacity_Shear_Percentage", "Capacity_Shear",
    "Capacity_Axial_Percentage", "Capacity_Axial",
    # diseno (chapa / pasos / rigidizadores)
    "g", "tws", "Bp", "Lp", "tp", "Lh", "e", "d",
    "p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8", "p9", "p10", "p11", "p12",
    "ts", "tbs", "tst", "Hole",
    # identificacion / metadatos
    "Unicode", "BEAM", "COLUMN", "DrawingCode", "Bolt", "SlipCritical",
    "Normativas", "AceroEstructural", "EstandarTornillos", "Source",
    "National_Annex", "standard",
    # geometria viga
    "BEAM_d_mm", "BEAM_bf_mm", "BEAM_tw_mm", "BEAM_tf_mm", "BEAM_A_mm",
    "BEAM_w_kgm", "BEAM_iy_mm", "BEAM_iz_mm", "BEAM_wely_mm", "BEAM_welz_mm",
    # geometria columna
    "COLUMN_d_mm", "COLUMN_bf_mm", "COLUMN_tw_mm", "COLUMN_tf_mm", "COLUMN_A_mm",
    "COLUMN_w_kgm", "COLUMN_iy_mm", "COLUMN_iz_mm", "COLUMN_wely_mm", "COLUMN_welz_mm",
    # materiales
    "fy_acero_mpa", "fu_acero_mpa",
    "fy_tornillo_mpa", "fu_tornillo_mpa", "fv_tornillo_mpa",
    # conteos
    "n_alma", "n_cantonera",
]

TEXT_COLUMNS = {
    "Unicode", "BEAM", "COLUMN", "DrawingCode", "Normativas",
    "AceroEstructural", "EstandarTornillos", "Source", "National_Annex", "standard",
}

BOOL_COLUMNS = {"SlipCritical"}

NUMERIC_COLUMNS = [
    c for c in TRAIN_COLUMNS if c not in TEXT_COLUMNS and c not in BOOL_COLUMNS
]
