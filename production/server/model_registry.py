"""Registro de modelos con activacion en caliente.

Cada modelo vive en `models/<NAME>/` como paquete autocontenido:

    models/V11/
        core/adapter.py     <- contrato + preproceso + load + predict
        weights.pt
        preprocessor.joblib
        data/

El adaptador se importa como submodulo del paquete `core` (nombre top-level) para
que los preprocesadores serializados (`core.dataset.Preprocessor`) resuelvan. Solo
puede haber un `core` registrado a la vez, lo que encaja con tener un unico modelo
activo; `activate()` purga y re-registra bajo lock, de forma que las peticiones en
vuelo terminan con el bundle con el que empezaron.
"""

import importlib
import importlib.util
import sys
import threading
from pathlib import Path

import config

MODELS_DIR: Path = config.MODELS_DIR

_LOCK = threading.RLock()
_BUNDLE = None  # dict con model/pre/device/adapter/name/contract/dir


def list_models() -> list:
    """Nombres de los modelos instalados (carpetas con core/adapter.py)."""
    if not MODELS_DIR.exists():
        return []
    return sorted(
        p.name for p in MODELS_DIR.iterdir() if (p / "core" / "adapter.py").exists()
    )


def _purge_core():
    for name in [n for n in list(sys.modules) if n == "core" or n.startswith("core.")]:
        del sys.modules[name]


def _register_core(model_dir: Path):
    core_dir = (model_dir / "core").resolve()
    spec = importlib.util.spec_from_file_location(
        "core", core_dir / "__init__.py", submodule_search_locations=[str(core_dir)]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["core"] = module
    spec.loader.exec_module(module)
    return module


def activate(name: str) -> dict:
    """Carga (o recarga desde disco) el modelo `name` y lo deja como activo."""
    global _BUNDLE
    model_dir = MODELS_DIR / name
    if not (model_dir / "core" / "adapter.py").exists():
        raise FileNotFoundError(
            f"No hay modelo instalado en {model_dir}. "
            f"Instalalo con 'make install-model MODEL={name}'. "
            f"Disponibles: {list_models()}"
        )

    with _LOCK:
        _purge_core()
        _register_core(model_dir)
        adapter = importlib.import_module("core.adapter")
        bundle = adapter.load()
        bundle.update(
            {
                "name": getattr(adapter, "MODEL_NAME", name),
                "adapter": adapter,
                "dir": str(model_dir),
                "contract": adapter.contract(),
            }
        )
        _BUNDLE = bundle
        return bundle


def get() -> dict:
    """Bundle activo (o error si aun no se ha activado ninguno)."""
    if _BUNDLE is None:
        raise RuntimeError(
            "No hay ningun modelo activo. Activa uno con POST /model/activate "
            f"o configura MODEL_NAME en config.py. Disponibles: {list_models()}"
        )
    return _BUNDLE


def activate_configured() -> dict:
    """Activa el modelo indicado por config.MODEL_NAME (o el primero disponible)."""
    name = config.MODEL_NAME
    available = list_models()
    if name not in available:
        if not available:
            raise RuntimeError(
                f"No hay modelos instalados en {MODELS_DIR}. "
                f"Ejecuta 'make install-model MODEL=V11'."
            )
        raise FileNotFoundError(
            f"El modelo configurado '{name}' no esta instalado. Disponibles: {available}"
        )
    return activate(name)
