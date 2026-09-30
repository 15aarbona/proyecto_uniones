# Aplicación de escritorio V3

Adaptación de `V2/app` al modelo V3 basado en `p1..p12` y sus etiquetas semánticas
`p1_label..p12_label`. V2 permanece sin cambios.

## Diferencias del modelo

La red predice conjuntamente:

- `DrawingCode`, `Bolt`, `SlipCritical`;
- `g`, `Bp`, `Lp`, `tp`, `e`, `d`;
- los doce valores `p` y sus doce etiquetas semánticas;
- `tws`, `ts`, `tbs`, `tst`.

`Hole`, `num_filas_tornillos` y `tiene_cantonera` se derivan en postproceso. Tras el
primer `UNUSED`, las posiciones restantes se fuerzan también a `UNUSED` para obtener
una secuencia física contigua.

## Datos locales no versionados

Crea `V3/app/data/` en el ordenador donde se ejecute la aplicación y coloca:

- `tekla_eu.csv`
- `tekla_cad.csv`
- `tekla_faltante.csv`

El CSV completo de entrenamiento tampoco se incluye en Git.

## Entrada de producción

La aplicación de predicción acepta CSV o Excel con:

```text
UNICODE, BEAM, COLUMN,
Capacity_Moment, Capacity_Shear, Capacity_Axial,
grado_acero, clase_tornillo, standard
```

`standard` es una entrada nueva de V3. `Source`, las propiedades de perfiles y las
resistencias se derivan automáticamente.

## Uso

```bash
pip install -r requirements.txt
python admin_app_tk.py
python predict_app_tk.py
```

### Entrenamiento inicial

En la aplicación administrativa se puede seleccionar:

- un único CSV/Excel rico: se divide 65 % train, 15 % validación y 20 % test;
- o un dataset de entrenamiento y un test externo separados.

El dataset rico debe incluir todas las features y objetivos mostrados en
`V3/model/pipeline_walkthrough_v3.ipynb`.

### Predicción y validación

La aplicación de usuario permite importar, predecir, editar valores y etiquetas,
exportar resultados y añadir filas validadas a `model_store/global_dataset.parquet`.
El reentrenamiento posterior usa todo el dataset global desde cero.

## Persistencia

`model_store/` contiene, tras entrenar:

- `model.pt`
- `preprocessor.pkl`
- `metadata.json`
- `training_history.json`
- `global_dataset.parquet`