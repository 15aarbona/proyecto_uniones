# Servidor de inferencia — modelos intercambiables (en caliente)

Servidor HTTP (FastAPI) que sirve modelos de prediseño de uniones. Los modelos son
**paquetes autocontenidos** dentro de `models/<NAME>/`, se instalan con el `Makefile`
del repositorio y se pueden **activar/cambiar sin reiniciar** el servidor.

```
production/server/
├── main.py             Endpoints FastAPI (docs interactivas en /docs)
├── model_registry.py   Carga dinámica de modelos + activación en caliente
├── predictor.py        Validación de contrato, preproceso e inferencia
├── storage.py          Dataset acumulado (validaciones; sin reentreno por ahora)
├── config.py           Ajustes del servidor + MODEL_NAME por defecto
├── models/             Paquetes de modelo instalados (generado por `make`)
│   └── V11/
│       ├── core/adapter.py     contrato + preproceso + load + predict
│       ├── weights.pt
│       ├── preprocessor.joblib
│       └── data/               catálogos Tekla
└── requirements.txt    Solo si NO usas `uv` desde la raíz
```

## Arrancar (con `uv`, desde la raíz del proyecto)

```bash
make install-model MODEL=V11          # copia el modelo a production/server/models/V11
uv run uvicorn main:app --app-dir production/server --host 0.0.0.0 --port 8080 --workers 1
```

> `--workers 1` es **obligatorio** para el cambio en caliente: el modelo activo vive en
> memoria de cada proceso; con varios workers cada uno tendría su propio modelo activo.

`uv` toma las dependencias del `pyproject.toml` de la raíz (fastapi, uvicorn, torch,
scikit-learn, joblib, pandas, pyarrow). Si prefieres el flujo antiguo con `pip`:
`pip install -r production/server/requirements.txt`.

## Instalar / actualizar un modelo

El `Makefile` (raíz) copia el paquete del modelo (código `core/` + artefactos + datos):

```bash
make install-model MODEL=V11
```

Rutas de origen: cada modelo puede fijar las suyas en `<NAME>/model.mk` (relativas a su
carpeta). Si no existe o no define alguna, se usa el valor por defecto.

| destino en `models/<NAME>/` | variable en `<NAME>/model.mk` | por defecto |
|---|---|---|
| `core/` | `CORE` | `core` |
| `data/` | `DATA` | `data` |
| `weights.pt` | `WEIGHTS` | `artifacts/model_final.pt` |
| `preprocessor.joblib` | `PREPROC` | `artifacts/preprocessor.joblib` |

Ejemplo de `V11/model.mk` (V11 guarda sus pesos en `artifacts_v4/`):

```make
WEIGHTS = artifacts_v4/model_final.pt
PREPROC = artifacts_v4/preprocessor.joblib
```

También se pueden sobreescribir por línea de comandos:

```bash
make install-model MODEL=V11
make install-model MODEL=V12 WEIGHTS=V12/otra/best.pt PREPROC=V12/otra/preprocessor.joblib
```

Si faltan artefactos, el Makefile **avisa** y copia solo lo que exista (el modelo no
podrá activarse hasta que haya `weights.pt` y `preprocessor.joblib`).

## Cambio de modelo en caliente

Puedes copiar un modelo nuevo **con el servidor en marcha**; el servidor no mantiene
abiertos los ficheros del modelo (los abre y cierra al cargar):

```bash
make install-model MODEL=V12
curl -X POST localhost:8080/model/activate \
     -H "Content-Type: application/json" -d '{"name":"V12"}'
```

`activate` **relee siempre desde disco**, así que también sirve para recargar los pesos
de un modelo ya activo tras actualizarlos. Las peticiones en vuelo terminan con el
modelo con el que empezaron.

## Endpoints

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/health` | Estado, modelo activo y nº de filas del dataset |
| GET | `/models` | Modelos instalados y cuál está activo |
| GET | `/model` | Contrato del modelo activo (inputs/features/outputs) |
| POST | `/model/activate` | `{"name":"V11"}` → activa/recarga un modelo |
| POST | `/predict` | Valida contrato, preprocesa y predice |
| POST | `/validate` | Guarda filas validadas (sin reentreno) |
| GET | `/dataset/summary` | Resumen del dataset acumulado |

Sin autenticación (API abierta en la red interna). Documentación interactiva en `/docs`
(Swagger) y `/redoc`.

## `POST /predict`

Cuerpo: las **entradas básicas** que define el modelo (contrato del adaptador).

```json
{"rows":[{"UNICODE":"U1","BEAM":"IPE200","COLUMN":"HEA100",
          "Capacity_Moment":120.0,"Capacity_Shear":80.0,"Capacity_Axial":50.0,
          "grado_acero":"S355JR","clase_tornillo":"10.9"}]}
```

Respuesta `200`: por cada fila, **todas** las columnas = entradas básicas + features
completas calculadas por el preproceso + predicciones del modelo.

```json
{"model_name":"V11",
 "raw_inputs":["UNICODE","BEAM","COLUMN", "..."],
 "output_fields":["standard","Bolt","n_alma","n_cantonera","g","e","d","Bp","tp","p1","..."],
 "rows":[{"UNICODE":"U1","BEAM":"IPE200","BEAM_type":"IPE","BEAM_d_mm":200.0,
          "...":"...","Bolt":20,"n_alma":2,"n_cantonera":2,"g":105.0,"p1":85.0}]}
```

### Error de contrato → HTTP 422

Si a alguna fila le falta alguno de los inputs requeridos por el modelo activo:

```json
{"detail":"Faltan inputs requeridos por el modelo activo",
 "missing":{"fila 1":["COLUMN","grado_acero","clase_tornillo"]},
 "expected":["UNICODE","BEAM","COLUMN","Capacity_Moment","Capacity_Shear",
             "Capacity_Axial","grado_acero","clase_tornillo"]}
```

También devuelve 422 si un perfil no está en los catálogos Tekla o si un valor de
material no está en las tablas del adaptador.

Los **grados de acero y clases de tornillo válidos que el modelo no vio en
entrenamiento** (p. ej. `S275JR` o `8.8` si el modelo solo se entrenó con `S355JR` y
`10.9/A325M`) **no dan error**: `fy/fu/fv` entran como features numéricas, así que la
categoría se aproxima a la clase conocida de propiedades más parecidas y se registra un
aviso en `data/server.log`.

Otros códigos: `400` filas vacías, `503` sin modelo activo.

## Añadir un modelo nuevo (carpeta V)

1. Crea `<V>/core/adapter.py` con la interfaz del contrato:

   ```python
   MODEL_NAME = "V12"
   RAW_INPUT_COLUMNS = [...]        # entradas básicas que enviará el cliente
   OUTPUT_FIELDS = [...]
   class InputContractError(ValueError): ...
   def preprocess(raw_df) -> pd.DataFrame: ...   # básico -> features completas
   def load() -> dict: ...                       # {"model", "pre", "device"}
   def predict(features_df, bundle) -> pd.DataFrame: ...
   def contract() -> dict: ...                   # {"name","raw_inputs","features","outputs"}
   ```

2. `make install-model MODEL=V12 WEIGHTS=<...> PREPROC=<...> DATA=<...>`
3. `POST /model/activate {"name":"V12"}`.

No hace falta tocar `main.py` ni `predictor.py`: el servidor sólo conoce la interfaz
del `adapter.py`.

## Notas técnicas

- El `preprocessor.joblib` de los modelos está serializado como
  `core.dataset.Preprocessor`; el registro importa el `core/` de cada paquete con el
  nombre top-level `core` para que resuelva. Solo hay un `core` activo a la vez.
- Los checkpoints se cargan con `torch.load(..., weights_only=False)` porque los
  metadatos incluyen arrays numpy (`p_mean_mm`/`p_std_mm`). Son artefactos propios.
- Cada modelo puede tener su propia arquitectura y su propio preproceso: todo vive en
  su `core/`.
