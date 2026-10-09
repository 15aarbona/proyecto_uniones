# Mapeo de columnas: dataset → CODAME (`Tabla_MOMENT_M1`)

Documento **general** (aplica a cualquier versión del modelo: V_pru, V6, V11, …): los
**datos son los mismos** entre modelos, lo único que cambia es cómo se generan las
predicciones. Aquí se describe **qué columna del dataset de entrada alimenta a qué
columna de CODAME**, y qué columnas se derivan, se fijan como constante o no se usan.

## Fuentes

- **Dataset de entrada**: `data/CONEXIONES_MOMENTO_ATORNILLADAS_CHAPA_FRONTAL.xlsx`
  (hoja `Sheet1`, **69 columnas**).
- **Destino**: hoja `IM_MOMENT` del libro CONNEXTOR, tabla **`Tabla_MOMENT_M1`**
  (**63 columnas**). Es lo que lee `CalcCodame.exe`.
- **Cliente oficial que vuelca dataset → tabla**: `CalcCodame/extracted_vba/VBA__AI_Client.bas`
  (ver `WriteResponseToSheet`, correspondencias directas en líneas **478‑574**, y
  `TryCalculateTensionRows` en **739‑775**). Las correspondencias se basan en la macro
  `TransformaValoresCodigoCalculo` (comentario en línea 477).
- `CalcCodame.exe` se engancha por COM a Excel (`GetActiveObject`) y, para los perfiles,
  abre `Server='TR-SQLISO-YEC01\AMS';Database='PerfilesBD';Trusted_Connection=True`
  (autenticación integrada de Windows; cadena fija en `codame.dll`/`auxiliar.dll`).

## Convenios clave

- **No existe la columna `p1`.** El primer paso se reparte en `pfo` y `pfi`:
  - `pfo = d`
  - `pfi = p1 − d − BEAM_tf_mm`  (espesor del ala de la viga)
- **No existe `p2`.** El 2.º paso se llama **`pb`** (CODAME `pb` ← dataset `p2`).
  Pasos completos: `pfo`, `pfi`, `pb` (=p2), `p3 … p12`.
- Los espesores de chapa/rigidizadores se guardan como **texto** `"20mm"`.
- Las cargas de capacidad se pasan como **porcentaje** (`..._Percentage`), no absolutas.

## Tabla de mapeo directo (dataset → CODAME)

| # | CODAME `Tabla_MOMENT_M1` | Origen en el dataset | Notas |
|---|---|---|---|
| 1 | `Unicode` | `Unicode` | |
| 2 | `Standards` | `Normativas` | ver nota Standards/Normativas |
| 3 | `BEAM` | `BEAM` | |
| 4 | `COLUMN` | `COLUMN` | |
| 5 | `MzEd_Porcen` | `Capacity_Moment_Percentage` | |
| 6 | `FyEd_Porcen` | `Capacity_Shear_Percentage` | |
| 7 | `FxEd_Porcen` | `Capacity_Axial_Percentage` | |
| 8 | `Pr_Porcen` | `Pr_Porcen` | |
| 10 | `MzEd_PanelZone` | `MzEd_PanelZone` | |
| 11 | `Vgra` | `Vgra` | |
| 12 | `Havg` | `Havg` | |
| 13 | `BoltName_ep` | `Bolt` | diámetro nominal (p.ej. `M24`) |
| 14 | `p2_ep` | `g` | separación transversal (gauge) |
| 15 | `ThicknessName_t_webstiff` | `tws` | texto |
| 16 | `Bws` | `Bws` | |
| 17 | `Lws` | `Lws` | |
| 18 | `b_ep` | `Bp` | ancho de la chapa |
| 19 | `Lp` | `Lp` | |
| 20 | `ThicknessName_t_ep` | `tp` | texto |
| 21 | `Lh` | `Lh` | |
| 23 | `dev` | `e` | |
| 24 | `p12_Outer` | `p0` | |
| 25 | `pfo` | `d` | |
| 26 | `pfi` | `p1 − d − BEAM_tf_mm` | derivada |
| 27 | **`pb`** | **`p2`** | ¡no hay columna `p2`! |
| 28‑37 | `p3 … p12` | `p3 … p12` | |
| 38 | `ThicknessName_t_compstiff` | `ts` | texto |
| 39 | `ThicknessName_t_BeamHcompstiff` | `tbs` | texto |
| 40 | `ThicknessName_t_tenstiff` | `tst` | texto |
| 41 | `wf` | `w1` | soldadura |
| 42 | `ww` | `w2` | soldadura |
| 43 | `w3` | `w3` | soldadura |
| 44 | `w4` | `w4` | soldadura |
| 45 | `wh` | `w5` | soldadura |
| 48 | `fy` | `fy_acero_mpa` (de `AceroEstructural`) | del material |
| 49 | `fu` | `fu_acero_mpa` | del material |
| 50 | `fyp` | `fy_acero_mpa` | = `fy` |
| 51 | `fup` | `fu_acero_mpa` | = `fu` |
| 53 | `BoltGrade` | `EstandarTornillos` | clase del tornillo |
| 55 | `Electrode` | `ElectrodoSoldadura` | |
| 56 | `yieldmethod` | `Yieldmethod` | |
| 61 | `Source` | `Source` | |
| 62 | `Designation` | `Designation` | |

## Valores derivados (no vienen directos del dataset)

| CODAME col | Cómo se obtiene |
|---|---|
| `pfo` | `= d` |
| `pfi` | `= p1 − d − BEAM_tf_mm` |
| `pb` | `= p2` |
| `AnguloCantonera` | `60` si `Lh ≠ 0`, si no `0` |
| `FactorCantoCantonera` | `0.7` si `Lh ≠ 0`, si no `0` |
| `ntensionrows` | `3` si hay ≥2 filas de tornillos dentro de `[d, d+BEAM_d_mm]` recorriendo `d` + cumsum(`p1..p12`); si no `2` |
| `fy`,`fyp` | `fy_acero_mpa` |
| `fu`,`fup` | `fu_acero_mpa` |

## Constantes fijadas por el cliente

| CODAME col | Valor |
|---|---|
| `BoltThreads` | `TRUE` |
| `WeldFactor` | `1` |
| `BoltsInTensionFactor` | `2` |

## Columnas de CODAME que el cliente NO rellena

`Traccion` (9), `E` (52), `SisUniBoltSI` (59), `SisUniPlateSI` (60), `Estado_IA` (63).
Se quedan con su valor por defecto / de estado (no provienen del dataset).

## Columnas del dataset que CODAME NO usa

`Capacity_Moment`, `Capacity_Shear`, `Capacity_Axial` (absolutas; sólo se usan las
`..._Percentage`), `DrawingCode`, `pfo` (la del dataset; CODAME lo recalcula desde `d`),
`thw`, `thf`, `w6`, `Hole`, `SlipCritical`, `Ordinary_Moment_Frames`,
`SpecialMomentFrames`, `Calculation_Tool`, `National_Annex` (`tso`, `Lst`),
`rib_thk`, `Representation_Angle`, `BoltConnectionTypeSelection`, `Acero_Estructural_Perfil`.

## `Standards` vs `Normativas` ¿son lo mismo?

**Sí.** La columna de CODAME se llama `Standards` y se rellena desde el campo
**`Normativas`** del dataset (`VBA__AI_Client.bas:479`):
```vba
CopyJsonValue rowObj, loMoment, targetRow, "Standards", "STANDARDS", "Normativas"
```
Es el mismo concepto (la normativa: `AISC-360-05/10`, `EN 1993-1-8`, …). No confundir con:
- `National_Annex` → **no** se mapea a CODAME.
- `standard` / `Calculation_Tool` → los usan los modelos (p.ej. V_pru) para clasificar;
  tampoco van a `Standards`.

## Equivalencias rápidas (recordatorio)

```
Standards   ← Normativas          BoltName_ep ← Bolt            b_ep  ← Bp
p2_ep       ← g                   p12_Outer   ← p0              dev   ← e
pfo         ← d                   pfi ← p1 − d − BEAM_tf_mm     pb    ← p2
wf/ww/w3/w4/wh ← w1/w2/w3/w4/w5   BoltGrade   ← EstandarTornillos
Electrode   ← ElectrodoSoldadura  ThicknessName_t_webstiff ← tws
ThicknessName_t_ep ← tp           ThicknessName_t_compstiff/…BeamHcompstiff/…tenstiff ← ts/tbs/tst
```

## Equivalencias con el diseño que predice el modelo (V_pru y posteriores)

Cuando el diseño lo genera un modelo (no viene del dataset), la traducción a la fila de
CODAME es la misma de arriba, con estas particularidades:

- El modelo emite pasos `p1..p12`; al escribirlos hay que mapear **`p2 → pb`** (una clave
  `p2` es **ignorada** en silencio por la tabla, porque no existe como encabezado).
- `pfo = d` y `pfi = p1 − d − BEAM_tf_mm` (igual que el cliente oficial).
- Columnas sin dato en el diseño (`Pr_Porcen`, `MzEd_PanelZone`, `Vgra`, `Havg`,
  `wf/ww/w3/w4/wh`, `Bws/Lws`, `p12_Outer`, `Electrode`) se envían a `0`/vacío o constante;
  CODAME las interpreta con sus valores por defecto.
