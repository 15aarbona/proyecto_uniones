"""
Servidor HTTP central de inferencia y reentrenamiento.

Endpoints:
  GET  /health            Estado del servidor y del modelo en memoria
  POST /predict           Predicciones para todas las filas de Excel
  POST /validate          Guarda filas validadas y programa reentrenamiento cada 100 filas
  POST /retrain           Dispara el reentrenamiento manual
  GET  /dataset/summary   Resumen del dataset acumulado
"""
import logging
import subprocess
import sys
from typing import Any, Dict, List

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

import config
import predictor
import storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(config.LOG_PATH), logging.StreamHandler()],
)
log = logging.getLogger("ai-server")

app = FastAPI(title="Servidor de inferencia — conexiones", version="0.1.0")


class RowsIn(BaseModel):
    rows: List[Dict[str, Any]] = Field(..., description="Filas recibidas desde Excel")


def _check_api_key(x_api_key: str | None):
    if x_api_key != config.API_KEY:
        raise HTTPException(status_code=401, detail="API key inválida o ausente (cabecera X-API-Key)")


@app.get("/health")
def health():
    status = predictor.model_status()
    ds = storage.summary()
    return {
        "status": "ok",
        "model_name": config.MODEL_VERSION,
        **status,
        "dataset_rows": ds["total_rows"],
    }


@app.post("/predict")
def predict(payload: RowsIn, x_api_key: str | None = Header(default=None)):
    _check_api_key(x_api_key)
    if not payload.rows:
        raise HTTPException(status_code=400, detail="La petición no trae filas (rows vacío)")
    log.info(f"/predict: {len(payload.rows)} filas recibidas")
    try:
        predictions = predictor.predict_rows(payload.rows)
    except Exception as e:
        log.exception("Error prediciendo")
        raise HTTPException(status_code=500, detail=f"Error al predecir: {e}")
    log.info(f"/predict: {len(predictions)} filas devueltas")
    return {"rows": predictions, "model_version": predictor.model_status()["model_version"]}


def _train_and_reload():
    """Ejecuta el script de entrenamiento usando el ejecutable actual de Python."""
    log.info("Iniciando reentrenamiento del modelo en segundo plano...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "train"],
            capture_output=True,
            text=True,
            cwd=config.BASE_DIR,
        )
        if result.returncode == 0:
            log.info("Reentrenamiento completado con éxito. Recargando pesos en memoria...")
            predictor.reload_model()
        else:
            log.error(f"Error en el reentrenamiento: {result.stderr}")
    except Exception as e:
        log.exception(f"Excepción al reentrenar: {e}")


@app.post("/validate")
def validate(
    payload: RowsIn,
    background_tasks: BackgroundTasks,
    x_api_key: str | None = Header(default=None),
):
    _check_api_key(x_api_key)
    if not payload.rows:
        raise HTTPException(status_code=400, detail="La petición no trae filas (rows vacío)")

    rows_before = len(storage.load_dataset())
    try:
        result = storage.append_rows(payload.rows, source="excel")
    except storage.InvalidRowsError as e:
        log.warning(f"/validate rechazado: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    rows_after = result["total_rows"]

    log.info(f"/validate: guardadas {result['saved']} filas, total dataset={rows_after}")

    # Si se cruza un múltiplo de 100 filas (ej. de 80 a 105), se lanza el reentrenamiento
    retrain_triggered = (rows_after // 100) > (rows_before // 100)
    if retrain_triggered:
        log.info(f"Paso de centenar ({rows_before} -> {rows_after} filas). Programando reentrenamiento...")
        background_tasks.add_task(_train_and_reload)

    return {
        "status": "ok",
        **result,
        "retrain_triggered": retrain_triggered,
    }


@app.post("/retrain")
def force_retrain(
    background_tasks: BackgroundTasks,
    x_api_key: str | None = Header(default=None),
):
    _check_api_key(x_api_key)
    background_tasks.add_task(_train_and_reload)
    return {
        "status": "ok",
        "message": "Reentrenamiento iniciado en segundo plano.",
    }


@app.get("/dataset/summary")
def dataset_summary(x_api_key: str | None = Header(default=None)):
    _check_api_key(x_api_key)
    return storage.summary()