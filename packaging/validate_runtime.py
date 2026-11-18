#!/usr/bin/env python3
"""Validate a staged esword4linux private runtime.

Checks the payload against packaging/runtime-manifest.yaml, resolves the
recursive ELF dependency closure, and imports the application with the system
Python interpreter and only the staged private paths. It never starts a GUI and
never writes bytecode into the staging tree.

Usage:
  packaging/validate_runtime.py --root debian/esword4linux/opt/esword4linux
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT / "packaging" / "runtime-manifest.yaml"


def fail(message: str) -> "NoReturn":
    print(f"validate_runtime: error: {message}", file=sys.stderr)
    raise SystemExit(1)


PLUGIN_GROUPS = (
    "platforms",
    "xcb_integrations",
    "wayland_integrations",
    "imageformats",
    "iconengines",
    "platforminputcontexts",
)


def load_manifest(path: Path) -> dict:
    try:
        import yaml
    except ImportError:
        fail("PyYAML is required to read the runtime manifest "
             "(install python3-yaml)")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        fail(f"could not read {path}: {exc}")
    except yaml.YAMLError as exc:
        fail(f"invalid YAML in {path}: {exc}")
    if not isinstance(data, dict) or not isinstance(data.get("staging"), dict):
        fail(f"{path}: missing staging mapping")
    staging = data["staging"]
    plugins: list[str] = []
    required_plugins = data.get("qt_plugins_required")
    if not isinstance(required_plugins, dict):
        fail(f"{path}: missing qt_plugins_required mapping")
    for group in PLUGIN_GROUPS:
        values = required_plugins.get(group)
        if not isinstance(values, list):
            fail(f"{path}: missing qt_plugins_required.{group} list")
        plugins.extend(str(value) for value in values)
    staging["qt_plugins"] = plugins
    return data


def runtime_env(root: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{root / 'app'}:{root / 'python'}"
    env["LD_LIBRARY_PATH"] = (
        f"{root / 'python' / 'PySide6' / 'Qt' / 'lib'}:"
        f"{root / 'python' / 'shiboken6'}"
    )
    env["QT_PLUGIN_PATH"] = str(
        root / "python" / "PySide6" / "Qt" / "plugins"
    )
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    env.pop("QT_QPA_PLATFORM", None)
    return env


def is_elf(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(4) == b"\x7fELF"
    except OSError:
        return False


def check_elf_closure(root: Path, env: dict[str, str]) -> int:
    private_prefixes = (
        "libQt6", "libicu", "libpyside6", "libshiboken6",
    )
    checked = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file() or not is_elf(path):
            continue
        checked += 1
        proc = subprocess.run(
            ["ldd", str(path)], capture_output=True, text=True, env=env,
            check=False,
        )
        output = proc.stdout + proc.stderr
        if "not found" in output:
            fail(f"unresolved libraries in {path.relative_to(root)}:\n{output}")
        resolved = {
            line.split("=>", 1)[1].split("(", 1)[0].strip()
            for line in output.splitlines() if "=>" in line
        }
        for needed_path in resolved:
            name = Path(needed_path).name
            if name.startswith(private_prefixes) and not needed_path.startswith(
                str(root)
            ):
                fail(
                    f"{path.relative_to(root)} resolves private library "
                    f"{name} outside the runtime: {needed_path}"
                )
    return checked


def check_payload(root: Path, staging: dict) -> None:
    app_icon = root / "app" / "esword4linux" / "assets" / "esword4linux.png"
    about_icon = root / "app" / "esword4linux" / "assets" / "esword4linux-about.png"
    required = [
        root / "app" / "esword4linux" / "app.py",
        root / "app" / "esword4linux" / "core" / "books.yaml",
        app_icon,
        about_icon,
        root / "python" / "PySide6" / "QtCore.abi3.so",
        root / "python" / "PySide6" / "QtGui.abi3.so",
        root / "python" / "PySide6" / "QtWidgets.abi3.so",
        root / "python" / "yaml" / "__init__.py",
        root / "licenses" / "GPL-3.0-only.txt",
        root / "licenses" / "LGPL-3.0-only.txt",
    ]
    for path in required:
        if not path.is_file():
            fail(f"missing required payload: {path}")
    # The window/launcher icon and the illustrated About artwork are distinct
    # by design. Requiring identical bytes was a regression from the discarded
    # single-icon change; validate that both assets are real PNG images.
    for icon in (app_icon, about_icon):
        if not icon.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
            fail(f"not a PNG image: {icon}")

    forbidden = [
        p for p in root.rglob("*")
        if p.name in {"__pycache__", "pip", ".venv", "site-packages"}
        or p.suffix in {".pyc", ".pyo", ".whl", ".egg-info"}
    ]
    if forbidden:
        fail(f"forbidden build artifact staged: {forbidden[0]}")

    if list((root / "python" / "yaml").glob("_yaml*.so")):
        fail("compiled PyYAML extension must not be staged")
    if (root / "python" / "yaml" / "cyaml.py").exists():
        fail("PyYAML cyaml.py must not be staged")

    for rel in staging.get("qt_libraries", []):
        if not (root / "python" / "PySide6" / "Qt" / "lib" / rel).is_file():
            fail(f"manifest Qt library missing: {rel}")
    for rel in staging.get("qt_plugins", []):
        if not (root / "python" / "PySide6" / "Qt" / "plugins" / rel).is_file():
            fail(f"manifest Qt plugin missing: {rel}")


def run_imports(root: Path, env: dict[str, str]) -> None:
    code = r"""
import sys
sys.dont_write_bytecode = True
import yaml
import PySide6
from PySide6 import QtCore, QtGui, QtWidgets
import esword4linux
from esword4linux.core.books import BOOKS
from esword4linux.i18n import tr

assert not yaml.__with_libyaml__, "PyYAML must run in pure-Python mode"
assert len(BOOKS) >= 66, f"book table incomplete: {len(BOOKS)}"
assert len(BOOKS) == len({book[0] for book in BOOKS}), "duplicate book IDs"
assert QtCore.__version__ == PySide6.__version__, "Qt version mismatch"
assert QtGui.__name__ == "PySide6.QtGui"
assert esword4linux.__version__ == "0.5.0"
assert isinstance(tr("app.title"), str)
print("python", sys.version.split()[0])
print("PySide6", QtCore.__version__)
print("PyYAML", yaml.__version__, "pure-python")
print("books", len(BOOKS))
"""
    proc = subprocess.run(
        [sys.executable, "-B", "-s", "-c", code],
        capture_output=True, text=True, env=env, check=False,
    )
    if proc.returncode != 0:
        fail(f"runtime import failed:\n{proc.stdout}\n{proc.stderr}")
    print(proc.stdout.rstrip())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args(argv)

    root = args.root.resolve()
    if not root.is_dir():
        fail(f"runtime root not found: {root}")
    if root == Path("/opt/esword4linux"):
        fail("refusing to validate the live installation in place; "
             "pass the staged or extracted runtime root")

    manifest = load_manifest(args.manifest)
    check_payload(root, manifest["staging"])
    env = runtime_env(root)
    checked = check_elf_closure(root, env)
    run_imports(root, env)
    print(f"ELF objects checked: {checked}")
    print(f"runtime root: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
