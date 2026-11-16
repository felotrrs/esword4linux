"""Checkbox style with a hand-drawn check mark.

The style sheet only colored the indicator. This `QProxyStyle` draws the box
and, when checked, a crisp check with the accent text color. It is installed
before the style sheet so the latter does not replace the indicator.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QProxyStyle, QStyle

from .theme import palette

_ACTIVE: "CheckMarkStyle | None" = None


class CheckMarkStyle(QProxyStyle):
    def __init__(self, base=None, theme: str = "light"):
        super().__init__(base)
        self._theme = theme

    def set_theme(self, theme: str) -> None:
        self._theme = theme

    def drawPrimitive(self, element, option, painter, widget=None):  # noqa: N802
        if element != QStyle.PrimitiveElement.PE_IndicatorCheckBox:
            return super().drawPrimitive(element, option, painter, widget)

        colors = palette(self._theme)
        enabled = bool(option.state & QStyle.StateFlag.State_Enabled)
        checked = bool(option.state & QStyle.StateFlag.State_On)
        partial = bool(option.state & QStyle.StateFlag.State_NoChange)
        hover = bool(option.state & QStyle.StateFlag.State_MouseOver)

        box = option.rect.adjusted(1, 1, -1, -1)
        fill = QColor(colors.panel_alt)
        border = QColor(colors.border)
        mark = QColor(colors.accent_text)
        if checked or partial:
            fill = QColor(colors.accent)
            border = QColor(colors.accent)
        elif hover:
            border = QColor(colors.accent)
        if not enabled:
            fill = QColor(colors.panel)
            border = QColor(colors.border)
            mark = QColor(colors.muted)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setBrush(fill)
        painter.setPen(QPen(border, 1))
        painter.drawRoundedRect(box, 3, 3)

        width = max(1.6, box.width() * 0.13)
        pen = QPen(mark, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        if checked:
            left = box.x() + box.width() * 0.22
            mid_x = box.x() + box.width() * 0.43
            mid_y = box.y() + box.height() * 0.72
            right = box.x() + box.width() * 0.79
            top = box.y() + box.height() * 0.29
            painter.drawLine(QPointF(left, box.y() + box.height() * 0.52),
                             QPointF(mid_x, mid_y))
            painter.drawLine(QPointF(mid_x, mid_y), QPointF(right, top))
        elif partial:
            y = box.center().y()
            painter.drawLine(QPointF(box.x() + box.width() * 0.26, y),
                             QPointF(box.x() + box.width() * 0.74, y))
        painter.restore()


def install(app, theme: str) -> CheckMarkStyle:
    """Install the style at application level (before `setStyleSheet`).

    It is built without an explicit base style: `QProxyStyle` uses the default
    style and the application becomes its owner. Wrapping `app.style()` would
    make both try to release the same object.
    """
    global _ACTIVE
    _ACTIVE = CheckMarkStyle(None, theme)
    app.setStyle(_ACTIVE)
    return _ACTIVE


def set_theme(theme: str) -> None:
    if _ACTIVE is not None:
        _ACTIVE.set_theme(theme)
