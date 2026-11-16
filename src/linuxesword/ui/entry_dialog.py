"""Diálogo de entrada completa (evita abrir una pestaña nueva por cada lectura)."""

from __future__ import annotations

import html as _html

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTextBrowser, QVBoxLayout

from ..core.context import AppContext
from ..core.text import to_rich
from ..i18n import tr
from .theme import document_css_for


class EntryDialog(QDialog):
    def __init__(self, ctx: AppContext, module_row: dict, ref: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(module_row.get("title") or tr("common.open"))
        self.resize(880, 640)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        browser = QTextBrowser()
        browser.setOpenLinks(False)
        browser.setOpenExternalLinks(False)
        browser.document().setDefaultStyleSheet(
            document_css_for(ctx.settings)
        )
        layout.addWidget(browser, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

        page = None
        mod = ctx.module(module_row)
        if mod is not None:
            page = mod.page_by_ref(ref)
        if page is None:
            browser.setHtml(f'<p class="muted">{tr("lib.no_selection")}</p>')
            return
        browser.setHtml(
            f'<div class="entry-title">{_html.escape(page.title)}</div>'
            f"{to_rich(page.raw, hint=mod.stem if mod else '', codepages=mod.codepages if mod else None)}"
        )
        browser.setFocus(Qt.OtherFocusReason)
