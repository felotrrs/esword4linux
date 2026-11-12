"""Ventana principal: panel lateral + pestañas-vista (workspaces)."""

from __future__ import annotations

import base64
import string

from PySide6.QtCore import QByteArray, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QKeySequence, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QInputDialog, QLabel, QMainWindow, QMenu, QMessageBox,
    QProgressBar, QSizePolicy, QSplitter, QTabBar, QTabWidget, QToolButton,
    QVBoxLayout, QWidget,
)

from .. import __version__, i18n
from ..config import asset
from ..core.books import Reference, parse_reference
from ..core.catalog import KIND_ORDER, Catalog
from ..core.context import AppContext
from ..core.indexer import Indexer
from ..core.store import ContentStore
from ..i18n import tr
from .checkstyle import set_theme as set_check_style_theme
from .search_view import SearchView
from .sidebar import Sidebar
from .rich_browser import RichBrowser
from .tab_bar import ColoredTabBar
from .tasks import Worker
from .theme import palette, stylesheet
from .workspace import Workspace
from .entry_dialog import EntryDialog

# La pestaña 0 es «Buscar» (fija). Las pestañas-vista empiezan en 1.
FIXED_TABS = 1
SIDEBAR_MIN_WIDTH = 240
SIDEBAR_HANDLE_WIDTH = 15

TAB_COLORS = [
    "#c9973f", "#4a7fb5", "#5f9a6b", "#b5564a",
    "#8a6aa8", "#4a9a9a", "#c97a3f", "#7a7568",
]


def color_dot(color: str, size: int = 12) -> QIcon:
    pm = QPixmap(QSize(size, size))
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(1, 1, size - 2, size - 2)
    painter.end()
    return QIcon(pm)


def search_icon(color: str = "#8a8378", size: int = 14) -> QIcon:
    pm = QPixmap(QSize(size, size))
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color), 1.7)
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    d = size - 6
    painter.drawEllipse(1, 1, d, d)
    painter.drawLine(d - 1, d - 1, size - 2, size - 2)
    painter.end()
    return QIcon(pm)


class MainWindow(QMainWindow):
    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        self.settings = ctx.settings
        self._worker: Worker | None = None
        self._workspaces: list[Workspace] = []
        self._closing = False
        self._sidebar_width = 290
        self._build_ui()
        self._build_menus()
        self._restore_state()
        self._refresh_status()
        QTimer.singleShot(200, self._bootstrap)

    # ── UI ───────────────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        self.setWindowTitle(tr("app.title"))
        self.setWindowIcon(QIcon(str(asset("linuxesword.png"))))
        self.resize(1400, 900)

        self.sidebar = Sidebar(self.ctx)
        self.sidebar.module_activated.connect(self.open_resource)
        self.sidebar.index_module_requested.connect(self._index_single)
        self.sidebar.index_kind_requested.connect(self._index_kind)

        self.tabs = QTabWidget()
        self.tabs.setTabBar(ColoredTabBar(self.tabs))
        self.tabs.setTabsClosable(False)   # el cierre lo pinta la barra custom
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.tabBar().tabCloseRequested.connect(self._close_tab)
        self.tabs.tabBar().new_tab_requested.connect(lambda: self._add_workspace())
        self.tabs.tabBar().setContextMenuPolicy(Qt.CustomContextMenu)
        self.tabs.tabBar().customContextMenuRequested.connect(self._tab_menu)
        self.tabs.currentChanged.connect(self._on_tab_changed)

        self.search = SearchView(self.ctx)
        self.search.open_hit.connect(self._open_hit)
        self.search.go_reference.connect(self._go_reference)
        p = palette(self.settings.theme)
        self.tabs.addTab(self.search, search_icon(p.muted), tr("search.tab"))

        self.sidebar_dock = self._build_sidebar_dock()
        self.sidebar.setVisible(self.settings.sidebar_visible)
        self._apply_tab_palette()

        split = QSplitter(Qt.Horizontal)
        split.addWidget(self.sidebar_dock)
        split.addWidget(self.tabs)
        split.setChildrenCollapsible(False)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setSizes([290, 1110])
        self._split = split
        self.setCentralWidget(split)
        self._apply_sidebar_constraints(self.settings.sidebar_visible)

        self.lbl_status = QLabel("")
        self.progress = QProgressBar()
        self.progress.setFixedWidth(220)
        self.progress.setFixedHeight(8)
        self.progress.setTextVisible(False)
        self.progress.hide()
        self.statusBar().addWidget(self.lbl_status, 1)
        self.statusBar().addPermanentWidget(self.progress)

    def _build_sidebar_dock(self) -> QWidget:
        """Panel lateral + asa vertical en su borde superior para plegarlo."""
        dock = QWidget()
        row = QHBoxLayout(dock)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addWidget(self.sidebar, 1)

        self.sidebar_handle = QToolButton()
        self.sidebar_handle.setObjectName("sidebarHandle")
        self.sidebar_handle.setText("‹" if self.settings.sidebar_visible else "›")
        self.sidebar_handle.setFixedSize(15, 26)
        self.sidebar_handle.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.sidebar_handle.setToolTip(tr("sidebar.hide") + "  (Ctrl+B)")
        self.sidebar_handle.setCursor(Qt.PointingHandCursor)
        self.sidebar_handle.clicked.connect(self.toggle_sidebar)
        row.addWidget(self.sidebar_handle, 0, Qt.AlignTop)
        dock.setMinimumWidth(SIDEBAR_HANDLE_WIDTH)
        return dock

    def _apply_sidebar_constraints(self, visible: bool) -> None:
        """Con el panel visible, el splitter no puede reducirlo a la nada."""
        if visible:
            self.sidebar_dock.setMinimumWidth(
                SIDEBAR_MIN_WIDTH + SIDEBAR_HANDLE_WIDTH
            )
            self.sidebar_dock.setMaximumWidth(16777215)
        else:
            self.sidebar_dock.setMinimumWidth(SIDEBAR_HANDLE_WIDTH)
            self.sidebar_dock.setMaximumWidth(16)

    def _apply_tab_palette(self) -> None:
        bar = self.tabs.tabBar()
        if isinstance(bar, ColoredTabBar):
            p = palette(self.settings.theme)
            bar.set_palette_colors(
                selected_bg=p.bg, panel_bg=p.panel, border=p.border,
                text=p.text, muted=p.muted,
            )

    def _build_menus(self) -> None:
        for name in ("act_find", "act_new"):
            old = getattr(self, name, None)
            if old is not None:
                self.removeAction(old)
        bar = self.menuBar()

        m_file = bar.addMenu(tr("menu.file"))
        act_scan = QAction(tr("menu.file.scan"), self)
        act_scan.setShortcut(QKeySequence("Ctrl+R"))
        act_scan.triggered.connect(self._start_scan)
        m_file.addAction(act_scan)
        act_folder = QAction(tr("menu.file.choose_folder"), self)
        act_folder.triggered.connect(lambda: self._choose_folder(first_run=False))
        m_file.addAction(act_folder)
        m_file.addSeparator()
        act_quit = QAction(tr("menu.file.quit"), self)
        act_quit.setShortcut(QKeySequence("Ctrl+Q"))
        act_quit.triggered.connect(self.close)
        m_file.addAction(act_quit)

        m_view = bar.addMenu(tr("menu.view"))
        self.act_sidebar = QAction(tr("menu.view.sidebar"), self)
        self.act_sidebar.setCheckable(True)
        self.act_sidebar.setChecked(self.settings.sidebar_visible)
        self.act_sidebar.setShortcut(QKeySequence("Ctrl+B"))
        self.act_sidebar.triggered.connect(self.toggle_sidebar)
        m_view.addAction(self.act_sidebar)
        act_unclass = QAction(tr("menu.view.show_unclassified"), self)
        act_unclass.setCheckable(True)
        act_unclass.setChecked(getattr(self.settings, "show_unclassified", False))
        act_unclass.triggered.connect(self._toggle_show_unclassified)
        m_view.addAction(act_unclass)
        m_view.addSeparator()
        group = QActionGroup(self)
        group.setExclusive(True)
        for theme, key in (("light", "menu.view.theme_light"), ("dark", "menu.view.theme_dark")):
            act = QAction(tr(key), self)
            act.setCheckable(True)
            act.setChecked(self.settings.theme == theme)
            act.triggered.connect(lambda _=False, t=theme: self._set_theme(t))
            group.addAction(act)
            m_view.addAction(act)
        m_view.addSeparator()
        self.menu_strong = m_view.addMenu(tr("menu.view.strong"))
        self.menu_strong.aboutToShow.connect(self._fill_strong_menu)
        lang_menu = m_view.addMenu(tr("menu.view.language"))
        glang = QActionGroup(self)
        glang.setExclusive(True)
        for code, label in (("es", "Español"), ("en", "English")):
            act = QAction(label, self)
            act.setCheckable(True)
            act.setChecked(self.settings.locale == code)
            act.triggered.connect(lambda _=False, c=code: self._set_locale(c))
            glang.addAction(act)
            lang_menu.addAction(act)

        m_index = bar.addMenu(tr("menu.index"))
        act_enc = QAction(tr("menu.index.encrypted"), self)
        act_enc.triggered.connect(lambda: self._prepare_encrypted(force=True))
        m_index.addAction(act_enc)
        act_pending = QAction(tr("menu.index.pending"), self)
        act_pending.triggered.connect(self._index_pending)
        m_index.addAction(act_pending)
        act_all = QAction(tr("menu.index.all"), self)
        act_all.triggered.connect(lambda: self._index_kinds(KIND_ORDER, tr("menu.index.all")))
        m_index.addAction(act_all)
        m_index.addSeparator()
        cat_menu = m_index.addMenu(tr("menu.index.category"))
        counts = self.ctx.catalog.counts_by_kind()
        for kind in KIND_ORDER:
            if not counts.get(kind):
                continue
            act = QAction(f"{tr(f'kind.{kind}')} ({counts[kind]})", self)
            act.triggered.connect(lambda _=False, k=kind: self._index_kind(k))
            cat_menu.addAction(act)

        m_help = bar.addMenu(tr("menu.help"))
        act_about = QAction(tr("menu.help.about"), self)
        act_about.triggered.connect(self._about)
        m_help.addAction(act_about)

        self.act_find = QAction(self)
        self.act_find.setShortcut(QKeySequence("Ctrl+F"))
        self.act_find.triggered.connect(self._focus_search)
        self.addAction(self.act_find)
        self.act_new = QAction(self)
        self.act_new.setShortcut(QKeySequence("Ctrl+T"))
        self.act_new.triggered.connect(lambda: self._add_workspace())
        self.addAction(self.act_new)

    # ── pestañas-vista ───────────────────────────────────────────────────
    def _next_name(self) -> tuple[str, str]:
        used = {ws.name for ws in self._workspaces}
        for letter in string.ascii_uppercase:
            name = tr("workspace.default_name", letter=letter)
            if name not in used:
                return letter, name
        letter = str(len(self._workspaces) + 1)
        return letter, tr("workspace.default_name", letter=letter)

    def _add_workspace(self, name: str | None = None, color: str | None = None,
                       state: dict | None = None, activate: bool = True) -> Workspace:
        auto_letter = ""
        if name is None:
            auto_letter, name = self._next_name()
        color = color or TAB_COLORS[len(self._workspaces) % len(TAB_COLORS)]
        ws = Workspace(self.ctx, name, color)
        ws.name_auto = bool(auto_letter)
        ws.auto_letter = auto_letter
        ws.reference_changed.connect(self._on_reference_changed)
        ws.search_requested.connect(self._search_for)
        ws.open_module.connect(self._open_entry_dialog)
        ws.reference_requested.connect(self._go_reference)

        if state:
            ws.apply_state(state)
        else:
            default = self.ctx.catalog.by_rel_path(self.settings.bible_module)
            if default is None:
                bibles = self.ctx.bibles()
                default = bibles[0] if bibles else None
            ws.set_main(default)

        idx = self.tabs.addTab(ws, ws.name)
        self.tabs.tabBar().set_tab_color(idx, ws.color)
        self.tabs.setTabToolTip(idx, self._workspace_tooltip(ws))
        self._workspaces.append(ws)
        if activate:
            self.tabs.setCurrentIndex(idx)
        return ws

    def _workspace_tooltip(self, ws: Workspace) -> str:
        row = self.ctx.catalog.by_rel_path(ws.main_rel) if ws.main_rel else None
        title = row["title"] if row else tr("main.no_resource")
        return f"{ws.name} · {title}"

    def _current_workspace(self) -> Workspace | None:
        widget = self.tabs.currentWidget()
        return widget if isinstance(widget, Workspace) else None

    def _active_workspace(self) -> Workspace:
        """Pestaña activa; si estamos en «Buscar», la última usada."""
        ws = self._current_workspace()
        if ws is not None:
            return ws
        idx = self.settings.workspace_active
        if 0 <= idx < len(self._workspaces):
            return self._workspaces[idx]
        return self._workspaces[0] if self._workspaces else self._add_workspace()

    def _workspace_index(self, ws: Workspace) -> int:
        return self.tabs.indexOf(ws)

    def _close_tab(self, index: int) -> None:
        if index < FIXED_TABS:
            return
        widget = self.tabs.widget(index)
        if len(self._workspaces) <= 1:
            self.statusBar().showMessage(tr("workspace.last"), 4000)
            return
        if isinstance(widget, Workspace) and widget in self._workspaces:
            self._workspaces.remove(widget)
        self.tabs.removeTab(index)
        widget.deleteLater()

    def _tab_menu(self, pos) -> None:
        index = self.tabs.tabBar().tabAt(pos)
        if index < FIXED_TABS:
            return
        widget = self.tabs.widget(index)
        if not isinstance(widget, Workspace):
            return
        ws = widget
        menu = QMenu(self)
        act_rename = QAction(tr("workspace.rename"), self)
        act_rename.triggered.connect(lambda: self._rename_workspace(ws))
        menu.addAction(act_rename)
        colors = menu.addMenu(tr("workspace.color"))
        for color in TAB_COLORS:
            act = QAction(color_dot(color, 14), color, self)
            act.triggered.connect(lambda _=False, c=color: self._set_workspace_color(ws, c))
            colors.addAction(act)
        menu.addSeparator()
        act_close = QAction(tr("workspace.close"), self)
        act_close.triggered.connect(lambda: self._close_tab(self._workspace_index(ws)))
        menu.addAction(act_close)
        menu.exec(self.tabs.tabBar().mapToGlobal(pos))

    def _rename_workspace(self, ws: Workspace) -> None:
        name, ok = QInputDialog.getText(
            self, tr("workspace.rename"), tr("workspace.rename_prompt"), text=ws.name
        )
        if ok and name.strip():
            ws.name = name.strip()
            idx = self._workspace_index(ws)
            self.tabs.setTabText(idx, ws.name)
            self.tabs.setTabToolTip(idx, self._workspace_tooltip(ws))
            self._save_state()

    def _set_workspace_color(self, ws: Workspace, color: str) -> None:
        ws.color = color
        idx = self._workspace_index(ws)
        self.tabs.tabBar().set_tab_color(idx, color)
        self._save_state()

    def _on_tab_changed(self, index: int) -> None:
        widget = self.tabs.widget(index)
        if isinstance(widget, Workspace):
            self.settings.workspace_active = self._workspaces.index(widget) \
                if widget in self._workspaces else 0
            self._refresh_status()

    def toggle_sidebar(self) -> None:
        visible = not self.sidebar.isVisible()
        sizes = self._split.sizes()
        total = max(sum(sizes), 400)
        self._apply_sidebar_constraints(visible)
        if visible:
            self.sidebar.show()
            width = min(
                self._sidebar_width or 290,
                max(SIDEBAR_MIN_WIDTH, total - 240),
            )
            self._split.setSizes([width, max(240, total - width)])
        else:
            self._sidebar_width = max(SIDEBAR_MIN_WIDTH, self.sidebar.width())
            self.sidebar.hide()
            self._split.setSizes([SIDEBAR_HANDLE_WIDTH, max(240, total - SIDEBAR_HANDLE_WIDTH)])
        self.sidebar_handle.setText("‹" if visible else "›")
        self.sidebar_handle.setToolTip(
            tr("sidebar.hide" if visible else "sidebar.show") + "  (Ctrl+B)"
        )
        self.settings.sidebar_visible = visible
        self.settings.save()
        if hasattr(self, "act_sidebar"):
            self.act_sidebar.setChecked(visible)

    def _toggle_show_unclassified(self, checked: bool) -> None:
        self.settings.show_unclassified = checked
        self.settings.save()
        self.sidebar.refresh()

    # ── recursos ─────────────────────────────────────────────────────────
    def open_resource(self, module_id: int) -> None:
        """Clic en el panel lateral: carga el recurso en la pestaña activa."""
        row = self.ctx.catalog.module(module_id)
        if not row:
            return
        ws = self._active_workspace()
        ws.set_main(row)
        idx = self._workspace_index(ws)
        if idx >= 0:
            self.tabs.setTabToolTip(idx, self._workspace_tooltip(ws))
            self.tabs.setCurrentIndex(idx)
        self._refresh_status()

    def _open_module_tab(self, module_id: int, ref: str | None = None) -> None:
        """Abre un módulo como recurso principal de una pestaña nueva."""
        row = self.ctx.catalog.module(module_id)
        if not row:
            return
        ws = self._add_workspace()
        ws.set_main(row, ref=ref)
        idx = self._workspace_index(ws)
        if idx >= 0:
            self.tabs.setTabToolTip(idx, self._workspace_tooltip(ws))

    def _open_entry_dialog(self, module_id: int, ref: str = "") -> None:
        """Lectura completa de una entrada sin crear pestañas."""
        row = self.ctx.catalog.module(module_id)
        if not row:
            return
        if not ref:
            ref = "1" if row.get("kind") == "bible" else ""
        dialog = EntryDialog(self.ctx, row, ref, self)
        dialog.exec()

    def _bible_workspace(self) -> Workspace:
        ws = self._current_workspace()
        if ws is not None and ws.is_bible():
            return ws
        for candidate in self._workspaces:
            if candidate.is_bible():
                return candidate
        ws = ws or self._add_workspace()
        default = self.ctx.catalog.by_rel_path(self.settings.bible_module)
        if default:
            ws.set_main(default)
        return ws

    def _go_reference(self, ref_text: str) -> None:
        ref = parse_reference(ref_text)
        if ref is None:
            import re

            m = re.search(r"([1-3]?\s*[A-Za-zÁÉÍÓÚÑáéíóúñ]+)\s+(\d+)(?::(\d+))?", ref_text)
            if m:
                ref = parse_reference(
                    f"{m.group(1)} {m.group(2)}" + (f":{m.group(3)}" if m.group(3) else "")
                )
        if not ref:
            return
        ws = self._bible_workspace()
        ws.bible.navigate(ref)
        idx = self._workspace_index(ws)
        if idx >= 0:
            self.tabs.setCurrentIndex(idx)

    def _open_hit(self, module_id: int, ref: str, kind: str) -> None:
        row = self.ctx.catalog.module(module_id)
        if not row:
            return
        if row["kind"] == "bible":
            ws = self._bible_workspace()
            if ws.main_rel != row["rel_path"]:
                ws.set_main(row)
            book, _, rest = ref.partition(":")
            chapter, _, verse = rest.partition(":")
            try:
                ws.bible.navigate(Reference(int(book), int(chapter), int(verse) or None))
            except ValueError:
                pass
            idx = self._workspace_index(ws)
            if idx >= 0:
                self.tabs.setCurrentIndex(idx)
            return
        ws = self._active_workspace()
        ws.set_main(row, ref=ref)
        idx = self._workspace_index(ws)
        if idx >= 0:
            self.tabs.setCurrentIndex(idx)
            self.tabs.setTabToolTip(idx, self._workspace_tooltip(ws))

    def _focus_search(self) -> None:
        self.tabs.setCurrentIndex(0)
        self.search.query.setFocus()
        self.search.query.selectAll()

    def _search_for(self, text: str) -> None:
        self.tabs.setCurrentIndex(0)
        self.search.set_query(text)

    def _on_reference_changed(self, label: str) -> None:
        self.settings.last_reference = label
        self.lbl_status.setText(f"{tr('status.ready')} · {label}")

    # ── estado ───────────────────────────────────────────────────────────
    def _restore_state(self) -> None:
        if self.settings.window_geometry:
            try:
                self.restoreGeometry(QByteArray(base64.b64decode(self.settings.window_geometry)))
            except (ValueError, TypeError):
                pass
        states = self.settings.workspaces or []
        if states:
            for state in states:
                try:
                    self._add_workspace(state=state, activate=False)
                except Exception:
                    continue
        if not self._workspaces:
            self._add_workspace(activate=False)
        idx = min(FIXED_TABS + max(0, self.settings.workspace_active),
                  self.tabs.count() - 1)
        self.tabs.setCurrentIndex(idx)

    def _save_state(self) -> None:
        self.settings.window_geometry = base64.b64encode(
            bytes(self.saveGeometry())
        ).decode("ascii")
        self.settings.workspaces = [ws.state() for ws in self._workspaces]
        current = self._current_workspace()
        if current is not None and current in self._workspaces:
            self.settings.workspace_active = self._workspaces.index(current)
        self.settings.save()

    def closeEvent(self, event) -> None:  # noqa: N802
        self._closing = True
        if self._worker and self._worker.isRunning():
            self._worker.requestInterruption()
            self._worker.wait(3000)
        self._save_state()
        self.ctx.close_all()
        super().closeEvent(event)

    # ── tema / idioma ────────────────────────────────────────────────────
    def _set_theme(self, theme: str) -> None:
        self.settings.theme = theme
        self.settings.save()
        set_check_style_theme(theme)
        p = palette(theme)
        self.tabs.setTabIcon(0, search_icon(p.muted))
        self.setStyleSheet(stylesheet(theme, self.settings.font_size))
        self._apply_tab_palette()
        for ws in self._workspaces:
            ws.reload_theme()
        self.search.run_search()

    def _fill_strong_menu(self) -> None:
        menu = self.menu_strong
        menu.clear()
        act_auto = QAction(tr("strong.auto"), self)
        act_auto.setCheckable(True)
        act_auto.setChecked(not self.settings.strong_rel)
        act_auto.triggered.connect(lambda: self._set_strong_default(""))
        menu.addAction(act_auto)
        menu.addSeparator()
        for mod in self.ctx.strong.candidates():
            act = QAction(f"{mod['abbreviation']} — {mod['title'][:60]}", self)
            act.setCheckable(True)
            act.setChecked(self.settings.strong_rel == mod["rel_path"])
            act.triggered.connect(
                lambda _=False, rel=mod["rel_path"]: self._set_strong_default(rel)
            )
            menu.addAction(act)

    def _set_strong_default(self, rel_path: str) -> None:
        self.ctx.strong.set_default(rel_path)
        RichBrowser.clear_all_caches()
        self.ctx.refs.clear()
        for ws in self._workspaces:
            ws.bible.strong.refresh_lexicons()
        row = self.ctx.strong.module()
        label = (f"{row['abbreviation']} — {row['title'][:60]}"
                 if row else tr("strong.bubble_auto"))
        self.statusBar().showMessage(
            tr("strong.bubble_status", label=label), 8000
        )

    def _set_locale(self, code: str) -> None:
        self.settings.locale = code
        self.settings.save()
        i18n.set_locale(code)
        self._retranslate_ui()

    def _retranslate_ui(self) -> None:
        self.setWindowTitle(tr("app.title"))
        self.menuBar().clear()
        self._build_menus()
        self.sidebar.retranslate()
        for ws in self._workspaces:
            ws.retranslate()
            idx = self._workspace_index(ws)
            if idx >= 0:
                self.tabs.setTabText(idx, ws.name)
                self.tabs.setTabToolTip(idx, self._workspace_tooltip(ws))
        self.tabs.setTabText(0, tr("search.tab"))
        p = palette(self.settings.theme)
        self.tabs.setTabIcon(0, search_icon(p.muted))
        self.search.retranslate()
        self._refresh_status()

    # ── escaneo ──────────────────────────────────────────────────────────
    def _bootstrap(self) -> None:
        from pathlib import Path

        if self._closing:
            return
        if not Path(self.settings.resources_dir).is_dir():
            self._choose_folder(first_run=True)
            return
        if self.ctx.catalog.is_empty():
            self._start_scan(auto_index=True)
        elif self.ctx.catalog.needs_metadata_refresh():
            # Actualiza metadatos (idioma incluido) sin tocar los índices;
            # después sigue el arranque normal (preindexado pendiente).
            self._start_scan(auto_index=True)
        else:
            self._auto_index()

    def _choose_folder(self, first_run: bool) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, tr("dialog.choose_folder"), self.settings.resources_dir
        )
        if not folder:
            if first_run:
                QMessageBox.warning(self, tr("dialog.first_run.title"), tr("dialog.first_run.text"))
            return
        self.settings.resources_dir = folder
        self.settings.save()
        self._start_scan(auto_index=True)

    def _start_scan(self, auto_index: bool = False) -> None:
        if self._busy():
            return
        self.statusBar().showMessage(tr("status.scanning"))
        self.progress.show()
        self.progress.setRange(0, 0)

        def task(progress):
            cat = Catalog(self.settings.catalog_db)
            try:
                return cat.scan(self.settings.resources_path, progress=progress)
            finally:
                cat.close()

        worker = Worker(task, self)
        worker.progress.connect(self._on_progress_scan)
        worker.done.connect(lambda result: self._scan_done(result, auto_index))
        worker.failed.connect(self._on_error)
        self._run(worker)

    def _on_progress_scan(self, done: int, total: int, label: str) -> None:
        self.progress.setRange(0, max(1, total))
        self.progress.setValue(done)
        self.statusBar().showMessage(f"{tr('status.scanning')} {done}/{total} {label[:40]}")

    def _scan_done(self, result, auto_index: bool) -> None:
        self._idle()
        self.sidebar.refresh()
        self._refresh_status()
        counts = self.ctx.catalog.counts_by_kind()
        total = sum(counts.values())
        self.statusBar().showMessage(
            f"{tr('status.modules', n=total)} · {result.added} nuevos · "
            f"{result.updated} actualizados · {result.seconds:.1f}s", 8000
        )
        if auto_index:
            self._auto_index()

    # ── indexación ───────────────────────────────────────────────────────
    def _auto_index(self) -> None:
        pending = [
            m for m in self.ctx.catalog.modules()
            if m["rel_path"] in self.settings.preindex and m["index_status"] != "ready"
        ]
        if pending:
            self._index_paths([m["rel_path"] for m in pending], tr("menu.index.pending"),
                              then=self._prepare_encrypted)
        else:
            self._prepare_encrypted()

    def _prepare_encrypted(self, force: bool = False) -> None:
        """Descifra e indexa todos los módulos cifrados (bajo demanda del usuario)."""
        if self._busy():
            return
        encrypted = [m for m in self.ctx.catalog.modules()
                     if m["encrypted"] and m["kind"] != "unknown"]
        if not encrypted:
            return
        pending = [m for m in encrypted if m["index_status"] != "ready"]
        if not pending:
            self.settings.encrypted_ready = True
            self.settings.save()
            return
        if not force and self.settings.encrypted_ready:
            return
        self._index_paths(
            [m["rel_path"] for m in pending],
            tr("menu.index.encrypted"),
        )

    def _index_single(self, module_id: int) -> None:
        row = self.ctx.catalog.module(module_id)
        if row:
            self._index_paths([row["rel_path"]], row["title"])

    def _index_kind(self, kind: str) -> None:
        self._index_kinds([kind], tr(f"kind.{kind}"))

    def _index_pending(self) -> None:
        pending = self.ctx.indexer.pending_modules()
        if pending:
            self._index_paths([m["rel_path"] for m in pending], tr("menu.index.pending"))

    def _index_kinds(self, kinds: list[str], label: str) -> None:
        self._index_worker(lambda idx, cb: idx.index_kind_list(kinds, progress=cb), label)

    def _index_paths(self, rel_paths: list[str], label: str, then=None) -> None:
        def runner(idx, cb):
            result = idx.index_paths(rel_paths, progress=cb)
            if then is not None:
                result["then"] = then
            return result

        self._index_worker(runner, label)

    def _index_worker(self, fn, label: str) -> None:
        if self._busy():
            return
        self.progress.show()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.statusBar().showMessage(f"{tr('status.indexing')} {label}")

        def task(progress):
            cat = Catalog(self.settings.catalog_db)
            store = ContentStore(self.settings.content_db)
            try:
                indexer = Indexer(cat, store)
                return fn(indexer, progress)
            finally:
                cat.close()
                store.close()

        worker = Worker(task, self)
        worker.progress.connect(self._on_progress_index)
        worker.done.connect(self._index_done)
        worker.failed.connect(self._on_error)
        self._run(worker)

    def _on_progress_index(self, done: int, total: int, label: str) -> None:
        self.progress.setRange(0, max(1, total))
        self.progress.setValue(done)
        self.statusBar().showMessage(f"{tr('status.indexing')} {done}/{total} {label[:48]}")

    def _index_done(self, result: dict) -> None:
        self._idle()
        self.sidebar.refresh()
        self._refresh_status()
        self.search.run_search()
        msg = tr("index.done", indexed=result.get("indexed", 0), pages=result.get("pages", 0))
        if result.get("failed"):
            msg += " · " + tr("index.failed", n=result["failed"])
        self.statusBar().showMessage(msg, 12000)

        encrypted = [m for m in self.ctx.catalog.modules()
                     if m["encrypted"] and m["kind"] != "unknown"]
        if encrypted and all(m["index_status"] == "ready" for m in encrypted):
            self.settings.encrypted_ready = True
            self.settings.save()

        then = result.get("then")
        if callable(then):
            QTimer.singleShot(400, then)

    # ── workers ──────────────────────────────────────────────────────────
    def _run(self, worker: Worker) -> None:
        self._worker = worker
        self.sidebar.setEnabled(False)
        worker.finished.connect(self._worker_finished)
        worker.start()

    def _worker_finished(self) -> None:
        worker = self._worker
        self._worker = None
        if worker:
            worker.deleteLater()
        self.sidebar.setEnabled(True)

    def _busy(self) -> bool:
        if self._worker and self._worker.isRunning():
            self.statusBar().showMessage(tr("status.indexing"), 3000)
            return True
        return False

    def _idle(self) -> None:
        self.progress.hide()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)

    def _on_error(self, message: str) -> None:
        self._idle()
        self._worker = None
        self.sidebar.setEnabled(True)
        QMessageBox.critical(self, tr("dialog.error"), message)

    def _refresh_status(self) -> None:
        counts = self.ctx.catalog.counts_by_kind()
        total = sum(counts.values())
        status = self.ctx.catalog.status_counts()
        indexed = status.get("ready", 0)
        pages = self.ctx.store.total_pages()
        size = self.ctx.store.db_size() / 1e6
        self.lbl_status.setText(
            f"{tr('status.modules', n=total)} · {tr('status.indexed', n=indexed)} · "
            f"{tr('status.pages', n=pages)} · {size:.0f} MB"
        )

    def _about(self) -> None:
        logo = str(asset("linuxesword-about.png"))
        box = QMessageBox(self)
        box.setWindowTitle(tr("dialog.about.title"))
        box.setTextFormat(Qt.RichText)
        box.setText(tr("dialog.about.text", version=__version__))
        pm = QPixmap(logo)
        if not pm.isNull():
            box.setIconPixmap(pm.scaled(160, 160, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        box.exec()
