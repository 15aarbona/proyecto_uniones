"""Inferencia y comprobacion estructural en produccion sobre modelos intercambiables.

Cada modelo expone su `input_schema()` y su diseno en claves canonicas. El servidor:
  - valida el contrato de entrada y enruta al modelo,
  - mapea input + diseno a las 63 columnas de CODAME (`codame.to_codame`, catalogo del
    servidor) e imputa lo que falte (nunca responde 500 por culpa del modelo),
  - ejecuta la comprobacion AISC 360-10 (`checker`) sobre el esquema CODAME.
"""

import logging
import math
from typing import Any, Dict, List

import numpy as np
import pandas as pd

import codame
import model_registry
from codame_schema import SERVED_COLUMNS, fill_served
from checker import check_rows as perform_check

log = logging.getLogger("ai-server")


class InputContractError(ValueError):
    """Los inputs recibidos no cumplen el contrato del modelo seleccionado."""

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
    """Garantiza compatibilidad JSON (sin NaN/inf)."""
    if value is None:
        return None
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (float, np.floating)):
        return None if (math.isnan(value) or math.isinf(value)) else float(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (list, tuple)):
        return [_clean_value(v) for v in value]
    if isinstance(value, dict):
        return {k: _clean_value(v) for k, v in value.items()}
    if isinstance(value, np.ndarray):
        return value.tolist()
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
    """Renombra alias (Unicode -> UNICODE...) sin distinguir mayusculas/espacios."""
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
        raise InputContractError("La peticion no trae filas (rows vacio)", model=model, expected=raw_inputs)
    optional = set(optional_inputs)
    required = [c for c in raw_inputs if c not in optional]  # UNICODE siempre obligatorio
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


def _national_annex(normativas, standard):
    """National_Annex derivado del `standard` predicho (quita el prefijo Normativas);
    NO reemplaza lo que el usuario puso en `Normativas`."""
    if not normativas or not standard:
        return None
    n, s = str(normativas).strip(), str(standard).strip()
    return s[len(n) + 3:] if s.startswith(n + " - ") else None


def _extras(input_row: Dict[str, Any], design_row: Dict[str, Any]) -> Dict[str, Any]:
    """Columnas de reentreno que CODAME no usa (vacias/NULL si el modelo no las aporta)."""
    inp = input_row or {}
    d = design_row or {}
    return {
        "Capacity_Moment": inp.get("Capacity_Moment"),
        "Capacity_Shear": inp.get("Capacity_Shear"),
        "Capacity_Axial": inp.get("Capacity_Axial"),
        "SlipCritical": d.get("SlipCritical", inp.get("SlipCritical")),
        "National_Annex": _national_annex(inp.get("Normativas"), d.get("standard")),
        "AceroEstructural": inp.get("grado_acero"),
    }


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
    except adapter.InputContractError as exc:
        raise InputContractError(str(exc), model=name, expected=raw_inputs) from exc

    output: List[Dict[str, Any]] = []
    for i in range(len(df)):
        input_row = features.iloc[i].to_dict()
        design_row = design.iloc[i].to_dict()
        extras = _extras(input_row, design_row)
        try:
            partial = codame.to_codame(input_row, design_row)
            if not isinstance(partial, dict):
                raise TypeError("codame.to_codame no devolvio un dict")
        except Exception:  # noqa: BLE001  (nunca fallar por culpa del modelo)
            log.exception(
                "codame.to_codame fallo (modelo=%s, fila=%d); se devuelven valores por defecto",
                name,
                i,
            )
            partial = {}
        output.append(_clean_dict(fill_served({**partial, **extras})))
    return output


def check_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Comprobacion AISC 360-10 sobre filas del esquema CODAME (editadas)."""
    output: List[Dict[str, Any]] = []
    for i, row in enumerate(rows):
        try:
            output.append(_clean_dict(perform_check([row])[0]))
        except Exception as exc:  # noqa: BLE001  (informe de error por entrada)
            log.exception("check_rows fallo (fila=%d)", i)
            output.append(
                {
                    "Unicode": row.get("Unicode", row.get("UNICODE", "")),
                    "cumple": False,
                    "ratio_pesimo": None,
                    "descripcion_ratio_pesimo": f"Error en la comprobacion: {exc}",
                    "ratios": [],
                    "complementarios": [],
                }
            )
    return output


def schema(model_name: str) -> Dict[str, Any]:
    """Inputs del modelo + columnas de resultado (comunes)."""
    bundle = model_registry.get(model_name)
    adapter = bundle["adapter"]
    fn = getattr(adapter, "input_schema", None)
    inputs = fn(bundle) if fn is not None else []
    return {
        "model": bundle["name"],
        "inputs": inputs,
        "result_columns": list(SERVED_COLUMNS),
    }


def model_status() -> Dict[str, Any]:
    return {
        "available_models": model_registry.list_models(),
        "loaded_models": model_registry.loaded_models(),
    }
