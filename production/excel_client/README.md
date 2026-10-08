# Cliente de Excel — fase de pruebas

Macro VBA genérica que manda **todas** las filas de una hoja al servidor de IA y escribe la
respuesta de vuelta, más un segundo botón para validar y guardar esas filas de cara a un
reentreno futuro. No asume ningún nombre de columna fijo: lee la fila de cabeceras tal cual
esté en la hoja, así que quien decida las "columnas de prueba" (o, más adelante, las
columnas reales) no tiene que tocar la macro — solo la hoja.

## Contenido

- `AI_Client.bas` — el módulo VBA con las dos macros y todo lo necesario (HTTP, JSON).
- `plantilla_prueba.xlsx` — un libro de ejemplo con la hoja `Datos_IA` ya preparada
  (cabeceras + 4 filas de muestra) para no partir de cero.

## Instalación (una vez)

1. Abre `plantilla_prueba.xlsx` (o el libro donde quieras montar esto) y guárdalo como
   **Excel habilitado para macros (`.xlsm`)**.
2. `Alt+F11` para abrir el editor de VBA → **Archivo → Importar archivo…** → selecciona
   `AI_Client.bas`.
3. En el editor de VBA: **Herramientas → Referencias…** → marca
   **"Microsoft WinHTTP Services, version 5.1"** (si no la marcas, dará un error de ActiveX
   al enviar). También necesita `Scripting.Runtime`/`ADODB` — normalmente ya están
   disponibles sin marcar nada, pero si diera error de referencia, márcalas también.
4. Abre `AI_Client.bas` en el editor y ajusta, si hace falta, estas constantes al principio:
   - `SERVER_URL` → `http://localhost:8000` en pruebas; la URL del equipo central cuando
     toque (p.ej. `http://10.0.0.5:8000`).
   - `SHEET_NAME` → el nombre de la hoja con la tabla de entrada (`Datos_IA` por defecto).
5. Vuelve a la hoja de Excel: **Programador → Insertar → Botón (control de formulario)**,
   dibuja un botón, y en el diálogo que aparece asígnale la macro `AI_Client.SendToAI`.
   Repite para un segundo botón con `AI_Client.ValidateAndSend`. Renómbralos como quieras
   (p.ej. "Enviar a IA" y "Validar y enviar").

   *(Si no ves la pestaña "Programador": Archivo → Opciones → Personalizar cinta → marca
   "Programador".)*

## Cómo funciona

### Botón "Enviar a IA" (`SendToAI`)
1. Lee la fila de cabeceras (fila 1) y todas las filas con datos de la hoja `Datos_IA`.
2. Manda cada fila tal cual al servidor (`POST /predict`).
3. Escribe la respuesta en la hoja: si una columna de la respuesta ya existe (mismo nombre
   de cabecera), la actualiza; si es nueva (p.ej. `pred_valor_A`), la añade al final.
4. Marca cada fila en la columna `Estado_IA` como `Predicho`.

### Botón "Validar y enviar" (`ValidateAndSend`)
1. El ingeniero puede editar directamente en la hoja cualquier valor predicho antes de
   pulsar este botón (son celdas normales).
2. Toma **todas** las filas marcadas como `Predicho` (con los valores ya editados si los
   tocaron) y las manda a `POST /validate`.
3. El servidor las guarda en su dataset global (para un reentreno futuro) y la macro marca
   esas filas como `Validado y enviado (fecha-hora)`, para no volver a enviarlas por error.

## Protocolo de prueba recomendado

Con el servidor arrancado en local (ver `server/README.md`):

1. Abre `plantilla_prueba.xlsm` con las 4 filas de muestra ya cargadas.
2. Pulsa **"Enviar a IA"** → deberían aparecer columnas nuevas (`pred_valor_A`,
   `pred_valor_B`, `pred_categoria`) rellenas, y `Estado_IA = Predicho` en las 4 filas.
3. Edita a mano algún valor de `pred_valor_A` en una fila, para simular la corrección de un
   ingeniero.
4. Pulsa **"Validar y enviar"** → debería confirmar "4 fila(s) validada(s)..." y
   `Estado_IA` pasar a `Validado y enviado (...)`.
5. Comprueba en el servidor que las filas han llegado:
   ```bash
   curl http://localhost:8000/dataset/summary
   ```
   o inspecciona `server/data/global_dataset.parquet` con pandas — el valor editado a mano
   debe verse reflejado ahí.
6. Añade una fila nueva a mano en la hoja (con `Estado_IA` vacío) y repite desde el paso 2:
   debe predecir solo lo pendiente sin tocar las ya validadas... *(en esta primera versión
   `SendToAI` reenvía TODAS las filas, validadas o no, tal y como pediste — si más adelante
   quieres que solo reenvíe las pendientes, es un cambio pequeño en `SendToAI`: filtrar por
   `Estado_IA` vacío antes de construir el JSON)*.

## Limitaciones conocidas de esta fase (a revisar antes de producción real)

- El parser/serializador JSON es uno mínimo escrito a mano (sin librerías externas) — vale
  para filas planas (texto/número/booleano), no para JSON anidado. Si el modelo real
  necesita estructuras anidadas, sustituir por la librería
  [VBA-JSON](https://github.com/VBA-tools/VBA-JSON) (un único módulo, fácil de importar
  igual que `AI_Client.bas`).
- `IsNumeric`/conversión de números en VBA depende de la configuración regional de Windows
  (coma o punto decimal) — probar en el PC real de destino, no solo en el tuyo.
- No hay control de qué usuario valida cada fila (dijiste que de momento pueden validar
  todos) — si más adelante hace falta, se puede mandar `Application.UserName` como un campo
  más de cada fila.
- `SERVER_URL` está como constante en el código; si el equipo central cambia de
  IP/puerto a menudo, conviene moverla a una celda de una hoja de configuración (p.ej. la
  hoja `PREFERENCES` del libro real) en vez de tener que reabrir el editor VBA cada vez.
