# Producción — servidor central + Excel (fase de pruebas)

Primera versión de la tubería completa **Excel ↔ servidor de IA**, pensada para probar la
comunicación y las acciones (enviar / predecir / editar / validar / guardar) mientras el
modelo real y sus columnas de entrada todavía se están cerrando. El "modelo" que responde
ahora mismo es un **stub determinista** (`server/predictor.py`) — no aprende nada, solo
sirve para poder probar todo el circuito de extremo a extremo.

```
production/
├── server/            Servidor HTTP (FastAPI) — ver server/README.md
│   ├── main.py           endpoints /predict, /validate, /health, /dataset/summary
│   ├── predictor.py       "modelo" de mentira, determinista, fácil de sustituir
│   ├── storage.py         guarda las filas validadas (esquema dinámico) en parquet
│   ├── config.py           configuración (API key, puerto, rutas) vía variables de entorno
│   └── requirements.txt
└── excel_client/       Macro VBA + libro de ejemplo — ver excel_client/README.md
    ├── AI_Client.bas      botones "Enviar a IA" y "Validar y enviar" + JSON/HTTP en VBA puro
    └── plantilla_prueba.xlsx
```

## Cómo probarlo ahora mismo (todo en tu propio ordenador)

1. `cd server && pip install -r requirements.txt && uvicorn main:app --port 8000`
2. Abre `excel_client/plantilla_prueba.xlsx`, guárdalo como `.xlsm`, importa `AI_Client.bas`
   y añade los dos botones (pasos detallados en `excel_client/README.md`).
3. Pulsa "Enviar a IA" → "Validar y enviar" y comprueba `server/data/global_dataset.parquet`.

Todo esto ya está probado por mi parte a nivel de servidor (predict → validate → dataset con
esquema evolutivo, con y sin API key) usando peticiones HTTP reales contra un `uvicorn` en
marcha. La parte VBA no la he podido ejecutar (no hay Excel/Windows en este entorno), así
que conviene que sigas el protocolo de prueba de `excel_client/README.md` antes de darlo por
bueno.

## Qué falta para pasar de "fase de pruebas" a producción real

1. Cerrar el esquema de columnas del modelo definitivo (entrada y salida) y ajustar
   `predictor.py` (sustituir el stub por la llamada al modelo real) y, si quieres más
   seguridad, el `RowsIn` de `main.py` (columnas fijas en vez de JSON libre).
2. Decidir dónde vive el servidor (equipo central, SO, puerto) y desplegarlo como servicio.
3. Cambiar `AI_API_KEY`/`API_KEY` a un valor real y apuntar `SERVER_URL` del `.bas` a esa
   máquina.
4. Decidir si `SendToAI` debe reenviar solo las filas pendientes en vez de todas (ahora
   mismo manda todas, como pediste) — es un cambio pequeño si hace falta más adelante.
5. Añadir `POST /retrain` (reentreno manual, como en la app de escritorio) cuando el modelo
   real esté integrado.
