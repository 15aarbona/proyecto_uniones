"""
Módulo de inferencia en producción (sin transformaciones en servidor).
Toma las 20 features directo del payload de Excel y ejecuta el modelo.
"""
import logging
import math
import pickle
import sys
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import torch

import config
import dataset
import model
from config import (
    MODEL_PATH,
    NUMERIC_FEATURES,
    PREPROCESSOR_PATH,
    RAW_INPUT_COLUMNS,
)
from dataset import Preprocessor
from model import ConnectionDesignNet
from training import outputs_to_design

# --- ALIAS DE COMPATIBILIDAD CON MODELOS GUARDADOS BAJO 'core' ---
sys.modules["core"] = sys.modules[__name__]
sys.modules["core.dataset"] = dataset
sys.modules["core.model"] = model
sys.modules["core.config"] = config
# -----------------------------------------------------------------

log = logging.getLogger("ai-server")

MODEL_VERSION = "resnet-tabular-uniones-v4"

OUTPUT_FIELDS = [
    "standard", "bolt", "SlipCritical", "n_alma", "n_cantonera", "N_Y",
    "P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9", "P10", "P11", "P12",
    "g", "e", "d", "Bp", "tp", "tws", "ts", "tbs", "tst",
    "Hole", "num_filas_tornillos", "tiene_cantonera"
]

_MODEL: ConnectionDesignNet | None = None
_PREPROCESSOR: Preprocessor | None = None
_DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _clean_value(val: Any) -> Any:
    """Sanea valores para garantizar compatibilidad JSON (evita NaN e Inf)."""
    if val is None:
        return None
    if isinstance(val, (float, np.floating)):
        if math.isnan(val) or math.isinf(val):
            return None
        return float(val)
    if isinstance(val, (int, np.integer)):
        return int(val)
    if isinstance(val, (bool, np.bool_)):
        return bool(val)
    if pd.isna(val):
        return None
    return val


def _clean_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    return {k: _clean_value(v) for k, v in d.items()}


def load_model_and_preprocessor():
    global _MODEL, _PREPROCESSOR
    if _MODEL is not None and _PREPROCESSOR is not None:
        return _MODEL, _PREPROCESSOR

    if PREPROCESSOR_PATH.exists() and MODEL_PATH.exists():
        try:
            with open(PREPROCESSOR_PATH, "rb") as f:
                _PREPROCESSOR = pickle.load(f)

            checkpoint = torch.load(MODEL_PATH, map_location=_DEVICE)
            cat_cards = _PREPROCESSOR.cat_cardinalities
            num_cont = len(NUMERIC_FEATURES)
            n_std_cls = _PREPROCESSOR.n_standard_classes

            _MODEL = ConnectionDesignNet(
                cat_cardinalities=cat_cards,
                num_continuous=num_cont,
                n_standard_classes=n_std_cls,
            ).to(_DEVICE)

            if isinstance(checkpoint, dict) and "model_state" in checkpoint:
                _MODEL.load_state_dict(checkpoint["model_state"])
            elif isinstance(checkpoint, dict):
                _MODEL.load_state_dict(checkpoint)
            else:
                _MODEL = checkpoint.to(_DEVICE)

            _MODEL.eval()
            log.info("Modelo PyTorch y Preprocesador cargados correctamente.")
        except Exception as e:
            log.exception(f"Error cargando modelo PyTorch: {e}. Se usará modo stub fallback.")
            _MODEL, _PREPROCESSOR = None, None
    else:
        log.warning(f"No se encontraron los pesos en {MODEL_PATH} o {PREPROCESSOR_PATH}. Usando modo stub.")

    return _MODEL, _PREPROCESSOR


def predict_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not rows:
        return []

    valid_rows = [
        r for r in rows
        if any(v is not None and str(v).strip() != "" for v in r.values())
    ]

    if not valid_rows:
        return []

    df = pd.DataFrame(valid_rows)
    model_inst, preprocessor = load_model_and_preprocessor()

    if model_inst is not None and preprocessor is not None:
        try:
            x_cat, x_num = preprocessor.transform_features(df)
            x_cat_t = torch.tensor(x_cat, dtype=torch.long).to(_DEVICE)
            x_num_t = torch.tensor(x_num, dtype=torch.float32).to(_DEVICE)

            with torch.no_grad():
                raw_outputs = model_inst(x_cat_t, x_num_t)
                outputs_np = {k: v.cpu().numpy() for k, v in raw_outputs.items()}

            design_df = outputs_to_design(outputs_np, preprocessor)
            return _format_outputs(df, design_df)
        except Exception as e:
            log.exception(f"Error durante la inferencia con PyTorch: {e}")

    return _stub_predict(valid_rows)


def _format_outputs(input_df: pd.DataFrame, design_df: pd.DataFrame) -> List[Dict[str, Any]]:
    out = []
    for idx, row in input_df.iterrows():
        des = design_df.iloc[idx].to_dict()
        bolt_val = des.get("Bolt", des.get("bolt", 20))
        
        pred = {}
        if "UNICODE" in row and pd.notna(row["UNICODE"]):
            pred["UNICODE"] = row["UNICODE"]

        pred.update({
            "standard": str(des.get("standard", "AISC 360-16")),
            "bolt": bolt_val,
            "SlipCritical": des.get("SlipCritical", "NO"),
            "n_alma": int(des.get("n_alma", 2)),
            "n_cantonera": int(des.get("n_cantonera", 0)),
            "N_Y": 12,
            **{f"P{i}": des.get(f"p{i}", 0.0) for i in range(1, 13)},
            "g": des.get("g", 100.0),
            "e": des.get("e", 50.0),
            "d": des.get("d", 50.0),
            "Bp": des.get("Bp", 200.0),
            "tp": des.get("tp", 20.0),
            "tws": des.get("tws", 0.0),
            "ts": des.get("ts", 0.0),
            "tbs": des.get("tbs", 0.0),
            "tst": des.get("tst", 0.0),
            "Hole": des.get("Hole", 22.0),
            "num_filas_tornillos": int(des.get("num_filas_tornillos", 4)),
            "tiene_cantonera": bool(des.get("tiene_cantonera", False)),
        })
        out.append(_clean_dict(pred))
    return out


def _stub_predict(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for row in rows:
        pred = {}
        if "UNICODE" in row and row["UNICODE"] is not None:
            pred["UNICODE"] = row["UNICODE"]

        pred.update({
            "standard": "AISC 360-16",
            "bolt": 20,
            "SlipCritical": "NO",
            "n_alma": 2,
            "n_cantonera": 0,
            "N_Y": 12,
            "P1": 70.0, "P2": 70.0, "P3": 70.0, "P4": 0.0,
            "P5": 0.0,  "P6": 0.0,  "P7": 0.0, "P8": 0.0,
            "P9": 0.0,  "P10": 0.0, "P11": 0.0, "P12": 0.0,
            "g": 100.0,
            "e": 50.0,
            "d": 50.0,
            "Bp": 200.0,
            "tp": 20.0,
            "tws": 0.0,
            "ts": 0.0,
            "tbs": 0.0,
            "tst": 0.0,
            "Hole": 22.0,
            "num_filas_tornillos": 4,
            "tiene_cantonera": False,
        })
        out.append(_clean_dict(pred))
    return out


def reload_model():
    global _MODEL, _PREPROCESSOR
    _MODEL = None
    _PREPROCESSOR = None
    return load_model_and_preprocessor()


def model_status() -> Dict[str, Any]:
    return {
        "model_loaded": _MODEL is not None,
        "model_version": MODEL_VERSION,
        "raw_inputs": RAW_INPUT_COLUMNS,
        "output_fields": OUTPUT_FIELDS,
    }