"""Generic module viewer: dictionaries, lexicons, commentaries, maps, etc."""

from __future__ import annotations

import html as _html

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QSplitter, QStackedWidget, QToolButton, QVBoxLayout, QWidget,
)

from ..core.context import AppContext
from ..core.refs import link_references
from ..core.text import to_rich
from ..i18n import tr
from .bible_view import fill_bible_combo
from .image_viewer import ImageViewer
from .rich_browser import RichBrowser
from .theme import document_css_for

MAX_ENTRIES = 3000
LIST_MIN_WIDTH = 220
DETAIL_MIN_WIDTH = 240
HANDLE_WIDTH = 15


class LibraryView(QWidget):
    open_reference = Signal(str)
    # Emitted when the user changes the reference Bible of this workspace
    ref_bible_changed = Signal(str)

    def __init__(self, ctx: AppContext, module: dict, initial_ref: str | None = None,
                 ref_bible_rel: str = "", parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.settings = ctx.settings
        self.module_row = module
        self.mod = ctx.module(module)
        self.initial_ref = initial_ref
        self._ref_bible_rel = (
            ref_bible_rel or self.settings.reference_bible
            or self.settings.bible_module or ""
        )
        if not self._ref_bible_rel:
            bibles = self.ctx.bibles()
            self._ref_bible_rel = bibles[0]["rel_path"] if bibles else ""
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

        # ── image size (maps/illustrations) ──────────────────────────────
        self.lbl_map_size = QLabel("")
        self.lbl_map_size.setObjectName("mapSize")
        self.lbl_map_size.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_map_size.hide()
        head_row.addWidget(self.lbl_map_size)

        head_row.addStretch(1)

        # ── image viewer (created before its header controls) ────────────
        self.image_viewer = ImageViewer(self)
        self.image_viewer.legend_toggled.connect(self._toggle_legend)
        self.image_viewer.image_size.connect(self._on_image_size)

        # ── map/image controls (same row as the Bible combo) ─────────────
        self.map_toolbar = QWidget()
        self.map_toolbar.setObjectName("mapToolbar")
        map_row = QHBoxLayout(self.map_toolbar)
        map_row.setContentsMargins(0, 0, 0, 0)
        map_row.setSpacing(4)

        self.btn_zoom_in = QToolButton()
        self.btn_zoom_in.setText("+")
        self.btn_zoom_in.setToolTip(tr("image.zoom_in"))
        self.btn_zoom_in.clicked.connect(self.image_viewer.zoom_in)
        map_row.addWidget(self.btn_zoom_in)

        self.btn_zoom_out = QToolButton()
        self.btn_zoom_out.setText("-")
        self.btn_zoom_out.setToolTip(tr("image.zoom_out"))
        self.btn_zoom_out.clicked.connect(self.image_viewer.zoom_out)
        map_row.addWidget(self.btn_zoom_out)

        self.btn_reset = QToolButton()
        self.btn_reset.setText("1:1")
        self.btn_reset.setToolTip(tr("image.zoom_real"))
        self.btn_reset.clicked.connect(self.image_viewer.reset_zoom)
        map_row.addWidget(self.btn_reset)

        self.btn_fit = QToolButton()
        self.btn_fit.setText(tr("image.fit"))
        self.btn_fit.setToolTip(tr("image.fit"))
        self.btn_fit.clicked.connect(self.image_viewer.fit_to_window)
        map_row.addWidget(self.btn_fit)

        self.btn_legend = QToolButton()
        self.btn_legend.setText(tr("image.legend"))
        self.btn_legend.setToolTip(tr("image.legend"))
        self.btn_legend.setCheckable(True)
        self.btn_legend.setChecked(True)
        self.btn_legend.clicked.connect(self.image_viewer.set_legend_visible)
        self.image_viewer.legend_toggled.connect(self.btn_legend.setChecked)
        map_row.addWidget(self.btn_legend)

        # The magnifier and hand buttons were removed: the mouse handles both
        # (left click = pan, wheel = zoom) without needing buttons.

        self.map_toolbar.hide()
        head_row.addWidget(self.map_toolbar)

        # ── reference Bible selector (always on the right) ───────────────
        bibles = self.ctx.bibles()
        if bibles:
            self._bible_lbl = QLabel(tr("workspace.bible") + ":")
            self._bible_lbl.setObjectName("appSubtitle")
            self._bible_combo = QComboBox()
            # Reuse the existing function in bible_view
            fill_bible_combo(self._bible_combo, bibles,
                             self._ref_bible_rel, editable=False)
            # If nothing is selected, select the first available one
            self._sync_combo_to_rel(self._ref_bible_rel)
            self._bible_combo.setToolTip(tr("workspace.bible_help"))
            self._bible_combo.currentIndexChanged.connect(self._on_bible_changed)
            head_row.addWidget(self._bible_lbl)
            head_row.addWidget(self._bible_combo)
        else:
            self._bible_lbl = None
            self._bible_combo = None

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
        self.detail.bible_rel = self._ref_bible_rel or None
        self.detail.setOpenLinks(False)
        self.detail.setOpenExternalLinks(False)
        self.detail.anchorClicked.connect(self._on_anchor)
        self.detail.document().setDefaultStyleSheet(
            document_css_for(self.settings)
        )

        self.detail.setMinimumWidth(DETAIL_MIN_WIDTH)
        self.right_split = QSplitter(Qt.Vertical)
        self.right_split.setChildrenCollapsible(False)
        self.right_split.setMinimumWidth(DETAIL_MIN_WIDTH)
        self.right_split.addWidget(self.image_viewer)
        self.right_split.addWidget(self.detail)
        self.right_split.setStretchFactor(0, 3 if self.mod and self.mod.structure == "maps" else 0)
        self.right_split.setStretchFactor(1, 1)
        self.image_viewer.setVisible(bool(self.mod and self.mod.structure == "maps"))
        self._legend_visible = True

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
        self.split.addWidget(self.right_split)
        self.split.setStretchFactor(0, 0)
        self.split.setStretchFactor(1, 1)
        self._apply_list_constraints(self.settings.library_list_visible)
        self._apply_list_sizes(self.settings.library_list_visible)
        self._update_handle()
        layout.addWidget(self.split, 1)

    def _subtitle(self) -> str:
        kind = tr(f"kind.{self.module_row.get('kind', 'unknown')}")
        entries = self.module_row.get("entries") or 0
        extra = " · " + tr("badge.encrypted") if self.module_row.get("encrypted") else ""
        return f"{kind} · {entries} {tr('lib.entries').lower()}{extra}"

    # ── reference Bible ──────────────────────────────────────────────────
    def _sync_combo_to_rel(self, rel: str) -> None:
        """Select in the combo the item whose UserRole == rel."""
        if self._bible_combo is None:
            return
        self._bible_combo.blockSignals(True)
        model = self._bible_combo.model()
        target = -1
        first_selectable = -1
        for i in range(model.rowCount()):
            item_rel = model.item(i).data(Qt.UserRole) if model.item(i) else None
            if item_rel is not None:
                if first_selectable < 0:
                    first_selectable = i
                if item_rel == rel:
                    target = i
                    break
        if target >= 0:
            self._bible_combo.setCurrentIndex(target)
        elif first_selectable >= 0:
            self._bible_combo.setCurrentIndex(first_selectable)
            # Update _ref_bible_rel to the first available one
            first_item = model.item(first_selectable)
            if first_item:
                self._ref_bible_rel = first_item.data(Qt.UserRole) or ""
        self._bible_combo.blockSignals(False)

    def _on_bible_changed(self, index: int) -> None:
        if self._bible_combo is None:
            return
        rel = self._bible_combo.currentData(Qt.UserRole)
        if rel and rel != self._ref_bible_rel:
            self._ref_bible_rel = rel
            self.detail.bible_rel = rel or None
            self.ref_bible_changed.emit(rel)

    def set_reference_bible(self, rel: str) -> None:
        """Update the selector when the workspace changes the Bible externally."""
        self._ref_bible_rel = rel or ""
        self._sync_combo_to_rel(self._ref_bible_rel)
        if self.detail is not None:
            self.detail.bible_rel = self._ref_bible_rel or None

    def _apply_list_constraints(self, visible: bool) -> None:
        if visible:
            self.left.show()
            self.left_dock.setMinimumWidth(LIST_MIN_WIDTH + HANDLE_WIDTH)
            self.left_dock.setMaximumWidth(16777215)
        else:
            self.left.hide()
            self.left_dock.setMinimumWidth(HANDLE_WIDTH)
            self.left_dock.setMaximumWidth(HANDLE_WIDTH + 1)

    def _apply_list_sizes(self, visible: bool) -> None:
        """Splitter sizes matched to the panel visibility from one place.

        The splitter keeps its own copy of the sizes: clamping the dock without
        calling ``setSizes`` again leaves an empty band where the list was.
        """
        if visible:
            total = max(
                self.width(), LIST_MIN_WIDTH + DETAIL_MIN_WIDTH + HANDLE_WIDTH
            )
            width = min(
                max(LIST_MIN_WIDTH, int(self.settings.library_list_width or 300)),
                max(LIST_MIN_WIDTH, total - DETAIL_MIN_WIDTH - HANDLE_WIDTH),
            )
            self.split.setSizes([
                width + HANDLE_WIDTH,
                max(DETAIL_MIN_WIDTH, total - width - HANDLE_WIDTH),
            ])
        else:
            self.split.setSizes([
                HANDLE_WIDTH,
                max(DETAIL_MIN_WIDTH, self.width() - HANDLE_WIDTH),
            ])

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
        self._apply_list_sizes(visible)
        self.settings.library_list_visible = visible
        self.settings.save()
        self._update_handle()

    def _on_split_moved(self, _pos: int, _index: int) -> None:
        if self.left.isVisible():
            self.settings.library_list_width = max(LIST_MIN_WIDTH, self.left.width())

    # ── data ─────────────────────────────────────────────────────────────
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
            # For maps/illustrations, show the pixel size next to the title
            # in the entry list.
            if self.mod and self.mod.structure == "maps":
                picture = self.mod.map_picture(ref)
                if picture:
                    pixmap = QPixmap()
                    if pixmap.loadFromData(picture):
                        label = f"{label} ({pixmap.width()} × {pixmap.height()} px)"
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
        css = document_css_for(self.settings)
        parts = [f"<style>{css}</style>"]
        parts.append(f'<div class="entry-title">{_html.escape(page.title)}</div>')
        if page.book and self.mod and self.mod.structure == "commentary":
            parts.append(
                f'<p class="muted"><a href="ref:'
                f'{_html.escape(page.title, quote=True)}">{tr("common.open")} →</a></p>'
            )
        parts.append(link_references(to_rich(page.raw, hint=self.mod.stem if self.mod else "", codepages=self.mod.codepages if self.mod else None)))
        is_maps = bool(self.mod and self.mod.structure == "maps")
        has_img = False
        if is_maps:
            pixmap = self.mod.map_picture(page.ref)
            self.image_viewer.show()
            self.map_toolbar.show()
            if pixmap:
                from PySide6.QtCore import QByteArray

                img = QPixmap()
                if img.loadFromData(QByteArray(pixmap)):
                    has_img = True
                    self.image_viewer.set_pixmap(img, page.title)
            if not has_img:
                self.image_viewer.set_pixmap(QPixmap(), page.title)
                parts.append(f'<p class="muted">{tr("map.no_image")}</p>')
        else:
            self.image_viewer.hide()
            self.map_toolbar.hide()
            self.lbl_map_size.hide()
        self.detail.setHtml("".join(parts))
        # The map legend (Details text) can be hidden with its button.
        # If there is no image, the detail must still be shown to display the
        # warning instead of leaving the whole panel blank.
        if is_maps:
            self.detail.setVisible(self._legend_visible or not has_img)
        else:
            self.detail.setVisible(True)
        self.detail.verticalScrollBar().setValue(0)

    def _toggle_legend(self, checked: bool) -> None:
        """Hide or show the legend (Details text) of a map/illustration."""
        self._legend_visible = bool(checked)
        if self.mod and self.mod.structure == "maps":
            self.detail.setVisible(self._legend_visible)

    def _on_image_size(self, text: str) -> None:
        """Show or hide the pixel size next to the Bible combo."""
        if self.mod and self.mod.structure == "maps" and text:
            self.lbl_map_size.setText(text)
            self.lbl_map_size.show()
        else:
            self.lbl_map_size.hide()

    def retranslate(self) -> None:
        self.title_label.setText(self.module_row.get("title") or "")
        self.sub_label.setText(self._subtitle())
        self.filter.setPlaceholderText(tr("lib.filter_placeholder"))
        self.filter.setToolTip(tr("lib.filter_help"))
        self._update_handle()
        if self._bible_lbl is not None:
            self._bible_lbl.setText(tr("workspace.bible") + ":")
        if self._bible_combo is not None:
            self._bible_combo.setToolTip(tr("workspace.bible_help"))
        current = self.list.currentItem()
        if current is not None:
            self._on_select(current, None)

    def reload_theme(self) -> None:
        """Reapply the style sheet without recreating the tab."""
        self.detail.document().setDefaultStyleSheet(
            document_css_for(self.ctx.settings)
        )
        current = self.list.currentItem()
        if current is not None:
            self._on_select(current, None)

    def _on_anchor(self, url) -> None:
        if url.scheme() == "ref":
            self.open_reference.emit(url.path() or url.toString()[4:])

