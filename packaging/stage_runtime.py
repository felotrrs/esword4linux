#!/usr/bin/env python3
"""Assemble the private esword4linux runtime in a staging directory.

This script is package-format neutral: Debian calls it from debian/rules, and a
future AppImage build can call it with a different destination prefix. It never
modifies the developer's .venv and never installs packages into the system
Python environment.

Inputs:
  --wheelhouse   directory containing the pinned PySide6-Essentials, shiboken6
                 and PyYAML wheels (see packaging/runtime-requirements.txt)
  --dest         runtime root to create (for Debian:
                 debian/esword4linux/opt/esword4linux)
  --app-src      src/esword4linux
  --manifest     packaging/runtime-manifest.yaml

The script fails closed: missing files, unverified wheels, an app version
mismatch or an unexpected native extension aborts the build.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT / "packaging" / "runtime-manifest.yaml"
DEFAULT_REQUIREMENTS = REPO_ROOT / "packaging" / "runtime-requirements.txt"
DEFAULT_APP_SRC = REPO_ROOT / "src" / "esword4linux"
DEFAULT_LICENSES = REPO_ROOT / "packaging" / "licenses"

RUNTIME_FILES = {
    "pyside6-essentials": "PySide6",
    "shiboken6": "shiboken6",
    "pyyaml": "yaml",
}

PLUGIN_GROUPS = (
    "platforms",
    "xcb_integrations",
    "wayland_integrations",
    "imageformats",
    "iconengines",
    "platforminputcontexts",
)


def fail(message: str) -> "NoReturn":
    print(f"stage_runtime: error: {message}", file=sys.stderr)
    raise SystemExit(1)


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
    if not isinstance(data, dict):
        fail(f"{path}: manifest root must be a mapping")
    if "app_version" not in data:
        fail(f"{path}: missing app_version")
    staging = data.get("staging")
    if not isinstance(staging, dict):
        fail(f"{path}: missing staging mapping")
    required = {
        "pyside6_files", "shiboken6_files", "qt_libraries",
    }
    missing = sorted(required - staging.keys())
    if missing:
        fail(f"{path}: missing staging keys: {', '.join(missing)}")

    # The exact plugin paths live once, in qt_plugins_required. Flatten them
    # for the staging loop instead of duplicating the list under staging.
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


def app_version(app_src: Path) -> str:
    text = (app_src / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', text, re.M)
    if not match:
        fail(f"could not read __version__ from {app_src / '__init__.py'}")
    return match.group(1)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_wheelhouse(wheelhouse: Path, requirements: Path) -> dict[str, Path]:
    if not wheelhouse.is_dir():
        fail(f"wheelhouse not found: {wheelhouse}")
    expected_hashes = set(
        re.findall(r"--hash=sha256:([0-9a-f]{64})",
                   requirements.read_text(encoding="utf-8"))
    )
    if not expected_hashes:
        fail(f"no hashes found in {requirements}")

    wheels: dict[str, Path] = {}
    for path in sorted(wheelhouse.glob("*.whl")):
        normalized = path.name.split("-", 1)[0].lower().replace("_", "-")
        if normalized not in RUNTIME_FILES:
            continue
        digest = sha256(path)
        if digest not in expected_hashes:
            fail(f"wheel hash is not pinned: {path.name} ({digest})")
        wheels[normalized] = path

    missing = sorted(set(RUNTIME_FILES) - wheels.keys())
    if missing:
        fail(f"wheelhouse is missing: {', '.join(missing)}")
    return wheels


def copy_file(src: Path, dst: Path, mode: int = 0o644,
              epoch: int | None = None) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    os.chmod(dst, mode)
    if epoch is not None:
        os.utime(dst, (epoch, epoch))


def copy_tree(src: Path, dst: Path, epoch: int | None = None,
              skip_suffixes: tuple[str, ...] = ()) -> int:
    copied = 0
    for item in sorted(src.rglob("*")):
        rel = item.relative_to(src)
        if "__pycache__" in rel.parts or item.suffix in {".pyc", ".pyo"}:
            continue
        if any(item.name.endswith(suffix) for suffix in skip_suffixes):
            continue
        target = dst / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif item.is_file():
            mode = 0o755 if item.suffix == ".so" else 0o644
            copy_file(item, target, mode, epoch)
            copied += 1
    return copied


def extract_wheel(wheel: Path, workdir: Path) -> Path:
    target = workdir / wheel.name.replace(".whl", "")
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(wheel) as archive:
        archive.extractall(target)
    return target


def stage_app(src: Path, dest: Path, epoch: int) -> int:
    if not (src / "__init__.py").is_file():
        fail(f"application source not found: {src}")
    target = dest / "app" / "esword4linux"
    copied = copy_tree(src, target, epoch)
    for required in (
        "__init__.py", "app.py", "core/books.yaml",
        "i18n/en.json", "i18n/es.json", "assets/esword4linux.png",
        "assets/esword4linux-about.png",
    ):
        if not (target / required).is_file():
            fail(f"application payload missing: {required}")
    unexpected = [p for p in target.rglob("*") if p.suffix in {".so", ".pyc"}]
    if unexpected:
        fail(f"unexpected native/bytecode file in app payload: {unexpected[0]}")
    return copied


def stage_pyside(extracted: dict[str, Path], staging: dict,
                 dest: Path, epoch: int) -> int:
    root = extracted["pyside6-essentials"] / "PySide6"
    copied = 0
    for rel in staging["pyside6_files"]:
        src = root / rel
        if not src.is_file():
            fail(f"missing PySide6 file: {rel}")
        mode = 0o755 if src.suffix == ".so" else 0o644
        copy_file(src, dest / "python" / "PySide6" / rel, mode, epoch)
        copied += 1
    for rel in staging["qt_libraries"]:
        src = root / "Qt" / "lib" / rel
        if not src.is_file():
            fail(f"missing Qt library: {rel}")
        copy_file(src, dest / "python" / "PySide6" / "Qt" / "lib" / rel,
                  0o755, epoch)
        copied += 1
    for rel in staging["qt_plugins"]:
        src = root / "Qt" / "plugins" / rel
        if not src.is_file():
            fail(f"missing Qt plugin: {rel}")
        copy_file(src, dest / "python" / "PySide6" / "Qt" / "plugins" / rel,
                  0o755, epoch)
        copied += 1
    return copied


def stage_shiboken(extracted: dict[str, Path], staging: dict,
                   dest: Path, epoch: int) -> int:
    root = extracted["shiboken6"] / "shiboken6"
    copied = 0
    for rel in staging["shiboken6_files"]:
        src = root / rel
        if not src.is_file():
            fail(f"missing shiboken6 file: {rel}")
        mode = 0o755 if src.suffix == ".so" else 0o644
        copy_file(src, dest / "python" / "shiboken6" / rel, mode, epoch)
        copied += 1
    return copied


def stage_yaml(extracted: dict[str, Path], dest: Path, epoch: int) -> int:
    source = extracted["pyyaml"] / "yaml"
    target = dest / "python" / "yaml"
    copied = 0
    for src in sorted(source.glob("*.py")):
        # Keep the wheel's pure-Python implementation. _yaml is a CPython
        # minor-version extension and cyaml.py is only its Python wrapper.
        if src.name == "cyaml.py":
            continue
        copy_file(src, target / src.name, 0o644, epoch)
        copied += 1
    if (target / "_yaml").exists():
        fail("compiled PyYAML extension was staged unexpectedly")
    return copied


def stage_licenses(source: Path, dest: Path, epoch: int) -> int:
    if not source.is_dir():
        fail(f"license directory not found: {source}")
    return copy_tree(source, dest / "licenses", epoch)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheelhouse", type=Path, required=True)
    parser.add_argument("--dest", type=Path, required=True)
    parser.add_argument("--app-src", type=Path, default=DEFAULT_APP_SRC)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--requirements", type=Path,
                        default=DEFAULT_REQUIREMENTS)
    parser.add_argument("--licenses", type=Path, default=DEFAULT_LICENSES)
    args = parser.parse_args(argv)

    manifest = load_manifest(args.manifest)
    staging = manifest["staging"]
    version = app_version(args.app_src)
    if str(manifest["app_version"]) != version:
        fail(f"manifest app_version {manifest['app_version']!r} does not match "
             f"application {version!r}")

    epoch = int(os.environ.get("SOURCE_DATE_EPOCH") or 315532800)

    if args.dest.exists():
        shutil.rmtree(args.dest)
    args.dest.mkdir(parents=True, exist_ok=True)

    wheels = verify_wheelhouse(args.wheelhouse, args.requirements)
    staged = 0
    with tempfile.TemporaryDirectory(prefix="esword4linux-wheels-") as tmp:
        workdir = Path(tmp)
        extracted = {
            name: extract_wheel(wheel, workdir)
            for name, wheel in wheels.items()
        }
        staged += stage_app(args.app_src, args.dest, epoch)
        staged += stage_pyside(extracted, staging, args.dest, epoch)
        staged += stage_shiboken(extracted, staging, args.dest, epoch)
        staged += stage_yaml(extracted, args.dest, epoch)

    staged += stage_licenses(args.licenses, args.dest, epoch)
    copy_file(args.manifest, args.dest / "RUNTIME-MANIFEST.yaml", 0o644, epoch)

    size = sum(p.stat().st_size for p in args.dest.rglob("*") if p.is_file())
    print(f"staged {staged} files ({size / 1024 / 1024:.1f} MiB) in {args.dest}")
    print(f"  application {version}")
    print("  PySide6 (private Qt runtime)")
    print("  PyYAML 6.0.3 (pure Python, no _yaml extension)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
