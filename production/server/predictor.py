"""Inferencia en produccion sobre el modelo activo.

El preproceso y la inferencia viven en el `adapter.py` de cada modelo (carpeta V).
Aqui solo se valida el contrato de entrada, se delega en el adaptador activo y se
compone la respuesta con TODAS las columnas: entradas basicas + features completas
que se han calculado + predicciones del modelo.
"""

import logging
import math
from typing import Any, Dict, List

import numpy as np
import pandas as pd

import model_registry

log = logging.getLogger("ai-server")


class InputContractError(ValueError):
    """Los inputs recibidos no cumplen el contrato del modelo activo."""

    def __init__(self, message: str, missing=None, expected=None):
        super().__init__(message)
        self.missing = missing
        self.expected = expected


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def _clean_value(value: Any) -> Any:
    """Garantiza compatibilidad JSON (sin NaN/inf)."""
    if value is None:
        return None
    if isinstance(value, (float, np.floating)):
        return None if (math.isnan(value) or math.isinf(value)) else float(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (np.ndarray, list, tuple)):
        return value
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _clean_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    return {k: _clean_value(v) for k, v in data.items()}


def _normalize_rows(
    rows: List[Dict[str, Any]], raw_inputs: List[str], optional_inputs: List[str]
) -> List[Dict[str, Any]]:
    """Renombra las claves de cada fila a los nombres canonicos del contrato
    (sin distinguir mayusculas ni espacios en los extremos: 'Unicode' -> 'UNICODE').
    Las claves desconocidas se conservan tal cual."""
    alias = {c.lower(): c for c in list(raw_inputs) + list(optional_inputs)}
    normalized = []
    for row in rows:
        new_row: Dict[str, Any] = {}
        for key, value in row.items():
            new_row[alias.get(str(key).strip().lower(), key)] = value
        normalized.append(new_row)
    return normalized


def _validate_contract(rows: List[Dict[str, Any]], raw_inputs: List[str]) -> None:
    if not rows:
        raise InputContractError("La peticion no trae filas (rows vacio)", expected=raw_inputs)
    missing = {}
    for i, row in enumerate(rows):
        absent = [c for c in raw_inputs if _is_missing(row.get(c))]
        if absent:
            missing[f"fila {i + 1}"] = absent
    if missing:
        raise InputContractError(
            "Faltan inputs requeridos por el modelo activo",
            missing=missing,
            expected=raw_inputs,
        )


def predict_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    bundle = model_registry.get()
    adapter = bundle["adapter"]
    contract = bundle["contract"]
    raw_inputs = contract["raw_inputs"]
    optional_inputs = contract.get("optional_inputs", [])

    rows = _normalize_rows(rows, raw_inputs, optional_inputs)
    _validate_contract(rows, raw_inputs)

    df = pd.DataFrame(rows)
    try:
        features = adapter.preprocess(df)
        design = adapter.predict(features, bundle)
    except adapter.InputContractError as exc:
        raise InputContractError(str(exc), expected=raw_inputs) from exc

    output: List[Dict[str, Any]] = []
    for i in range(len(df)):
        merged: Dict[str, Any] = {}
        for column in features.columns:
            merged[column] = features.iloc[i][column]
        merged.update(design.iloc[i].to_dict())
        output.append(_clean_dict(merged))
    return output


def model_status() -> Dict[str, Any]:
    available = model_registry.list_models()
    try:
        bundle = model_registry.get()
    except RuntimeError:
        return {"model_loaded": False, "model_name": None, "available_models": available}
    return {
        "model_loaded": True,
        "model_name": bundle["name"],
        "available_models": available,
        **bundle["contract"],
    }
