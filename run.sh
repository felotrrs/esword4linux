#!/usr/bin/env bash
# Lanzador de linuxEsword. Crea el venv la primera vez y arranca la app.
set -euo pipefail
cd "$(dirname "$0")"

VENV=".venv"
if [ ! -x "$VENV/bin/python" ]; then
    echo "Creando entorno virtual…"
    python3 -m venv "$VENV"
    "$VENV/bin/pip" -q install --upgrade pip
    echo "Instalando dependencias (PySide6)…"
    "$VENV/bin/pip" -q install -e .
fi

exec "$VENV/bin/python" -m linuxesword "$@"
