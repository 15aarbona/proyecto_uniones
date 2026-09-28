# Modelo de diseño de conexiones a momento atornilladas — v3

## Cambios v3 (E-S / D_i / I-C / C_i / E-C en vez de p1..p12)
Motivo: `p_k` mezclaba roles distintos según la topología (a veces `D`, a veces `I-C`, a
veces un hueco de cantonera), lo que lo volvía multimodal para una regresión. Se sustituye
por variables con **significado fijo** en todas las muestras, calcadas del plano de detalle:
`E-S` (extensión superior), `D_1..D_5` (huecos interiores en la viga), `I-C` (hueco con el
ala inferior), `C_1..C_5` (**nuevo**: huecos interiores en la cantonera, antes se perdían) y
`E-C` (última extensión).

1. **`geometry.py` (nuevo)**: `gaps_from_p` deriva estas variables de `p1..p12+e+d+BEAM_d_mm`
   (no existe columna `C_i` real: es un concepto nuevo, no una fuente de información nueva).
   `assemble_from_named` calcula `Hole`/`num_filas_tornillos`/`tiene_cantonera` por
   aritmética pura sobre esas variables (ya no hace falta recorrer p1..p12 en producción).
   `p_from_named`/`check_reversibility` reconstruyen p1..p12 y comprueban que la
   descomposición no pierde información frente al p real.
2. **Bug encontrado y corregido**: cuando el ala inferior cae ya en el primer hueco
   (vigas poco profundas), `E-S` e `I-C` coincidían y ese hueco se contaba dos veces
   (afecta a `num_filas_tornillos` y a la reconstrucción de p). Corregido en `geometry.py`.
3. **`model.py`/`losses.py`/`dataset.py`**: `GEOM_COLUMNS` se trata como regresión con
   máscara, igual que los rigidizadores (Huber + presencia, normalizado por columna, media/
   desviación ajustadas solo con valores activos). Al tener cada variable un rol fijo ya no
   hace falta la clasificación sobre rejilla ni la cabeza de "nº de pasos" de la v2.
4. **Límite a vigilar**: `D_1..D_5` y `C_1..C_5` truncan a 5 huecos cada tramo. Con
   conexiones muy altas puede perderse información — el notebook lo mide en la sección 2
   (`verificar_reversibilidad`) antes de entrenar.

**Sin verificar con datos reales**: probado solo con datos sintéticos (mecánica, reversibilidad
y aprendizaje). En la prueba sintética, `C_1` con pocos ejemplos activos (~15%) mostró el
mismo problema de escasez que antes tenían `p8+`: la reparametrización no sustituye
recolectar más casos de cantonera multi-fila si estos son raros en los datos reales.

## Qué contiene esto
Pipeline PyTorch corregido respecto a `model2.ipynb`, ya probado de punta a punta
(smoke test) contra `test.parquet`.

- `config.py` — columnas de entrada/salida y catálogos comerciales (Bolt, g, e, Bp, tp, tws, ts, tbs, tst).
- `lookups.py` — reconstruye en inferencia las features "ricas" (geometría de perfil, fy/fu)
  a partir del input pobre real (`BEAM`, `COLUMN`, `grado_acero`, `clase_tornillo`).
- `model.py` — red con embeddings + backbone ResNet + **6 cabezas** (antes había 3).
- `losses.py` — loss compuesta (CrossEntropy + Huber + BCE enmascarado + penalizaciones geométricas).
- `dataset.py` — encoders/scalers ajustados solo en train, reutilizables en val/test/inferencia.
- `postprocess.py` — snapping a catálogo comercial + recálculo de columnas derivadas.
- `train.py` — entrenamiento; con `--smoke_test` corre sobre las 945 filas de `test.parquet`
  solo para validar que el código funciona (**no es un modelo de producción**).

Resultado del smoke test: el loop de entrenamiento converge, y las columnas derivadas
(`Hole`, `num_filas_tornillos`, `tiene_cantonera`, `E-S`, `I-C`, `E-C`) se recalculan
correctamente a partir de las predicciones, replicando la lógica de `variables.ipynb`.

## Qué se corrigió respecto a `model2.ipynb`
1. **Targets completos**: antes se predecían 16+3 valores; ahora se predicen TODOS los
   reales: `DrawingCode`, `Bolt`, `SlipCritical`, `g,e,d,Bp,Lp,tp`, `p1..p12`,
   `tws,ts,tbs,tst`. `Hole`, `D_1..D_5`, `E-S`, `E-C`, `I-C`, `num_filas_tornillos` y
   `tiene_cantonera` NO se modelan: se derivan matemáticamente (son función determinista
   de `p1..p12`, `e`, `d`, `BEAM_d_mm`, o de `Bolt`), igual que ya hacía `variables.ipynb`.
2. **Catálogo de `Bolt` corregido**: a `model2.ipynb` le faltaba `M22` (existe en los datos reales).
3. **Bolt y DrawingCode pasan a ser clasificación** (antes se regresionaba el diámetro
   como si fuera continuo, lo cual no tiene sentido para un catálogo discreto de 7 valores).
4. **Features de entrada alineadas con el input real de producción**: se eliminaron
   capacidades absolutas y geometría "de más" que `model2.ipynb` usaba pero que
   `fictional.csv` nunca va a traer. En su lugar, `lookups.py` reconstruye esas
   features a partir de lo que sí llega (`BEAM`, `COLUMN`, `grado_acero`, `clase_tornillo`).
5. **`processed_data.csv` con columnas inventadas** (`pos_p1`, `ratio_depth_beam_col`...)
   sustituido por las columnas reales de `train/test.parquet`.

## Bloqueantes resueltos
1. ~~Falta `train.parquet`~~ → resuelto (3.777 filas de train + 945 de test).
2. ~~Porcentajes de capacidad no disponibles~~ → decisión: se usan las capacidades
   **absolutas** (`Capacity_Moment/Shear/Axial`), ya presentes en train/test.parquet.
3. ~~Tabla de perfiles limitada~~ → resuelto con `tekla_eu.csv` + `tekla_cad.csv` +
   `tekla_faltante.csv` (incluidos en esta carpeta). Cobertura verificada: 100% de los
   perfiles de `fictional.csv` (incluida la serie W690/W760 que faltaba) están cubiertos.
   `train.py` ahora acepta `--tekla_eu / --tekla_cad / --tekla_faltante` y valida la
   cobertura antes de entrenar (falla con un error claro si falta algún perfil).
4. Bug de `BatchNorm1d` con el último batch de tamaño 1 → arreglado con `drop_last=True`.

## Bloqueante pendiente
- **`DrawingCode` sigue desbalanceado** incluso con el dataset completo (train: MLE=2258,
  MHE=1450, MOE=34, MSE=16, M1E=12, MOE1=4, MOE2=3). Se agrupan clases con <20 muestras
  en "OTHER" para que el entrenamiento sea estable. Resultado actual (80 épocas, ver
  `pipeline_walkthrough.ipynb`): accuracy 93.7%. Si en producción interesa distinguir
  esas plantillas raras, hay que decidir si se recolectan más ejemplos o se tratan aparte.

## Resultados de referencia (80 épocas, sin tuning fino)
- Accuracy `DrawingCode`: 93.7% | `Bolt`: 94.0% | `SlipCritical`: 99.0%
- MAE: `g`=3.3mm, `e`=0.4mm, `d`=1.5mm, `Bp`=5.6mm, `Lp`=27.2mm, `tp`=0.6mm
- Ver `pipeline_walkthrough.ipynb` para el desglose completo (incluye `p1..p12` y rigidizadores).

## Notebook paso a paso
`pipeline_walkthrough.ipynb` recorre todo el proceso (carga de datos, features, dataset,
modelo, entrenamiento con curva de loss, métricas por variable, gráficas real-vs-predicho,
inspección de casos concretos y un ejemplo de inferencia con input "pobre" tipo
`fictional.csv`) reutilizando el mismo código de los módulos `.py` — no hay lógica
duplicada entre el notebook y `train.py`.

## Cómo seguir
```bash
python train.py --train_path train.parquet --test_path test.parquet --epochs 150 \
    --tekla_eu tekla_eu.csv --tekla_cad tekla_cad.csv --tekla_faltante tekla_faltante.csv
```
O abre `pipeline_walkthrough.ipynb` para ir paso a paso / depurar interactivamente
(sube `EPOCHS` a 150+ en la celda de entrenamiento para el resultado final).
