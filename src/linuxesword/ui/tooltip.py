"""Burbuja de ayuda propia (sustituye al tooltip nativo de Qt).

El tooltip nativo hereda la hoja de estilo de la app (mismo fondo que los
paneles) y no limita el ancho. Esta burbuja es una tarjeta independiente:

* fondo oscuro propio, borde izquierdo de acento y esquinas redondeadas;
* **ancho máximo** con ajuste de línea;
* cabecera en color de acento y cuerpo en claro;
* se coloca junto al cursor y se voltea si no cabe en pantalla.
"""

from __future__ import annotations

import html as _html

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QGuiApplication, QTextDocument
from PySide6.QtWidgets import QFrame, QTextBrowser, QVBoxLayout, QWidget

MAX_WIDTH = 380
MIN_WIDTH = 190
PAD_H = 30
PAD_V = 20

_BG = "#23262e"
_BORDER = "#3d4250"
_ACCENT = "#d9a066"
_TEXT = "#e9e4da"

_STYLE = f"""
#tipFrame {{
    background: {_BG};
    border: 1px solid {_BORDER};
    border-left: 3px solid {_ACCENT};
    border-radius: 9px;
}}
QTextBrowser {{
    background: transparent;
    border: 0;
    color: {_TEXT};
    font-size: 12px;
}}
"""

_DOC_CSS = f"""
body {{ color: {_TEXT}; }}
.hdr {{ color: {_ACCENT}; font-weight: 700; margin-bottom: 3px; }}
b {{ color: {_ACCENT}; }}
"""


def to_bubble_html(text: str) -> str:
    """Texto de la burbuja (cabecera\\ncuerpo) → HTML de la tarjeta."""
    if not text:
        return ""
    head, _, body = text.partition("\n")
    parts = [f'<div class="hdr">{_html.escape(head)}</div>']
    body = body.strip()
    if body:
        parts.append(f"<div>{_html.escape(body).replace(chr(10), '<br>')}</div>")
    return "".join(parts)


class TipBubble(QWidget):
    def __init__(self):
        super().__init__(None, Qt.ToolTip | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet(_STYLE)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.frame = QFrame()
        self.frame.setObjectName("tipFrame")
        inner = QVBoxLayout(self.frame)
        inner.setContentsMargins(12, 9, 12, 9)
        self.browser = QTextBrowser()
        self.browser.setOpenLinks(False)
        self.browser.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.browser.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.browser.setFrameShape(QFrame.NoFrame)
        self.browser.document().setDefaultStyleSheet(_DOC_CSS)
        inner.addWidget(self.browser)
        outer.addWidget(self.frame)

    # ── presentación ─────────────────────────────────────────────────────
    def show_html(self, global_pos: QPoint, text: str, max_width: int = MAX_WIDTH) -> None:
        html = to_bubble_html(text)
        if not html:
            self.hide()
            return
        width = self._measure_width(html, max_width)
        inner_w = max(120, width - PAD_H)
        self.browser.setFixedWidth(inner_w)
        self.browser.setHtml(html)
        doc = self.browser.document()
        doc.setDocumentMargin(0)
        doc.setTextWidth(inner_w - 4)
        body_h = max(16, int(doc.size().height()))
        self.browser.setFixedHeight(body_h + 2)
        # frame: layout 12+12 / 9+9  +  borde 3+1 / 1+1
        self.setFixedSize(inner_w + 28, body_h + 20)
        self.move(self._place(global_pos))
        self.show()

    def hide(self) -> None:  # noqa: A003
        if self.isVisible():
            super().hide()

    # ── geometría ────────────────────────────────────────────────────────
    @staticmethod
    def _measure_width(html: str, max_width: int) -> int:
        doc = QTextDocument()
        doc.setDefaultStyleSheet(_DOC_CSS)
        doc.setHtml(html)
        ideal = 0
        try:
            ideal = int(doc.idealWidth())
        except AttributeError:
            ideal = int(doc.size().width()) if hasattr(doc, "size") else 0
        return max(MIN_WIDTH, min(max_width, ideal + PAD_H + 6))

    def _place(self, cursor: QPoint) -> QPoint:
        self.adjustSize()
        w, h = self.width(), self.height()
        screen = QGuiApplication.screenAt(cursor) or QGuiApplication.primaryScreen()
        area: QRect = screen.availableGeometry() if screen else QRect(0, 0, 1280, 800)
        x = cursor.x() + 14
        y = cursor.y() + 18
        if x + w > area.right() - 8:
            x = max(area.left() + 8, cursor.x() - w - 14)
        if y + h > area.bottom() - 8:
            y = max(area.top() + 8, cursor.y() - h - 14)
        return QPoint(x, y)
