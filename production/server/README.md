# Servidor de inferencia — modelos intercambiables por petición

Servidor HTTP (FastAPI) que sirve modelos de prediseño de uniones. Los modelos son
**paquetes autocontenidos** dentro de `models/<NAME>/`, se instalan con el `Makefile` del
repositorio y **todos los instalados se cargan a la vez** (conviven en memoria). Cada
petición se **enruta al modelo** que se indique en `model`.

```
production/server/
├── main.py             Endpoints FastAPI (docs interactivas en /docs)
├── model_registry.py   Carga simultánea de modelos + recarga en caliente
├── predictor.py        Validación de contrato, routing e inferencia
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
uv run uvicorn main:app --app-dir production/server --host 0.0.0.0 --port 8080
```

`uv` toma las dependencias del `pyproject.toml` de la raíz (fastapi, uvicorn, torch,
scikit-learn, joblib, pandas, pyarrow). Si prefieres el flujo antiguo con `pip`:
`pip install -r production/server/requirements.txt`.

> Recomendado **1 worker**. Con varios, cada proceso carga su propia copia de todos los
> modelos y una recarga (`POST /model/activate`) solo afectaría al worker que la atiende.

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

Tras instalar/actualizar, recarga sin reiniciar:

```bash
curl -X POST localhost:8080/model/activate -H "Content-Type: application/json" -d '{"name":"V11"}'
```

## Endpoints

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/health` | Estado, modelos instalados/cargados y nº de filas del dataset |
| GET | `/models` | Modelos instalados y cargados; modelo por defecto |
| GET | `/model` | Contrato del modelo por defecto (inputs/opcionales/outputs) |
| GET | `/options?model=...` | Valores admitidos para desplegables (del modelo) |
| GET | `/` y `/web/...` | Interfaz web (`web/conexiones_tr.html`) |
| POST | `/model/activate` | `{"name":"V11"}` → carga/recarga un modelo |
| POST | `/predict` | `{"model":"V11","rows":[...]}` → valida, predice y devuelve la tabla |
| POST | `/validate` | Guarda filas validadas (sin reentreno) |
| GET | `/dataset/summary` | Resumen del dataset acumulado |

Sin autenticación (API abierta en la red interna). Documentación interactiva en `/docs`
(Swagger) y `/redoc`.

## `POST /predict`

Cuerpo: el **esquema de tabla** = inputs que espera el modelo (`raw_inputs`) + campos
opcionales. Los no obligatorios pueden ir en blanco (se aplican defaults/0).

```json
{"model":"V11",
 "rows":[{"UNICODE":"U1","BEAM":"IPE200","COLUMN":"HEA100",
          "ratio_moment":0.82,"ratio_shear":0.25,"ratio_axial":0.03,
          "grado_acero":"S355JR","clase_tornillo":"10.9"}]}
```

- `UNICODE` es **obligatorio** (trazabilidad); el resto de `raw_inputs` también, salvo
  los declarados `optional_inputs` (en V11: `grado_acero`, `clase_tornillo`, con
  defaults `S355JR` / `A325M`).
- `ratio_*` se dan en la **escala con la que se entrenó** el modelo (0–1).

Respuesta `200`: por cada fila, **columnas de tabla** = inputs enviados (o defaults) +
campos predichos. **No** se incluyen features internas.

```json
{"model_name":"V11",
 "rows":[{"UNICODE":"U1","BEAM":"IPE200","COLUMN":"HEA100","ratio_moment":0.82,
          "grado_acero":"S355JR","clase_tornillo":"A325M",
          "standard":"AISC-360-05/10","Bolt":20,"n_alma":2,"n_cantonera":1,
          "g":90.0,"e":40.0,"p1":85.0,"Hole":22,"num_filas_tornillos":5}]}
```

### Error de contrato → HTTP 422

Si a alguna fila le falta un input requerido del modelo seleccionado:

```json
{"detail":"Faltan inputs requeridos por el modelo 'V11'",
 "model":"V11",
 "missing":{"fila 1":["UNICODE","ratio_moment"]},
 "expected":["UNICODE","BEAM","COLUMN","ratio_moment","ratio_shear","ratio_axial",
             "grado_acero","clase_tornillo"]}
```

También devuelve 422 si el perfil no está en los catálogos Tekla o si un valor de
material **no es uno de los vistos en entrenamiento** (V11: `S355JR`; `10.9`/`A325M`).
Otros códigos: `400` filas vacías, `404` modelo no disponible, `503` sin modelos.

## Opciones para los desplegables (`GET /options?model=V11`)

El adaptador publica los valores válidos; se usan tal cual en la web:

```json
{"BEAM":["HEA100","IPE200","..."],"COLUMN":["HEA100","IPE200","..."],
 "grado_acero":["S355JR"],"clase_tornillo":["10.9","A325M"],
 "defaults":{"grado_acero":"S355JR","clase_tornillo":"A325M"}}
```

## Añadir un modelo nuevo (carpeta V)

1. Crea `<V>/core/adapter.py` con la interfaz:

   ```python
   MODEL_NAME = "V12"
   RAW_INPUT_COLUMNS = [...]        # inputs requeridos (esquema de tabla)
   OPTIONAL_INPUT_COLUMNS = [...]   # opcionales con default
   OUTPUT_FIELDS = [...]            # campos que predice
   class InputContractError(ValueError): ...

   def to_internal(table_df) -> pd.DataFrame: ...   # tabla -> features internas
   def from_internal(design_df) -> pd.DataFrame: ...# salidas -> columnas de tabla
   def load() -> dict: ...                          # {"model","pre","device"}
   def predict(features_df, bundle) -> pd.DataFrame: ...
   def contract() -> dict: ...   # {"name","raw_inputs","optional_inputs","outputs"}
   def options(bundle=None) -> dict: ...            # valores válidos (opcional)
   ```

2. `make install-model MODEL=V12 [WEIGHTS=... PREPROC=... DATA=...]`
3. `POST /model/activate {"name":"V12"}` (o reiniciar).

No hace falta tocar `main.py` ni `predictor.py`: el servidor sólo conoce la interfaz del
`adapter.py`.

## Notas técnicas

- El `preprocessor.joblib` de los modelos está serializado como
  `core.dataset.Preprocessor`. El registro importa el `core/` de cada paquete con el
  nombre top-level `core` de forma **secuencial**, capturando las referencias en cada
  bundle; así varios modelos conviven. El código del modelo no debe hacer `import core.*`
  en tiempo de ejecución (solo en el import del módulo).
- Los checkpoints se cargan con `torch.load(..., weights_only=False)` porque los
  metadatos incluyen arrays numpy (`p_mean_mm`/`p_std_mm`). Son artefactos propios.
- Cada modelo puede tener su propia arquitectura y su propio preproceso: todo vive en su
  `core/`.
