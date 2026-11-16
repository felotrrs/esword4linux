#!/usr/bin/env python3
"""Genera el icono oficial y los PNG de hicolor desde `linuxesword3.jpeg`.

El JPEG elegido trae un damero de transparencia pintado y una tarjeta
redondeada con el pingüino, la espada y el libro. El damero no debe acabar en
el icono, así que se recorta la tarjeta por geometría: un cuadrado centrado
(64,3 % del lienzo) con esquinas redondeadas. El resultado se guarda con
transparencia real en `linuxesword.png`, que es el icono que usan la ventana,
el lanzador y hicolor.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (
    QGuiApplication, QImage, QPainter, QPainterPath,
)

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "src" / "linuxesword" / "assets" / "linuxesword3.jpeg"
CLEAN = ROOT / "src" / "linuxesword" / "assets" / "linuxesword.png"
SIZES = (16, 22, 24, 32, 48, 64, 128, 256, 512)

# La tarjeta del JPEG ocupa de 17,87 % a 82,18 % en X y de 17,68 % a 82,08 %
# en Y (medido sobre el original de 2048×2048). Se recorta un cuadrado
# centrado y se encoge un 0,5 % para no incluir la sombra ni el borde del JPEG.
CARD_SIDE = 0.6431
CARD_INSET = 0.005
CORNER_RADIUS = 0.20


def extract_card_icon(source: QImage) -> QImage:
    """Recorta la tarjeta redondeada y deja transparente el damero exterior."""
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
    args = list(sys.argv[1:] if argv is None else argv)
    dest = Path(args[0]).expanduser() if args else Path.home() / ".local/share/icons/hicolor"
    app = QGuiApplication.instance() or QGuiApplication([])  # noqa: F841
    source = QImage(str(SOURCE))
    if source.isNull():
        print(f"No se pudo leer {SOURCE}", file=sys.stderr)
        return 1
    icon = extract_card_icon(source).scaled(
        512, 512, Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    if not icon.save(str(CLEAN), "PNG"):
        print(f"No se pudo escribir {CLEAN}", file=sys.stderr)
        return 1
    for size in SIZES:
        target = dest / f"{size}x{size}" / "apps"
        target.mkdir(parents=True, exist_ok=True)
        scaled = icon.scaled(
            size, size, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        out = target / "linuxesword.png"
        if not scaled.save(str(out), "PNG"):
            print(f"No se pudo escribir {out}", file=sys.stderr)
            return 1
    print(f"Iconos generados desde {SOURCE.name}: {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
