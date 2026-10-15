"""Servidor HTTP central de inferencia y comprobacion estructural.

Cada modelo es un paquete autocontenido en `models/<NAME>/` (lo instala el Makefile).
Se cargan todos los modelos instalados y conviven en memoria; cada peticion se enruta al
modelo indicado. Los resultados son SIEMPRE las 63 columnas de CODAME (`Tabla_MOMENT_M1`).
Sobre esa tabla (editada por el revisor) se puede ejecutar la comprobacion AISC 360-10.

Endpoints:
  GET  /health                  Estado del servidor
  GET  /models                  Modelos instalados y cargados
  GET  /model                   Contrato del modelo por defecto
  GET  /schema?model=...        Inputs del modelo + columnas de resultado CODAME
  POST /model/activate          Carga/recarga un modelo por nombre
  POST /predict                 {"model": "...", "rows": [...]} -> columnas CODAME + comprobacion ("checks")
  POST /check                   Comprobacion AISC 360-10 sobre filas CODAME
  POST /validate                Guarda filas validadas (sin reentreno)
  GET  /dataset/summary         Resumen del dataset acumulado
"""

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
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

# Logs: un archivo por sesion (cada arranque del servidor), sin salida por pantalla.
# La ruta se comparte por variable de entorno con los procesos hijos del ajuste (refinar.py),
# que escriben en el mismo archivo. AI_LOG_CONSOLE=1 vuelve a mostrarlos tambien por consola.
_LOG_DIR = config.DATA_DIR / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = os.environ.setdefault(
    "AI_LOG_FILE", str(_LOG_DIR / f"server_{datetime.now():%Y-%m-%d_%H-%M-%S}.log")
)
_handlers = [logging.FileHandler(LOG_FILE, encoding="utf-8")]
if os.environ.get("AI_LOG_CONSOLE", "").strip().lower() in ("1", "true", "yes"):
    _handlers.append(logging.StreamHandler())
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=_handlers,
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
    title="Servidor de inferencia y comprobacion - conexiones",
    version="1.0.0",
    description=(
        "Servidor de pre-diseno por IA y comprobacion estructural AISC 360-10. Los modelos "
        "viven en `models/<NAME>/` y conviven en memoria; cada peticion se enruta al modelo "
        "indicado en `model`. El contrato de entrada lo define su `core/adapter.py`; si una "
        "peticion no lo cumple se devuelve **HTTP 422**. El resultado son SIEMPRE las 63 "
        "columnas de CODAME (`Tabla_MOMENT_M1`), con independencia del modelo."
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
        ..., description="Filas de la tabla (inputs del modelo o filas CODAME, segun endpoint)."
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
    return {
        "status": "ok",
        "default_model": config.MODEL_NAME,
        **predictor.model_status(),
        "dataset_rows": storage.summary()["total_rows"],
    }


@app.get("/models", tags=["modelos"], summary="Lista los modelos instalados y cargados")
def list_models() -> Dict[str, Any]:
    return {
        "available_models": model_registry.list_models(),
        "loaded_models": model_registry.loaded_models(),
        "default_model": config.MODEL_NAME,
    }


@app.get("/model", tags=["modelos"], summary="Contrato del modelo por defecto")
def default_model() -> Dict[str, Any]:
    try:
        bundle = model_registry.get(config.MODEL_NAME)
    except KeyError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {"name": bundle["name"], **bundle["contract"]}


@app.get(
    "/schema",
    tags=["modelos"],
    summary="Inputs del modelo y columnas de resultado",
    response_description="Campos de entrada (tipo/descripcion/opciones) y las 63 columnas CODAME.",
    responses={404: {"description": "El modelo no esta disponible"}},
)
def schema(model: str | None = Query(default=None, description="Modelo (por defecto, el configurado)")):
    """Esquema de entrada del modelo indicado y columnas de resultado (fijas)."""
    name = model or config.MODEL_NAME
    try:
        return predictor.schema(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/model/activate", tags=["modelos"], summary="Carga/recarga un modelo")
def activate_model(payload: ActivateIn):
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
    summary="Pre-diseña y devuelve las 63 columnas CODAME",
    response_description="Una fila por entrada con las columnas de CODAME.",
    responses={
        422: {"description": "La peticion no cumple el contrato del modelo."},
        404: {"description": "El modelo indicado no esta disponible"},
    },
)
def predict(payload: RowsIn):
    if not payload.rows:
        raise HTTPException(status_code=400, detail="La peticion no trae filas (rows vacio)")
    name = payload.model or config.MODEL_NAME
    log.info("/predict: modelo=%s, %d filas", name, len(payload.rows))
    try:
        predictions, checks = predictor.predict_and_check(name, payload.rows)
    except predictor.InputContractError:
        raise
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        log.exception("Error prediciendo")
        raise HTTPException(status_code=500, detail=f"Error al predecir: {exc}")
    log.info("/predict: %d filas devueltas", len(predictions))
    return {"model_name": name, "rows": predictions, "checks": checks}


@app.post(
    "/check",
    tags=["comprobacion"],
    summary="Ejecuta la comprobacion AISC 360-10 sobre filas CODAME",
    response_description="Una fila por entrada con cumple, ratio pesimo y detalle.",
)
@app.post("/comprobar", tags=["comprobacion"], include_in_schema=False)
def check(payload: RowsIn):
    if not payload.rows:
        raise HTTPException(status_code=400, detail="La peticion no trae filas (rows vacio)")
    log.info("/check: comprobando %d filas", len(payload.rows))
    try:
        results = predictor.check_rows(payload.rows)
    except Exception as exc:  # noqa: BLE001
        log.exception("Error en la comprobacion")
        raise HTTPException(status_code=500, detail=f"Error en la comprobacion: {exc}")
    return {"status": "ok", "rows": results}


@app.post("/validate", tags=["datos"], summary="Guarda filas validadas en el dataset")
def validate(payload: RowsIn, background_tasks: BackgroundTasks):
    if not payload.rows:
        raise HTTPException(status_code=400, detail="La peticion no trae filas (rows vacio)")
    try:
        result = storage.append_rows(payload.rows, source="excel")
    except storage.InvalidRowsError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
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

    # log_config=None: los logs de uvicorn (accesos, errores) van al mismo archivo, no a pantalla.
    print(f"Servidor en http://{config.HOST}:{config.PORT}  |  logs: {LOG_FILE}", flush=True)
    uvicorn.run(app, host=config.HOST, port=config.PORT, log_config=None)