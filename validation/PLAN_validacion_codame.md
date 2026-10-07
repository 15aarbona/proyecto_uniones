# Plan — Validación de diseños con `CalcCodame.exe`

Estado: **planificado, sin implementar**. Entorno confirmado: hay Excel de escritorio x64 y
acceso al SQL `TR-SQLISO-YEC01\AMS`. Alcance confirmado: **1 fila a la vez**.

## 1. Objetivo

Dado el input de producción + el diseño predicho por el modelo (1 fila), ejecutar la
validación oficial de CODAME y recoger el veredicto (PASS/FAIL + ratios y causa) **sin
manipulación manual de Excel**.

## 2. Hallazgos sobre el ejecutable

`CalcCodame.exe` (.NET Framework 4.8, x64) **no es un CLI puro**: se engancha por COM a una
instancia de Excel abierta (`Excel.GetActiveCOMObject` → `GetActiveObject("Excel.Application")`),
lee una tabla del libro, calcula y **escribe los resultados en el propio libro**. No abre
fichero por sí mismo.

Detalles verificados por IL (`Program.Main`, `FuncionesPrincipales.Interfaz_PROCESAR`) y strings:

- La ruta del libro y el nombre de tabla se obtienen por reflexión de la propiedad `objMapeo`
  sobre `ProcesarCodame` (`DatosConexionExcel.RutaArchivoExcel`, `.Tabla`).
- El motor de cálculo se invoca por reflexión sobre `objCalc`: `ConsultaPerfilesSQLServer`,
  `CalculaEsfuerzos`, `CalculoConexion`, `ConnectionDesignRedim`, `ConnectionDesign`,
  `CalculoParametrosAux`.
- Conexión SQL **hardcoded**:
  `Server='TR-SQLISO-YEC01\AMS';DataBase='CONEXIONES';Trusted_Connection=True`.
- Entrada `Program.Main` →
  `FuncionesPrincipales.Interfaz_PROCESAR(connStr, args, objMapeo, objCalc, Escalculo, Esdimensionamiento, Esparametrosaux)`.

## 3. Contrato de invocación

```
CalcCodame.exe <ACCION> "<nombreLibro>" "<addrLectura>" "<addrEscritura>" "<Tabla>" "<objMapeo>" "<objCalc>"
```

- `ACCION`: `CALCULAR_CODAME` | `DIMENSIONAMIENTO_CODAME` | `PARAMETROS_AUX_CODAME`.
- `Main` **solo usa** `args[0]`, `args[len-2]` y `args[len-1]` (los dos nombres de objeto).
  El libro y las direcciones los resuelve internamente; por seguridad se replica la llamada
  VBA completa (`VBA__IU_CODAME.bas:24-41`).
- Para MOMENT (hoja `ObjetosTablaCodame`, fila `IM_MOMENT`):
  - `objMapeo = CodigoMOMENTAgregadorCODAME0`
  - `objCalc  = MOMENT_CODAMEaux`

## 4. Flujo de validación (1 fila)

1. Abrir Excel oculto (`Visible=False`, `DisplayAlerts=False`, `AutomationSecurity=ForceDisable`)
   con una **copia temporal** del libro real (`CONNEXTOR - CRIS_final.xlsm`) guardado como `.xlsm`
   temporal.
2. Escribir la fila de entrada+diseño en `Tabla_MOMENT_M1` (hoja `IM_MOMENT`) replicando
   `VBA__AI_Client.bas:477-576` (mapeo de campos, `p1→pfi`, `d→pfo`, espesores `"NNmm"`,
   `Lh`/`AnguloCantonera`/`FactorCantoCantonera`, `ntensionrows`, `fy/fu/fyp/fup`, constantes
   `BoltThreads/WeldFactor/BoltsInTensionFactor`).
3. Asegurar `TParametrosAux` (geometría de perfil/aux) para la fila.
4. Lanzar:
   ```
   CalcCodame.exe CALCULAR_CODAME "<libro>" <addrLectura> <addrEscritura> "Tabla_MOMENT_M1" "CodigoMOMENTAgregadorCODAME0" "MOMENT_CODAMEaux"
   ```
   y esperar su salida.
5. Leer resultados en `IM_MOMENT`: `TResultadosRatios_1` (BE16:BV17),
   `TResultadosComplemen_1` (BX16:DA17) y el mensaje de error (`MensajeError`).
6. Devolver `{pasa, ratio_pesimo, causa, ratios{...}}` y cerrar sin guardar.

## 5. Criterio de PASS/FAIL

- `RatioPesimo ≤ 1.0` y flags `BMFailWeb/BMFailFlange/BMFailHaunch` falsos → válido.
- `DescripRatioPesimo` indica el check gobernante.
- Extra: `CoincidenFilas`, `NoHaunchPerfilCentrado`, `NoHaunchTornilloImparCentrado`,
  `NoHaunchSimetriaFilasTornillos`.

### Columnas de la tabla de resultados (`TResultadosRatios_1`)

`PRMIN, PRMAX, DEH_MIN, DEH_MAX, DEV_MIN, DEV_MAX, SPACING_MIN, SPACING_MAX,
ENTER_TOP_FLANGE_TOP, ENTER_TOP_FLANGE_LOW, ENTER_LOW_FLANGE_TOP, ENTER_LOW_FLANGE_LOW,
ENTER_HAUNCH_FLANGE_TOP, ENTER_HAUNCH_FLANGE_LOW, bc&bb, bep&bb, bep&bepmin, bep&bc, Zb/Zc,
BMFailWeb, BMFailFlange, BMFailHaunch, wfMIN, RatioPesimo, DescripRatioPesimo, CoincidenFilas,
NoHaunchPerfilCentrado, NoHaunchTornilloImparCentrado, NoHaunchSimetriaFilasTornillos,
Número de filas de tornillos interiores...`

## 6. Diseño del script

- Ubicación: `production/validation/validate_codame.py`.
- API: `validate_design(input_row: dict, design_row: dict) -> dict`.
- Dependencias: `pywin32` (`win32com.client`), `subprocess`, `shutil`, `tempfile`, `pathlib`.
- Pasos encapsulados y limpieza garantizada (try/finally para cerrar Excel).

## 7. Requisitos

- Windows con **Excel de escritorio x64** (coincide con el exe; una sola instancia de Excel).
- Acceso a **SQL `TR-SQLISO-YEC01\AMS` / `CONEXIONES`** (Windows auth).
- Copia de `CONNEXTOR - CRIS.xlsm` / `CONNEXTOR - CRIS_final.xlsm` como plantilla.

## 8. Riesgos / verificaciones pendientes

- Confirmar si el exe valida **solo la fila activa** (tablas de resultados con 1 fila) →
  asumimos 1×fila.
- Confirmar que el libro enganchado es el que abrimos (una sola instancia de Excel).
- Excel headless en servicio es frágil (perfiles, diálogos); para servidor, valorar modo
  headless de CODAME.
- Direcciones exactas (`addrLectura`/`addrEscritura`): obtenerlas del template vía COM
  (`ListObjects`, `Names`), no hardcodear.

## 9. Alternativa

Solicitar al equipo de CODAME una entrada headless (CLI/CSV/API) que elimine la dependencia de
Excel.

## 10. Estado del entorno SQL (verificado 2026-06)

Pruebas realizadas con `production/validation/test_sql_connection.ps1`.

| Comprobación | Resultado |
|---|---|
| DNS `TR-SQLISO-YEC01` | `172.16.251.64` (`ad.tecnicasreunidas.es`) — resuelve |
| Ping | OK |
| Instancia `TR-SQLISO-YEC01\AMS` | Resuelve; **escucha en TCP 1434** (1433 cerrado, 14330 cerrado) |
| Autenticación desde equipo NO unido al dominio (WORKGROUP) | **Falla** `SQL Number=18452` — "untrusted domain" |
| Autenticación desde equipo unido al dominio | **Login OK**, pero **sin acceso a la BD `CONEXIONES`** (actúa el `18456` / `HAS_DBACCESS('CONEXIONES')=0`) |

**Conclusión / requisito:**
- La red y la instancia están disponibles; el bloqueo es de **credenciales/permisos**.
- `CalcCodame.exe` lleva `Trusted_Connection=True` **hardcodeado**, por lo que debe ejecutarse:
  - en un equipo **unido al dominio TR**, y
  - bajo una **cuenta de dominio con acceso de lectura a `CONEXIONES`** (la que usa
    `ConsultaPerfilesSQLServer`).
- Petición concreta a IT: *conceder a la cuenta que ejecutará la validación acceso de lectura
  (`db_datareader`) sobre `CONEXIONES` en `TR-SQLISO-YEC01\AMS`*.
- Si el SQL Browser (UDP 1434) diera problemas, conectar directo a `tcp:TR-SQLISO-YEC01,1434`.

## 11. Ejecución desde un equipo NO unido al dominio

El bloqueo es de **identidad de dominio**, no de red: por eso **un reenvío TCP (portproxy/SSH
-L) NO sirve** — el logon Windows del proceso sigue siendo el local (`portatilmsi\jabal`), no
confiable para el SQL.

### Opción recomendada: `runas /netonly`

Ejecuta el proceso en la máquina local, pero su **autenticación de red** usa las credenciales
de dominio (logon `LOGON32_LOGON_NEW_CREDENTIALS`), sin unir el equipo al dominio. Vale tanto
para el sondeo SQL como para `CalcCodame.exe` (que hace `Trusted_Connection=True`).

```cmd
runas /netonly /user:ad.tecnicasreunidas.es\<usuario> ^
  "cmd /c C:\Users\jabal\OtrosProyectos\proyecto_uniones\production\validation\run_test_netonly.cmd"
```

- Pide la contraseña de la cuenta de dominio una vez.
- La ventana se cierra sola; el resultado queda en
  `production/validation/sql_test_result.txt`.
- Como `CalcCodame.exe` se engancha por COM a Excel **de la misma máquina**, con este método la
  validación completa (Excel + exe + SQL) puede correr **localmente**; el otro equipo solo
  aporta las credenciales, no hace falta forwarding.
- Matiz: `runas /netonly` no configura acceso a recursos por SMB/rutas UNC; el SQL (TCP) sí
  funciona.

### Alternativas si se quiere ejecutar realmente en el otro equipo

- **SSH remoto** (si el equipo de dominio tiene OpenSSH Server):
  `ssh dominio\usuario@maquina "powershell -ExecutionPolicy Bypass -File C:\ruta\test_sql_connection.ps1"`
  y recoger stdout; o copiar el `sql_test_result.txt` con `scp`.
- **WinRM / PowerShell Remoting**:
  `Invoke-Command -ComputerName maquina -Credential (Get-Credential) -FilePath .\test_sql_connection.ps1`.
- **Agente de validación** (solución a medio plazo, la más robusta para producción): un pequeño
  servicio HTTP en el equipo de dominio que reciba el input+diseño (JSON), ejecute
  Excel+`CalcCodame.exe` y devuelva el veredicto (JSON). Encaja con el servidor de
  `production/server` como endpoint `/validate_design`.



## 12. Implementacion (estado actual)

Artefactos creados en `production/validation/`:

| Fichero | Para que |
|---|---|
| `test_sql_connection.ps1` | Prueba de red + login + acceso a `CONEXIONES` (2 etapas). |
| `run_as_netonly.cmd` / `run_test_netonly.cmd` | Lanzan la prueba SQL con `runas /netonly` y guardan el log. |
| `inspect_workbook.py` | Introspeccion READ-ONLY del `.xlsm` por COM (hojas, tablas, cabeceras, names). |
| `validate_codame.py` | Validacion 1 fila: copia temporal + Excel oculto + escritura en `Tabla_MOMENT_M1` + lanza el exe + lee resultados. |
| `run_validate_netonly.cmd` / `validate_netonly_body.cmd` | Lanzan `validate_codame.py` bajo `runas /netonly`. |

### Nombres reales (via `inspect_workbook.py`, hoja `IM_MOMENT`)

- Entrada/diseno: `Tabla_MOMENT_M1` (`$B$16:$BC$1358`), 54 columnas.
- Resultados: `TResultadosComplemen` (`$BX$16:$DA$17`) → `RatioPesimo`, `DescripRatioPesimo`, `BMFail*`, `CoincidenFilas`...
- Ratios por check: `TResultadosRatios` (`$BE$16:$BV$17`) → 18 checks de norma.
- No existe tabla `TParametrosAux` en la plantilla (el flujo IA la asume; para `CALCULAR_CODAME`
  no se usa).

### Uso

```cmd
:: Prueba SQL (cuenta de dominio):
production\validation\run_as_netonly.cmd ad.tecnicasreunidas.es\<usuario>

:: Validar una fila ya presente en el libro:
production\validation\run_validate_netonly.cmd ad.tecnicasreunidas.es\<usuario> --row 1

:: Escribir un diseno {columna_excel: valor} y validar:
production\validation\run_validate_netonly.cmd ad.tecnicasreunidas.es\<usuario> --row 1 --values diseno.json
```

Verificado en local (sin SQL): apertura oculta del libro, escritura y lectura en
`Tabla_MOMENT_M1`, y lectura de `RatioPesimo`. Pendiente de probar con SQL: el lanzamiento
real de `CalcCodame.exe` bajo `/netonly`.

### Requisitos tecnicos

- `pywin32` instalado en el venv (hecho).
- Excel de escritorio x64 y acceso a `CONEXIONES` con la cuenta de dominio.
- Lanzar siempre bajo `runas /netonly` (la contrasena la pide `runas`, nunca el script).

## 13. Integracion con el modelo (V_num)

No hay que crear ningun `diseno.json` a mano. El puente es `model_to_row.py`, que replica
`VBA__AI_Client.bas:477-576` (input+output del modelo -> columnas de `Tabla_MOMENT_M1`).

Flujo:

```cmd
:: 1) predecir con el modelo V_num y exportar el JSON del modelo
cd V_num\app
..\..\.venv\Scripts\python.exe export_for_codame.py --input caso.csv --out ..\..\model.json

:: 2) validar con CODAME (bajo la cuenta de dominio)
cd ..\..\
production\validation\run_validate_netonly.cmd ad.tecnicasreunidas.es\<usuario> --row 1 --model-json model.json
```

Formato de `model.json` (lo genera `export_for_codame.py`):

```json
{ "input":  { "UNICODE": "...", "BEAM": "...", "COLUMN": "...",
              "Capacity_Moment_Percentage": ..., "grado_acero": "...", "clase_tornillo": "..." },
  "design": { "g":..., "e":..., "d":..., "Bp":..., "tp":..., "p1":..., ...,
              "Bolt":..., "standard":..., "n_alma":..., "n_cantonera":... },
  "feats":  { "BEAM_tf_mm":..., "fy_acero_mpa":..., "fu_acero_mpa":... } }
```

Mapeo clave (replica AI_Client): `dev=e`, `pfo=d`, `pfi=p1-d-BEAM_tf`, `p2_ep=g`, `b_ep=Bp`,
`BoltName_ep="M"+Bolt`, `Standards=standard`, espesores como `"NNmm"`, `AnguloCantonera=60` si
`Lh>0`, `WeldFactor=1`, `BoltsInTensionFactor=2`, `BoltThreads=True`.

### Limitacion detectada

El modelo de **V_num no predice `Lh`** (`MASKED_COLUMNS = P_COLUMNS + STIFFENER_COLUMNS`, sin
`Lh`), asi que para uniones **con cartabon** la validacion saldria sin cartabon. El modelo de
**V_pru si predice `Lh`**; si se valida con V_num y hay cartabon, hay que aportar `Lh` por otra
via (o usar el modelo V_pru).

## 14. Correccion importante: usar la instancia de Excel EN EJECUCION

`CalcCodame.exe` se engancha con `GetActiveObject` a la **instancia de Excel que ya esta
abierta**. Por eso el validador **NO debe abrir una copia oculta en una instancia nueva**
(si hay otra instancia, el exe se engancha a la equivocada y "no genera resultado").

`validate_codame.py` ahora:
  1. Reutiliza la instancia abierta (o crea una si no hay ninguna).
  2. Selecciona el libro objetivo (`--workbook-name`, por defecto 'CONNEXTOR').
  3. Escribe el diseno en `Tabla_MOMENT_M1` (hoja `IM_MOMENT`), selecciona la fila objetivo.
  4. Lanza el exe y lee `TResultadosComplemen`/`TResultadosRatios` del mismo libro.
  5. No cierra el libro ni Excel si la instancia ya existia.

Requisito operativo: tener abierto el libro real (`CONNEXTOR - CRIS.xlsm`) en Excel antes de
lanzar la validacion; si hay varias instancias/ventanas de Excel, cerrar las sobrantes.
