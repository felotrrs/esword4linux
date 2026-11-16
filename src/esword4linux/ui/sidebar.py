"""Sidebar: resource catalog with filters and combinable groupings.

The organizer allows choosing up to three grouping levels (kind, language,
work) and filtering by several kinds and languages at once. The text filter
remains available and is applied to the resulting hierarchy.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QColor, QFont
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QMenu, QSizePolicy,
    QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from ..core.catalog import KIND_ORDER, work_key
from ..core.context import AppContext
from ..i18n import tr
from .language import language_label, language_sort_key
from .theme import palette

STATUS_GLYPH = {"ready": "●", "pending": "○", "indexing": "◐", "failed": "✕",
                "skipped": "–"}

_GROUPINGS = ("kind", "language", "work")


class Sidebar(QWidget):
    module_activated = Signal(int)
    index_module_requested = Signal(int)
    index_kind_requested = Signal(str)

    def __init__(self, ctx: AppContext, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.settings = ctx.settings
        self.setMinimumWidth(240)
        grouping = [g for g in (self.settings.sidebar_grouping or ["kind"])
                    if g in _GROUPINGS]
        if not grouping:
            grouping = ["kind"]
        # Migration from the single-mode version.
        if (grouping == ["kind"] and self.settings.sidebar_mode in ("work", "language")):
            grouping = [self.settings.sidebar_mode]
        self._grouping = grouping[:3]
        self._kind_filters = [k for k in self.settings.sidebar_kind_filters
                              if k in KIND_ORDER]
        self._language_filters = list(self.settings.sidebar_language_filters or [])
        self._build_ui()
        self.refresh()

    # ── UI ───────────────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        head = QWidget()
        head_row = QVBoxLayout(head)
        head_row.setContentsMargins(12, 10, 12, 4)
        head_row.setSpacing(2)
        self.title_label = QLabel(tr("sidebar.title"))
        self.title_label.setObjectName("appTitle")
        head_row.addWidget(self.title_label)
        self.folder_label = QLabel(self.settings.resources_dir)
        self.folder_label.setObjectName("appSubtitle")
        self.folder_label.setToolTip(self.settings.resources_dir)
        self.folder_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        head_row.addWidget(self.folder_label)
        layout.addWidget(head)

        organizer = QFrame()
        organizer.setObjectName("sidebarOrganizer")
        org = QVBoxLayout(organizer)
        org.setContentsMargins(7, 6, 7, 6)
        org.setSpacing(5)

        self.group_label = QLabel(tr("sidebar.group_by"))
        self.group_label.setObjectName("organizerLabel")
        org.addWidget(self.group_label)
        group_row = QHBoxLayout()
        group_row.setSpacing(2)
        self.group_combos: list[QComboBox] = []
        for i in range(3):
            if i:
                sep = QLabel("›")
                sep.setObjectName("organizerSep")
                group_row.addWidget(sep)
            combo = QComboBox()
            combo.setObjectName("organizerCombo")
            combo.setMinimumWidth(52)
            combo.setToolTip(tr("sidebar.group_help"))
            combo.currentIndexChanged.connect(self._on_grouping_changed)
            group_row.addWidget(combo, 1)
            self.group_combos.append(combo)
        org.addLayout(group_row)

        # Full-width section title, like "Group by". The vertical space
        # marks that the filters are a separate block.
        org.addSpacing(6)
        self.filter_label = QLabel(tr("sidebar.filter"))
        self.filter_label.setObjectName("organizerLabel")
        org.addWidget(self.filter_label)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(2)
        self.btn_kind_filter = QToolButton()
        self.btn_kind_filter.setObjectName("organizerFilter")
        self.btn_kind_filter.setPopupMode(QToolButton.InstantPopup)
        self.btn_kind_filter.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.btn_kind_filter.setMinimumWidth(70)
        self.kind_menu = QMenu(self.btn_kind_filter)
        self.kind_menu.aboutToShow.connect(self._fill_kind_menu)
        self.btn_kind_filter.setMenu(self.kind_menu)
        filter_row.addWidget(self.btn_kind_filter, 0)

        self.btn_language_filter = QToolButton()
        self.btn_language_filter.setObjectName("organizerFilter")
        self.btn_language_filter.setPopupMode(QToolButton.InstantPopup)
        self.btn_language_filter.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.btn_language_filter.setMinimumWidth(70)
        self.language_menu = QMenu(self.btn_language_filter)
        self.language_menu.aboutToShow.connect(self._fill_language_menu)
        self.btn_language_filter.setMenu(self.language_menu)
        filter_row.addWidget(self.btn_language_filter, 0)
        filter_row.addStretch(1)

        org.addLayout(filter_row)
        wrap_org = QWidget()
        wrap_layout = QVBoxLayout(wrap_org)
        wrap_layout.setContentsMargins(8, 2, 8, 5)
        wrap_layout.addWidget(organizer)
        layout.addWidget(wrap_org)

        self.filter = QLineEdit()
        self.filter.setPlaceholderText(tr("sidebar.filter_placeholder"))
        self.filter.setClearButtonEnabled(True)
        self.filter.textChanged.connect(self._apply_filter)
        wrap = QWidget()
        wrap_row = QVBoxLayout(wrap)
        wrap_row.setContentsMargins(10, 0, 10, 6)
        wrap_row.addWidget(self.filter)
        layout.addWidget(wrap)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(14)
        self.tree.setAnimated(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._context_menu)
        self.tree.itemClicked.connect(self._on_click)
        self.tree.itemActivated.connect(self._on_keyboard)
        layout.addWidget(self.tree, 1)

        self._refresh_group_combos()
        self._update_filter_buttons()

    def retranslate(self) -> None:
        self.title_label.setText(tr("sidebar.title"))
        self.group_label.setText(tr("sidebar.group_by"))
        self.filter_label.setText(tr("sidebar.filter"))
        self.filter.setPlaceholderText(tr("sidebar.filter_placeholder"))
        self._refresh_group_combos()
        self._update_filter_buttons()
        self.refresh()

    # ── grouping ─────────────────────────────────────────────────────────
    def _group_label(self, code: str) -> str:
        return {
            "kind": tr("sidebar.group_kind"),
            "language": tr("sidebar.group_language"),
            "work": tr("sidebar.group_work"),
        }.get(code, code)

    def _refresh_group_combos(self) -> None:
        for i, combo in enumerate(self.group_combos):
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(tr("sidebar.group_none"), "")
            for code in _GROUPINGS:
                combo.addItem(self._group_label(code), code)
            value = self._grouping[i] if i < len(self._grouping) else ""
            idx = combo.findData(value)
            combo.setCurrentIndex(idx if idx >= 0 else 0)
            combo.blockSignals(False)

    def _on_grouping_changed(self, _index: int = 0) -> None:
        selected: list[str] = []
        for combo in self.group_combos:
            code = combo.currentData() or ""
            if code and code not in selected:
                selected.append(code)
        self._grouping = selected
        self.settings.sidebar_grouping = list(selected)
        self.settings.sidebar_mode = selected[0] if selected else "kind"
        self.settings.save()
        self._refresh_group_combos()
        self.refresh()

    def set_mode(self, mode: str) -> None:
        """Compatibility: set a single grouping."""
        self._grouping = [mode] if mode in _GROUPINGS else []
        self.settings.sidebar_grouping = list(self._grouping)
        self.settings.sidebar_mode = mode if mode in _GROUPINGS else "kind"
        self.settings.save()
        self._refresh_group_combos()
        self.refresh()

    # ── filters ──────────────────────────────────────────────────────────
    def _update_filter_buttons(self) -> None:
        if self._kind_filters:
            self.btn_kind_filter.setText(
                tr("sidebar.filter_kind_n", n=len(self._kind_filters))
            )
        else:
            self.btn_kind_filter.setText(tr("sidebar.filter_kind"))
        self.btn_kind_filter.setToolTip(tr("sidebar.filter_kind_help"))
        if self._language_filters:
            self.btn_language_filter.setText(
                tr("sidebar.filter_language_n", n=len(self._language_filters))
            )
        else:
            self.btn_language_filter.setText(tr("sidebar.filter_language"))
        self.btn_language_filter.setToolTip(tr("sidebar.filter_language_help"))

    def _fill_kind_menu(self) -> None:
        menu = self.kind_menu
        menu.clear()
        act_all = QAction(tr("sidebar.filter_all"), self)
        act_all.setCheckable(True)
        act_all.setChecked(not self._kind_filters)
        act_all.triggered.connect(self._clear_kind_filters)
        menu.addAction(act_all)
        menu.addSeparator()
        counts = self.ctx.catalog.counts_by_kind()
        for kind in KIND_ORDER:
            if not counts.get(kind):
                continue
            act = QAction(f"{tr(f'kind.{kind}')} ({counts[kind]})", self)
            act.setCheckable(True)
            act.setChecked(kind in self._kind_filters)
            act.triggered.connect(
                lambda checked=False, k=kind: self._toggle_kind_filter(k, checked)
            )
            menu.addAction(act)

    def _fill_language_menu(self) -> None:
        menu = self.language_menu
        menu.clear()
        act_all = QAction(tr("sidebar.filter_all"), self)
        act_all.setCheckable(True)
        act_all.setChecked(not self._language_filters)
        act_all.triggered.connect(self._clear_language_filters)
        menu.addAction(act_all)
        menu.addSeparator()
        counts: dict[str, int] = {}
        for mod in self.ctx.catalog.modules():
            code = mod.get("language") or "und"
            counts[code] = counts.get(code, 0) + 1
        for code in sorted(counts, key=language_sort_key):
            act = QAction(f"{language_label(code)} ({counts[code]})", self)
            act.setCheckable(True)
            act.setChecked(code in self._language_filters)
            act.triggered.connect(
                lambda checked=False, c=code: self._toggle_language_filter(c, checked)
            )
            menu.addAction(act)

    def _toggle_kind_filter(self, kind: str, checked: bool) -> None:
        if checked and kind not in self._kind_filters:
            self._kind_filters.append(kind)
        elif not checked and kind in self._kind_filters:
            self._kind_filters.remove(kind)
        self.settings.sidebar_kind_filters = list(self._kind_filters)
        self.settings.save()
        self._update_filter_buttons()
        self.refresh()

    def _clear_kind_filters(self) -> None:
        self._kind_filters = []
        self.settings.sidebar_kind_filters = []
        self.settings.save()
        self._update_filter_buttons()
        self.refresh()

    def _toggle_language_filter(self, code: str, checked: bool) -> None:
        if checked and code not in self._language_filters:
            self._language_filters.append(code)
        elif not checked and code in self._language_filters:
            self._language_filters.remove(code)
        self.settings.sidebar_language_filters = list(self._language_filters)
        self.settings.save()
        self._update_filter_buttons()
        self.refresh()

    def _clear_language_filters(self) -> None:
        self._language_filters = []
        self.settings.sidebar_language_filters = []
        self.settings.save()
        self._update_filter_buttons()
        self.refresh()

    def _filtered_modules(self) -> list[dict]:
        modules = self.ctx.catalog.modules()
        show_unclassified = getattr(self.settings, "show_unclassified", False)
        if not show_unclassified and "unknown" not in self._kind_filters:
            modules = [m for m in modules if not (m.get("kind") == "unknown" and (m.get("entries") or 0) == 0)]
        if self._kind_filters:
            modules = [m for m in modules if m["kind"] in self._kind_filters]
        if self._language_filters:
            modules = [
                m for m in modules
                if (m.get("language") or "und") in self._language_filters
            ]
        return modules

    # ── tree ─────────────────────────────────────────────────────────────
    def refresh(self) -> None:
        expanded = self._expanded_keys()
        self.tree.clear()
        self._build_groups(None, self._filtered_modules(), 0, expanded)
        self._apply_filter(self.filter.text())

    def _expanded_keys(self) -> set:
        expanded: set = set()

        def walk(item: QTreeWidgetItem) -> None:
            data = item.data(0, Qt.UserRole)
            if item.isExpanded() and isinstance(data, str):
                expanded.add(data)
            for i in range(item.childCount()):
                walk(item.child(i))

        for i in range(self.tree.topLevelItemCount()):
            walk(self.tree.topLevelItem(i))
        return expanded

    def _new_item(self, parent: QTreeWidgetItem | None,
                  text: str, data: str) -> QTreeWidgetItem:
        item = QTreeWidgetItem([text])
        item.setData(0, Qt.UserRole, data)
        font = QFont()
        font.setBold(True)
        item.setFont(0, font)
        item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
        if parent is None:
            self.tree.addTopLevelItem(item)
        else:
            parent.addChild(item)
        return item

    def _add_module(self, parent: QTreeWidgetItem | None, mod: dict,
                    label: str | None = None) -> None:
        item = self._module_item(mod, label)
        if parent is None:
            self.tree.addTopLevelItem(item)
        else:
            parent.addChild(item)

    def _build_groups(self, parent: QTreeWidgetItem | None, modules: list[dict],
                      level: int, expanded: set) -> None:
        if level >= len(self._grouping):
            work_context = (level > 0 and self._grouping[level - 1] == "work"
                            and len(modules) > 1)
            for mod in sorted(modules, key=lambda m: (m["title"] or "").lower()):
                label = None
                if work_context:
                    role = tr("role." + mod["kind"])
                    label = (
                        f"{STATUS_GLYPH.get(mod['index_status'], '○')} "
                        f"{role} · {mod['abbreviation'] or mod['filename']}"
                    )
                self._add_module(parent, mod, label)
            return

        grouping = self._grouping[level]
        groups: dict[tuple[str, str], list[dict]] = {}
        if grouping == "kind":
            for mod in modules:
                kind = mod["kind"]
                groups.setdefault((kind, tr(f"kind.{kind}")), []).append(mod)
            ordered = sorted(groups.items(),
                             key=lambda kv: KIND_ORDER.index(kv[0][0])
                             if kv[0][0] in KIND_ORDER else 99)
        elif grouping == "language":
            for mod in modules:
                code = mod.get("language") or "und"
                groups.setdefault((code, language_label(code)), []).append(mod)
            ordered = sorted(groups.items(),
                             key=lambda kv: language_sort_key(kv[0][0]))
        else:  # work
            works = {m["id"]: w for w in self.ctx.catalog.works()
                     for m in w["modules"]}
            for mod in modules:
                work = works.get(mod["id"])
                key = work["key"] if work else work_key(mod["title"])
                label = work["title"] if work else (mod["title"] or "")
                groups.setdefault((key, label), []).append(mod)
            ordered = sorted(groups.items(), key=lambda kv: kv[0][1].lower())

        for (key, label), items in ordered:
            data = f"group:{grouping}:{key}"
            item = self._new_item(
                parent, f"{label}  ({len(items)})", data
            )
            item.setExpanded(data in expanded)
            if grouping == "kind":
                item.setToolTip(0, tr("sidebar.ctx.index_category"))
            self._build_groups(item, items, level + 1, expanded)

    def _module_item(self, mod: dict, label: str | None = None) -> QTreeWidgetItem:
        status = mod["index_status"]
        glyph = STATUS_GLYPH.get(status, "○")
        lock = " 🔒" if mod["encrypted"] else ""
        text = label or f"{glyph} {mod['title']}{lock}"
        item = QTreeWidgetItem([text])
        item.setData(0, Qt.UserRole, mod["id"])
        item.setToolTip(0, self._tooltip(mod))
        p = palette(self.settings.theme)
        if status == "ready":
            item.setForeground(0, QColor(p.success))
        elif status == "failed":
            item.setForeground(0, QColor(p.error))
        return item

    @staticmethod
    def _tooltip(mod: dict) -> str:
        return (
            f"{mod['title']}\n{mod['rel_path']}\n"
            f"{mod['entries']} {tr('lib.entries').lower()} · {mod['size'] / 1e6:.1f} MB\n"
            f"{tr('sidebar.tooltip_status', status=mod['index_status'])}"
        )

    # ── text filter ──────────────────────────────────────────────────────
    def _apply_filter(self, text: str) -> None:
        needle = (text or "").strip().lower()

        def show_all(item: QTreeWidgetItem) -> None:
            item.setHidden(False)
            for j in range(item.childCount()):
                show_all(item.child(j))

        def visit(item: QTreeWidgetItem) -> bool:
            own = needle in item.text(0).lower() if needle else True
            if not needle:
                item.setHidden(False)
                for j in range(item.childCount()):
                    visit(item.child(j))
                return True
            if own:
                show_all(item)
                item.setExpanded(True)
                return True
            visible = False
            for j in range(item.childCount()):
                if visit(item.child(j)):
                    visible = True
            item.setHidden(not visible)
            if visible:
                item.setExpanded(True)
            return visible

        for i in range(self.tree.topLevelItemCount()):
            visit(self.tree.topLevelItem(i))

    # ── interaction ──────────────────────────────────────────────────────
    def _module_id(self, item: QTreeWidgetItem) -> int | None:
        data = item.data(0, Qt.UserRole)
        return data if isinstance(data, int) else None

    def _on_click(self, item: QTreeWidgetItem, _column: int = 0) -> None:
        mid = self._module_id(item)
        if mid is not None:
            self.module_activated.emit(mid)
            return
        data = item.data(0, Qt.UserRole)
        if isinstance(data, str) and data.startswith("group:"):
            item.setExpanded(not item.isExpanded())

    def _on_keyboard(self, item: QTreeWidgetItem, _column: int = 0) -> None:
        mid = self._module_id(item)
        if mid is not None:
            self.module_activated.emit(mid)

    def _context_menu(self, pos) -> None:
        item = self.tree.itemAt(pos)
        if item is None:
            return
        menu = QMenu(self)
        mid = self._module_id(item)
        if mid is not None:
            act = QAction(tr("sidebar.ctx.open"), self)
            act.triggered.connect(lambda: self.module_activated.emit(mid))
            menu.addAction(act)
            act_idx = QAction(tr("sidebar.ctx.index_module"), self)
            act_idx.triggered.connect(lambda: self.index_module_requested.emit(mid))
            menu.addAction(act_idx)
            row = self.ctx.catalog.module(mid)
            if row:
                act_rev = QAction(tr("sidebar.ctx.reveal"), self)
                act_rev.triggered.connect(lambda: self._reveal(row["path"]))
                menu.addAction(act_rev)
        else:
            data = item.data(0, Qt.UserRole)
            if isinstance(data, str) and data.startswith("group:kind:"):
                kind = data.rsplit(":", 1)[-1]
                act = QAction(tr("sidebar.ctx.index_category"), self)
                act.triggered.connect(lambda: self.index_kind_requested.emit(kind))
                menu.addAction(act)
        if menu.actions():
            menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _reveal(self, path) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
