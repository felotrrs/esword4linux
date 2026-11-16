#!/usr/bin/env bash
# esword4linux launcher. Creates the venv on first use and starts the app.
set -euo pipefail
cd "$(dirname "$0")"

VENV=".venv"
if [ ! -x "$VENV/bin/python" ]; then
    echo "Creating virtual environment…"
    python3 -m venv "$VENV"
    "$VENV/bin/pip" -q install --upgrade pip
    echo "Installing dependencies (PySide6, PyYAML)…"
    "$VENV/bin/pip" -q install -e .
fi

# After a checkout update the existing venv may lack new dependencies.
if ! "$VENV/bin/python" -c "import PySide6, yaml, esword4linux" >/dev/null 2>&1; then
    echo "Updating dependencies…"
    "$VENV/bin/pip" -q install -e .
fi

exec "$VENV/bin/python" -m esword4linux "$@"
