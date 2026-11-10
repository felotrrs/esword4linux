"""Panel lateral: carpeta de recursos agrupada por categoría, desplegable."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (
    QLabel, QLineEdit, QMenu, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from ..core.catalog import KIND_LABELS, KIND_ORDER
from ..core.context import AppContext
from ..i18n import tr

STATUS_GLYPH = {"ready": "●", "pending": "○", "indexing": "◐", "failed": "✕"}


class Sidebar(QWidget):
    module_activated = Signal(int)
    index_module_requested = Signal(int)
    index_kind_requested = Signal(str)

    def __init__(self, ctx: AppContext, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.settings = ctx.settings
        self.setMinimumWidth(260)
        self.setMaximumWidth(460)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        head = QWidget()
        head_row = QVBoxLayout(head)
        head_row.setContentsMargins(12, 10, 12, 6)
        head_row.setSpacing(0)
        title = QLabel(tr("sidebar.title"))
        title.setObjectName("appTitle")
        row = QVBoxLayout()
        row.setSpacing(0)
        row.addWidget(title)
        row.addWidget(self._folder_label())
        head_row.addLayout(row)
        layout.addWidget(head)

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

    def _folder_label(self) -> QLabel:
        label = QLabel(self.settings.resources_dir)
        label.setObjectName("appSubtitle")
        label.setToolTip(self.settings.resources_dir)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        return label

    # ── construcción del árbol ───────────────────────────────────────────
    def refresh(self) -> None:
        expanded = {
            self.tree.topLevelItem(i).data(0, Qt.UserRole)
            for i in range(self.tree.topLevelItemCount())
            if self.tree.topLevelItem(i).isExpanded()
        }
        self.tree.clear()
        counts = self.ctx.catalog.counts_by_kind()
        modules = self.ctx.catalog.modules()
        by_kind: dict[str, list[dict]] = {}
        for mod in modules:
            by_kind.setdefault(mod["kind"], []).append(mod)

        bold = QFont()
        bold.setBold(True)

        for kind in KIND_ORDER:
            items = by_kind.get(kind)
            if not items:
                continue
            label = tr(f"kind.{kind}")
            top = QTreeWidgetItem(self.tree, [f"{label}  ({len(items)})"])
            top.setData(0, Qt.UserRole, f"kind:{kind}")
            top.setFont(0, bold)
            top.setFlags(top.flags() & ~Qt.ItemIsSelectable)
            for mod in items:
                status = mod["index_status"]
                glyph = STATUS_GLYPH.get(status, "○")
                lock = " 🔒" if mod["encrypted"] else ""
                text = f"{glyph} {mod['title']}{lock}"
                child = QTreeWidgetItem(top, [text])
                child.setData(0, Qt.UserRole, mod["id"])
                child.setToolTip(
                    0,
                    f"{mod['title']}\n{mod['rel_path']}\n"
                    f"{mod['entries']} entradas · {mod['size'] / 1e6:.1f} MB\n"
                    f"estado: {status}",
                )
                if status == "ready":
                    child.setForeground(0, Qt.GlobalColor.darkGreen)
                elif status == "failed":
                    child.setForeground(0, Qt.GlobalColor.darkRed)
            if kind in expanded:
                top.setExpanded(True)
        self._apply_filter(self.filter.text())

    # ── interacción ──────────────────────────────────────────────────────
    def _apply_filter(self, text: str) -> None:
        needle = (text or "").strip().lower()
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            visible_children = 0
            for j in range(top.childCount()):
                child = top.child(j)
                match = not needle or needle in child.text(0).lower()
                child.setHidden(not match)
                if match:
                    visible_children += 1
            top.setHidden(visible_children == 0)
            if needle and visible_children:
                top.setExpanded(True)

    def _module_id(self, item: QTreeWidgetItem) -> int | None:
        data = item.data(0, Qt.UserRole)
        return data if isinstance(data, int) else None

    def _on_click(self, item: QTreeWidgetItem, _column: int = 0) -> None:
        """Un solo clic carga el recurso; en una categoría, la despliega."""
        mid = self._module_id(item)
        if mid is not None:
            self.module_activated.emit(mid)
            return
        data = item.data(0, Qt.UserRole)
        if isinstance(data, str) and data.startswith("kind:"):
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
