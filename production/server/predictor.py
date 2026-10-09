"""Inferencia y comprobación estructural en producción sobre modelos intercambiables."""

import logging
import math
from typing import Any, Dict, List

import numpy as np
import pandas as pd

import model_registry
from checker import check_rows as perform_check

log = logging.getLogger("ai-server")


class InputContractError(ValueError):
    def __init__(self, message: str, model: str = None, missing=None, expected=None):
        super().__init__(message)
        self.model = model
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
    alias = {c.lower(): c for c in list(raw_inputs) + list(optional_inputs)}
    normalized = []
    for row in rows:
        new_row: Dict[str, Any] = {}
        for key, value in row.items():
            new_row[alias.get(str(key).strip().lower(), key)] = value
        normalized.append(new_row)
    return normalized


def _validate_contract(
    rows: List[Dict[str, Any]], raw_inputs: List[str], optional_inputs: List[str], model: str
) -> None:
    if not rows:
        raise InputContractError("La petición no trae filas (rows vacío)", model=model, expected=raw_inputs)
    optional = set(optional_inputs)
    required = [c for c in raw_inputs if c not in optional]
    missing = {}
    for i, row in enumerate(rows):
        absent = [c for c in required if _is_missing(row.get(c))]
        if absent:
            missing[f"fila {i + 1}"] = absent
    if missing:
        raise InputContractError(
            f"Faltan inputs requeridos por el modelo '{model}'",
            model=model,
            missing=missing,
            expected=raw_inputs,
        )


def predict_rows(model_name: str, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    bundle = model_registry.get(model_name)
    adapter = bundle["adapter"]
    contract = bundle["contract"]
    raw_inputs = contract["raw_inputs"]
    optional_inputs = contract.get("optional_inputs", [])
    name = bundle["name"]

    rows = _normalize_rows(rows, raw_inputs, optional_inputs)
    _validate_contract(rows, raw_inputs, optional_inputs, name)

    df = pd.DataFrame(rows)
    try:
        features = adapter.to_internal(df)
        design = adapter.predict(features, bundle)
        table_out = adapter.from_internal(design)
    except adapter.InputContractError as exc:
        raise InputContractError(str(exc), model=name, expected=raw_inputs) from exc

    input_columns = [c for c in raw_inputs if c in features.columns]
    output: List[Dict[str, Any]] = []
    for i in range(len(df)):
        merged: Dict[str, Any] = {c: features.iloc[i][c] for c in input_columns}
        merged.update(table_out.iloc[i].to_dict())
        output.append(_clean_dict(merged))
    return output


def check_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    results = perform_check(rows)
    return [_clean_dict(r) for r in results]


def model_status() -> Dict[str, Any]:
    return {
        "available_models": model_registry.list_models(),
        "loaded_models": model_registry.loaded_models(),
    }


def options(model_name: str) -> Dict[str, Any]:
    bundle = model_registry.get(model_name)
    fn = getattr(bundle["adapter"], "options", None)
    if fn is None:
        raise InputContractError(
            f"El modelo '{bundle['name']}' no publica opciones", model=bundle["name"]
        )
    return fn(bundle)