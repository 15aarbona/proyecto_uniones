# Producción — servidor central + cliente Excel

Tubería completa **Excel/web ↔ servidor de IA**. El servidor sirve modelos reales
(paquetes autocontenidos en `server/models/<NAME>/`): **todos los instalados se cargan a
la vez** y cada petición se **enruta al modelo** indicado en `model`. El preproceso
(tabla → features internas) vive en el `adapter.py` de cada modelo.

```
production/
├── server/            Servidor HTTP (FastAPI) — ver server/README.md
│   ├── main.py            endpoints /health, /models, /model, /model/activate, /predict
│   ├── model_registry.py  carga de modelos + activación en caliente
│   ├── predictor.py       validación de contrato e inferencia
│   ├── storage.py         guarda las filas validadas en parquet
│   ├── config.py          ajustes del servidor + MODEL_NAME por defecto
│   └── models/            paquetes de modelo (generado por `make`)
└── excel_client/       Macro VBA + libro de ejemplo — ver excel_client/README.md
    ├── AI_Client.bas      botones "Enviar a IA" y "Validar y enviar" + JSON/HTTP en VBA puro
    └── plantilla_prueba.xlsx
```

## Cómo probarlo ahora mismo

1. Desde la **raíz** del repo:
   ```bash
   make install-model MODEL=V11
   uv run uvicorn main:app --app-dir production/server --host 0.0.0.0 --port 8080
   ```
2. Abre `http://localhost:8080/web/conexiones_tr.html` (interfaz web) o el Excel de
   `excel_client/` (ver `excel_client/README.md`).
3. Las predicciones devuelven la **tabla completa**: inputs enviados/imputados + campos
   predichos.

Detalles del servidor, contrato y multi-modelo: **`server/README.md`**.
Documentación interactiva de la API: `http://localhost:8080/docs`.

## Añadir / recargar un modelo

```bash
make install-model MODEL=V12
curl -X POST localhost:8080/model/activate \
     -H "Content-Type: application/json" -d '{"name":"V12"}'
```

Tras recargar, ese modelo queda disponible para enrutar con `{"model":"V12", ...}`.

## Qué falta para producción real

1. Decidir dónde vive el servidor (equipo central, SO, puerto) y desplegarlo como servicio.
2. Apuntar `SERVER_URL` del `.bas` a esa máquina.
3. Cuando toque, añadir el guardado de un **dataset raw para reentreno**: cada modelo
   transformará ese dataset con su propio `adapter.py`.
