# GUIs de escritorio (tkinter) para el modelo de diseño de conexiones

Dos aplicaciones de **escritorio con tkinter** (sin servidor, sin abrir puertos —
adecuadas para redes de empresa restrictivas) que envuelven tu pipeline
(`config.py`, `dataset.py`, `geometry.py`, `lookups.py`, `losses.py`, `model.py`,
`postprocess.py`, `training.py`, `evaluation.py` — copiados sin cambios de lógica
dentro de `core/`):

- **`predict_app_tk.py`** (GUI de usuario): carga un CSV **o Excel** (`.xlsx/.xls`)
  "pobre" tipo `fictional.csv` (`UNICODE, BEAM, COLUMN, Capacity_Moment,
  Capacity_Shear, Capacity_Axial, grado_acero, clase_tornillo`) y exporta los
  resultados en **CSV o Excel**, a elección del usuario, con **todas** las
  predicciones, incluidas `p1..p12` reconstruidas a partir de `E-S/D_i/I-C/C_i/E-C`
  (`geometry.p_from_named`, vía `reconstruct_p=True`). También permite validar filas
  (doble clic en la columna "Validar") y añadirlas al dataset de entrenamiento.
- **`admin_app_tk.py`** (GUI de administrador): entrena el modelo por primera vez,
  reentrena con el dataset acumulado, y muestra métricas/historial/dataset en pestañas.

`store.py` es la capa de orquestación (entrena/reentrena/predice/gestiona el dataset
global) y es idéntica se use la GUI que se use — no depende de tkinter ni de ningún
framework web.

## Instalación

```bash
python -m venv .venv && source .venv/bin/activate   # opcional pero recomendado
pip install -r requirements.txt
```

`tkinter` es parte de la librería estándar de Python, así que normalmente no hace
falta instalarlo aparte:
- **Windows / macOS** (instalador oficial de python.org): ya viene incluido.
- **Linux**: si al ejecutar da `ModuleNotFoundError: No module named 'tkinter'`,
  instala el paquete del sistema, p.ej. `sudo apt install python3-tk` (Debian/Ubuntu)
  o el equivalente de tu distro.

No hace falta ningún puerto abierto ni servidor: las GUIs son ventanas nativas del
sistema operativo, se ejecutan y se usan completamente en local.

## Cómo se guarda todo (`model_store/`)

Al entrenar por primera o siguientes veces se crean/actualizan estos ficheros:

| Fichero | Contenido |
|---|---|
| `model_store/model.pt` | Pesos de `ConnectionDesignNet` (`state_dict`). |
| `model_store/preprocessor.pkl` | El `Preprocessor` ajustado (encoders/scalers) — imprescindible para decodificar predicciones futuras exactamente igual que en entrenamiento. |
| `model_store/metadata.json` | Fecha, modo (`initial`/`retrain`), épocas, lr, nº de filas del dataset, métricas de test del último (re)entreno. |
| `model_store/training_history.json` | Lista con el `metadata.json` de cada entrenamiento realizado (para ver la evolución). |
| `model_store/global_dataset.parquet` | **El dataset global**: el dataframe ya preparado para entrenar (con lookup de perfiles/material y la geometría con nombre `E-S/D_i/I-C/C_i/E-C` ya calculada por `dataset.add_geometry_targets`). Es la base de todos los reentrenos futuros. |

El dataset global se guarda **siempre en parquet** internamente (es lo que se usa para
reentrenar); el botón "Exportar…" de la pestaña "Dataset global" solo genera una copia
de lectura en `.xlsx` o `.csv` para inspeccionarlo fuera de la app — no sustituye al
parquet ni afecta al reentreno.

`data/tekla_eu.csv`, `data/tekla_cad.csv`, `data/tekla_faltante.csv` van incluidos como
catálogo de perfiles por defecto (los mismos que usabas en el notebook). Si tu tabla de
perfiles cambia, sustitúyelos ahí.

## Flujo de trabajo

### 1. Entrenamiento inicial (`admin_app_tk.py` → pestaña "🆕 Entrenamiento inicial")

Elige `test.parquet` (obligatorio) y, si lo tienes, `train.parquet` (si no lo eliges,
se hace un split interno de `test.parquet`, equivalente al `--smoke_test` de
`train.py` — útil para probar la GUI, **no** para producción). Al terminar:

- Se guarda el modelo (`model.pt` + `preprocessor.pkl`).
- Se crea `global_dataset.parquet` = `train_df + val_df + test_df`, ya con la
  geometría con nombre calculada. Este es el dataset que alimentará los reentrenos.

⚠️ Repetir el entrenamiento inicial **sobrescribe** el dataset global (pierdes las
filas validadas que se hayan ido acumulando; la GUI pide confirmación antes). Para
incorporar casos nuevos sin perder nada, usa "Reentrenar".

### 2. Predicción (`predict_app_tk.py`)

1. **Cargar CSV/Excel…** con las 8 columnas "pobres" de producción (acepta `.csv`,
   `.xlsx`, `.xls`, `.xlsm`).
2. **Predecir**: reconstruye las features ricas (`lookups.build_training_features`:
   geometría de perfil vía catálogos Tekla + propiedades mecánicas de acero/tornillo),
   corre el modelo y decodifica las predicciones (`postprocess.decode_predictions` +
   `derive_dependent_columns`), incluida la reconstrucción de `p1..p12`.
3. **Descargar resultados…** — elige el nombre y la extensión (`.xlsx` o `.csv`) y se
   guarda en ese formato.
4. Doble clic en la columna **"Validar"** de las filas que un ingeniero ha revisado y
   da por buenas → **"Guardar validadas en el dataset"** las añade como filas nuevas
   al dataset global (no reentrena automáticamente — eso lo decide el administrador).

### 3. Reentrenar (`admin_app_tk.py` → pestaña "🔁 Reentrenar")

Reentrena el modelo **desde cero** (nuevo split train/val/test, nuevo `Preprocessor`)
usando todo `global_dataset.parquet` (dataset original + filas validadas desde la
última vez). Si el entrenamiento termina bien, sobrescribe `model.pt` /
`preprocessor.pkl` y añade una entrada al historial. El dataset global no se toca
(sigue creciendo con cada validación, independientemente de cuándo se reentrene).

> Nota de diseño: el reentreno es siempre desde cero (no *fine-tuning* incremental)
> porque el nº de clases de `DrawingCode` y las cardinalidades categóricas pueden
> cambiar al añadir filas nuevas, lo que invalidaría un *warm start* directo de pesos.
> Con el tamaño de datos típico de este problema, reentrenar desde cero cada vez es
> más simple y más robusto que gestionar esa complejidad.

Entrenar/reentrenar corren en un hilo aparte (no se congela la ventana), con una
barra de progreso indeterminada mientras dura — no cierres la ventana mientras corre.

## Ejecutar

```bash
# Ventana de administrador
python admin_app_tk.py

# Ventana de predicción (se puede abrir a la vez, son procesos independientes)
python predict_app_tk.py
```

## Estructura

```
gui_app/
├── admin_app_tk.py       GUI de administrador (tkinter): entrenar / reentrenar / estado
├── predict_app_tk.py      GUI de usuario (tkinter): predecir / validar
├── gui_common.py           Tabla (Treeview) reutilizable + runner de tareas en 2º plano
├── store.py                 Orquestación: guardar/cargar modelo, dataset global, train/retrain/predict
├── requirements.txt
├── core/                     Tu pipeline original, sin cambios de lógica (imports adaptados a paquete)
│   ├── config.py
│   ├── dataset.py
│   ├── geometry.py
│   ├── lookups.py
│   ├── losses.py
│   ├── model.py
│   ├── postprocess.py
│   ├── training.py
│   └── evaluation.py
├── data/                     Catálogos Tekla por defecto
│   ├── tekla_eu.csv
│   ├── tekla_cad.csv
│   └── tekla_faltante.csv
└── model_store/              Se genera al entrenar (modelo, preprocesador, dataset global, historial)
```

## Limitaciones conocidas / cosas a vigilar

- El primer entrenamiento necesita `train.parquet`/`test.parquet` en el mismo formato
  "rico" que ya usabas (con `p1..p12`, `DrawingCode`, `Bolt`, etc. y, si vienen con los
  nombres antiguos, `AceroEstructural`/`EstandarTornillos`). La GUI no genera ese
  parquet desde cero: lo tienes que traer tú (por ejemplo, exportado igual que en
  `variables.ipynb`).
- Como en `train.py`, las clases de `DrawingCode` con menos de 20 muestras se agrupan
  en `"OTHER"` antes de entrenar — si reentrenas con muy pocas filas nuevas de una
  clase rara, seguirán cayendo en `"OTHER"`.
- Las tablas (Treeview) muestran como máximo las últimas/primeras ~2000 filas por
  rendimiento; para CSVs de entrada muy grandes, la predicción se calcula igualmente
  sobre todas las filas y el CSV exportado las incluye todas — solo la vista en
  pantalla se recorta.
- Entrenar/reentrenar tarda varios minutos según nº de épocas y tamaño del dataset;
  con GPU disponible (CUDA) se usa automáticamente, si no cae a CPU.
