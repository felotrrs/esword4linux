VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: help install run scan test clean deps drift desktop encrypted dedup deb

help:
	@echo "esword4linux — targets:"
	@echo "  make install   Create the venv and install the app"
	@echo "  make run       Start the application"
	@echo "  make scan      Scan the modules folder (metadata only)"
	@echo "  make encrypted Decrypt and index every encrypted module"
	@echo "  make dedup     Duplicate report (--apply moves copies to _duplicados/)"
	@echo "  make test      Run the test suite"
	@echo "  make deps      Reinstall dependencies"
	@echo "  make drift     Check vendored core against ESWORD4LINUX_VENDOR_ORIGIN"
	@echo "  make desktop   Install the launcher and icons for the current user"
	@echo "  make deb       Build the native Debian package"
	@echo "  make clean     Remove the venv and cache"

install:
	python3 -m venv $(VENV)
	$(PIP) -q install --upgrade pip
	$(PIP) -q install -e ".[dev]"
	@echo "Done. Run: make run"

deps:
	$(PIP) -q install -e ".[dev]"

run:
	$(PY) -m esword4linux

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

deb:
	packaging/build-deb.sh

desktop:
	@mkdir -p ~/.local/share/applications
	@sed "s|@ROOT@|$(CURDIR)|g" packaging/esword4linux.desktop.in \
		> ~/.local/share/applications/esword4linux.desktop
	@chmod +x "$(CURDIR)/run.sh"
	@$(PY) tools/make_icons.py "$$HOME/.local/share/icons/hicolor"
	@gtk-update-icon-cache -f -t ~/.local/share/icons/hicolor >/dev/null 2>&1 || true
	@update-desktop-database ~/.local/share/applications >/dev/null 2>&1 || true
	@echo "Installed: application + hicolor icons (16–512 px)"

clean:
	rm -rf $(VENV) .pytest_cache .cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
