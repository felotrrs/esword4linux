#!/usr/bin/env python3
"""Generate the application and hicolor icons from the official logo.

``packaging/icons/source/esword4linux-logo.png`` is the canonical artwork:
the penguin reading the book with the sword and the e-Sword wordmark. It is
used unchanged for:

* ``src/esword4linux/assets/esword4linux.png`` — window, launcher and About
* ``src/esword4linux/assets/esword4linux-about.png`` — explicit About asset
* ``packaging/icons/apps/`` — installer/source copies
* every hicolor size generated below

The previous card-cropping code that used ``esword4linux3.jpeg`` is gone; that
JPEG remains only as an archived source asset under ``packaging/icons/source``.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QImage

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "packaging" / "icons" / "source" / "esword4linux-logo.png"
APP_ASSET = ROOT / "src" / "esword4linux" / "assets" / "esword4linux.png"
ABOUT_ASSET = ROOT / "src" / "esword4linux" / "assets" / "esword4linux-about.png"
PACKAGING_APPS = ROOT / "packaging" / "icons" / "apps"
SIZES = (16, 22, 24, 32, 48, 64, 128, 256, 512)


def save_png(image: QImage, path: Path) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    return image.save(str(path), "PNG")


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

    base = source.scaled(
        512, 512, Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    for target in (
        APP_ASSET,
        ABOUT_ASSET,
        PACKAGING_APPS / "esword4linux.png",
        PACKAGING_APPS / "esword4linux-about.png",
    ):
        if not save_png(base, target):
            print(f"Could not write {target}", file=sys.stderr)
            return 1

    for size in SIZES:
        scaled = source.scaled(
            size, size, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        target = dest / f"{size}x{size}" / "apps" / "esword4linux.png"
        if not save_png(scaled, target):
            print(f"Could not write {target}", file=sys.stderr)
            return 1

    print(f"Icons generated from {SOURCE.name}: {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
