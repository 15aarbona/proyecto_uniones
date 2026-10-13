# Instalacion de modelos en el servidor de produccion.
#
#   make install-model MODEL=V11
#
# Copia el paquete autocontenido del modelo (codigo de core/ + artefactos + datos)
# a production/server/models/<MODEL>/. El servidor puede activarlo en caliente, sin
# reiniciar, via POST /model/activate {"name":"<MODEL>"}.
#
# Cada modelo puede definir sus rutas en <MODEL>/model.mk (relativas a su carpeta):
#
#   WEIGHTS = artifacts_v4/model_final.pt     # artefactos (por defecto artifacts/...)
#   PREPROC = artifacts_v4/preprocessor.joblib
#   CORE    = core                            # por defecto
#   DATA    = data                            # por defecto
#
# Si <MODEL>/model.mk no existe o no define alguna ruta, se usa el valor por defecto.

MODEL ?= V11

ifeq ($(OS),Windows_NT)
    SHELL  := cmd.exe
    COPY   := copy /y
    XCOPY  := xcopy /e /i /y
    RMDIR  := rmdir /s /q
    SEP    := \\
    MKDIR   = if not exist "$(1)" mkdir "$(1)"
    ISFILE  = if exist "$(1)" (echo   OK: $(1)) else (echo   [AVISO] no existe $(1), se copiara solo lo que haya)
else
    SHELL  := /bin/sh
    COPY   := cp -f
    XCOPY  := cp -r
    RMDIR  := rm -rf
    SEP    := /
    MKDIR   = mkdir -p "$(1)"
    ISFILE  = if [ -f "$(1)" ]; then echo "  OK: $(1)"; else echo "  [AVISO] no existe $(1), se copiara solo lo que haya"; fi
endif

# Rutas por defecto (relativas a la carpeta del modelo, con '/').
# El .mk del modelo puede sobreescribirlas.
CORE    ?= core
DATA    ?= data
WEIGHTS ?= artifacts/model_final.pt
PREPROC ?= artifacts/preprocessor.joblib

-include $(MODEL)/model.mk

# Conversion '/' -> separador del SO.
slash = $(subst /,$(SEP),$(1))

SRC         = $(MODEL)
DEST        = production$(SEP)server$(SEP)models$(SEP)$(MODEL)
CORE_SRC    = $(call slash,$(SRC)/$(CORE))
DATA_SRC    = $(call slash,$(SRC)/$(DATA))
WEIGHTS_SRC = $(call slash,$(SRC)/$(WEIGHTS))
PREPROC_SRC = $(call slash,$(SRC)/$(PREPROC))

.PHONY: install-model check-artifacts clean-model

install-model: check-artifacts
	@echo Instalando modelo $(MODEL) en $(DEST) ...
	@$(call MKDIR,$(DEST))
	$(XCOPY) "$(CORE_SRC)" "$(DEST)$(SEP)core"
	-$(COPY) "$(WEIGHTS_SRC)" "$(DEST)$(SEP)weights.pt"
	-$(COPY) "$(PREPROC_SRC)" "$(DEST)$(SEP)preprocessor.joblib"
	-$(XCOPY) "$(DATA_SRC)" "$(DEST)$(SEP)data"
	@echo Modelo $(MODEL) instalado.
	@echo Activalo en caliente con: POST /model/activate {"name":"$(MODEL)"}

check-artifacts:
	@echo Comprobando artefactos de $(MODEL):
	@$(call ISFILE,$(WEIGHTS_SRC))
	@$(call ISFILE,$(PREPROC_SRC))

clean-model:
	$(RMDIR) "$(DEST)"
