"""Panel Strong: entrada del léxico abierta al pulsar un número."""

from __future__ import annotations

import html as _html

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QPushButton, QTextBrowser, QVBoxLayout, QWidget,
)

from ..core.context import AppContext
from ..core.text import to_plain
from ..i18n import tr
from .theme import document_css, palette


class StrongPane(QWidget):
    """Muestra la entrada Strong del número seleccionado."""

    open_module = Signal(int, str)

    def __init__(self, ctx: AppContext, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.settings = ctx.settings
        self._code = ""
        self.setMinimumHeight(120)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        head = QWidget()
        row = QHBoxLayout(head)
        row.setContentsMargins(12, 5, 10, 5)
        row.setSpacing(8)

        title = QLabel(tr("strong.title"))
        title.setObjectName("sectionTitle")
        row.addWidget(title)

        self.badge = QLabel("")
        self.badge.setObjectName("strongBadge")
        row.addWidget(self.badge)

        row.addStretch(1)

        self.lexicon = QComboBox()
        self.lexicon.setMinimumWidth(240)
        self.lexicon.currentIndexChanged.connect(lambda _=0: self._rerender())
        row.addWidget(self.lexicon)

        self.btn_open = QPushButton(tr("common.open"))
        self.btn_open.clicked.connect(self._open_full)
        row.addWidget(self.btn_open)

        self.btn_hide = QPushButton("✕")
        self.btn_hide.setFixedWidth(30)
        self.btn_hide.clicked.connect(self._hide)
        row.addWidget(self.btn_hide)

        layout.addWidget(head)

        self.browser = QTextBrowser()
        self.browser.setOpenLinks(False)
        self.browser.setOpenExternalLinks(False)
        self.browser.anchorClicked.connect(self._on_anchor)
        self.browser.document().setDefaultStyleSheet(
            document_css(self.settings.theme, self.settings.font_size, self.settings.font_family)
        )
        layout.addWidget(self.browser, 1)

    # ── API ──────────────────────────────────────────────────────────────
    def show_code(self, code: str) -> None:
        self._code = (code or "").upper()
        self._fill_lexicons()
        self._rerender()

    @property
    def code(self) -> str:
        return self._code

    def reload_theme(self) -> None:
        self.browser.document().setDefaultStyleSheet(
            document_css(self.settings.theme, self.settings.font_size, self.settings.font_family)
        )
        self._rerender()

    # ── interno ──────────────────────────────────────────────────────────
    def _fill_lexicons(self) -> None:
        if self.lexicon.count():
            return
        row = self.ctx.strong.module()
        self.lexicon.blockSignals(True)
        for mod in self.ctx.catalog.modules(kind="lexicon"):
            if row and mod["id"] == row["id"]:
                self.lexicon.addItem(mod["title"][:70], mod["rel_path"])
        if self.lexicon.count() == 0 and row:
            self.lexicon.addItem(row["title"][:70], row["rel_path"])
        self.lexicon.blockSignals(False)

    def _rerender(self) -> None:
        self.browser.document().setDefaultStyleSheet(
            document_css(self.settings.theme, self.settings.font_size, self.settings.font_family)
        )
        if not self._code:
            self.browser.setHtml(f'<p class="muted">{tr("strong.hint")}</p>')
            return
        title, body = self.ctx.strong.entry(self._code)
        if not body:
            self.browser.setHtml(
                f'<p class="muted">{tr("strong.not_found", code=_html.escape(self._code))}</p>'
            )
            return
        pal = palette(self.settings.theme)
        self.badge.setText(self._code)
        self.badge.setStyleSheet(
            f"color:{pal.accent_text}; background:{pal.accent}; border-radius:6px;"
            f" padding:1px 8px; font-weight:700;"
        )
        self.browser.setHtml(
            f'<div class="entry-title">{_html.escape(title)}</div>'
            f'<div style="color:{pal.muted}; font-size:{max(9, self.settings.font_size-4)}px;'
            f' margin-bottom:8px;">{_html.escape(self.ctx.strong.label())}</div>'
            f'<div class="strong-body">{_html.escape(body).replace(chr(10), "<br>")}</div>'
        )
        self.browser.verticalScrollBar().setValue(0)

    def _open_full(self) -> None:
        row = self.ctx.strong.module()
        if row is not None and self._code:
            self.open_module.emit(row["id"], self._code)

    def _hide(self) -> None:
        parent = self.parent()
        while parent is not None and not hasattr(parent, "_on_strong_closed"):
            parent = parent.parent()
        if parent is not None:
            parent._on_strong_closed()

    def _on_anchor(self, url) -> None:
        if url.scheme() == "ref":
            pass  # las entradas Strong no navegan; se deja para futuro
