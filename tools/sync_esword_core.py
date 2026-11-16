#!/usr/bin/env python3
"""Check drift of the vendored e-Sword core.

Compares the local copies under ``src/esword4linux/core/esword`` with an
upstream folder. The upstream is private to the maintainer and is not required
to build or test this project. Set ``ESWORD4LINUX_VENDOR_ORIGIN`` or pass
``--origin`` to check; otherwise the command exits cleanly.

``sqliteplus.py`` is compared after normalising the only line that must change
(the relative Twofish import).

Usage:
    python tools/sync_esword_core.py --origin DIR
    python tools/sync_esword_core.py --origin DIR --sync
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (vendored file, upstream file, normalise the import?)
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
    ap = argparse.ArgumentParser(description=__doc__)
    default_origin = os.environ.get("ESWORD4LINUX_VENDOR_ORIGIN", "")
    ap.add_argument("--origin", default=default_origin)
    ap.add_argument("--sync", action="store_true", help="copy from upstream")
    args = ap.parse_args()

    if not args.origin:
        print("Upstream origin not configured; skipping drift check.")
        print("Set ESWORD4LINUX_VENDOR_ORIGIN or use --origin DIR.")
        return 0

    origin = Path(args.origin).expanduser()
    dest = ROOT / "src" / "esword4linux" / "core" / "esword"

    if not origin.is_dir():
        print(f"Upstream origin not available: {origin}")
        print("(skipping drift check)")
        return 0

    drift = False
    for vendored, source, normalize in FILES:
        vpath = dest / vendored
        spath = origin / source
        if not spath.is_file():
            print(f"  ?  {vendored:22} missing upstream file: {source}")
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
            print(f"  ↻  {vendored:22} synced from {source}")
            continue
        if not vpath.is_file():
            print(f"  ✕  {vendored:22} MISSING from the project")
            drift = True
            continue
        dv = _digest(vpath, normalize)
        ds = _digest(spath, normalize)
        if dv == ds:
            print(f"  ✓  {vendored:22} identical to {source}")
        else:
            print(f"  ✕  {vendored:22} DRIFTED from {source}")
            print(f"       project {dv[:16]}…  upstream {ds[:16]}…")
            drift = True

    if args.sync:
        print("\nSync complete. Review the diff and run the tests.")
        return 0
    if drift:
        print("\nDrift detected. If intentional, document the reason in")
        print("docs/CHANGELOG.md and update this check.")
        return 1
    print("\nVendored core has no drift.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
