#!/usr/bin/env bash
# Lanzador de linuxEsword. Crea el venv la primera vez y arranca la app.
set -euo pipefail
cd "$(dirname "$0")"

VENV=".venv"
if [ ! -x "$VENV/bin/python" ]; then
    echo "Creando entorno virtual…"
    python3 -m venv "$VENV"
    "$VENV/bin/pip" -q install --upgrade pip
    echo "Instalando dependencias (PySide6, PyYAML)…"
    "$VENV/bin/pip" -q install -e .
fi

# Tras actualizar el checkout, el venv existente puede no tener las
# dependencias nuevas (p. ej. PyYAML); se reinstala solo si falta alguna.
if ! "$VENV/bin/python" -c "import PySide6, yaml" >/dev/null 2>&1; then
    echo "Actualizando dependencias…"
    "$VENV/bin/pip" -q install -e .
fi

exec "$VENV/bin/python" -m linuxesword "$@"
