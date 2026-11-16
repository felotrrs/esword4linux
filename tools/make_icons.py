#!/usr/bin/env python3
"""Generate the app icon and hicolor PNGs from ``esword4linux3.jpeg``.

The chosen JPEG contains a painted transparency checkerboard and a rounded
card with the penguin, sword and book. The checkerboard must not reach the
icon, so the card is cropped geometrically: a centred square (64.3 % of the
canvas) with rounded corners. The result is saved with real transparency as
``esword4linux.png``, used by the window, launcher and hicolor sizes.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (
    QGuiApplication, QImage, QPainter, QPainterPath,
)

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "src" / "esword4linux" / "assets" / "esword4linux3.jpeg"
CLEAN = ROOT / "src" / "esword4linux" / "assets" / "esword4linux.png"
SIZES = (16, 22, 24, 32, 48, 64, 128, 256, 512)

# The card occupies 17.87 %–82.18 % in X and 17.68 %–82.08 % in Y
# (measured on the 2048×2048 original). Crop a centred square and shrink it
# by 0.5 % to avoid the shadow and JPEG border.
CARD_SIDE = 0.6431
CARD_INSET = 0.005
CORNER_RADIUS = 0.20


def extract_card_icon(source: QImage) -> QImage:
    """Crop the rounded card and make the outer checkerboard transparent."""
    image = source.convertToFormat(QImage.Format.Format_ARGB32)
    w, h = image.width(), image.height()
    side = min(w, h) * CARD_SIDE
    side -= max(2.0, min(w, h) * CARD_INSET)
    left = (w - side) / 2
    top = (h - side) / 2

    canvas = QImage(int(round(side)), int(round(side)),
                    QImage.Format.Format_ARGB32)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(
        QRectF(0, 0, canvas.width(), canvas.height()),
        canvas.width() * CORNER_RADIUS,
        canvas.height() * CORNER_RADIUS,
    )
    painter.setClipPath(path)
    painter.drawImage(
        QRectF(0, 0, canvas.width(), canvas.height()),
        image,
        QRectF(left, top, side, side),
    )
    painter.end()
    return canvas


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
    icon = extract_card_icon(source).scaled(
        512, 512, Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    if not icon.save(str(CLEAN), "PNG"):
        print(f"Could not write {CLEAN}", file=sys.stderr)
        return 1
    for size in SIZES:
        target = dest / f"{size}x{size}" / "apps"
        target.mkdir(parents=True, exist_ok=True)
        scaled = icon.scaled(
            size, size, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        out = target / "esword4linux.png"
        if not scaled.save(str(out), "PNG"):
            print(f"Could not write {out}", file=sys.stderr)
            return 1
    print(f"Icons generated from {SOURCE.name}: {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
