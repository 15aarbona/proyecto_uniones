"""Servidor HTTP central de inferencia con modelos intercambiables.

Cada modelo es un paquete autocontenido en `models/<NAME>/` (lo instala el Makefile).
Se cargan todos los modelos instalados y conviven en memoria; cada peticion se enruta
al modelo indicado en el cuerpo o en la query. Se pueden recargar en caliente, sin
reiniciar, con `POST /model/activate`.

Endpoints:
  GET  /health                  Estado del servidor
  GET  /models                  Modelos instalados y cargados
  GET  /model                   Contrato del modelo por defecto
  GET  /options?model=...       Valores validos para los desplegables (del modelo)
  POST /model/activate          Carga/recarga un modelo por nombre
  POST /predict                 {"model": "...", "rows": [...]}
  POST /validate                Guarda filas validadas (sin reentreno)
  GET  /dataset/summary         Resumen del dataset acumulado
"""

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
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
        model_registry.activate_configured()
        log.info("Modelos cargados: %s", model_registry.loaded_models())
    except Exception as exc:  # noqa: BLE001
        log.error("No se pudo cargar ningun modelo: %s", exc)
    yield


app = FastAPI(
    title="Servidor de inferencia - conexiones",
    version="1.0.0",
    description=(
        "Servidor de inferencia para modelos de prediseno de uniones atornilladas. "
        "Los modelos viven en `models/<NAME>/` y conviven en memoria; cada peticion se "
        "enruta al modelo indicado en `model`. El contrato de tabla de cada modelo lo "
        "define su `core/adapter.py`; si una peticion no cumple el contrato se devuelve "
        "**HTTP 422** indicando los campos que faltan. Las columnas de la respuesta son "
        "los inputs enviados (o imputados) mas los campos predichos por el modelo."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class RowsIn(BaseModel):
    model: str | None = Field(
        default=None, description="Modelo a usar (carpeta en models/). Si falta, el por defecto."
    )
    rows: List[Dict[str, Any]] = Field(
        ..., description="Filas de la tabla (inputs del modelo; los predichos pueden ir en blanco)."
    )


class ActivateIn(BaseModel):
    name: str = Field(..., description="Nombre de la carpeta del modelo, p. ej. 'V11'.")


@app.exception_handler(predictor.InputContractError)
async def _contract_error_handler(request: Request, exc: predictor.InputContractError):
    return JSONResponse(
        status_code=422,
        content={
            "detail": str(exc),
            "model": exc.model,
            "missing": exc.missing,
            "expected": exc.expected,
        },
    )


@app.get("/health", tags=["estado"], summary="Estado del servidor")
def health() -> Dict[str, Any]:
    """Estado del servidor y modelos instalados/cargados."""
    return {
        "status": "ok",
        "default_model": config.MODEL_NAME,
        **predictor.model_status(),
        "dataset_rows": storage.summary()["total_rows"],
    }


@app.get(
    "/models",
    tags=["modelos"],
    summary="Lista los modelos instalados y cargados",
    response_description="Modelos disponibles y cargados en memoria.",
)
def list_models() -> Dict[str, Any]:
    """Modelos instalados en `models/` y los cargados actualmente."""
    return {
        "available_models": model_registry.list_models(),
        "loaded_models": model_registry.loaded_models(),
        "default_model": config.MODEL_NAME,
    }


@app.get("/model", tags=["modelos"], summary="Contrato del modelo por defecto")
def default_model() -> Dict[str, Any]:
    """Contrato (inputs/opcionales/outputs) del modelo por defecto."""
    try:
        bundle = model_registry.get(config.MODEL_NAME)
    except KeyError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {"name": bundle["name"], **bundle["contract"]}


@app.get(
    "/options",
    tags=["modelos"],
    summary="Valores validos para los desplegables",
    response_description="Valores admitidos por campo, publicados por el modelo.",
    responses={
        404: {"description": "El modelo no esta disponible o no publica opciones"},
    },
)
def options(model: str | None = Query(default=None, description="Modelo (por defecto, el configurado)")):
    """Opciones (perfiles, materiales...) del modelo indicado."""
    name = model or config.MODEL_NAME
    try:
        return predictor.options(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except predictor.InputContractError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post(
    "/model/activate",
    tags=["modelos"],
    summary="Carga/recarga un modelo",
    response_description="Modelo cargado y su contrato.",
    responses={404: {"description": "El modelo no esta instalado"}},
)
def activate_model(payload: ActivateIn):
    """Carga (o recarga desde disco) el modelo `name`, sin reiniciar el servidor."""
    try:
        bundle = model_registry.activate(payload.name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        log.exception("Error activando modelo %s", payload.name)
        raise HTTPException(status_code=500, detail=f"Error activando modelo: {exc}")
    log.info("Modelo cargado: %s", bundle["name"])
    return {"status": "ok", "name": bundle["name"], **bundle["contract"]}


@app.post(
    "/predict",
    tags=["inferencia"],
    summary="Predice y devuelve la tabla completa",
    response_description="Una fila por entrada con inputs + campos predichos.",
    responses={
        422: {
            "description": (
                "La peticion no cumple el contrato del modelo. El cuerpo incluye "
                "`model`, `missing` (campos que faltan) y `expected` (contrato)."
            )
        },
        404: {"description": "El modelo indicado no esta disponible"},
    },
)
def predict(payload: RowsIn):
    """Valida el contrato, preprocesa y predice con el modelo indicado.

    Devuelve, por fila, los inputs (enviados o imputados) y los campos predichos."""
    if not payload.rows:
        raise HTTPException(status_code=400, detail="La peticion no trae filas (rows vacio)")
    name = payload.model or config.MODEL_NAME
    log.info("/predict: modelo=%s, %d filas", name, len(payload.rows))
    try:
        predictions = predictor.predict_rows(name, payload.rows)
    except predictor.InputContractError:
        raise
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        log.exception("Error prediciendo")
        raise HTTPException(status_code=500, detail=f"Error al predecir: {exc}")
    log.info("/predict: %d filas devueltas", len(predictions))
    return {
        "model_name": name,
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
):
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
def dataset_summary():
    return storage.summary()


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/web/conexiones_tr.html")


app.mount("/web", StaticFiles(directory=config.BASE_DIR / "web", html=True), name="web")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=config.HOST, port=config.PORT)
