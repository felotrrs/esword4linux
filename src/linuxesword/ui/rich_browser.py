"""QTextBrowser con burbujas perezosas para anclas internas.

Qt ya muestra el atributo `title` de un `<a>` como tooltip nativo. Cuando el
ancla no trae `title` (porque resolverlo al pintar sería caro), este widget lo
resuelve al pasar el ratón —con 180 ms de retardo y caché— y lo muestra con
`QToolTip`, igual que hace el admin de `bible`.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QTextBrowser, QToolTip

RESOLVABLE = ("strong:", "ref:", "note:")
HOVER_MS = 180


class RichBrowser(QTextBrowser):
    def __init__(self, resolver=None, parent=None):
        super().__init__(parent)
        self._resolver = resolver
        self._cache: dict[str, str] = {}
        self._hover_href = ""
        self._hover_pos = QPoint()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(HOVER_MS)
        self._timer.timeout.connect(self._show_tooltip)
        self.setMouseTracking(True)

    # ── introspección ────────────────────────────────────────────────────
    def anchor_info(self, pos: QPoint) -> tuple[str, str]:
        """(href, title) del carácter bajo el punto."""
        cursor = self.cursorForPosition(pos)
        fmt = cursor.charFormat()
        href = fmt.anchorHref()
        if not href:
            probe = QTextCursor(cursor)
            probe.movePosition(QTextCursor.Right)
            href = probe.charFormat().anchorHref()
            if href:
                fmt = probe.charFormat()
        return href or "", fmt.toolTip() or ""

    # ── eventos ──────────────────────────────────────────────────────────
    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        super().mouseMoveEvent(event)
        pos = event.position().toPoint()
        href, title = self.anchor_info(pos)
        if href != self._hover_href:
            self._hover_href = href
            self._timer.stop()
            QToolTip.hideText()
            if href and not title and href.startswith(RESOLVABLE) and self._resolver:
                self._hover_pos = event.globalPosition().toPoint()
                self._timer.start()
        elif href:
            self._hover_pos = event.globalPosition().toPoint()

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._timer.stop()
        self._hover_href = ""
        QToolTip.hideText()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self._timer.stop()
        QToolTip.hideText()
        super().mousePressEvent(event)

    # ── resolución ───────────────────────────────────────────────────────
    def _show_tooltip(self) -> None:
        href = self._hover_href
        if not href or self._resolver is None:
            return
        text = self._cache.get(href)
        if text is None:
            try:
                text = self._resolver(href) or ""
            except Exception:
                text = ""
            self._cache[href] = text
        if text:
            QToolTip.showText(self._hover_pos, text, self)

    def clear_cache(self) -> None:
        self._cache.clear()
