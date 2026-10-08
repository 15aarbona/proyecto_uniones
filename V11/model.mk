# Rutas de los artefactos de V11, relativas a la carpeta del modelo (V11/).
# El Makefile de la raiz las incluye y hace fallback si no estan definidas.

WEIGHTS = artifacts_v4/model_final.pt
PREPROC = artifacts_v4/preprocessor.joblib

# DATA y CORE usan los valores por defecto del Makefile (data/ y core/) porque
# siguen la estructura comun. Descomenta para sobreescribir:
# CORE = core
# DATA = data
