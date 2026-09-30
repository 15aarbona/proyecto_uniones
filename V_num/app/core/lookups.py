"""
Reconstruye, para el momento de INFERENCIA, exactamente los mismos merges que hace
variables.ipynb para construir train/test.parquet a partir de un input "pobre"
como fictional.csv (UNICODE, BEAM, COLUMN, %capacidades, grado_acero, clase_tornillo).

Tabla de perfiles (BEAM/COLUMN -> dimensiones en mm): la fuente de verdad son los
catálogos tekla_eu.csv / tekla_cad.csv / tekla_faltante.csv (build_profile_lookup_from_tekla_csvs),
igual que en variables.ipynb. build_profile_lookup_from_df es un fallback más pobre
(solo cubre los perfiles que ya aparecen en train/test.parquet) útil para smoke tests.
"""
import re
import pandas as pd

from .config import ACERO_TABLE, TORNILLO_TABLE

PROFILE_GEOM_COLS = ["type", "d_mm", "bf_mm", "tw_mm", "tf_mm", "r1_mm", "wely_mm", "w_kgm"]


def build_profile_lookup_from_tekla_csvs(eu_path, cad_path, faltante_path) -> pd.DataFrame:
    """
    Réplica exacta de la celda "AÑADIR DATOS DE TEKLA" de variables.ipynb.
    Esta es la fuente de verdad completa (cubre perfiles que no aparecen en
    train/test.parquet, p.ej. la serie W690/W760 de fictional.csv).
    """
    eu = pd.read_csv(eu_path)
    cad = pd.read_csv(cad_path)
    resto = pd.read_csv(faltante_path)

    union = pd.concat([eu, cad, resto], ignore_index=True)
    union = union[["tekla_nomenclature_1", "type", "d_mm", "bf_mm", "tw_mm", "tf_mm", "r1_mm", "wely_mm", "w_kgm"]]
    union = union.drop_duplicates(subset="tekla_nomenclature_1").set_index("tekla_nomenclature_1")
    union.index.name = "profile"
    return union


def build_profile_lookup_from_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extrae, de un dataframe ya procesado (como test.parquet / train.parquet),
    la tabla única perfil -> geometría, usando tanto las filas BEAM_* como COLUMN_*.
    Sustituir por carga directa de los catálogos Tekla cuando estén disponibles.
    """
    beam_part = df[["BEAM", "BEAM_type", "BEAM_d_mm", "BEAM_bf_mm", "BEAM_tw_mm",
                     "BEAM_tf_mm", "BEAM_r1_mm", "BEAM_wely_mm", "BEAM_w_kgm"]].copy()
    beam_part.columns = ["profile"] + PROFILE_GEOM_COLS

    col_part = df[["COLUMN", "COLUMN_type", "COLUMN_d_mm", "COLUMN_bf_mm", "COLUMN_tw_mm",
                    "COLUMN_tf_mm", "COLUMN_r1_mm", "COLUMN_wely_mm", "COLUMN_w_kgm"]].copy()
    col_part.columns = ["profile"] + PROFILE_GEOM_COLS

    lookup = pd.concat([beam_part, col_part], ignore_index=True).drop_duplicates(subset="profile")
    lookup = lookup.set_index("profile")
    return lookup


def infer_source_from_profile(profile_code: str) -> str:
    """
    Source (European/Canadian) está 100% determinado por el prefijo del perfil en los datos
    reales (HE/IPE -> European, W -> Canadian). No hace falta pedirlo como input ni modelarlo.
    """
    code = str(profile_code).upper()
    if code.startswith("W"):
        return "Canadian"
    return "European"


def check_profile_coverage(profiles_needed, profile_lookup: pd.DataFrame) -> list:
    """Devuelve la lista de perfiles pedidos que NO están en la tabla de lookup."""
    return sorted(set(profiles_needed) - set(profile_lookup.index))


def add_profile_features(df: pd.DataFrame, profile_lookup: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    missing_beam = set(df["BEAM"].unique()) - set(profile_lookup.index)
    missing_col = set(df["COLUMN"].unique()) - set(profile_lookup.index)
    if missing_beam or missing_col:
        raise KeyError(
            f"Perfiles no encontrados en la tabla de lookup: "
            f"BEAM={sorted(missing_beam)} COLUMN={sorted(missing_col)}. "
            f"Hace falta ampliar profile_lookup (ideal: catálogos Tekla completos)."
        )

    beam_geom = profile_lookup.loc[df["BEAM"]].add_prefix("BEAM_").reset_index(drop=True)
    col_geom = profile_lookup.loc[df["COLUMN"]].add_prefix("COLUMN_").reset_index(drop=True)

    df = pd.concat([df.reset_index(drop=True), beam_geom, col_geom], axis=1)
    return df


def add_material_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    unknown_acero = set(df["grado_acero"].unique()) - set(ACERO_TABLE)
    unknown_tornillo = set(df["clase_tornillo"].unique()) - set(TORNILLO_TABLE)
    if unknown_acero or unknown_tornillo:
        raise KeyError(f"Grados no reconocidos: acero={unknown_acero} tornillo={unknown_tornillo}")

    acero_df = df["grado_acero"].map(ACERO_TABLE).apply(pd.Series)
    tornillo_df = df["clase_tornillo"].map(TORNILLO_TABLE).apply(pd.Series)

    df = pd.concat([df, acero_df, tornillo_df], axis=1)
    return df


def build_training_features(raw_df: pd.DataFrame, profile_lookup: pd.DataFrame) -> pd.DataFrame:
    """
    Punto único de entrada: recibe un dataframe con las columnas "pobres" de
    fictional.csv (o equivalentes ya presentes en train/test.parquet) y devuelve
    el dataframe con TODAS las features que espera el modelo (config.FEATURE_COLUMNS).
    """
    df = raw_df.copy()
    df = add_profile_features(df, profile_lookup)
    df = add_material_features(df)
    return df
