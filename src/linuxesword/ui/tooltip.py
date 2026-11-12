"""Burbuja de ayuda propia (sustituye al tooltip nativo de Qt).

La burbuja es un widget que **pinta directamente un `QTextDocument`**. No usa
`QTextBrowser` ni un viewport intermedio: así el ancho y el alto se calculan
sobre el mismo documento que se dibuja y no hay padding heredado del QSS que
recorte la última línea.

* fondo oscuro propio, borde izquierdo de acento y esquinas redondeadas;
* ancho máximo amplio (600 px) con ajuste de línea;
* una línea de origen = un bloque del documento (respeta RTL/hebreo);
* margen inferior de seguridad para descendentes y redondeos.
"""

from __future__ import annotations

import html as _html
import math
import re

from PySide6.QtCore import QPoint, QRect, QRectF, Qt
from PySide6.QtGui import (
    QColor, QFont, QGuiApplication, QPainter, QPen, QTextDocument,
)
from PySide6.QtWidgets import QWidget

MAX_WIDTH = 600
MIN_WIDTH = 220
PAD_H = 14
PAD_V = 10
BOTTOM_EXTRA = 5

_BG = "#23262e"
_BORDER = "#3d4250"
_ACCENT = "#d9a066"
_TEXT = "#e9e4da"

_DOC_CSS = f"""
.hdr {{ color: {_ACCENT}; font-weight: 700; margin: 0 0 4px 0; }}
.ln {{ color: {_TEXT}; margin: 0; }}
.heb {{ color: {_TEXT}; font-size: 14px; }}
"""

_HEBREW = re.compile(r"[\u0590-\u05FF]")


def _is_hebrew_headword(line: str) -> bool:
    """Solo la palabra hebrea suelta (no definiciones que la mencionan)."""
    letters = [char for char in line if char.isalpha()]
    return bool(letters) and all(_HEBREW.match(char) for char in letters)


_TAG_LEFTOVER = re.compile(r"</?[A-Za-z][^>]*>")


def normalize_bubble_body(body: str) -> str:
    """Cuerpo canónico: una línea por versículo, sin líneas vacías ni tags."""
    body = (body or "").replace("\r\n", "\n").replace("\r", "\n")
    body = body.replace("\xa0", " ")
    body = _TAG_LEFTOVER.sub(" ", body)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in body.split("\n")]
    return "\n".join(line for line in lines if line)


def to_bubble_html(text: str) -> str:
    """Texto de la burbuja (cabecera\\ncuerpo) → HTML de la tarjeta.

    Cada línea del cuerpo es un bloque independiente. Esto es importante para
    las entradas de léxico que empiezan por una palabra hebrea: así la palabra
    conserva su dirección RTL y no arrastra al resto de la definición.
    """
    if not text:
        return ""
    head, _, body = text.partition("\n")
    parts = [f'<div class="hdr">{_html.escape(head.strip())}</div>']
    body = normalize_bubble_body(body)
    for line in body.split("\n"):
        if line:
            cls = "ln heb" if _is_hebrew_headword(line) else "ln"
            parts.append(f'<div class="{cls}">{_html.escape(line)}</div>')
    return "".join(parts)


class TipBubble(QWidget):
    def __init__(self):
        super().__init__(None, Qt.ToolTip | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TranslucentBackground)

        font = QFont()
        font.setFamilies(["Noto Sans", "Noto Sans Hebrew", "DejaVu Sans"])
        font.setPixelSize(12)

        self._doc = QTextDocument(self)
        self._doc.setDocumentMargin(0)
        self._doc.setDefaultFont(font)
        self._doc.setDefaultStyleSheet(_DOC_CSS)
        self._content_w = 0
        self._content_h = 0

    # ── presentación ─────────────────────────────────────────────────────
    def document(self) -> QTextDocument:
        return self._doc

    @property
    def content_height(self) -> int:
        return self._content_h

    def show_html(self, global_pos: QPoint, text: str, max_width: int = MAX_WIDTH) -> None:
        html = to_bubble_html(text)
        if not html:
            self.hide()
            return
        screen = QGuiApplication.screenAt(global_pos) or QGuiApplication.primaryScreen()
        area: QRect = screen.availableGeometry() if screen else QRect(0, 0, 1280, 800)
        max_inner = min(max_width, area.width() - 32) - 2 * PAD_H
        width = self._measure_width(html, max(120, max_inner))
        self._set_content(html, width)
        self.move(self._place(global_pos))
        self.show()

    def _set_content(self, html: str, content_w: int) -> None:
        self._doc.setHtml(html)
        self._doc.setTextWidth(content_w)
        h = max(16, math.ceil(self._doc.documentLayout().documentSize().height()))
        self._content_w = content_w
        self._content_h = h
        # El margen inferior extra es el "retorno de carro" final: garantiza
        # que los descendentes de la última línea y el redondeo no se corten.
        self.setFixedSize(
            content_w + 2 * PAD_H,
            h + 2 * PAD_V + BOTTOM_EXTRA,
        )

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        card = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        painter.setBrush(QColor(_BG))
        painter.setPen(QPen(QColor(_BORDER), 1))
        painter.drawRoundedRect(card, 9, 9)
        painter.setPen(QPen(QColor(_ACCENT), 3))
        painter.drawLine(2, 12, 2, self.height() - 12)
        painter.translate(PAD_H, PAD_V)
        self._doc.drawContents(painter)
        painter.end()

    def hide(self) -> None:  # noqa: A003
        if self.isVisible():
            super().hide()

    # ── geometría ────────────────────────────────────────────────────────
    @staticmethod
    def _measure_width(html: str, max_width: int) -> int:
        doc = QTextDocument()
        font = QFont()
        font.setFamilies(["Noto Sans", "Noto Sans Hebrew", "DejaVu Sans"])
        font.setPixelSize(12)
        doc.setDefaultFont(font)
        doc.setDefaultStyleSheet(_DOC_CSS)
        doc.setHtml(html)
        ideal = int(math.ceil(doc.idealWidth())) + 2
        return max(MIN_WIDTH - 2 * PAD_H, min(max_width, ideal))

    def _place(self, cursor: QPoint) -> QPoint:
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
