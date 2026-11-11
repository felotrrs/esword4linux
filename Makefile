VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: help install run scan test clean deps drift desktop encrypted dedup

help:
	@echo "linuxEsword — objetivos:"
	@echo "  make install   Crea el venv e instala la app"
	@echo "  make run       Arranca la aplicación"
	@echo "  make scan      Escanea la carpeta de recursos y pre-indexa la base"
	@echo "  make encrypted Descifra e indexa todos los módulos cifrados"
	@echo "  make dedup     Informe de duplicados (--apply los mueve a _duplicados/)"
	@echo "  make test      Ejecuta la suite de pruebas"
	@echo "  make deps      Reinstala dependencias"
	@echo "  make drift     Comprueba deriva del núcleo vendorizado vs ~/StorageC/bible"
	@echo "  make desktop   Instala el lanzador y los iconos del usuario"
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

encrypted:
	$(PY) tools/prepare_encrypted.py

dedup:
	$(PY) tools/deduplicate.py --write-report

test:
	$(PY) -m pytest -q

drift:
	$(PY) tools/sync_esword_core.py

desktop:
	@mkdir -p ~/.local/share/applications
	@sed "s|@ROOT@|$(CURDIR)|g" packaging/linuxesword.desktop.in \
		> ~/.local/share/applications/linuxesword.desktop
	@chmod +x "$(CURDIR)/run.sh"
	@for s in 16 22 24 32 48 64 128 256 512; do \
		mkdir -p "$$HOME/.local/share/icons/hicolor/$${s}x$${s}/apps"; \
		cp "packaging/icons/hicolor/$${s}x$${s}/apps/linuxesword.png" \
		   "$$HOME/.local/share/icons/hicolor/$${s}x$${s}/apps/linuxesword.png"; \
	done
	@gtk-update-icon-cache -f -t ~/.local/share/icons/hicolor >/dev/null 2>&1 || true
	@update-desktop-database ~/.local/share/applications >/dev/null 2>&1 || true
	@echo "Instalado: aplicación + iconos hicolor (16–512 px)"

clean:
	rm -rf $(VENV) .pytest_cache .cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
