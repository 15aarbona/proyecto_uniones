"""Servidor HTTP central de inferencia con modelos intercambiables.

Cada modelo es un paquete autocontenido en `models/<NAME>/` (lo instala el Makefile
del repositorio). El modelo activo se puede **cambiar en caliente**, sin reiniciar,
con `POST /model/activate`; cada peticion termina con el modelo con el que empezo.

Endpoints:
  GET  /health            Estado del servidor y del modelo activo
  GET  /models            Modelos instalados y cual esta activo
  POST /model/activate    Activa (o recarga) un modelo por nombre
  POST /predict           Predicciones + dataset completo de inputs
  POST /validate          Guarda filas validadas (sin reentreno)
  GET  /dataset/summary   Resumen del dataset acumulado
"""

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import config
import model_registry
import predictor
import storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(config.LOG_PATH), logging.StreamHandler()],
)
log = logging.getLogger("ai-server")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        bundle = model_registry.activate_configured()
        log.info("Modelo activo al arrancar: %s (%s)", bundle["name"], bundle["dir"])
    except Exception as exc:  # noqa: BLE001
        log.error("No se pudo activar el modelo configurado: %s", exc)
    yield


app = FastAPI(
    title="Servidor de inferencia - conexiones",
    version="1.0.0",
    description=(
        "Servidor de inferencia para modelos de prediseno de uniones atornilladas. "
        "Los modelos viven en `models/<NAME>/` y pueden intercambiarse en caliente. "
        "El contrato de entrada de cada modelo lo define su `core/adapter.py`; si una "
        "peticion no cumple el contrato se devuelve **HTTP 422** indicando los campos "
        "que faltan."
    ),
    lifespan=lifespan,
)


class RowsIn(BaseModel):
    rows: List[Dict[str, Any]] = Field(
        ..., description="Filas recibidas desde Excel (inputs basicos del modelo)."
    )


class ActivateIn(BaseModel):
    name: str = Field(..., description="Nombre de la carpeta del modelo, p. ej. 'V11'.")


def _check_api_key(x_api_key: str | None):
    if x_api_key != config.API_KEY:
        raise HTTPException(
            status_code=401, detail="API key invalida o ausente (cabecera X-API-Key)"
        )


@app.exception_handler(predictor.InputContractError)
async def _contract_error_handler(request: Request, exc: predictor.InputContractError):
    return JSONResponse(
        status_code=422,
        content={
            "detail": str(exc),
            "missing": exc.missing,
            "expected": exc.expected,
        },
    )


@app.get("/health", tags=["estado"], summary="Estado del servidor y del modelo activo")
def health() -> Dict[str, Any]:
    """Devuelve el estado del servidor, el modelo activo y la lista de instalados."""
    return {
        "status": "ok",
        "model_name": config.MODEL_NAME,
        **predictor.model_status(),
        "dataset_rows": storage.summary()["total_rows"],
    }


@app.get(
    "/models",
    tags=["modelos"],
    summary="Lista los modelos instalados",
    response_description="Modelos disponibles y el activo.",
)
def list_models() -> Dict[str, Any]:
    """Modelos instalados en `models/` y el que esta activo en memoria."""
    status = predictor.model_status()
    return {"available_models": model_registry.list_models(), "active": status.get("model_name")}


@app.get("/model", tags=["modelos"], summary="Contrato del modelo activo")
def active_model() -> Dict[str, Any]:
    """Contrato (inputs basicos, features, outputs) del modelo en memoria."""
    status = predictor.model_status()
    if not status["model_loaded"]:
        raise HTTPException(status_code=503, detail="No hay ningun modelo activo")
    return status


@app.post(
    "/model/activate",
    tags=["modelos"],
    summary="Activa (o recarga) un modelo en caliente",
    response_description="Modelo activado y su contrato.",
    responses={404: {"description": "El modelo no esta instalado"}},
)
def activate_model(payload: ActivateIn, x_api_key: str | None = Header(default=None)):
    """Carga desde disco el modelo `name` y lo deja activo, sin reiniciar el servidor.

    Si ya estaba activo, lo recarga (util si se han actualizado sus pesos)."""
    _check_api_key(x_api_key)
    try:
        bundle = model_registry.activate(payload.name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        log.exception("Error activando modelo %s", payload.name)
        raise HTTPException(status_code=500, detail=f"Error activando modelo: {exc}")
    log.info("Modelo activado: %s", bundle["name"])
    return {"status": "ok", "model_name": bundle["name"], **bundle["contract"]}


@app.post(
    "/predict",
    tags=["inferencia"],
    summary="Predice y devuelve inputs completos + predicciones",
    response_description="Una fila por entrada con todas las columnas (inputs + outputs).",
    responses={
        422: {
            "description": (
                "Los inputs no cumplen el contrato del modelo activo. "
                "El cuerpo incluye `missing` (campos que faltan) y `expected` (contrato)."
            )
        },
        503: {"description": "No hay ningun modelo activo"},
    },
)
def predict(payload: RowsIn, x_api_key: str | None = Header(default=None)):
    """Valida el contrato, preprocesa y predice con el modelo activo.

    La respuesta incluye, por fila, las entradas basicas, las features completas
    calculadas por el adaptador y las predicciones del modelo."""
    _check_api_key(x_api_key)
    if not payload.rows:
        raise HTTPException(status_code=400, detail="La peticion no trae filas (rows vacio)")
    log.info("/predict: %d filas recibidas", len(payload.rows))
    try:
        predictions = predictor.predict_rows(payload.rows)
    except predictor.InputContractError:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        log.exception("Error prediciendo")
        raise HTTPException(status_code=500, detail=f"Error al predecir: {exc}")
    status = predictor.model_status()
    log.info("/predict: %d filas devueltas", len(predictions))
    return {
        "model_name": status.get("model_name"),
        "raw_inputs": status.get("raw_inputs", []),
        "output_fields": status.get("outputs", []),
        "rows": predictions,
    }


@app.post(
    "/validate",
    tags=["datos"],
    summary="Guarda filas validadas en el dataset",
    responses={422: {"description": "Filas sin las entradas minimas"}},
)
def validate(
    payload: RowsIn,
    background_tasks: BackgroundTasks,
    x_api_key: str | None = Header(default=None),
):
    _check_api_key(x_api_key)
    if not payload.rows:
        raise HTTPException(status_code=400, detail="La peticion no trae filas (rows vacio)")
    try:
        result = storage.append_rows(payload.rows, source="excel")
    except storage.InvalidRowsError as exc:
        log.warning("/validate rechazado: %s", exc)
        raise HTTPException(status_code=422, detail=str(exc))

    log.info("/validate: guardadas %d filas, total dataset=%d", result["saved"], result["total_rows"])
    return {"status": "ok", **result}


@app.get("/dataset/summary", tags=["datos"], summary="Resumen del dataset acumulado")
def dataset_summary(x_api_key: str | None = Header(default=None)):
    _check_api_key(x_api_key)
    return storage.summary()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=config.HOST, port=config.PORT)
