# validation — validación de diseños con CODAME

Módulo para validar diseños con `CalcCodame.exe` **sin tocar Excel a mano** y obtener,
identificados por la columna `Unicode`, los **ratios** y demás salidas de CODAME.

## Uso (Python)

```python
from validation.codame import validate_csv

df = validate_csv("resultado_v_pru.csv", out_csv="ratios.csv")
# df: DataFrame con columnas [Unicode, Estado, <18 checks>, RatioPesimo, DescripRatioPesimo]
```

O por línea de comandos:

```bash
python -m validation.codame --csv resultado_v_pru.csv --out ratios.csv
```

Se puede llamar desde `production` o desde `V_pru` (añadiendo la raíz del repo al
`sys.path`).

## Requisitos

- Windows + **Excel de escritorio x64** + `pywin32`.
- La autenticación SQL de CODAME usa `Trusted_Connection=True`. Ver más abajo
  según si tu cuenta de Windows ya tiene acceso o no.

## Formas de ejecución

**A) Con Python** (API o CLI):
```python
from validation.codame import validate_csv
df = validate_csv("resultado_v_pru.csv", out_csv="ratios.csv")
```
```bash
python -m validation.codame --csv resultado_v_pru.csv --out ratios.csv
```

**B) Con un .cmd** (wrapper):
```cmd
run_codame.cmd ad.tecnicasreunidas.es\<usuario> --csv resultado_v_pru.csv --out ratios.csv
```

## ¿Hace falta abrir Excel a mano?

**No.** El módulo:
1. Reutiliza la instancia de Excel abierta si la hay.
2. Si no hay ninguna, **crea una oculta y abre el libro** `CONNEXTOR` (busca
   `CalcCodame\CONNEXTOR - CRIS.xlsm` y, si no, `production\excel_client\CONNEXTOR - CRIS_final.xlsm`).
   Puedes forzar otro con `--workbook-path`.
3. Al terminar, cierra **solo** la instancia que él creó (deja intacta la tuya).

> `CalcCodame.exe` se engancha por COM a la instancia activa; por eso el módulo
> garantiza que exista una y con el libro correcto.

## Credenciales: ¿runas o acceso directo?

La autenticación la hace `CalcCodame.exe` con tu identidad Windows
(`Trusted_Connection`). Dos escenarios:

- **Tu usuario Windows YA tiene acceso al SQL `CONEXIONES`** (equipo unido al dominio,
  o credencial ya almacenada): ejecuta **directo**, sin `runas`:
  ```cmd
  run_codame_direct.cmd --csv resultado_v_pru.csv --out ratios.csv
  ```
- **No tienes acceso desde tu usuario actual** (equipo en WORKGROUP): usa `runas /netonly`
  con la cuenta de dominio (`run_codame.cmd`). La contraseña la pide Windows.

## CSV de entrada (salida de V_pru)

Genera predicciones del modelo sobre el **conjunto de validación** (test) con:

```cmd
cd V_pru\app
..\..\.venv\Scripts\python.exe predict_val_to_csv.py ..\..\val_predicciones.csv
```

Reproduce el split `train_test_split(df, test_size=0.2, random_state=2)`, predice con
`store.predict_df` y escribe `input + diseño predicho + feats` (945 filas). Luego:

```cmd
python -m validation.codame --csv val_predicciones.csv --out val_ratios.csv
```

Se admiten alias; columnas usadas:

- **Input**: `UNICODE`, `BEAM`, `COLUMN`, `Capacity_Moment/Shear/Axial` (+ `_Percentage`),
  `grado_acero` (o `AceroEstructural`), `clase_tornillo` (o `EstandarTornillos`).
- **Diseño**: `standard, Bolt, SlipCritical, g, e, d, Bp, tp, Lh, p1..p12, tws, ts, tbs, tst, n_alma, n_cantonera`.
- **Feats** (opcional): `BEAM_tf_mm, fy_acero_mpa, fu_acero_mpa`. Si faltan, se rellenan
  de los catálogos Tekla (`tekla_eu.csv`/`tekla_cad.csv`) y de la tabla de aceros.

## Comportamiento

- Escribe los diseños en `Tabla_MOMENT_M1` (hoja `IM_MOMENT`) **en bloque**, lanza el
  exe **una vez por lote** (por defecto 200) y lee `TResultadosRatios` / `TResultadosComplemen`.
- El exe **aborta en la primera fila conflictiva**; el módulo la marca `FAILED` y continúa.
- Restaura el contenido original de la tabla (no guarda el libro).
- Los centinelas de error de CODAME (`-2146826252`) se devuelven como `NaN`.

## Ficheros

- `codame.py` — API y lógica COM/batch.
- `model_to_row.py` — traducción diseño→columnas de `Tabla_MOMENT_M1`.
- `run_codame.cmd` — wrapper `runas /netonly`.
- `run_codame_direct.cmd` — ejecución directa (sin `runas`) si ya tienes acceso.
