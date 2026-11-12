"""Visor genérico de módulos: diccionarios, léxicos, comentarios, mapas, etc."""

from __future__ import annotations

import html as _html

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QSplitter, QToolButton, QVBoxLayout, QWidget,
)

from ..core.context import AppContext
from ..core.refs import link_references
from ..core.text import to_rich
from ..i18n import tr
from .rich_browser import RichBrowser
from .theme import document_css

MAX_ENTRIES = 3000
LIST_MIN_WIDTH = 220
DETAIL_MIN_WIDTH = 240
HANDLE_WIDTH = 15


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
        self.title_label = QLabel(self.module_row.get("title") or "")
        self.title_label.setObjectName("appTitle")
        self.sub_label = QLabel(self._subtitle())
        self.sub_label.setObjectName("appSubtitle")
        box = QVBoxLayout()
        box.setSpacing(0)
        box.addWidget(self.title_label)
        box.addWidget(self.sub_label)
        head_row.addLayout(box)
        head_row.addStretch(1)
        layout.addWidget(head)

        self.split = QSplitter(Qt.Horizontal)
        self.split.setChildrenCollapsible(False)
        self.split.splitterMoved.connect(self._on_split_moved)
        left = QWidget()
        self.left = left
        left.setMinimumWidth(LIST_MIN_WIDTH)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        self.filter = QLineEdit()
        self.filter.setPlaceholderText(tr("lib.filter_placeholder"))
        self.filter.setToolTip(tr("lib.filter_help"))
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
        self.list.setAlternatingRowColors(True)
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

        self.detail.setMinimumWidth(DETAIL_MIN_WIDTH)
        self.left_dock = QWidget()
        dock_row = QHBoxLayout(self.left_dock)
        dock_row.setContentsMargins(0, 0, 0, 0)
        dock_row.setSpacing(0)
        dock_row.addWidget(left, 1)
        self.handle = QToolButton()
        self.handle.setObjectName("sidebarHandle")
        self.handle.setFixedSize(HANDLE_WIDTH, 26)
        self.handle.setCursor(Qt.PointingHandCursor)
        self.handle.clicked.connect(self._toggle_list)
        dock_row.addWidget(self.handle, 0, Qt.AlignTop)
        self.split.addWidget(self.left_dock)
        self.split.addWidget(self.detail)
        self.split.setStretchFactor(0, 0)
        self.split.setStretchFactor(1, 1)
        width = max(LIST_MIN_WIDTH, int(self.settings.library_list_width or 300))
        self.split.setSizes([width + HANDLE_WIDTH, 700])
        self._apply_list_constraints(self.settings.library_list_visible)
        self._update_handle()
        layout.addWidget(self.split, 1)

    def _subtitle(self) -> str:
        kind = tr(f"kind.{self.module_row.get('kind', 'unknown')}")
        entries = self.module_row.get("entries") or 0
        extra = " · " + tr("badge.encrypted") if self.module_row.get("encrypted") else ""
        return f"{kind} · {entries} {tr('lib.entries').lower()}{extra}"

    def _apply_list_constraints(self, visible: bool) -> None:
        if visible:
            self.left.show()
            self.left_dock.setMinimumWidth(LIST_MIN_WIDTH + HANDLE_WIDTH)
            self.left_dock.setMaximumWidth(16777215)
        else:
            self.left.hide()
            self.left_dock.setMinimumWidth(HANDLE_WIDTH)
            self.left_dock.setMaximumWidth(16)

    def _update_handle(self) -> None:
        visible = self.settings.library_list_visible
        self.handle.setText("‹" if visible else "›")
        self.handle.setToolTip(
            tr("lib.hide_list" if visible else "lib.show_list")
        )

    def _toggle_list(self) -> None:
        visible = not self.settings.library_list_visible
        if not visible and self.left.isVisible():
            self.settings.library_list_width = max(LIST_MIN_WIDTH, self.left.width())
        self._apply_list_constraints(visible)
        if visible:
            total = max(self.width(), LIST_MIN_WIDTH + DETAIL_MIN_WIDTH + HANDLE_WIDTH)
            width = min(
                max(LIST_MIN_WIDTH, int(self.settings.library_list_width or 300)),
                max(LIST_MIN_WIDTH, total - DETAIL_MIN_WIDTH - HANDLE_WIDTH),
            )
            self.split.setSizes([width + HANDLE_WIDTH, max(DETAIL_MIN_WIDTH, total - width - HANDLE_WIDTH)])
        else:
            self.split.setSizes([HANDLE_WIDTH, max(DETAIL_MIN_WIDTH, self.width() - HANDLE_WIDTH)])
        self.settings.library_list_visible = visible
        self.settings.save()
        self._update_handle()

    def _on_split_moved(self, _pos: int, _index: int) -> None:
        if self.left.isVisible():
            self.settings.library_list_width = max(LIST_MIN_WIDTH, self.left.width())

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

    def retranslate(self) -> None:
        self.title_label.setText(self.module_row.get("title") or "")
        self.sub_label.setText(self._subtitle())
        self.filter.setPlaceholderText(tr("lib.filter_placeholder"))
        self.filter.setToolTip(tr("lib.filter_help"))
        self._update_handle()
        current = self.list.currentItem()
        if current is not None:
            self._on_select(current, None)

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
