"""Dark theme contrast and branding assets."""

from __future__ import annotations

import os

import pytest


def _luminance(color: str) -> float:
    color = color.lstrip("#")
    channels = [int(color[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    channels = [
        c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
        for c in channels
    ]
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _contrast(a: str, b: str) -> float:
    high, low = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def test_dark_palette_has_visible_steps():
    from esword4linux.ui.theme import DARK

    assert _contrast(DARK.bg, DARK.panel) >= 1.10
    assert _contrast(DARK.panel, DARK.panel_alt) >= 1.15
    assert _contrast(DARK.border, DARK.panel) >= 1.80
    assert _contrast(DARK.text, DARK.bg) >= 10.0


def test_new_icon_is_readable():
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QApplication

    from esword4linux.config import asset

    app = QApplication.instance() or QApplication([])  # noqa: F841
    image = QImage(str(asset("esword4linux.png")))
    assert not image.isNull()
    assert image.width() == image.height()
    assert image.pixelColor(0, 0).alpha() == 0
    assert image.pixelColor(image.width() // 2, image.height() // 2).alpha() > 0


def test_checkbox_draws_checkmark_when_checked():
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QRect, Qt
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtWidgets import QApplication, QStyle, QStyleOptionButton

    from esword4linux.ui.checkstyle import CheckMarkStyle
    from esword4linux.ui.theme import stylesheet

    app = QApplication.instance() or QApplication([])
    # The QSS must no longer override the indicator drawn by the proxy style.
    assert "QCheckBox::indicator" not in stylesheet("dark", 15)

    style = CheckMarkStyle(None, "dark")
    option = QStyleOptionButton()
    option.rect = QRect(0, 0, 15, 15)
    option.state = (
        QStyle.StateFlag.State_Enabled | QStyle.StateFlag.State_On
    )
    image = QImage(16, 16, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    style.drawPrimitive(
        QStyle.PrimitiveElement.PE_IndicatorCheckBox, option, painter
    )
    painter.end()

    interior = [
        image.pixelColor(x, y)
        for y in range(4, 12)
        for x in range(4, 12)
        if image.pixelColor(x, y).alpha() > 0
    ]
    # The box ends up filled with the accent and the check is drawn dark on top.
    assert any(c.lightness() > 150 for c in interior)
    assert any(c.lightness() < 80 for c in interior)


def test_document_css_separates_reading_and_running_text():
    from types import SimpleNamespace

    from esword4linux.ui.theme import document_css_for, ui_stylesheet

    settings = SimpleNamespace(
        theme="light",
        ui_font_family="DejaVu Sans",
        ui_font_size=12,
        font_family="Noto Serif",
        font_size=18,
        content_font_family="DejaVu Sans Mono",
        content_font_size=11,
    )
    css = document_css_for(settings)
    # Scripture keeps its own family and size.
    assert 'font-family: "Noto Serif"' in css
    assert "font-size: 18px" in css
    # Running text uses its own.
    assert 'font-family: "DejaVu Sans Mono"' in css
    assert "font-size: 11px" in css
    # The Qt sheet uses the interface typography, not the reading one.
    sheet = ui_stylesheet(settings)
    assert 'font-family: "DejaVu Sans"' in sheet
    assert "font-size: 12px" in sheet
    assert "Noto Serif" not in sheet
