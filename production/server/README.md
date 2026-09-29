# Servidor de inferencia — fase de pruebas (columnas de prueba)

Servidor HTTP central que hará de base para el modelo de IA. **De momento el "modelo" es un
`predictor.py` de mentira** (determinista, no aprende nada) — el objetivo de esta fase es
dejar montada y probada toda la tubería (Excel → servidor → Excel, y validar → guardar para
reentrenar) mientras se cierran las columnas de entrada/salida reales del modelo definitivo.

## Instalación

```bash
cd server
python -m venv .venv && source .venv/bin/activate   # opcional
pip install -r requirements.txt
```

## Arrancar

```bash
# variables de entorno opcionales (por defecto valen para pruebas en local):
export AI_API_KEY=testkey        # cambiar en el despliegue real
export AI_PORT=8000

uvicorn main:app --host 0.0.0.0 --port 8000
```

Si prefieres no usar variables de entorno, edita directamente los valores por defecto en
`config.py`.

## Endpoints

| Método | Ruta | Auth | Qué hace |
|---|---|---|---|
| GET | `/health` | no | Estado del servidor y del modelo cargado |
| POST | `/predict` | sí (`X-API-Key`) | `{"rows": [...]}` → predicciones para cada fila |
| POST | `/validate` | sí | `{"rows": [...]}` (filas ya revisadas) → se guardan en el dataset global |
| GET | `/dataset/summary` | sí | nº de filas guardadas, columnas, última validación |

La cabecera `X-API-Key` debe coincidir con `AI_API_KEY` (o el valor de `config.API_KEY`).

## Probar sin Excel (curl)

```bash
curl http://localhost:8000/health

curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" -H "X-API-Key: testkey" \
  -d '{"rows": [{"Unicode":"U1","BEAM":"IPE300","COLUMN":"HEB240"}]}'

curl -X POST http://localhost:8000/validate \
  -H "Content-Type: application/json" -H "X-API-Key: testkey" \
  -d '{"rows": [{"Unicode":"U1","BEAM":"IPE300","COLUMN":"HEB240","pred_valor_A":999.9}]}'

curl http://localhost:8000/dataset/summary -H "X-API-Key: testkey"
```

También puedes abrir `http://localhost:8000/docs` (Swagger, generado automáticamente por
FastAPI) para probar los endpoints desde el navegador sin escribir curl.

## Qué guarda y dónde

- `data/global_dataset.parquet`: todas las filas **validadas** (nunca las predichas sin
  revisar), con el esquema que traigan en cada momento (si cambian las columnas de entrada,
  el fichero se adapta solo — ver `storage.py`). Cada fila lleva además `_validated_at` y
  `_source` para trazabilidad.
- `data/server.log`: log de peticiones y errores.

## Cómo se conecta esto con el modelo real cuando esté listo

Todo el cableado (FastAPI, autenticación, guardado del dataset, logging) es independiente
del modelo. El único fichero que hay que tocar es **`predictor.py`**: sustituir el cuerpo de
`predict_rows()` por la llamada real (por ejemplo, reutilizando `store.py` de la app de
escritorio: `store.load_model_bundle()` + `store.predict_df()`), manteniendo la misma firma
`list[dict] -> list[dict]`. `main.py` no necesitaría cambios.

Cuando el esquema de columnas esté cerrado, conviene además:
- Sustituir el `RowsIn` genérico de `main.py` por un modelo Pydantic con los campos reales
  (validación de tipos y de campos obligatorios en vez de aceptar cualquier JSON).
- Añadir un endpoint `POST /retrain` (protegido) que dispare `store.retrain()` sobre
  `data/global_dataset.parquet`.

## Pendiente para el despliegue real (fuera de esta fase de pruebas)

- Cambiar `AI_API_KEY` por un valor real (no "testkey").
- Decidir el puerto definitivo con el equipo/IT y, si aplica, HTTPS.
- Ejecutar como servicio (systemd en Linux / NSSM en Windows) para que arranque solo y se
  reinicie si falla, en vez de lanzarlo a mano con `uvicorn`.
