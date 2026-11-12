"""Barra de pestañas coloreada (estilo navegador).

QSS no permite pintar cada pestaña de un color: `QTabBar` no expone
`:nth-child`. Esta subclase pinta a mano el fondo, el texto, el botón de
cierre y el botón **＋** detrás de la última pestaña.

Reglas visuales:

* pestaña seleccionada  → color pleno, texto **en negrita** y con contraste.
* pestaña no seleccionada → tinte pálido del mismo color y texto atenuado.
* el botón de cierre deja margen derecho (no queda pegado al borde).
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QStyle, QStyleOptionTab, QTabBar

CLOSE_W = 16
CLOSE_MARGIN = 10
TAB_H = 30
NEW_TAB_W = 30
MIN_TAB_W = 90
MAX_TAB_W = 260


def blend(fg: str, bg: str, ratio: float) -> QColor:
    """Mezcla `fg` sobre `bg` (ratio 0 = solo bg, 1 = solo fg)."""
    a, b = QColor(fg), QColor(bg)
    r = int(b.red() * ratio + a.red() * (1 - ratio))
    g = int(b.green() * ratio + a.green() * (1 - ratio))
    bl = int(b.blue() * ratio + a.blue() * (1 - ratio))
    return QColor(r, g, bl)


def _luminance(color: QColor) -> float:
    return 0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()


class ColoredTabBar(QTabBar):
    new_tab_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDrawBase(False)
        self.setExpanding(False)
        self.setMovable(True)
        self.setElideMode(Qt.ElideRight)
        self.setUsesScrollButtons(True)
        self.setMouseTracking(True)
        self._close_rects: dict[int, QRect] = {}
        self._new_rect = QRect()
        self._hover_close = -1
        self._bg_selected = "#fbf9f4"
        self._bg_panel = "#f3efe6"
        self._border = "#d9d2c2"
        self._text = "#26231d"
        self._muted = "#6f685a"
        self._default_color = "#8a8378"

    # ── configuración ────────────────────────────────────────────────────
    def set_palette_colors(self, *, selected_bg: str, panel_bg: str, border: str,
                           text: str, muted: str) -> None:
        self._bg_selected = selected_bg
        self._bg_panel = panel_bg
        self._border = border
        self._text = text
        self._muted = muted
        self.update()

    def set_tab_color(self, index: int, color: str) -> None:
        if 0 <= index < self.count():
            self.setTabData(index, color)
            self.update()

    def tab_color(self, index: int) -> str:
        data = self.tabData(index)
        return data if isinstance(data, str) and data else self._default_color

    # ── geometría ────────────────────────────────────────────────────────
    def tabSizeHint(self, index: int) -> QSize:  # noqa: N802
        base = super().tabSizeHint(index)
        closable = index >= self._first_closable()
        icon = self.tabIcon(index)
        icon_w = 20 if not icon.isNull() else 0
        width = base.width() + (CLOSE_W + CLOSE_MARGIN if closable else 14) + icon_w
        width = max(MIN_TAB_W, min(MAX_TAB_W, width + 18))
        return QSize(width, TAB_H)

    def _first_closable(self) -> int:
        """Índice de la primera pestaña cerrable (la 0 es «Buscar»)."""
        return 1

    def _new_tab_rect(self) -> QRect:
        if self.count() == 0:
            return QRect(6, 4, NEW_TAB_W, TAB_H - 8)
        last = self.tabRect(self.count() - 1)
        return QRect(last.right() + 5, last.top() + 3, NEW_TAB_W - 4, last.height() - 6)

    # ── pintado ──────────────────────────────────────────────────────────
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        self._close_rects.clear()
        selected = self.currentIndex()

        for i in range(self.count()):
            rect = self.tabRect(i)
            if rect.isNull():
                continue
            is_sel = i == selected
            color = QColor(self.tab_color(i))
            if is_sel:
                bg = color
                fg = QColor("#ffffff") if _luminance(color) < 150 else QColor("#1b1a16")
            else:
                bg = blend(color.name(), self._bg_panel, 0.82)
                fg = QColor(self._muted)
            self._paint_tab(painter, rect, i, bg, fg, is_sel)

        self._new_rect = self._new_tab_rect()
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(self._bg_panel))
        painter.drawRoundedRect(self._new_rect, 7, 7)
        painter.setPen(QPen(QColor(self._muted), 1.6))
        r = self._new_rect
        painter.drawLine(r.center().x() - 5, r.center().y(), r.center().x() + 5, r.center().y())
        painter.drawLine(r.center().x(), r.center().y() - 5, r.center().x(), r.center().y() + 5)
        painter.end()

    def _paint_tab(self, painter: QPainter, rect: QRect, index: int,
                   bg: QColor, fg: QColor, is_sel: bool) -> None:
        painter.setPen(Qt.NoPen)
        painter.setBrush(bg)
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, 0), 7, 7)
        if is_sel:
            painter.setBrush(QColor("#ffffff"))
            painter.setOpacity(0.22)
            painter.drawRoundedRect(QRect(rect.left() + 1, rect.top() + 1,
                                          rect.width() - 2, 3), 2, 2)
            painter.setOpacity(1.0)

        font = QFont(self.font())
        font.setBold(is_sel)
        painter.setFont(font)
        painter.setPen(fg)

        icon = self.tabIcon(index)
        left_pad = 12
        if not icon.isNull():
            icon_size = 14
            icon_rect = QRect(rect.left() + 10, rect.center().y() - icon_size // 2, icon_size, icon_size)
            icon.paint(painter, icon_rect)
            left_pad = 10 + icon_size + 6

        closable = index >= self._first_closable()
        right_pad = (CLOSE_W + CLOSE_MARGIN) if closable else 10
        text_rect = rect.adjusted(left_pad, 0, -right_pad, 0)
        elided = painter.fontMetrics().elidedText(
            self.tabText(index), Qt.ElideRight, text_rect.width()
        )
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, elided)

        if closable:
            close = QRect(rect.right() - CLOSE_MARGIN - CLOSE_W + 4,
                          rect.center().y() - CLOSE_W // 2, CLOSE_W, CLOSE_W)
            self._close_rects[index] = close
            hovered = self._hover_close == index
            if hovered:
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(0, 0, 0, 40) if _luminance(bg) > 150
                                 else QColor(255, 255, 255, 60))
                painter.drawEllipse(close.adjusted(1, 1, -1, -1))
            painter.setPen(QPen(fg, 1.4))
            c = close.center()
            painter.drawLine(c.x() - 3, c.y() - 3, c.x() + 3, c.y() + 3)
            painter.drawLine(c.x() - 3, c.y() + 3, c.x() + 3, c.y() - 3)

    # ── interacción ──────────────────────────────────────────────────────
    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        pos = event.position().toPoint()
        hover = -1
        for index, rect in self._close_rects.items():
            if rect.contains(pos):
                hover = index
                break
        if hover != self._hover_close:
            self._hover_close = hover
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover_close = -1
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        pos: QPoint = event.position().toPoint()
        if event.button() == Qt.LeftButton and self._new_rect.contains(pos):
            self.new_tab_requested.emit()
            return
        for index, rect in self._close_rects.items():
            if rect.contains(pos):
                self.tabCloseRequested.emit(index)
                return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        pos = event.position().toPoint()
        if self._new_rect.contains(pos) or self.tabAt(pos) < 0:
            self.new_tab_requested.emit()
            return
        super().mouseDoubleClickEvent(event)

    def refresh_style(self) -> None:
        self.update()
