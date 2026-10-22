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
  GET  /profiles?names=...      Geometria de secciones (para el visualizador 2D)
  POST /model/activate          Carga/recarga un modelo por nombre
  POST /predict                 {"model": "...", "rows": [...]} -> columnas CODAME + comprobacion ("checks")
  POST /scenarios               {"row": {...}} -> E1/E2/E3 subiendo cargas (parcial si se agota el tiempo)
  POST /check                   Comprobacion AISC 360-10 sobre filas CODAME
  POST /validate                Guarda filas validadas (sin reentreno)
  GET  /dataset/summary         Resumen del dataset acumulado
  MCP  /mcp                     Servidor MCP para integracion con Microsoft Copilot
"""

import asyncio
import contextlib
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import pandas as pd

import catalogo
import config
import model_registry
import escenarios
import predictor
import refinar
import storage

import dataset_valid, retrain_manager

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

# Logs: un archivo por sesion (cada arranque del servidor), sin salida por pantalla.
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


# =============================================================================
# Runner de trabajo pesado (no bloquear el event loop de FastAPI/MCP)
# =============================================================================
class _Runner:
    """Ejecuta funciones sincronas en una hebra dedicada.

    Si una peticion supera su timeout, se reemplaza el executor para que las siguientes
    no queden detras de una tarea colgada (la hebra antigua puede seguir viva; se deja
    terminar y se descarta).
    """

    def __init__(self, name: str, max_workers: int = 1) -> None:
        self._name = name
        self._max_workers = max(1, int(max_workers))
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(
            max_workers=self._max_workers, thread_name_prefix=name
        )

    def submit(self, fn, *args, **kwargs):
        with self._lock:
            return self._executor.submit(fn, *args, **kwargs)

    def reset(self) -> None:
        with self._lock:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = ThreadPoolExecutor(
                max_workers=self._max_workers, thread_name_prefix=self._name
            )

    def shutdown(self) -> None:
        with self._lock:
            self._executor.shutdown(wait=False, cancel_futures=True)


_PREDICT_RUNNER = _Runner("mcp-predict")
_CHECK_RUNNER = _Runner("mcp-check")
# Cola ilimitada de escenarios; el limite real lo ponen los workers y el batcher.
_SCENARIO_RUNNER = _Runner("scenarios", max_workers=config.SCENARIO_WORKERS)


async def _run_sync(runner: _Runner, fn, args: tuple, timeout: Optional[float],
                    label: str, kwargs: Optional[Dict[str, Any]] = None):
    """Ejecuta `fn(*args, **kwargs)` fuera del event loop.

    Con `timeout=None` espera sin limite (los escenarios usan su propio deadline
    cooperativo, que empieza cuando el workitem arranca, no cuando entra en cola).
    """
    future = runner.submit(fn, *args, **(kwargs or {}))
    if timeout is None:
        return await asyncio.wrap_future(future)
    try:
        return await asyncio.wait_for(asyncio.wrap_future(future), timeout=timeout)
    except asyncio.TimeoutError:
        runner.reset()
        log.error("%s: timeout tras %.0fs; runner reiniciado", label, timeout)
        raise TimeoutError(f"{label}: tiempo de espera agotado ({timeout:.0f}s)") from None


# =============================================================================
# Servidor MCP (Model Context Protocol) para Microsoft Copilot
# =============================================================================
mcp = FastMCP(
    "ServidorConexionesEstructurales",
    stateless_http=True,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False  # o allowed_hosts=["0tpn3dld-8080.uks1.devtunnels.ms", "localhost:*"]
    ),
)

@mcp.tool()
async def predecir_conexion(rows: List[Dict[str, Any]], model: str = "") -> Dict[str, Any]:
    """Pre-diseña conexiones y devuelve las 63 columnas CODAME con sus comprobaciones.

    Args:
        rows: Lista de diccionarios con las propiedades geométricas y de carga.
        model: Nombre opcional del modelo a usar (si falta, usa el modelo configurado por defecto).
    """
    name = model or config.MODEL_NAME
    log.info("[MCP] /predict: modelo=%s, %d filas", name, len(rows))
    predictions, checks = await _run_sync(
        _PREDICT_RUNNER,
        predictor.predict_and_check,
        (name, rows),
        config.PREDICT_TIMEOUT_S,
        "predecir_conexion",
    )
    return {"model_name": name, "rows": predictions, "checks": checks}


@mcp.tool()
async def comprobar_aisc(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Ejecuta la comprobación estructural AISC 360-10 sobre filas CODAME.

    Args:
        rows: Lista de filas con los parámetros del diseño CODAME a verificar.
    """
    log.info("[MCP] /check: comprobando %d filas", len(rows))
    results = await _run_sync(
        _CHECK_RUNNER,
        predictor.check_rows,
        (rows,),
        config.CHECK_TIMEOUT_S,
        "comprobar_aisc",
    )
    return {"status": "ok", "rows": results}


def _consultar_perfiles(names: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for raw in names.split(","):
        name = raw.strip()
        if not name:
            continue
        geom = catalogo.get_profile(name)
        if geom is None:
            result[name] = None
        else:
            def g(k):
                if k not in geom.index:
                    return None
                v = geom.get(k)
                return None if pd.isna(v) else v
            bf = g("bf_mm")
            if bf in (None, 0, 0.0):
                bf = g("b_mm")
            result[name] = {
                "type": g("type"), "d_mm": g("d_mm"), "bf_mm": bf,
                "tw_mm": g("tw_mm"), "tf_mm": g("tf_mm"), "r1_mm": g("r1_mm"),
            }
    return {"profiles": result}


@mcp.tool()
async def consultar_perfiles(names: str) -> Dict[str, Any]:
    """Consulta la geometría de secciones/perfiles de acero por nombre para el visualizador.

    Args:
        names: Nombres de los perfiles separados por comas (ej. "HEB200, IPE300").
    """
    return await asyncio.to_thread(_consultar_perfiles, names)


@mcp.tool()
async def listar_modelos() -> Dict[str, Any]:
    """Consulta los modelos de IA instalados y cargados en el servidor."""
    return {
        "available_models": model_registry.list_models(),
        "loaded_models": model_registry.loaded_models(),
        "default_model": config.MODEL_NAME,
    }


# =============================================================================
# Escenarios de carga (MCP)
# =============================================================================
@mcp.tool()
async def disenar_escenarios_carga(
    row: Dict[str, Any],
    model: str = "",
    incremento: float = 0.05,
    max_pasos: int = 40,
) -> Dict[str, Any]:
    """Predice UNA conexion y busca 3 disenos de referencia subiendo las cargas un 5 % por paso.

    Devuelve `tabla_markdown` (la tabla a mostrar al usuario), `escenarios` (con la fila CODAME
    completa de cada diseno) y `historial` (todos los pasos probados).
      E1: mayor carga que aguanta SIN cantonera.
      E2: primer diseno CON cantonera.
      E3: mayor carga que aguanta CON cantonera.
    Solo cuentan los disenos que cumplen la comprobacion AISC 360-10.

    Args:
        row: UNA fila con UNICODE, BEAM, COLUMN, ratio_moment, ratio_shear, ratio_axial
            (0-1) y opcionalmente Normativas, grado_acero, clase_tornillo.
        model: Nombre opcional del modelo (por defecto, el configurado).
        incremento: Aumento de carga por paso (0.05 = 5 %).
        max_pasos: Maximo de pasos de aumento a explorar.
    """
    name = model or config.MODEL_NAME
    log.info("[MCP] escenarios: modelo=%s", name)
    result = await _run_sync(
        _SCENARIO_RUNNER,
        escenarios.run,
        (name, row),
        None,
        "disenar_escenarios_carga",
        {
            "incremento": incremento,
            "max_pasos": max_pasos,
            "timeout_s": config.SCENARIO_TIMEOUT_S,
        },
    )
    log.info(
        "[MCP] escenarios: %s (parcial=%s, %.1fs)",
        result.get("parada"), result.get("parcial"), result.get("tiempo_s", 0.0),
    )
    return {"model_name": name, **result}


# =============================================================================
# App FastAPI & Lifespan
# =============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Carga de modelos, batcher de inferencia, pool de refinado y watcher de reentreno
    try:
        model_registry.activate_configured()
        log.info("Modelos cargados: %s", model_registry.loaded_models())
    except Exception as exc:  # noqa: BLE001
        log.error("No se pudo cargar ningun modelo: %s", exc)
    try:
        predictor.start_inference()
    except Exception:  # noqa: BLE001
        log.exception("No se pudo iniciar el batcher de inferencia")
    try:
        refinar.start_backend()
        retrain_manager.start_watcher()
    except Exception as exc:  # noqa: BLE001
        log.error("No se pudo iniciar el refinado/reentreno: %s", exc)

    try:
        # Administrador de sesión de MCP sobre HTTP/SSE
        async with contextlib.AsyncExitStack() as stack:
            await stack.enter_async_context(mcp.session_manager.run())
            yield
    finally:
        _SCENARIO_RUNNER.shutdown()
        try:
            predictor.shutdown_inference()
        except Exception:  # noqa: BLE001
            log.exception("Error cerrando el batcher de inferencia")
        try:
            refinar.shutdown_backend()
        except Exception:  # noqa: BLE001
            log.exception("Error cerrando el backend de refinado")
        _PREDICT_RUNNER.shutdown()
        _CHECK_RUNNER.shutdown()


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

mcp_app = mcp.streamable_http_app()
app.router.routes.extend(mcp_app.routes)

# =============================================================================
# Modelos Pydantic & Handlers
# =============================================================================
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


# =============================================================================
# Endpoints HTTP REST
# =============================================================================
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


@app.get(
    "/profiles",
    tags=["catalogo"],
    summary="Geometria de secciones por nombre (para el visualizador 2D)",
)
def profiles(names: str = Query(..., description="Nombres de perfil separados por comas")):
    """Devuelve {nombre: {cota: valor}} o null por cada perfil desconocido."""
    result: Dict[str, Any] = {}
    for raw in names.split(","):
        name = raw.strip()
        if not name:
            continue
        geom = catalogo.get_profile(name)
        if geom is None:
            result[name] = None
        else:
            def g(k):
                if k not in geom.index:
                    return None
                v = geom.get(k)
                return None if pd.isna(v) else v
            bf = g("bf_mm")
            if bf in (None, 0, 0.0):
                bf = g("b_mm")   # en el catalogo EU el ancho de ala va en b_mm
            result[name] = {
                "type": g("type"), "d_mm": g("d_mm"), "bf_mm": bf,
                "tw_mm": g("tw_mm"), "tf_mm": g("tf_mm"), "r1_mm": g("r1_mm"),
            }
    return {"profiles": result}


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
        predictions, checks, rows_raw = predictor.predict_full(name, payload.rows)
    except predictor.InputContractError:
        raise
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        log.exception("Error prediciendo")
        raise HTTPException(status_code=500, detail=f"Error al predecir: {exc}")
    log.info("/predict: %d filas devueltas", len(predictions))
    return {"model_name": name, "rows": predictions, "checks": checks, "rows_raw": rows_raw}


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


@app.post("/dataset/append", tags=["datos"], summary="Guarda uniones validadas")
@app.post("/validate", tags=["datos"], include_in_schema=False)
def validate(payload: RowsIn):
    if not payload.rows:
        raise HTTPException(status_code=400, detail="rows vacio")
    retrain_manager.init_baseline()
    res = dataset_valid.append(payload.rows)

    print(f"[validate] recibidas={len(payload.rows)} added={res['added']} updated={res['updated']} "
          f"rechazadas={len(res['rejected'])} total={res['total_rows']}", flush=True)
    for r in res["rejected"][:10]: print("[validate] rechazada:", r, flush=True)

    if not res["added"] and not res["updated"]:
        raise HTTPException(status_code=422, detail="; ".join(res["rejected"][:5]) or "sin filas validas")
    started = retrain_manager.maybe_start() if res["added"] else False
    return {"status": "ok", **res, "retrain": retrain_manager.status(), "retrain_started": started}


@app.get("/retrain/status", tags=["datos"])
def retrain_status():
    return retrain_manager.status()


@app.post("/retrain", tags=["datos"])
def retrain_now():
    return {"started": retrain_manager.maybe_start(force=True), **retrain_manager.status()}


class ScenarioIn(BaseModel):
    model: str | None = Field(default=None, description="Modelo a usar. Si falta, el por defecto.")
    row: Dict[str, Any] = Field(..., description="UNA fila de entrada del modelo.")
    incremento: float = Field(default=0.05, gt=0, description="Aumento de carga por paso (0.05 = 5 %).")
    max_pasos: int = Field(default=40, ge=1, le=200)
    max_fallos_seguidos: int = Field(default=3, ge=1)


@app.post(
    "/scenarios",
    tags=["inferencia"],
    summary="Predice una fila y busca 3 disenos subiendo las cargas",
    response_description="Tabla E1 (max. sin cantonera), E2 (primera con cantonera), E3 (max. con cantonera).",
)
async def scenarios(payload: ScenarioIn):
    name = payload.model or config.MODEL_NAME
    log.info("/scenarios: modelo=%s", name)
    try:
        result = await _run_sync(
            _SCENARIO_RUNNER,
            escenarios.run,
            (name, payload.row),
            None,
            "scenarios",
            {
                "incremento": payload.incremento,
                "max_pasos": payload.max_pasos,
                "max_fallos_seguidos": payload.max_fallos_seguidos,
                "timeout_s": config.SCENARIO_TIMEOUT_S,
            },
        )
    except predictor.InputContractError:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        log.exception("Error generando escenarios")
        raise HTTPException(status_code=500, detail=f"Error en escenarios: {exc}")
    log.info(
        "/scenarios: %s (parcial=%s, %.1fs)",
        result.get("parada"), result.get("parcial"), result.get("tiempo_s", 0.0),
    )
    return {"model_name": name, **result}


@app.get("/dataset/summary", tags=["datos"], summary="Resumen del dataset acumulado")
def dataset_summary():
    return storage.summary()


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/web/conexiones_tr.html")


app.mount("/web", StaticFiles(directory=config.BASE_DIR / "web", html=True), name="web")

if __name__ == "__main__":
    import uvicorn

    # log_config=None: los logs de uvicorn van al mismo archivo, no a pantalla
    print(f"Servidor en http://{config.HOST}:{config.PORT}  |  logs: {LOG_FILE}", flush=True)
    uvicorn.run(app, host=config.HOST, port=config.PORT, log_config=None)