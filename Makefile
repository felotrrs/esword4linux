VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: help install run scan test clean deps drift desktop

help:
	@echo "linuxEsword — objetivos:"
	@echo "  make install   Crea el venv e instala la app"
	@echo "  make run       Arranca la aplicación"
	@echo "  make scan      Escanea la carpeta de recursos y pre-indexa la base"
	@echo "  make test      Ejecuta la suite de pruebas"
	@echo "  make deps      Reinstala dependencias"
	@echo "  make drift     Comprueba deriva del núcleo vendorizado vs ~/StorageC/bible"
	@echo "  make desktop   Instala el lanzador .desktop del usuario"
	@echo "  make clean     Elimina venv y caché"

install:
	python3 -m venv $(VENV)
	$(PIP) -q install --upgrade pip
	$(PIP) -q install -e .
	@echo "Listo. Ejecuta: make run"

deps:
	$(PIP) -q install -e .

run:
	$(PY) -m linuxesword

scan:
	$(PY) tools/bootstrap.py

test:
	$(PY) -m pytest -q

drift:
	$(PY) tools/sync_esword_core.py

desktop:
	@mkdir -p ~/.local/share/applications
	@sed "s|@ROOT@|$(CURDIR)|g" packaging/linuxesword.desktop.in \
		> ~/.local/share/applications/linuxesword.desktop
	@chmod +x "$(CURDIR)/run.sh"
	@echo "Instalado en ~/.local/share/applications/linuxesword.desktop"

clean:
	rm -rf $(VENV) .pytest_cache .cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
