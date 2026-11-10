#!/usr/bin/env python3
"""Control de deriva del núcleo e-Sword vendorizado.

Compara los archivos copiados desde `~/StorageC/bible/shared/esword/` con su
origen. `sqliteplus.py` se compara normalizando la única línea que debe
cambiar (el import relativo del Twofish).

Uso:
    python tools/sync_esword_core.py            # solo comprobar (exit 1 si deriva)
    python tools/sync_esword_core.py --sync     # re-copiar desde el origen
    python tools/sync_esword_core.py --origin DIR
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ORIGIN = Path("/home/felipe/StorageC/bible/shared/esword")

# (archivo vendorizado, archivo de origen, ¿normalizar el import?)
FILES = [
    ("twofish.py", "twofish.py", False),
    ("rtf.py", "rtf_plain.py", False),
    ("font_codepages.py", "font_codepages.py", False),
    ("legacy_translit.py", "legacy_translit.py", False),
    ("sqliteplus.py", "sqliteplus.py", True),
]

IMPORT_ORIGIN = "from shared.esword.twofish import Twofish128"
IMPORT_VENDOR = "from .twofish import Twofish128"


def _digest(path: Path, normalize: bool) -> str:
    data = path.read_bytes()
    if normalize:
        data = data.replace(IMPORT_VENDOR.encode(), IMPORT_ORIGIN.encode())
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--origin", default=str(DEFAULT_ORIGIN))
    ap.add_argument("--sync", action="store_true", help="re-copiar desde el origen")
    args = ap.parse_args()

    origin = Path(args.origin)
    dest = ROOT / "src" / "linuxesword" / "core" / "esword"

    if not origin.is_dir():
        print(f"origen no disponible: {origin}")
        print("(se omite la comprobación de deriva)")
        return 0

    drift = False
    for vendored, source, normalize in FILES:
        vpath = dest / vendored
        spath = origin / source
        if not spath.is_file():
            print(f"  ?  {vendored:22} origen ausente: {source}")
            continue
        if args.sync:
            if vendored == "rtf.py":
                shutil.copyfile(spath, vpath)
            elif normalize:
                text = spath.read_text(encoding="utf-8").replace(
                    IMPORT_ORIGIN, IMPORT_VENDOR
                )
                vpath.write_text(text, encoding="utf-8")
            else:
                shutil.copyfile(spath, vpath)
            print(f"  ↻  {vendored:22} sincronizado desde {source}")
            continue
        if not vpath.is_file():
            print(f"  ✕  {vendored:22} FALTA en el proyecto")
            drift = True
            continue
        dv = _digest(vpath, normalize)
        ds = _digest(spath, normalize)
        if dv == ds:
            print(f"  ✓  {vendored:22} idéntico a {source}")
        else:
            print(f"  ✕  {vendored:22} DERIVA respecto a {source}")
            print(f"       proyecto {dv[:16]}…  origen {ds[:16]}…")
            drift = True

    if args.sync:
        print("\nSincronización completada. Revisa el diff y ejecuta las pruebas.")
        return 0
    if drift:
        print("\nHay deriva. Si es intencional, documenta el motivo en")
        print("documentacion/CHANGELOG.md y actualiza este control.")
        return 1
    print("\nNúcleo vendorizado sin deriva.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
