"""QTextBrowser con burbujas propias para anclas internas.

El `title` de un `<a>` lo mostraría Qt con su tooltip nativo (mismo fondo que
los paneles y sin límite de ancho). Aquí se **extrae** el `title` a un mapa
interno, se quita del HTML y se muestra con `TipBubble`, que sí tiene ancho
máximo y color propio.

Las anclas sin texto precalculado (los números Strong) se resuelven al pasar
el ratón, con 150 ms de retardo y caché.
"""

from __future__ import annotations

import html as _html
import re
import weakref

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QTextBrowser

from .tooltip import TipBubble

RESOLVABLE = ("strong:", "ref:", "note:", "#")
HOVER_MS = 150

_ANCHOR_RE = re.compile(r"(<a\b[^>]*>)", re.I)
_HREF_RE = re.compile(r'href="([^"]*)"', re.I)
_TITLE_RE = re.compile(r"""\s+title\s*=\s*(["\'])(.*?)\1""", re.I | re.S)


class RichBrowser(QTextBrowser):
    _instances: weakref.WeakSet = weakref.WeakSet()

    def __init__(self, resolver=None, parent=None):
        super().__init__(parent)
        type(self)._instances.add(self)
        self._resolver = resolver
        self._cache: dict[str, str] = {}
        self._titles: dict[str, str] = {}
        self._hover_href = ""
        self._hover_pos = QPoint()
        self._bubble = TipBubble()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(HOVER_MS)
        self._timer.timeout.connect(self._show_tooltip)
        self.setMouseTracking(True)
        # Biblia de referencia de este visor (workspace). Si se establece,
        # se pasa al resolvedor para resolver citas con la traducción propia
        # de este espacio de trabajo en lugar de la global.
        self.bible_rel: str | None = None

    # ── HTML ─────────────────────────────────────────────────────────────
    def setHtml(self, html: str) -> None:  # noqa: N802
        if not html:
            super().setHtml(html)
            return
        super().setHtml(self._harvest_titles(html))

    def _harvest_titles(self, html: str) -> str:
        """Extrae `title=` de cada `<a>` al mapa interno y lo quita del HTML."""
        self._titles.clear()

        def fix(match: re.Match) -> str:
            tag = match.group(1)
            href = _HREF_RE.search(tag)
            title = _TITLE_RE.search(tag)
            if title:
                if href:
                    key = _html.unescape(href.group(1))
                    self._titles.setdefault(key, _html.unescape(title.group(2)))
                # Se quita siempre: Qt no debe mostrar su tooltip nativo.
                return _TITLE_RE.sub("", tag)
            return tag

        return _ANCHOR_RE.sub(fix, html)

    # ── introspección ────────────────────────────────────────────────────
    def anchor_info(self, pos: QPoint) -> tuple[str, str]:
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

    def title_for(self, href: str) -> str:
        return self._titles.get(href, "")

    # ── eventos ──────────────────────────────────────────────────────────
    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        super().mouseMoveEvent(event)
        pos = event.position().toPoint()
        href, _title = self.anchor_info(pos)
        self._hover_pos = event.globalPosition().toPoint()
        if href != self._hover_href:
            self._hover_href = href
            self._timer.stop()
            self._bubble.hide()
            if href and href.startswith(RESOLVABLE):
                self._timer.start()

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._timer.stop()
        self._hover_href = ""
        self._bubble.hide()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self._timer.stop()
        self._bubble.hide()
        super().mousePressEvent(event)

    def wheelEvent(self, event) -> None:  # noqa: N802
        self._bubble.hide()
        super().wheelEvent(event)

    # ── resolución ───────────────────────────────────────────────────────
    def _show_tooltip(self) -> None:
        href = self._hover_href
        if not href:
            return
        # Clave de caché que incluye la biblia de referencia de este visor,
        # así dos workspaces con traducciones distintas no se pisarán.
        cache_key = f"{self.bible_rel or ''}::{href}" if self.bible_rel else href
        text = self._titles.get(href) or self._cache.get(cache_key)
        if not text:
            if self._resolver is None:
                return
            try:
                text = self._resolver(href, self.bible_rel) or ""
            except TypeError:
                # Resolvedor antiguo que no acepta rel_path.
                text = self._resolver(href) or ""
            except Exception:
                text = ""
            self._cache[cache_key] = text
        if text:
            self._bubble.show_html(self._hover_pos, text)

    def clear_cache(self) -> None:
        self._cache.clear()
        self._bubble.hide()

    @classmethod
    def clear_all_caches(cls) -> None:
        """Invalida burbujas resueltas en todos los visores abiertos."""
        for browser in list(cls._instances):
            browser.clear_cache()
