"""Artefactos Parquet temporales para no enviar resultados pesados al contexto MCP.

El tool devuelve solo un resumen pequeno + una URL. El diseno completo (una fila por
E1/E2/E3 de cada conexion) se escribe en el directorio temporal del dispositivo y se
sirve por `/artifacts/<id>.parquet`.
"""
from __future__ import annotations

import logging
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

import config

log = logging.getLogger("ai-server")

_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def _ensure_dir(directory: Optional[Path] = None) -> Path:
    path = Path(directory or config.ARTIFACTS_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def cleanup(directory: Optional[Path] = None) -> int:
    """Elimina artefactos caducados. Devuelve cuantos borro."""
    path = _ensure_dir(directory)
    ttl = max(0.0, float(config.ARTIFACT_TTL_S))
    if ttl <= 0:
        return 0
    limit = time.time() - ttl
    removed = 0
    for item in path.glob("*.parquet"):
        try:
            if item.stat().st_mtime < limit:
                item.unlink()
                removed += 1
        except OSError:
            pass
    return removed


def _find_existing(rows: List[Dict[str, Any]], label: str) -> Dict[str, Any]:
    for row in rows:
        if str(row.get("Escenario", "")) == label:
            return row
    return {}


def _find_check(checks: List[Dict[str, Any]], label: str) -> Dict[str, Any]:
    for check in checks:
        if str(check.get("Escenario", "")) == label:
            return check
    return {}


def _design_rows(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Una fila por E1/E2/E3 de cada conexion procesada correctamente."""
    out: List[Dict[str, Any]] = []
    for item in results:
        if item.get("status") != "OK":
            # Los errores de conexion se resumen en la respuesta MCP, no son disenos.
            continue
        result = item.get("resultado") or {}
        uid = item.get("unicode") or "?"
        rows = result.get("rows") or []
        checks = result.get("checks") or []
        for esc in result.get("escenarios") or []:
            idx = esc.get("id")
            label = f"{idx} - {esc.get('escenario', '')}"
            found = bool(esc.get("encontrado"))
            base: Dict[str, Any] = {
                "UNICODE": uid,
                "Status": "OK",
                "Escenario": idx,
                "EscenarioNombre": esc.get("escenario"),
                "Encontrado": found,
                "Motivo": esc.get("motivo"),
                "Paso": esc.get("paso"),
                "FactorCarga": esc.get("factor_carga"),
                "RatioMoment": esc.get("ratio_moment"),
                "RatioShear": esc.get("ratio_shear"),
                "RatioAxial": esc.get("ratio_axial"),
                "Cumple": esc.get("cumple"),
                "RatioPesimo": esc.get("ratio_pesimo"),
                "DescripcionRatioPesimo": esc.get("descripcion_ratio_pesimo"),
                "Lh": esc.get("Lh"),
                "n_cantonera": esc.get("n_cantonera"),
                "FueraRangoEntrenamiento": ", ".join(esc.get("fuera_rango_entrenamiento") or []),
            }
            if found:
                design = _find_existing(rows, label)
                check = _find_check(checks, label)
                # Columnas CODAME del diseno + resumen de comprobacion.
                for key, value in design.items():
                    if key != "Escenario":
                        base[key] = value
                base["check_cumple"] = check.get("cumple")
                base["check_ratio_pesimo"] = check.get("ratio_pesimo")
                base["check_descripcion"] = check.get("descripcion_ratio_pesimo")
            out.append(base)
    return out


def save_scenarios(
    results: List[Dict[str, Any]],
    model_name: str,
    directory: Optional[Path] = None,
) -> Dict[str, Any]:
    """Escribe los disenos E1/E2/E3 en un Parquet temporal y devuelve sus metadatos."""
    path_dir = _ensure_dir(directory)
    cleanup(path_dir)
    rows = _design_rows(results)
    df = pd.DataFrame(rows)
    artifact_id = uuid.uuid4().hex
    file_path = path_dir / f"{artifact_id}.parquet"
    df.to_parquet(file_path, engine="pyarrow", index=False)
    ttl = max(0.0, float(config.ARTIFACT_TTL_S))
    expires = datetime.now(timezone.utc) + timedelta(seconds=ttl)
    base = config.PUBLIC_BASE_URL
    url = f"{base}/artifacts/{artifact_id}.parquet" if base else f"/artifacts/{artifact_id}.parquet"
    meta = {
        "id": artifact_id,
        "formato": "parquet",
        "filename": file_path.name,
        "url": url,
        "filas": int(len(df)),
        "bytes": int(file_path.stat().st_size),
        "expira_en": expires.isoformat(timespec="seconds"),
        "modelo": model_name,
    }
    log.info("artefacto: %s (%d filas, %d bytes) -> %s", artifact_id, len(df), meta["bytes"], file_path)
    return meta


def get_path(artifact_id: str, directory: Optional[Path] = None) -> Optional[Path]:
    """Ruta segura del Parquet o None si el ID no es valido/no existe/caduco."""
    if not _ID_RE.match(str(artifact_id or "")):
        return None
    path_dir = _ensure_dir(directory).resolve()
    path = (path_dir / f"{artifact_id}.parquet").resolve()
    try:
        path.relative_to(path_dir)
    except ValueError:
        return None
    if not path.is_file():
        return None
    return path
