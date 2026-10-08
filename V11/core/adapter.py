"""Adaptador del modelo V11 (v4: p discretizada + topologia conjunta).

Este modulo es la unica interfaz que necesita el servidor de produccion. Define:
  - El CONTRATO de entrada (RAW_INPUT_COLUMNS): los 12 campos que envia Excel/web.
  - Entradas opcionales (OPTIONAL_INPUT_COLUMNS): grado_acero y clase_tornillo,
    con valores por defecto si no llegan.
  - El preproceso que expande esos campos a las FEATURE_COLUMNS completas del
    modelo (lookup de perfiles Tekla + tabla de materiales + porcentajes).
  - La carga del bundle (pesos + preprocesador) y la inferencia.
  - options(): valores validos para los desplegables (GET /options).

Correspondencia con las features de V11:
    Capacity_Moment <- MzEd_Porcen   (mismo valor, escala 0-100)
    Capacity_Shear  <- FyEd_Porcen
    Capacity_Axial  <- FxEd_Porcen
    Standards, Pr_Porcen, Traccion, MzEd_PanelZone, Vgra, Havg: V11 no los usa
    (se aceptan y se devuelven tal cual en la respuesta).

Estructura del paquete instalado:

    models/V11/
        weights.pt              <- V11/artifacts_v4/model_final.pt
        preprocessor.joblib     <- V11/artifacts_v4/preprocessor.joblib
        data/                   <- V11/data (catalogos Tekla)
        core/adapter.py         <- este archivo
"""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch

from .config import (
    CATEGORICAL_FEATURES,
    N_Y,
    NUMERIC_FEATURES,
)
from .dataset import Preprocessor
from .model import ConnectionDesignNetV4
from .postprocess import decode_predictions, derive_dependent_columns

MODEL_NAME = "V11"

# ---------------------------------------------------------------------------
# Contrato de entrada
# ---------------------------------------------------------------------------
RAW_INPUT_COLUMNS = [
    "UNICODE",
    "Standards",
    "BEAM",
    "COLUMN",
    "MzEd_Porcen",
    "FyEd_Porcen",
    "FxEd_Porcen",
    "Pr_Porcen",
    "Traccion",
    "MzEd_PanelZone",
    "Vgra",
    "Havg",
]

# Opcionales: si no llegan (o llegan vacias) se usan los valores por defecto.
OPTIONAL_INPUT_COLUMNS = ["grado_acero", "clase_tornillo"]

DEFAULT_GRADO_ACERO = "S355JR"
DEFAULT_CLASE_TORNILLO = "A325M"

PERCENT_COLUMNS = ["MzEd_Porcen", "FyEd_Porcen", "FxEd_Porcen", "Pr_Porcen"]

# Capacity_X de V11 <- columna de porcentaje del contrato (mismo valor, sin escalar).
PERCENT_TO_CAPACITY = {
    "ratio_moment": "MzEd_Porcen",
    "ratio_shear": "FyEd_Porcen",
    "ratio_axial": "FxEd_Porcen",
}

# Columnas completas que consume el modelo (V11 no las define en config.py).
FEATURE_COLUMNS = list(CATEGORICAL_FEATURES) + list(NUMERIC_FEATURES)

# Directorios y artefactos relativos al paquete del modelo (models/V11/ o V11/).
MODEL_DIR = Path(__file__).resolve().parent.parent
WEIGHTS_PATH = MODEL_DIR / "weights.pt"
PREPROCESSOR_PATH = MODEL_DIR / "preprocessor.joblib"
DATA_DIR = MODEL_DIR / "data"

_TEKLA_FILES = ("tekla_eu.csv", "tekla_cad.csv", "tekla_faltante.csv")

# Catalogos de materiales (referencia: V7/variables.py).
ACERO_TABLE = {
    "S275JR": {"fy_acero_mpa": 275.0, "fu_acero_mpa": 430.0},
    "S355JR": {"fy_acero_mpa": 355.0, "fu_acero_mpa": 490.0},
}
TORNILLO_TABLE = {
    "8.8": {"fy_tornillo_mpa": 640.0, "fu_tornillo_mpa": 800.0, "fv_tornillo_mpa": 480.0},
    "10.9": {"fy_tornillo_mpa": 900.0, "fu_tornillo_mpa": 1000.0, "fv_tornillo_mpa": 500.0},
    "A325M": {"fy_tornillo_mpa": 660.0, "fu_tornillo_mpa": 830.0, "fv_tornillo_mpa": 372.0},
}

OUTPUT_FIELDS = (
    ["standard", "Bolt", "SlipCritical", "n_alma", "n_cantonera"]
    + ["g", "e", "d", "Bp", "tp", "tws", "ts", "tbs", "tst"]
    + [f"p{i}" for i in range(1, N_Y + 1)]
    + [f"p{i}_transition" for i in range(1, N_Y + 1)]
    + ["Hole", "num_filas_tornillos", "tiene_cantonera"]
)

_PROFILE_LOOKUP = None


class InputContractError(ValueError):
    """La fila recibida no encaja con el contrato de entrada del modelo."""


# ---------------------------------------------------------------------------
# Catalogo de perfiles
# ---------------------------------------------------------------------------
def _profile_lookup() -> pd.DataFrame:
    """Tabla perfil -> (type, d_mm), indexada por nombre en MAYUSCULAS (sin espacios)."""
    global _PROFILE_LOOKUP
    if _PROFILE_LOOKUP is None:
        frames = [pd.read_csv(DATA_DIR / name) for name in _TEKLA_FILES]
        union = pd.concat(frames, ignore_index=True)
        union["_key"] = union["tekla_nomenclature_1"].astype(str).str.strip().str.upper()
        _PROFILE_LOOKUP = union.drop_duplicates(subset="_key").set_index("_key")
    return _PROFILE_LOOKUP


def _canonicalize(df: pd.DataFrame) -> pd.DataFrame:
    """Renombra alias (Unicode, beam, ...) a los nombres canonicos del contrato."""
    alias = {c.lower(): c for c in RAW_INPUT_COLUMNS + OPTIONAL_INPUT_COLUMNS}
    return df.rename(
        columns={c: alias.get(str(c).strip().lower(), c) for c in df.columns}
    )


def _add_profiles(df: pd.DataFrame) -> pd.DataFrame:
    lookup = _profile_lookup()
    for col in ("BEAM", "COLUMN"):
        keys = df[col].astype(str).str.strip().str.upper()
        unknown = sorted(set(df.loc[~keys.isin(lookup.index), col].astype(str)))
        if unknown:
            raise InputContractError(
                f"Perfiles no reconocidos en {col} (no estan en los catalogos "
                f"Tekla): {unknown}"
            )
        geom = lookup.loc[keys].reset_index(drop=True)
        df[f"{col}_type"] = geom["type"].to_numpy()
        df[f"{col}_d_mm"] = pd.to_numeric(geom["d_mm"].to_numpy(), errors="coerce")
    return df


def _add_materials(df: pd.DataFrame) -> pd.DataFrame:
    for column, table, default in (
        ("grado_acero", ACERO_TABLE, DEFAULT_GRADO_ACERO),
        ("clase_tornillo", TORNILLO_TABLE, DEFAULT_CLASE_TORNILLO),
    ):
        if column not in df.columns:
            df[column] = default
        values = (
            df[column]
            .replace(r"^\s*$", np.nan, regex=True)
            .fillna(default)
            .astype(str)
            .str.strip()
        )
        unknown = sorted({v for v in values if v not in table})
        if unknown:
            raise InputContractError(
                f"Valores no reconocidos en {column}: {unknown}. "
                f"Admitidos: {sorted(table)}"
            )
        df[column] = values.to_numpy()
        props = pd.DataFrame([table[v] for v in values], index=df.index)
        for name in props.columns:
            df[name] = props[name].to_numpy()
    return df


def _to_number(series: pd.Series, column: str) -> pd.Series:
    """Convierte a numero aceptando coma decimal; error de contrato si no es posible."""
    cleaned = series.map(lambda v: v.replace(",", ".") if isinstance(v, str) else v)
    try:
        return pd.to_numeric(cleaned, errors="raise").astype(float)
    except (ValueError, TypeError) as exc:
        raise InputContractError(f"{column} debe ser numerico (escala 0-100): {exc}") from exc


def _add_capacities(df: pd.DataFrame) -> pd.DataFrame:
    for pct in PERCENT_COLUMNS:
        df[pct] = _to_number(df[pct], pct)

    # Rango 0-100 solo en los porcentajes que alimentan el modelo.
    for pct in PERCENT_TO_CAPACITY.values():
        if ((df[pct] < 0) | (df[pct] > 100)).any():
            raise InputContractError(f"{pct} fuera de rango 0-100")

    for cap, pct_col in PERCENT_TO_CAPACITY.items():
        df[cap] = df[pct_col].astype(float)
    return df


def preprocess(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Input basico -> dataframe con las FEATURE_COLUMNS completas del modelo."""
    df = _canonicalize(raw_df.copy())
    df = _add_profiles(df)
    df = _add_materials(df)
    df = _add_capacities(df)

    # Se conservan los identificadores crudos + las features que usa el modelo.
    keep = list(
        dict.fromkeys(
            [c for c in RAW_INPUT_COLUMNS if c in df.columns] + list(FEATURE_COLUMNS)
        )
    )
    return df[keep]


# ---------------------------------------------------------------------------
# Carga e inferencia
# ---------------------------------------------------------------------------
def load() -> dict:
    """Carga pesos + preprocesador y devuelve el bundle de inferencia."""
    if not WEIGHTS_PATH.exists() or not PREPROCESSOR_PATH.exists():
        raise FileNotFoundError(
            f"Faltan artefactos del modelo en {MODEL_DIR}. "
            f"Ejecuta 'make install-model MODEL=V11' desde la raiz del proyecto."
        )

    pre: Preprocessor = joblib.load(PREPROCESSOR_PATH)

    # weights_only=False: el checkpoint lleva arrays numpy en los metadatos
    # (p_mean_mm/p_std_mm). Es un artefacto propio y de confianza.
    checkpoint = torch.load(WEIGHTS_PATH, map_location="cpu", weights_only=False)
    state = checkpoint.get("model_state_dict", checkpoint)
    cfg = checkpoint.get("cfg", {})

    model = ConnectionDesignNetV4(
        cat_cardinalities=checkpoint["cat_cardinalities"],
        num_continuous=len(checkpoint["numeric_features"]),
        n_standard_classes=checkpoint["n_standard_classes"],
        p_mean_mm=checkpoint["p_mean_mm"],
        p_std_mm=checkpoint["p_std_mm"],
        hidden_dim=checkpoint.get("hidden_dim", 192),
        num_blocks=checkpoint.get("num_blocks", 3),
        dropout=checkpoint.get("dropout", 0.1),
        gru_hidden_dim=checkpoint.get("gru_hidden_dim", 128),
        n_p_bins=checkpoint["n_p_bins"],
        p_bin_step_mm=checkpoint["p_bin_step_mm"],
        joint_topology=bool(cfg.get("joint_topology", False)),
    )
    model.load_state_dict(state)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.eval()
    return {"model": model, "pre": pre, "device": device}


@torch.no_grad()
def predict(features_df: pd.DataFrame, bundle: dict) -> pd.DataFrame:
    """Features completas -> dataframe con las predicciones decodificadas."""
    model = bundle["model"]
    pre: Preprocessor = bundle["pre"]
    device = bundle["device"]

    try:
        x_cat, x_num = pre.transform_features(features_df)
    except ValueError as exc:
        # Categorias (perfil/grado/clase) que el preprocesador no vio en entrenamiento.
        raise InputContractError(f"Valores no admitidos por el modelo: {exc}") from exc

    outputs = model(
        torch.as_tensor(x_cat, dtype=torch.long, device=device),
        torch.as_tensor(x_num, dtype=torch.float32, device=device),
    )
    outputs = {k: v.detach().cpu().numpy() for k, v in outputs.items()}

    presence = 1.0 / (1.0 + np.exp(-np.clip(outputs["masked_presence_logit"], -30, 30)))
    design = decode_predictions(
        reg_always_real=pre.inverse_reg_always(outputs["reg_always"]),
        masked_value_real=pre.inverse_masked(outputs["masked_value"]),
        masked_presence_prob=presence,
        bolt_logits=outputs["bolt_logits"],
        n_alma_logits=outputs["n_alma_logits"],
        n_cantonera_logits=outputs["n_cantonera_logits"],
        standard_logits=outputs["standard_logits"],
        standard_classes=pre.standard_encoder.classes_,
        slip_critical_logit=outputs["slip_critical_logit"],
    )
    design = derive_dependent_columns(design)
    return design.drop(columns=["_bolt_nominal_mm"], errors="ignore")


# ---------------------------------------------------------------------------
# Contrato y opciones publicadas
# ---------------------------------------------------------------------------
def contract() -> dict:
    """Descripcion del contrato de entrada/salida del modelo."""
    return {
        "name": MODEL_NAME,
        "raw_inputs": list(RAW_INPUT_COLUMNS),
        "optional_inputs": list(OPTIONAL_INPUT_COLUMNS),
        "features": list(FEATURE_COLUMNS),
        "outputs": list(OUTPUT_FIELDS),
    }


def options() -> dict:
    """Valores validos para los desplegables de la web (GET /options)."""
    perfiles = sorted(
        _profile_lookup()["tekla_nomenclature_1"].astype(str).str.strip().unique()
    )
    return {
        "BEAM": perfiles,
        "COLUMN": perfiles,
        "grado_acero": sorted(ACERO_TABLE),
        "clase_tornillo": sorted(TORNILLO_TABLE),
        "defaults": {
            "grado_acero": DEFAULT_GRADO_ACERO,
            "clase_tornillo": DEFAULT_CLASE_TORNILLO,
        },
    }
