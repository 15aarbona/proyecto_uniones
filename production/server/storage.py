"""
Persistencia del dataset global (filas ya VALIDADAS por un ingeniero). Como las columnas de
entrada todavía son "de prueba" y van a cambiar, el esquema se trata como dinámico: cada
`append_rows` añade las columnas que falten (con NaN en las filas antiguas) en vez de
exigir un esquema fijo desde el principio. Cuando el esquema real esté cerrado esto se puede
endurecer (columnas fijas, tipos, validación) sin tocar el resto del servidor.

Formato en disco: parquet (rápido, tipado, columnar) con el mismo criterio que ya usamos en
la app de escritorio (`model_store/global_dataset.parquet`).
"""
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List

import pandas as pd

import config

_LOCK = threading.Lock()  # evita carreras si llegan varias validaciones a la vez


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_dataset() -> pd.DataFrame:
    if config.DATASET_PATH.exists():
        return pd.read_parquet(config.DATASET_PATH)
    return pd.DataFrame()


def append_rows(rows: List[Dict[str, Any]], source: str = "excel") -> Dict[str, Any]:
    """Añade filas validadas al dataset global. Devuelve un resumen (nº guardadas, total, columnas)."""
    if not rows:
        return {"saved": 0, "total_rows": len(load_dataset()), "columns": list(load_dataset().columns)}

    stamped = []
    for r in rows:
        stamped.append({**r, "_validated_at": _now_iso(), "_source": source})
    new_df = pd.DataFrame(stamped)

    with _LOCK:
        current = load_dataset()
        combined = pd.concat([current, new_df], ignore_index=True) if not current.empty else new_df

        # Sanear columnas de tipo object para evitar conflictos en PyArrow
        # cuando conviven números y texto en la misma columna (ej. clase_tornillo)
        for col in combined.columns:
            if combined[col].dtype == "object":
                combined[col] = combined[col].apply(
                    lambda x: str(x) if pd.notna(x) and x is not None else None
                )

        combined.to_parquet(config.DATASET_PATH, index=False)

    return {"saved": len(rows), "total_rows": len(combined), "columns": list(combined.columns)}


def summary() -> Dict[str, Any]:
    df = load_dataset()
    if df.empty:
        return {"total_rows": 0, "columns": [], "last_validated_at": None}
    return {
        "total_rows": len(df),
        "columns": [c for c in df.columns if not c.startswith("_")],
        "last_validated_at": df["_validated_at"].max() if "_validated_at" in df.columns else None,
    }
