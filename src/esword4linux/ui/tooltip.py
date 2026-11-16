"""Custom help bubble (replaces the native Qt tooltip).

The bubble is a widget that **paints a `QTextDocument` directly**. It does not
use `QTextBrowser` or an intermediate viewport: thus width and height are
computed on the same document that is drawn and there is no padding inherited
from the QSS that clips the last line.

* own dark background, accent left border and rounded corners;
* generous max width (600 px) with line wrapping;
* one source line = one document block (respects RTL/Hebrew);
* extra bottom margin for descenders and rounded corners.
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
    """Only the bare Hebrew word (not definitions that mention it)."""
    letters = [char for char in line if char.isalpha()]
    return bool(letters) and all(_HEBREW.match(char) for char in letters)


_TAG_LEFTOVER = re.compile(r"</?[A-Za-z][^>]*>")


def normalize_bubble_body(body: str) -> str:
    """Canonical body: one line per verse, without empty lines or tags."""
    body = (body or "").replace("\r\n", "\n").replace("\r", "\n")
    body = body.replace("\xa0", " ")
    body = _TAG_LEFTOVER.sub(" ", body)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in body.split("\n")]
    return "\n".join(line for line in lines if line)


def to_bubble_html(text: str) -> str:
    """Bubble text (header\\nbody) → card HTML.

    Each body line is an independent block. This matters for lexicon entries
    that start with a Hebrew word: the word keeps its RTL direction and does
    not drag the rest of the definition with it.
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

    # ── presentation ─────────────────────────────────────────────────────
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
        # The extra bottom margin is the final "carriage return": it ensures
        # the descenders of the last line and the rounding are not clipped.
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

    # ── geometry ─────────────────────────────────────────────────────────
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
