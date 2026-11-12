#!/usr/bin/env python3
"""Genera el icono por defecto y los PNG de hicolor.

El icono elegido es el mismo que usa el diálogo «Acerca de»
(`linuxesword-about.png`): el pingüino con la espada y el libro. El WebP
original se conserva por si se quiere volver al icono anterior.
"""

from __future__ import annotations

import os
import sys
from collections import deque
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QImage

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "src" / "linuxesword" / "assets" / "linuxesword-about.png"
CLEAN = ROOT / "src" / "linuxesword" / "assets" / "linuxesword.png"
SIZES = (16, 22, 24, 32, 48, 64, 128, 256, 512)


def _is_background(color) -> bool:
    """Claro y neutro: damero, tarjeta gris y sombra suave."""
    r, g, b = color.red(), color.green(), color.blue()
    return (max(r, g, b) - min(r, g, b) <= 34
            and min(r, g, b) >= 120)


def clean_icon(source: QImage) -> QImage:
    """Quita un fondo claro/neutro si existe y recorta al contenido.

    El icono de «Acerca de» ya trae transparencia; el flood-fill solo actúa
    sobre píxeles opacos claros conectados con los bordes, así que las zonas
    blancas interiores (vientre, hoja de la espada) se conservan.
    """
    image = source.convertToFormat(QImage.Format.Format_ARGB32)
    w, h = image.width(), image.height()
    visited = bytearray(w * h)
    queue: deque[tuple[int, int]] = deque()

    def push(x: int, y: int) -> None:
        idx = y * w + x
        if visited[idx]:
            return
        if not _is_background(image.pixelColor(x, y)):
            return
        visited[idx] = 1
        queue.append((x, y))

    for x in range(w):
        push(x, 0)
        push(x, h - 1)
    for y in range(h):
        push(0, y)
        push(w - 1, y)
    while queue:
        x, y = queue.popleft()
        if x > 0:
            push(x - 1, y)
        if x + 1 < w:
            push(x + 1, y)
        if y > 0:
            push(x, y - 1)
        if y + 1 < h:
            push(x, y + 1)

    for y in range(h):
        row = y * w
        for x in range(w):
            if visited[row + x]:
                image.setPixelColor(x, y, Qt.GlobalColor.transparent)

    # Recortar al contenido y dejar un pequeño margen cuadrado.
    left, top, right, bottom = w, h, -1, -1
    for y in range(h):
        row = y * w
        for x in range(w):
            if visited[row + x]:
                continue
            if image.pixelColor(x, y).alpha() == 0:
                continue
            left = min(left, x); right = max(right, x)
            top = min(top, y); bottom = max(bottom, y)
    if right < left or bottom < top:
        return image
    side = max(right - left + 1, bottom - top + 1)
    side = int(side * 1.08)
    canvas = QImage(side, side, QImage.Format.Format_ARGB32)
    canvas.fill(Qt.GlobalColor.transparent)
    cropped = image.copy(left, top, right - left + 1, bottom - top + 1)
    dx = (side - cropped.width()) // 2
    dy = (side - cropped.height()) // 2
    from PySide6.QtGui import QPainter
    painter = QPainter(canvas)
    painter.drawImage(dx, dy, cropped)
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
    cleaned = clean_icon(source)
    if not cleaned.save(str(CLEAN), "PNG"):
        print(f"No se pudo escribir {CLEAN}", file=sys.stderr)
        return 1
    for size in SIZES:
        target = dest / f"{size}x{size}" / "apps"
        target.mkdir(parents=True, exist_ok=True)
        scaled = cleaned.scaled(
            size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        out = target / "linuxesword.png"
        if not scaled.save(str(out), "PNG"):
            print(f"No se pudo escribir {out}", file=sys.stderr)
            return 1
    print(f"Iconos generados desde {SOURCE.name}: {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
