# Modelo V3 — etiquetas semánticas de p

Pipeline experimental para el nuevo `data_pi_tag.csv`. No reemplaza V2.

1. Copia `data_pi_tag.csv` en esta carpeta o cambia `CSV_PATH` en el notebook.
2. Instala las dependencias de `V2/app/requirements.txt` y `matplotlib`/`jupyter`.
3. Abre `pipeline_walkthrough_v3.ipynb` y ejecuta las celdas en orden.

La diferencia principal es que se predicen conjuntamente `p1..p12` y
`p1_label..p12_label`. `UNUSED` actúa como máscara de cada valor p. Las etiquetas
permiten conservar directamente la semántica proporcionada por los datos, sin la
reparametrización geométrica de V2.
