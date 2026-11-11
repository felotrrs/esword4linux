"""Panel lateral: carpeta de recursos con dos vistas.

* **Por tipo** — categorías (Biblias, Comentarios, Diccionarios…). Es la vista
  para *encontrar* un material por su naturaleza sin saber de qué obra es.
* **Por obra** — agrupa los módulos por título. Una obra con texto + notas +
  léxico aparece una sola vez, con sus piezas como sub-elementos.

El clic simple carga el recurso; en una obra con varios módulos, el clic en el
submódulo carga esa pieza concreta.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (
    QButtonGroup, QHBoxLayout, QLabel, QLineEdit, QMenu, QSizePolicy,
    QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from ..core.catalog import KIND_ORDER, work_key
from ..core.context import AppContext
from ..i18n import tr

STATUS_GLYPH = {"ready": "●", "pending": "○", "indexing": "◐", "failed": "✕",
                "skipped": "–"}


class Sidebar(QWidget):
    module_activated = Signal(int)
    index_module_requested = Signal(int)
    index_kind_requested = Signal(str)

    def __init__(self, ctx: AppContext, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.settings = ctx.settings
        self._mode = self.settings.sidebar_mode if self.settings.sidebar_mode in (
            "kind", "work") else "kind"
        self.setMinimumWidth(240)
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
        title = QLabel(tr("sidebar.title"))
        title.setObjectName("appTitle")
        head_row.addWidget(title)
        self.folder_label = QLabel(self.settings.resources_dir)
        self.folder_label.setObjectName("appSubtitle")
        self.folder_label.setToolTip(self.settings.resources_dir)
        self.folder_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        head_row.addWidget(self.folder_label)
        layout.addWidget(head)

        modes = QWidget()
        mrow = QHBoxLayout(modes)
        mrow.setContentsMargins(10, 2, 10, 4)
        mrow.setSpacing(4)
        self.btn_kind = QToolButton()
        self.btn_kind.setText(tr("sidebar.by_kind"))
        self.btn_kind.setCheckable(True)
        self.btn_kind.clicked.connect(lambda: self.set_mode("kind"))
        self.btn_work = QToolButton()
        self.btn_work.setText(tr("sidebar.by_work"))
        self.btn_work.setCheckable(True)
        self.btn_work.clicked.connect(lambda: self.set_mode("work"))
        group = QButtonGroup(self)
        group.setExclusive(True)
        group.addButton(self.btn_kind)
        group.addButton(self.btn_work)
        self.btn_kind.setChecked(self._mode == "kind")
        self.btn_work.setChecked(self._mode == "work")
        for btn in (self.btn_kind, self.btn_work):
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            mrow.addWidget(btn)
        layout.addWidget(modes)

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
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._context_menu)
        self.tree.itemClicked.connect(self._on_click)
        self.tree.itemActivated.connect(self._on_keyboard)
        layout.addWidget(self.tree, 1)

    def set_mode(self, mode: str) -> None:
        if mode == self._mode:
            return
        self._mode = mode
        self.settings.sidebar_mode = mode
        self.settings.save()
        self.btn_kind.setChecked(mode == "kind")
        self.btn_work.setChecked(mode == "work")
        self.refresh()

    # ── construcción del árbol ───────────────────────────────────────────
    def refresh(self) -> None:
        expanded = {
            self.tree.topLevelItem(i).data(0, Qt.UserRole)
            for i in range(self.tree.topLevelItemCount())
            if self.tree.topLevelItem(i).isExpanded()
        }
        self.tree.clear()
        if self._mode == "work":
            self._build_works(expanded)
        else:
            self._build_kinds(expanded)
        self._apply_filter(self.filter.text())

    def _module_item(self, mod: dict, label: str | None = None) -> QTreeWidgetItem:
        status = mod["index_status"]
        glyph = STATUS_GLYPH.get(status, "○")
        lock = " 🔒" if mod["encrypted"] else ""
        text = label or f"{glyph} {mod['title']}{lock}"
        item = QTreeWidgetItem([text])
        item.setData(0, Qt.UserRole, mod["id"])
        item.setToolTip(0, self._tooltip(mod))
        if status == "ready":
            item.setForeground(0, Qt.GlobalColor.darkGreen)
        elif status == "failed":
            item.setForeground(0, Qt.GlobalColor.darkRed)
        return item

    @staticmethod
    def _tooltip(mod: dict) -> str:
        return (
            f"{mod['title']}\n{mod['rel_path']}\n"
            f"{mod['entries']} entradas · {mod['size'] / 1e6:.1f} MB\n"
            f"estado: {mod['index_status']}"
        )

    def _build_kinds(self, expanded: set) -> None:
        by_kind: dict[str, list[dict]] = {}
        for mod in self.ctx.catalog.modules():
            by_kind.setdefault(mod["kind"], []).append(mod)

        bold = QFont()
        bold.setBold(True)
        for kind in KIND_ORDER:
            items = by_kind.get(kind)
            if not items:
                continue
            top = QTreeWidgetItem(self.tree, [f"{tr(f'kind.{kind}')}  ({len(items)})"])
            top.setData(0, Qt.UserRole, f"kind:{kind}")
            top.setFont(0, bold)
            top.setFlags(top.flags() & ~Qt.ItemIsSelectable)
            for mod in items:
                top.addChild(self._module_item(mod))
            top.setExpanded(f"kind:{kind}" in expanded)

    def _build_works(self, expanded: set) -> None:
        works = self.ctx.catalog.works()
        bold = QFont()
        bold.setBold(True)
        for work in works:
            modules = work["modules"]
            first = modules[0]
            if len(modules) == 1:
                item = self._module_item(first)
                self.tree.addTopLevelItem(item)
                continue
            roles = " · ".join(tr(f"role.{k}") for k in work["kinds"])
            top = QTreeWidgetItem(self.tree, [f"{first['title']}  ({len(modules)})"])
            top.setData(0, Qt.UserRole, f"work:{work['key']}")
            top.setToolTip(0, roles)
            top.setFont(0, bold)
            top.setFlags(top.flags() & ~Qt.ItemIsSelectable)
            for mod in modules:
                role = tr(f"role.{mod['kind']}")
                label = f"{STATUS_GLYPH.get(mod['index_status'], '○')} " \
                        f"{role} · {mod['abbreviation'] or mod['filename']}"
                top.addChild(self._module_item(mod, label))
            top.setExpanded(f"work:{work['key']}" in expanded)

    # ── interacción ──────────────────────────────────────────────────────
    def _apply_filter(self, text: str) -> None:
        needle = (text or "").strip().lower()
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            if top.childCount() == 0:
                top.setHidden(bool(needle) and needle not in top.text(0).lower())
                continue
            visible = 0
            for j in range(top.childCount()):
                child = top.child(j)
                match = not needle or needle in child.text(0).lower() \
                    or needle in top.text(0).lower()
                child.setHidden(not match)
                if match:
                    visible += 1
            top.setHidden(visible == 0)
            if needle and visible:
                top.setExpanded(True)

    def _module_id(self, item: QTreeWidgetItem) -> int | None:
        data = item.data(0, Qt.UserRole)
        return data if isinstance(data, int) else None

    def _on_click(self, item: QTreeWidgetItem, _column: int = 0) -> None:
        """Un solo clic carga el recurso; en una agrupación, la despliega."""
        mid = self._module_id(item)
        if mid is not None:
            self.module_activated.emit(mid)
            return
        data = item.data(0, Qt.UserRole)
        if isinstance(data, str) and data.startswith(("kind:", "work:")):
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
            if isinstance(data, str) and data.startswith("kind:"):
                kind = data.split(":", 1)[1]
                act = QAction(tr("sidebar.ctx.index_category"), self)
                act.triggered.connect(lambda: self.index_kind_requested.emit(kind))
                menu.addAction(act)
        if menu.actions():
            menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _reveal(self, path: str) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
