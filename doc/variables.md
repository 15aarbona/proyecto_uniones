# Diccionario y Asignación de Variables

## 1. Inputs (Variables Predictoras Comunes)
*Se usan como datos de entrada (features) para entrenar ambos modelos (Tornillería y Placa).*
- **Geometría de Viga**: `BEAM_type`, `BEAM_d_mm`, `BEAM_bf_mm`, `BEAM_tw_mm`, `BEAM_tf_mm`, `BEAM_r1_mm`
- **Geometría de Columna**: `COLUMN_type`, `COLUMN_d_mm`, `COLUMN_bf_mm`, `COLUMN_tw_mm`, `COLUMN_tf_mm`, `COLUMN_r1_mm`
- **Propiedades Mecánicas**: `fy_acero_mpa`, `fu_acero_mpa`, `fy_tornillo_mpa`, `fu_tornillo_mpa`, `fv_tornillo_mpa`
- **Fuerzas y Capacidades (Absolutas)**: `Capacity_Moment`, `Capacity_Shear`, `Capacity_Axial`, (`MzEd_PanelZone`, `Vgra`, `Havg`)(QUITAR)
- **Parámetros de Diseño**: `SlipCritical`, `SpecialMomentFrames` (quitar verdadero, p0), `Ordinary_Moment_Frames` (QUITAR, en esfuerzo), `Yieldmethod` (QUITAR), `cantonera` (QUITAR, se deduce de las filas)

## 2. Modelo de Tornillería (Outputs a Predecir)
*Variables objetivo (targets) que este modelo debe calcular.*
- **Tornillo**: `Bolt` (Grosor nominal)
- **Distribución Horizontal**: `g` (Gramil), `e` (Distancia al borde), `d` (Ajuste)
- **Distribución Vertical**: `p1`, `p2`, `p3`, `p4`, `p5`, `p6`, `p7`, `p8`, `p9`, `p10`, `p11`, `p12`

## 3. Modelo de Placa y Rigilizadores (Outputs a Predecir)
*Variables objetivo (targets) que este modelo debe calcular.*
- **Dimensiones de Placa**: `tp` (Grosor), `Bp` (Ancho)
- **Posicionamiento**: `p0` (Desfase inicial)
- **Rigidizadores**: `tws` (Grosor 1), `tso` (QUITAR con Special), `Lst` (QUITAR con Special), `ts`(AÑADIR), `tbs`(AÑADIR), `tst`(NUEVA)

## 4. Variables Excluidas del Modelo ML
*Columnas que debes eliminar del dataset (`.drop()`) antes del entrenamiento, ya sea por ser texto crudo, metadatos, o valores que calcularás por código tradicional (deterministas).*
- **Nombres Comerciales y Textos**: `BEAM`, `COLUMN`, `AceroEstructural`, `EstandarTornillos`
- **Metadatos y Rastreo**: `standard` (normativa + national anex), `DrawingCode`, `Source`
- **Valores Deterministas**: `Hole` *(Se calculará sumando holgura normativa a la predicción de `Bolt`)*., `Lp` (Alto)(DEDUCIBLE)
- **Propiedades Derivadas Auxiliares**: `BEAM_wely_mm`, `BEAM_w_kgm`, `COLUMN_wely_mm`, `COLUMN_w_kgm` *(Como la IA ya tiene todas las cotas en milímetros, calcularán el peso e inercia implícitamente; introducirlas generaría multicolinealidad, aunque puedes conservarlas solo para analítica de datos)*.

### grosor rigizador, arriostramiento, cantonera
