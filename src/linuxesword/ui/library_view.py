"""Visor genérico de módulos: diccionarios, léxicos, comentarios, mapas, etc."""

from __future__ import annotations

import html as _html

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QSplitter, QVBoxLayout, QWidget,
)

from ..core.context import AppContext
from ..core.refs import link_references
from ..core.text import to_rich
from ..i18n import tr
from .rich_browser import RichBrowser
from .theme import document_css

MAX_ENTRIES = 3000


class LibraryView(QWidget):
    open_reference = Signal(str)

    def __init__(self, ctx: AppContext, module: dict, initial_ref: str | None = None,
                 parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.settings = ctx.settings
        self.module_row = module
        self.mod = ctx.module(module)
        self.initial_ref = initial_ref
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(180)
        self._filter_timer.timeout.connect(self._load_entries)
        self._build_ui()
        self._load_entries()

    # ── UI ───────────────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        head = QWidget()
        head_row = QHBoxLayout(head)
        head_row.setContentsMargins(12, 8, 12, 8)
        title = QLabel(self.module_row.get("title") or "")
        title.setObjectName("appTitle")
        sub = QLabel(self._subtitle())
        sub.setObjectName("appSubtitle")
        box = QVBoxLayout()
        box.setSpacing(0)
        box.addWidget(title)
        box.addWidget(sub)
        head_row.addLayout(box)
        head_row.addStretch(1)
        layout.addWidget(head)

        split = QSplitter(Qt.Horizontal)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        self.filter = QLineEdit()
        self.filter.setPlaceholderText(tr("lib.filter_placeholder"))
        self.filter.setClearButtonEnabled(True)
        self.filter.textChanged.connect(lambda _=0: self._filter_timer.start())
        left_layout.addWidget(self.filter)

        if self.mod and self.mod.structure in ("dictionary", "lexicon", "reference", "topic"):
            alpha = QWidget()
            alpha_row = QHBoxLayout(alpha)
            alpha_row.setContentsMargins(6, 2, 6, 2)
            alpha_row.setSpacing(0)
            small = alpha.font()
            small.setPointSizeF(8.5)
            for letter in "ABCDEFGHIJKLMNÑOPQRSTUVWXYZ":
                btn = QLabel(f'<a href="{letter}" style="text-decoration:none">{letter}</a>')
                btn.setTextFormat(Qt.RichText)
                btn.setAlignment(Qt.AlignCenter)
                btn.setFixedWidth(12)
                btn.setFont(small)
                btn.setCursor(Qt.PointingHandCursor)
                btn.linkActivated.connect(self._jump_letter)
                alpha_row.addWidget(btn)
            alpha_row.addStretch(1)
            left_layout.addWidget(alpha)

        self.list = QListWidget()
        self.list.setUniformItemSizes(True)
        self.list.currentItemChanged.connect(self._on_select)
        left_layout.addWidget(self.list, 1)

        self.count_label = QLabel("")
        self.count_label.setObjectName("appSubtitle")
        self.count_label.setContentsMargins(10, 4, 10, 4)
        left_layout.addWidget(self.count_label)

        self.detail = RichBrowser(resolver=self.ctx.refs.tooltip)
        self.detail.setOpenLinks(False)
        self.detail.setOpenExternalLinks(False)
        self.detail.anchorClicked.connect(self._on_anchor)
        self.detail.document().setDefaultStyleSheet(
            document_css(self.settings.theme, self.settings.font_size, self.settings.font_family)
        )

        split.addWidget(left)
        split.addWidget(self.detail)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 3)
        split.setSizes([300, 700])
        layout.addWidget(split, 1)

    def _subtitle(self) -> str:
        kind = tr(f"kind.{self.module_row.get('kind', 'unknown')}")
        entries = self.module_row.get("entries") or 0
        extra = " · " + tr("badge.encrypted") if self.module_row.get("encrypted") else ""
        return f"{kind} · {entries} {tr('lib.entries').lower()}{extra}"

    # ── datos ────────────────────────────────────────────────────────────
    def _load_entries(self, prefix: str | None = None, contains: bool = True) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        if self.mod is None:
            self.list.blockSignals(False)
            self.detail.setHtml(f'<p class="muted">{tr("lib.empty")}</p>')
            return
        if prefix is None:
            prefix = self.filter.text().strip()
        entries = self.mod.list_entries(prefix=prefix, limit=MAX_ENTRIES, contains=contains)
        for ref, label in entries:
            item = QListWidgetItem(label or ref)
            item.setData(Qt.UserRole, ref)
            self.list.addItem(item)
        self.list.blockSignals(False)
        total = self.module_row.get("entries") or 0
        self.count_label.setText(f"{len(entries)} / {total}")
        if entries:
            target = 0
            if self.initial_ref:
                for i in range(self.list.count()):
                    if self.list.item(i).data(Qt.UserRole) == self.initial_ref:
                        target = i
                        break
                self.initial_ref = None
            self.list.setCurrentRow(target)
        else:
            self.detail.setHtml(f'<p class="muted">{tr("lib.empty")}</p>')

    def _jump_letter(self, letter: str) -> None:
        self.filter.setText(letter)
        self._filter_timer.stop()
        self._load_entries(prefix=letter, contains=False)

    def _on_select(self, current: QListWidgetItem | None, _previous=None) -> None:
        if current is None or self.mod is None:
            return
        ref = current.data(Qt.UserRole)
        page = self.mod.page_by_ref(ref)
        if page is None:
            self.detail.setHtml(f'<p class="muted">{tr("lib.no_selection")}</p>')
            return
        self._show_page(page)

    def _show_page(self, page) -> None:
        css = document_css(self.settings.theme, self.settings.font_size, self.settings.font_family)
        parts = [f"<style>{css}</style>"]
        parts.append(f'<div class="entry-title">{_html.escape(page.title)}</div>')
        if page.book and self.mod and self.mod.structure == "commentary":
            parts.append(
                f'<p class="muted"><a href="ref:'
                f'{_html.escape(page.title, quote=True)}">{tr("common.open")} →</a></p>'
            )
        parts.append(link_references(to_rich(page.raw, hint=self.mod.stem if self.mod else "", codepages=self.mod.codepages if self.mod else None)))
        if self.mod and self.mod.structure == "maps":
            pixmap = self.mod.map_picture(page.ref)
            if pixmap:
                from PySide6.QtCore import QByteArray

                img = QPixmap()
                if img.loadFromData(QByteArray(pixmap)):
                    from PySide6.QtCore import QUrl

                    doc = self.detail.document()
                    doc.addResource(
                        doc.ResourceType.ImageResource,
                        QUrl(f"map:{page.ref}"),
                        img,
                    )
                    parts.append(
                        f'<p><img src="map:{_html.escape(page.ref, quote=True)}" '
                        f'width="{min(img.width(), 760)}"></p>'
                    )
            else:
                parts.append(f'<p class="muted">{tr("map.no_image")}</p>')
        self.detail.setHtml("".join(parts))
        self.detail.verticalScrollBar().setValue(0)

    def reload_theme(self) -> None:
        """Reaplica la hoja de estilo sin recrear la pestaña."""
        self.detail.document().setDefaultStyleSheet(
            document_css(self.ctx.settings.theme, self.ctx.settings.font_size,
                         self.ctx.settings.font_family)
        )
        current = self.list.currentItem()
        if current is not None:
            self._on_select(current, None)

    def _on_anchor(self, url) -> None:
        if url.scheme() == "ref":
            self.open_reference.emit(url.path() or url.toString()[4:])
