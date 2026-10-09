"""Servidor HTTP central de inferencia y comprobación estructural."""

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
    except Exception as exc:
        log.error("No se pudo cargar ningún modelo: %s", exc)
    yield


app = FastAPI(
    title="Servidor de inferencia y comprobación - conexiones",
    version="1.0.0",
    description="Servidor de pre-diseño por IA y comprobación AISC 360-10.",
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
        default=None, description="Modelo a usar (carpeta en models/)."
    )
    rows: List[Dict[str, Any]] = Field(
        ..., description="Filas de la tabla."
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


@app.get("/options", tags=["modelos"], summary="Valores válidos para los desplegables")
def options(model: str | None = Query(default=None)):
    name = model or config.MODEL_NAME
    try:
        return predictor.options(name)
    except (KeyError, predictor.InputContractError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/model/activate", tags=["modelos"], summary="Carga/recarga un modelo")
def activate_model(payload: ActivateIn):
    try:
        bundle = model_registry.activate(payload.name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        log.exception("Error activando modelo %s", payload.name)
        raise HTTPException(status_code=500, detail=f"Error activando modelo: {exc}")
    log.info("Modelo cargado: %s", bundle["name"])
    return {"status": "ok", "name": bundle["name"], **bundle["contract"]}


@app.post("/predict", tags=["inferencia"], summary="Predice la geometría de la conexión")
def predict(payload: RowsIn):
    if not payload.rows:
        raise HTTPException(status_code=400, detail="La petición no trae filas (rows vacío)")
    name = payload.model or config.MODEL_NAME
    log.info("/predict: modelo=%s, %d filas", name, len(payload.rows))
    try:
        predictions = predictor.predict_rows(name, payload.rows)
    except predictor.InputContractError:
        raise
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        log.exception("Error prediciendo")
        raise HTTPException(status_code=500, detail=f"Error al predecir: {exc}")
    return {
        "model_name": name,
        "rows": predictions,
    }


@app.post("/check", tags=["comprobacion"], summary="Ejecuta comprobaciones AISC 360-10")
@app.post("/comprobar", tags=["comprobacion"], include_in_schema=False)
def check(payload: RowsIn):
    if not payload.rows:
        raise HTTPException(status_code=400, detail="La petición no trae filas (rows vacío)")
    log.info("/check: comprobando %d filas", len(payload.rows))
    try:
        results = predictor.check_rows(payload.rows)
    except Exception as exc:
        log.exception("Error en la comprobación")
        raise HTTPException(status_code=500, detail=f"Error en la comprobación: {exc}")
    return {
        "status": "ok",
        "rows": results,
    }


@app.post("/validate", tags=["datos"], summary="Guarda filas validadas en el dataset")
def validate(payload: RowsIn, background_tasks: BackgroundTasks):
    if not payload.rows:
        raise HTTPException(status_code=400, detail="La petición no trae filas (rows vacío)")
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
    uvicorn.run(app, host=config.HOST, port=config.PORT)