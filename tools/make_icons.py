#!/usr/bin/env python3
"""Generate hicolor PNGs from the canonical application icon.

``src/esword4linux/assets/esword4linux.png`` is the window/launcher icon.
``src/esword4linux/assets/esword4linux-about.png`` is the separate illustrated
About artwork and is never overwritten by this tool.

Usage:
  tools/make_icons.py [DEST]
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QImage

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "src" / "esword4linux" / "assets" / "esword4linux.png"
SIZES = (16, 22, 24, 32, 48, 64, 128, 256, 512)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "dest", nargs="?", default=str(Path.home() / ".local/share/icons/hicolor"),
        help="hicolor icon root (default: ~/.local/share/icons/hicolor)",
    )
    args = ap.parse_args(argv)
    dest = Path(args.dest).expanduser()

    app = QGuiApplication.instance() or QGuiApplication([])  # noqa: F841
    source = QImage(str(SOURCE))
    if source.isNull():
        print(f"Could not read {SOURCE}", file=sys.stderr)
        return 1

    for size in SIZES:
        target = dest / f"{size}x{size}" / "apps" / "esword4linux.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        if size == 512:
            shutil.copyfile(SOURCE, target)
            continue
        scaled = source.scaled(
            size, size, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        if not scaled.save(str(target), "PNG"):
            print(f"Could not write {target}", file=sys.stderr)
            return 1
    print(f"Icons generated from {SOURCE.name}: {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
