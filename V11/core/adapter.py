"""Adaptador del modelo V11 (v4: p discretizada + topologia conjunta).

Este modulo es la unica interfaz que necesita el servidor de produccion. Define:
  - El CONTRATO de entrada (RAW_INPUT_COLUMNS): los 8 campos basicos que envia Excel.
  - El preproceso que expande esos campos basicos a las FEATURE_COLUMNS completas
    (lookup de perfiles Tekla + tabla de materiales).
  - La carga del bundle (pesos + preprocesador) y la inferencia.

El servidor copia toda la carpeta `core/` (incluido este archivo) y los artefactos
a `production/server/models/V11/` mediante el Makefile. Aqui se asume por tanto la
estructura del paquete instalado:

    models/V11/
        weights.pt              <- V11/artifacts_v4/model_final.pt
        preprocessor.joblib     <- V11/artifacts_v4/preprocessor.joblib
        data/                   <- V11/data (catalogos Tekla)
        core/adapter.py         <- este archivo
"""

from pathlib import Path

import joblib
import logging
import numpy as np
import pandas as pd
import torch

from .config import (
    CATEGORICAL_FEATURES,
    N_Y,
    NUMERIC_FEATURES,
    RAW_INPUT_COLUMNS,
)
from .dataset import Preprocessor
from .model import ConnectionDesignNetV4
from .postprocess import decode_predictions, derive_dependent_columns

MODEL_NAME = "V11"

log = logging.getLogger("model-adapter")

# Columnas completas que consume el modelo (V11 no las define en config.py).
FEATURE_COLUMNS = list(CATEGORICAL_FEATURES) + list(NUMERIC_FEATURES)

# Directorios y artefactos relativos al paquete del modelo (models/V11/ o V11/).
MODEL_DIR = Path(__file__).resolve().parent.parent
WEIGHTS_PATH = MODEL_DIR / "weights.pt"
PREPROCESSOR_PATH = MODEL_DIR / "preprocessor.joblib"
DATA_DIR = MODEL_DIR / "data"

_TEKLA_FILES = ("tekla_eu.csv", "tekla_cad.csv", "tekla_faltante.csv")

# Catalogos de materiales (referencia: V7/variables.py). Se aceptan de mas para no
# limitar el adaptador; el preprocesador validara luego las clases que conoce.
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


def _profile_lookup() -> pd.DataFrame:
    """Tabla perfil -> (type, d_mm) construida una vez desde los csv de Tekla."""
    global _PROFILE_LOOKUP
    if _PROFILE_LOOKUP is None:
        frames = [pd.read_csv(DATA_DIR / name) for name in _TEKLA_FILES]
        union = pd.concat(frames, ignore_index=True)
        union = (
            union[["tekla_nomenclature_1", "type", "d_mm"]]
            .drop_duplicates(subset="tekla_nomenclature_1")
            .set_index("tekla_nomenclature_1")
        )
        _PROFILE_LOOKUP = union
    return _PROFILE_LOOKUP


def _canonicalize(df: pd.DataFrame) -> pd.DataFrame:
    """Renombra alias (Unicode, beam, ...) a los nombres canonicos del contrato."""
    alias = {c.lower(): c for c in RAW_INPUT_COLUMNS}
    return df.rename(
        columns={c: alias.get(str(c).strip().lower(), c) for c in df.columns}
    )


def _add_profiles(df: pd.DataFrame) -> pd.DataFrame:
    lookup = _profile_lookup()
    known = set(lookup.index)
    for profile_col in ("BEAM", "COLUMN"):
        values = df[profile_col].astype(str).str.strip()
        unknown = sorted(set(values) - known)
        if unknown:
            raise InputContractError(
                f"Perfiles no reconocidos en {profile_col} (no estan en los catalogos "
                f"Tekla): {unknown}"
            )
        geom = lookup.loc[values].reset_index(drop=True)
        df[f"{profile_col}_type"] = geom["type"].to_numpy()
        df[f"{profile_col}_d_mm"] = pd.to_numeric(
            geom["d_mm"].to_numpy(), errors="coerce"
        )
    return df


def _add_materials(df: pd.DataFrame) -> pd.DataFrame:
    for column, table in (
        ("grado_acero", ACERO_TABLE),
        ("clase_tornillo", TORNILLO_TABLE),
    ):
        values = df[column].astype(str).str.strip()
        unknown = sorted({v for v in values if v not in table})
        if unknown:
            raise InputContractError(
                f"Valores no reconocidos en {column}: {unknown}. "
                f"Admitidos: {sorted(table)}"
            )
        props = values.map(table).apply(pd.Series)
        for name, series in props.items():
            df[name] = series.to_numpy()
    return df


def preprocess(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Input basico -> dataframe con las FEATURE_COLUMNS completas del modelo."""
    df = _canonicalize(raw_df.copy())
    df = _add_profiles(df)
    df = _add_materials(df)

    for column in ("Capacity_Moment", "Capacity_Shear", "Capacity_Axial"):
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.0)

    # Se conservan los identificadores crudos + las features que usa el modelo.
    keep = list(
        dict.fromkeys(
            [c for c in RAW_INPUT_COLUMNS if c in df.columns] + list(FEATURE_COLUMNS)
        )
    )
    return df[keep]


def _nearest_known(value: str, table: dict, known: list, keys: tuple) -> str:
    """Clase conocida con propiedades mas parecidas (distancia relativa al cuadrado)."""
    target = table.get(value)
    if target is None:
        return known[0]
    best, best_dist = known[0], None
    for candidate in known:
        props = table.get(candidate)
        if not props:
            continue
        dist = sum(((target[k] - props[k]) / (props[k] + 1e-9)) ** 2 for k in keys)
        if best_dist is None or dist < best_dist:
            best, best_dist = candidate, dist
    return best


# Categorias de material -> (tabla, propiedades) para aproximar valores no vistos.
_MATERIAL_FALLBACK = {
    "grado_acero": (ACERO_TABLE, ("fy_acero_mpa", "fu_acero_mpa")),
    "clase_tornillo": (
        TORNILLO_TABLE,
        ("fy_tornillo_mpa", "fu_tornillo_mpa", "fv_tornillo_mpa"),
    ),
}


def _coerce_categories(df: pd.DataFrame, pre: Preprocessor) -> pd.DataFrame:
    """Mapea categorias no vistas en entrenamiento a una clase conocida.

    `grado_acero`/`clase_tornillo` son redundantes con `fy/fu/fv`, que si entran como
    features numericas; por eso un valor no visto no impide predecir: se aproxima a la
    clase conocida de propiedades mas parecidas. El resto (BEAM_type/COLUMN_type) cae a
    la primera clase conocida. Se registra un aviso en el log."""
    df = df.copy()
    for feature in CATEGORICAL_FEATURES:
        known = [str(c) for c in pre.cat_encoders[feature].classes_]
        known_set = set(known)
        values = df[feature].astype(str)
        unknown = sorted(set(values) - known_set)
        if not unknown:
            continue
        table, keys = _MATERIAL_FALLBACK.get(feature, (None, None))
        if table is not None:
            mapping = {u: _nearest_known(u, table, known, keys) for u in unknown}
        else:
            mapping = {u: known[0] for u in unknown}
        log.warning(
            "Categorias de '%s' no vistas en entrenamiento %s -> %s",
            feature,
            unknown,
            mapping,
        )
        df[feature] = [mapping.get(v, v) for v in values]
    return df


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
        features_df = _coerce_categories(features_df, pre)
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


def contract() -> dict:
    """Descripcion del contrato de entrada/salida del modelo."""
    return {
        "name": MODEL_NAME,
        "raw_inputs": list(RAW_INPUT_COLUMNS),
        "features": list(FEATURE_COLUMNS),
        "outputs": list(OUTPUT_FIELDS),
    }
