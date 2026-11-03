"""Adaptador del modelo PINN (misma interfaz que V11 para el servidor).

  contract(), input_schema(), options()      contrato de entrada
  to_internal()/preprocess()                 input -> features (perfiles Tekla + materiales)
  load() / predict()                         pesos + preprocesador e inferencia
  from_internal()                            salida -> claves canonicas

Paquete instalado (make install-model MODEL=PINN):
    models/PINN/{weights.pt, preprocessor.joblib, data/, core/}
"""
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch

from .config import (
    BOLT_DIAMETERS, GEOMETRY_COLUMNS, INPUT_DIM, NORMATIVAS, OPTIONAL_INPUT_COLUMNS,
    RAW_INPUT_COLUMNS,
)
from .dataset import Preprocessor
from .model import BoltedConnectionPINN
from .postprocess import decode_predictions

MODEL_NAME = "PINN"

MODEL_DIR = Path(__file__).resolve().parent.parent
WEIGHTS_PATH = MODEL_DIR / "weights.pt"
PREPROCESSOR_PATH = MODEL_DIR / "preprocessor.joblib"
DATA_DIR = MODEL_DIR / "data"
_TEKLA_FILES = ("tekla_eu.csv", "tekla_cad.csv", "tekla_faltante.csv", "tekla_uk.csv")

DEFAULT_GRADO_ACERO = "S355JR"
DEFAULT_CLASE_TORNILLO = "A325M"
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
    + [f"p{i}" for i in range(1, 13)]
    + ["Hole", "num_filas_tornillos", "tiene_cantonera"]
)


class InputContractError(ValueError):
    """La fila recibida no encaja con el contrato de entrada del modelo."""


# ---------------------------------------------------------------- catalogo de perfiles
_PROFILE_LOOKUP = None


def _profile_lookup() -> pd.DataFrame:
    global _PROFILE_LOOKUP
    if _PROFILE_LOOKUP is None:
        frames = [pd.read_csv(DATA_DIR / n) for n in _TEKLA_FILES]
        union = pd.concat(frames, ignore_index=True).dropna(subset=["tekla_nomenclature_1"])
        union["_key"] = union["tekla_nomenclature_1"].astype(str).str.strip().str.upper()
        _PROFILE_LOOKUP = union.drop_duplicates(subset="_key").set_index("_key")
    return _PROFILE_LOOKUP


def _profile_names() -> list:
    names = _profile_lookup()["tekla_nomenclature_1"].astype(str).str.strip()
    return sorted(n for n in names.unique() if n)


def _col(geom: pd.DataFrame, *names):
    """Primera columna existente (b_mm / b_m / bf_mm segun el catalogo)."""
    for n in names:
        if n in geom.columns:
            return pd.to_numeric(geom[n], errors="coerce").to_numpy()
    return np.full(len(geom), np.nan)


def _canonicalize(df: pd.DataFrame) -> pd.DataFrame:
    alias = {c.lower(): c for c in RAW_INPUT_COLUMNS + OPTIONAL_INPUT_COLUMNS}
    return df.rename(columns={c: alias.get(str(c).strip().lower(), c) for c in df.columns})


def _add_profiles(df: pd.DataFrame) -> pd.DataFrame:
    lookup = _profile_lookup()
    for side in ("BEAM", "COLUMN"):
        keys = df[side].astype(str).str.strip().str.upper()
        unknown = sorted(set(df.loc[~keys.isin(lookup.index), side].astype(str)))
        if unknown:
            raise InputContractError(
                f"Perfiles no reconocidos en {side} (no estan en los catalogos Tekla): {unknown}")
        geom = lookup.loc[keys].reset_index(drop=True)
        df[f"{side}_type"] = geom["type"].to_numpy() if "type" in geom.columns else ""
        df[f"{side}_d_mm"] = _col(geom, "d_mm")
        df[f"{side}_b_mm"] = _col(geom, "b_mm", "b_m", "bf_mm")
        df[f"{side}_tf_mm"] = _col(geom, "tf_mm")
        df[f"{side}_tw_mm"] = _col(geom, "tw_mm")
        df[f"{side}_r1_mm"] = _col(geom, "r1_mm")
    return df


def _add_materials(df: pd.DataFrame) -> pd.DataFrame:
    for column, table, default in (("grado_acero", ACERO_TABLE, DEFAULT_GRADO_ACERO),
                                   ("clase_tornillo", TORNILLO_TABLE, DEFAULT_CLASE_TORNILLO)):
        if column not in df.columns:
            df[column] = default
        values = (df[column].replace(r"^\s*$", np.nan, regex=True)
                  .fillna(default).astype(str).str.strip())
        unknown = sorted({v for v in values if v not in table})
        if unknown:
            raise InputContractError(
                f"Valores no reconocidos en {column}: {unknown}. Admitidos: {sorted(table)}")
        df[column] = values.to_numpy()
        props = pd.DataFrame([table[v] for v in values], index=df.index)
        for name in props.columns:
            df[name] = props[name].to_numpy()
    return df


def _to_number(series: pd.Series, column: str) -> pd.Series:
    cleaned = series.map(lambda v: v.replace(",", ".") if isinstance(v, str) else v)
    try:
        return pd.to_numeric(cleaned, errors="raise").astype(float)
    except (ValueError, TypeError) as exc:
        raise InputContractError(f"{column} debe ser numerico: {exc}") from exc


def preprocess(raw_df: pd.DataFrame) -> pd.DataFrame:
    df = _canonicalize(raw_df.copy())
    df = _add_profiles(df)
    df = _add_materials(df)
    for c in ("ratio_moment", "ratio_shear", "ratio_axial"):
        df[c] = _to_number(df[c], c)
    return df.reset_index(drop=True)


def to_internal(table_df: pd.DataFrame) -> pd.DataFrame:
    return preprocess(table_df)


def from_internal(design_df: pd.DataFrame) -> pd.DataFrame:
    out = design_df.copy()
    for c in OUTPUT_FIELDS:
        if c not in out.columns:
            out[c] = 0
    return out[OUTPUT_FIELDS].reset_index(drop=True)


# ---------------------------------------------------------------- carga e inferencia
def load() -> dict:
    if not WEIGHTS_PATH.exists() or not PREPROCESSOR_PATH.exists():
        raise FileNotFoundError(
            f"Faltan artefactos del modelo en {MODEL_DIR}. "
            f"Ejecuta 'make install-model MODEL=PINN' desde la raiz del proyecto.")
    pre: Preprocessor = joblib.load(PREPROCESSOR_PATH)
    ckpt = torch.load(WEIGHTS_PATH, map_location="cpu", weights_only=False)
    hp = ckpt["hyperparameters"]
    model = BoltedConnectionPINN(
        input_dim=INPUT_DIM, hidden_dim=hp["hidden_dim"],
        num_res_blocks=hp["num_res_blocks"], dropout_rate=hp.get("dropout_rate", 0.1))
    model.load_state_dict(ckpt["model_state_dict"])
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device).eval()
    return {"model": model, "pre": pre, "device": device}


@torch.no_grad()
def predict(features_df: pd.DataFrame, bundle: dict) -> pd.DataFrame:
    model, pre, device = bundle["model"], bundle["pre"], bundle["device"]
    try:
        x = torch.as_tensor(pre.transform(features_df), dtype=torch.float32, device=device)
    except ValueError as exc:
        raise InputContractError(f"Valores no admitidos por el modelo: {exc}") from exc

    out = model(x)
    bolt_idx = out["bolt_diam_logits"].argmax(-1)
    diam = torch.tensor(BOLT_DIAMETERS, dtype=torch.float32, device=device)[bolt_idx]
    geom = model.decode_geometry(out, x, diam)

    to_np = lambda d: {k: v.detach().cpu().numpy() for k, v in d.items()}
    design = decode_predictions(
        out=to_np(out), geom=to_np(geom),
        bolt_idx=bolt_idx.cpu().numpy(),
        rows_idx=out["num_rows_logits"].argmax(-1).cpu().numpy(),
        tf_beam=pd.to_numeric(features_df["BEAM_tf_mm"], errors="coerce").fillna(10.0).to_numpy(),
    )
    return design


# ---------------------------------------------------------------- contrato / schema
def contract() -> dict:
    return {
        "name": MODEL_NAME,
        "raw_inputs": list(RAW_INPUT_COLUMNS),
        "optional_inputs": list(OPTIONAL_INPUT_COLUMNS),
        "outputs": list(OUTPUT_FIELDS),
    }


def input_schema(bundle: dict = None) -> list:
    perfiles = _profile_names()
    return [
        {"key": "UNICODE", "description": "Identificador unico", "type": "text"},
        {"key": "Normativas", "description": "Normativa aplicable", "type": "categorical",
         "options": list(NORMATIVAS)},
        {"key": "BEAM", "description": "Perfil de la viga", "type": "categorical", "options": perfiles},
        {"key": "COLUMN", "description": "Perfil de la columna", "type": "categorical", "options": perfiles},
        {"key": "ratio_moment", "description": "(0-1)", "type": "number"},
        {"key": "ratio_shear", "description": "(0-1)", "type": "number"},
        {"key": "ratio_axial", "description": "(0-1)", "type": "number"},
        {"key": "grado_acero", "description": "Grado del acero", "type": "categorical",
         "options": sorted(ACERO_TABLE)},
        {"key": "clase_tornillo", "description": "Clase del tornillo", "type": "categorical",
         "options": sorted(TORNILLO_TABLE)},
    ]


def options(bundle: dict = None) -> dict:
    perfiles = _profile_names()
    return {
        "BEAM": perfiles, "COLUMN": perfiles,
        "grado_acero": sorted(ACERO_TABLE), "clase_tornillo": sorted(TORNILLO_TABLE),
        "defaults": {"grado_acero": DEFAULT_GRADO_ACERO, "clase_tornillo": DEFAULT_CLASE_TORNILLO},
    }