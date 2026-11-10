"""Ventana principal: panel lateral + pestañas centrales modificables."""

from __future__ import annotations

import base64
import json
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QLabel, QMainWindow, QMenu,
    QMessageBox, QProgressBar, QSplitter, QTabWidget, QVBoxLayout, QWidget,
)

from .. import __version__
from ..core.books import Reference, parse_reference
from ..core.catalog import KIND_LABELS, KIND_ORDER, Catalog
from ..core.context import AppContext
from ..core.indexer import Indexer
from ..core.store import ContentStore
from ..i18n import tr
from .bible_view import BibleView
from .library_view import LibraryView
from .search_view import SearchView
from .sidebar import Sidebar
from .tasks import Worker
from .theme import stylesheet

FIXED_TABS = 2  # Biblia + Buscar


class MainWindow(QMainWindow):
    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        self.settings = ctx.settings
        self._worker: Worker | None = None
        self._index_tabs: dict[int, int] = {}
        self._build_ui()
        self._build_menus()
        self._restore_state()
        self._refresh_status()
        QTimer.singleShot(200, self._bootstrap)

    # ── UI ───────────────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        self.setWindowTitle(tr("app.title"))
        self.resize(1400, 900)

        self.sidebar = Sidebar(self.ctx)
        self.sidebar.module_activated.connect(self.open_module)
        self.sidebar.index_module_requested.connect(self._index_single)
        self.sidebar.index_kind_requested.connect(self._index_kind)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.tabCloseRequested.connect(self._close_tab)

        self.bible = BibleView(self.ctx)
        self.bible.open_module.connect(self.open_module)
        self.bible.search_requested.connect(self._search_for)
        self.bible.reference_changed.connect(self._on_reference_changed)
        self.tabs.addTab(self.bible, tr("bible.tab"))

        self.search = SearchView(self.ctx)
        self.search.open_hit.connect(self._open_hit)
        self.search.go_reference.connect(self._go_reference)
        self.tabs.addTab(self.search, tr("search.tab"))

        split = QSplitter(Qt.Horizontal)
        split.addWidget(self.sidebar)
        split.addWidget(self.tabs)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setSizes([300, 1100])
        self.setCentralWidget(split)

        self.lbl_status = QLabel("")
        self.progress = QProgressBar()
        self.progress.setFixedWidth(220)
        self.progress.setFixedHeight(8)
        self.progress.setTextVisible(False)
        self.progress.hide()
        self.statusBar().addWidget(self.lbl_status, 1)
        self.statusBar().addPermanentWidget(self.progress)

    def _build_menus(self) -> None:
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

        act_find = QAction(self)
        act_find.setShortcut(QKeySequence("Ctrl+F"))
        act_find.triggered.connect(self._focus_search)
        self.addAction(act_find)

    # ── estado ───────────────────────────────────────────────────────────
    def _restore_state(self) -> None:
        if self.settings.window_geometry:
            try:
                self.restoreGeometry(QByteArray(base64.b64decode(self.settings.window_geometry)))
            except (ValueError, TypeError):
                pass
        target = self.settings.last_reference
        ref = parse_reference(target) or Reference(43, 3, 16)
        self.bible.navigate(ref)
        for tab in self.settings.open_tabs:
            try:
                self.open_module(int(tab["module_id"]), tab.get("ref"), activate=False)
            except (KeyError, TypeError, ValueError):
                continue
        self.tabs.setCurrentIndex(0)

    def _save_state(self) -> None:
        self.settings.window_geometry = base64.b64encode(
            bytes(self.saveGeometry())
        ).decode("ascii")
        open_tabs = []
        for i in range(FIXED_TABS, self.tabs.count()):
            widget = self.tabs.widget(i)
            row = getattr(widget, "module_row", None)
            if row:
                open_tabs.append({"module_id": row["id"]})
        self.settings.open_tabs = open_tabs
        self.settings.save()

    def closeEvent(self, event) -> None:  # noqa: N802
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
        self.setStyleSheet(stylesheet(theme, self.settings.font_size))
        self.bible.reload()
        self.search.run_search()
        for i in range(FIXED_TABS, self.tabs.count()):
            widget = self.tabs.widget(i)
            if isinstance(widget, LibraryView):
                widget.reload_theme()

    def _set_locale(self, code: str) -> None:
        from .. import i18n

        self.settings.locale = code
        self.settings.save()
        i18n.set_locale(code)
        QMessageBox.information(
            self, tr("app.title"),
            "Idioma guardado. Reinicia linuxEsword para aplicarlo por completo."
            if code == "es" else
            "Language saved. Restart linuxEsword to apply it fully.",
        )

    # ── pestañas ─────────────────────────────────────────────────────────
    def open_module(self, module_id: int, ref: str | None = None,
                    activate: bool = True) -> None:
        row = self.ctx.catalog.module(module_id)
        if not row:
            return
        if row["kind"] == "bible":
            self.tabs.setCurrentIndex(0)
            target = parse_reference(ref) if ref else None
            if target:
                self.bible.navigate(target)
            return
        if module_id in self._index_tabs:
            idx = self._index_tabs[module_id]
            if idx < self.tabs.count():
                self.tabs.setCurrentIndex(idx)
                if ref:
                    view = self.tabs.widget(idx)
                    if isinstance(view, LibraryView):
                        view.initial_ref = ref
                        view._load_entries()
                return
        view = LibraryView(self.ctx, row, initial_ref=ref)
        view.open_reference.connect(self._go_reference)
        title = row["abbreviation"] or row["title"]
        idx = self.tabs.addTab(view, title[:26])
        self.tabs.setTabToolTip(idx, row["title"])
        self._index_tabs[module_id] = idx
        if activate:
            self.tabs.setCurrentIndex(idx)

    def _close_tab(self, index: int) -> None:
        if index < FIXED_TABS:
            return
        widget = self.tabs.widget(index)
        row = getattr(widget, "module_row", None)
        if row and row["id"] in self._index_tabs:
            del self._index_tabs[row["id"]]
        self.tabs.removeTab(index)
        widget.deleteLater()
        # reindexa el mapa de pestañas
        self._index_tabs = {
            mid: i for mid, i in self._index_tabs.items() if i < index
        }
        for i in range(FIXED_TABS, self.tabs.count()):
            w = self.tabs.widget(i)
            r = getattr(w, "module_row", None)
            if r:
                self._index_tabs[r["id"]] = i
        widget.deleteLater()

    def _focus_search(self) -> None:
        self.tabs.setCurrentIndex(1)
        self.search.query.setFocus()
        self.search.query.selectAll()

    def _search_for(self, text: str) -> None:
        self.tabs.setCurrentIndex(1)
        self.search.set_query(text)

    def _go_reference(self, ref_text: str) -> None:
        ref = parse_reference(ref_text)
        if ref is None:
            # pudo venir como "Juan 3:16" dentro de un título
            import re

            m = re.search(r"([1-3]?\s*[A-Za-zÁÉÍÓÚÑáéíóúñ]+)\s+(\d+)(?::(\d+))?", ref_text)
            if m:
                ref = parse_reference(f"{m.group(1)} {m.group(2)}" +
                                      (f":{m.group(3)}" if m.group(3) else ""))
        if ref:
            self.tabs.setCurrentIndex(0)
            self.bible.navigate(ref)

    def _open_hit(self, module_id: int, ref: str, kind: str) -> None:
        row = self.ctx.catalog.module(module_id)
        if not row:
            return
        if row["kind"] == "bible":
            book, _, rest = ref.partition(":")
            chapter, _, verse = rest.partition(":")
            try:
                self.tabs.setCurrentIndex(0)
                self.bible.navigate(Reference(int(book), int(chapter), int(verse) or None))
            except ValueError:
                pass
            return
        self.tabs.setCurrentIndex(1)
        self.open_module(module_id, ref)

    def _on_reference_changed(self, label: str) -> None:
        self.settings.last_reference = label
        self.lbl_status.setText(f"{tr('status.ready')} · {label}")

    # ── escaneo ──────────────────────────────────────────────────────────
    def _bootstrap(self) -> None:
        if not Path(self.settings.resources_dir).is_dir():
            self._choose_folder(first_run=True)
            return
        if self.ctx.catalog.is_empty():
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
        counts = self.ctx.catalog.counts_by_kind()
        total = sum(counts.values())
        self.statusBar().showMessage(
            f"{tr('status.modules', n=total)} · {result.added} nuevos · "
            f"{result.updated} actualizados · {result.seconds:.1f}s", 8000
        )
        self.sidebar.refresh()
        self._refresh_status()
        if auto_index:
            self._auto_index()

    # ── indexación ───────────────────────────────────────────────────────
    def _auto_index(self) -> None:
        pending = [
            m for m in self.ctx.catalog.modules()
            if m["rel_path"] in self.settings.preindex and m["index_status"] != "ready"
        ]
        if pending:
            self._index_paths([m["rel_path"] for m in pending], tr("menu.index.pending"))
        else:
            self._refresh_status()

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

    def _index_paths(self, rel_paths: list[str], label: str) -> None:
        self._index_worker(lambda idx, cb: idx.index_paths(rel_paths, progress=cb), label)

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
        self.statusBar().showMessage(
            f"{tr('status.indexing')} {done}/{total} {label[:48]}"
        )

    def _index_done(self, result: dict) -> None:
        self._idle()
        self.sidebar.refresh()
        self._refresh_status()
        self.search.run_search()
        msg = tr("index.done", indexed=result.get("indexed", 0), pages=result.get("pages", 0))
        if result.get("failed"):
            msg += " · " + tr("index.failed", n=result["failed"])
        self.statusBar().showMessage(msg, 12000)

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
        QMessageBox.about(self, tr("dialog.about.title"),
                          tr("dialog.about.text", version=__version__))
