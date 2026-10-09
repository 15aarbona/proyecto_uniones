# Mapeo a columnas de CODAME: ambigüedades y datos que faltan

Con "mapeo" nos referimos a la **traducción del diseño (V_pru) → las 54 columnas de
`Tabla_MOMENT_M1`** que consume CODAME (`validation/model_to_row.py`). Hay dos tipos de
problema: **(a) datos que no tenemos y rellenamos con 0/constantes**, y **(b) convenciones
que asumimos**.

## Inventario de las 54 columnas

**Mapeadas de datos (fiables):**
`Unicode, Standards(Normativas), BEAM, COLUMN, MzEd_Porcen*, FyEd_Porcen*, FxEd_Porcen*, BoltName_ep,
p2_ep(g), b_ep(Bp), Lp, ThicknessName_t_ep(tp), dev(e), Lh, pfo(d), pfi(p1-d-BEAM_tf_mm), p2..p12,
espesores (tws/ts/tbs/tst), fy/fu/fyp/fup, BoltGrade`

**Rellenadas con 0 (NO las tenemos):**

| Columna | Qué es | Afecta a |
|---|---|---|
| `Pr_Porcen`, `MzEd_PanelZone`, `Vgra`, `Havg` | cargas adicionales (axial %, panel zone, cortante/Havg) | panel zone, axial |
| `wf, ww, w3, w4, wh` | **tamaños de soldadura** | **todos los checks de soldadura (los que más fallan)** |
| `Bws, Lws` | **ancho/longitud de rigidizadores** | checks de rigidizadores |
| `p12_Outer` | paso exterior | geometría de filas |

**Asumidas como constantes (convención):**

| Columna | Valor | Riesgo |
|---|---|---|
| `Electrode` | `""` (vacío) | soldadura |
| `yieldmethod` | `True` | método de cálculo |
| `WeldFactor` | `1` | soldadura |
| `BoltsInTensionFactor` | `2` | tracción |
| `BoltThreads` | `True` | tracción |
| `AnguloCantonera` | `60` si `Lh>0` | cartabón |

**Derivadas con ambigüedad:**
- `pfi = p1 − d − BEAM_tf` (depende de la convención y de tener `BEAM_tf_mm` correcto; con
  perfiles que vienen de `tekla_faltante` podría no ser fiable).
- `Lp = 2e + Σp` (fórmula, no dato).
- `*_Porcen`: usa `*_Percentage` si está; **si no, 0** (el fallback a la capacidad absoluta
  no está implementado).

## Por qué importa

Los checks que **más fallan** son de **soldadura de ala (54.9%)** y **panel zone (8.8%)** —
justo cuyas entradas (`wf/ww/wh`, `Electrode`, `WeldFactor`, `yieldmethod`, `MzEd_PanelZone`)
ponemos a **0/constantes**. Puede ser:
- que CODAME los calcule por defecto y esté bien, o
- que **nos falte el dato** (tamaño de soldadura / electrodo) y por eso salgan >1.

## Cómo desambiguarlo (verificación propuesta)

1. **Leer una fila REAL poblada del libro** (`IM_MOMENT`, la JBE6000 original) e inspeccionar
   esas columnas (`Electrode`, `wf/ww/wh`, `Pr_Porcen`, `Vgra`, `Havg`, `Bws/Lws`,
   `yieldmethod`, `WeldFactor`). Si en el libro también están a 0/vacías → nuestros defaults
   son correctos; si tienen valores → **nos faltan datos**.
2. Comprobar si esos campos existen en el **dataset/BD** (perfiles/material) o hay que pedirlos.

## Preguntas abiertas

1. ¿Se revisa (read-only) esa fila real del libro para ver qué valores traen esas columnas?
2. ¿El tamaño de soldadura / electrodo se decide en el diseño (y por tanto debería venir del
   modelo) o lo asume CODAME?
