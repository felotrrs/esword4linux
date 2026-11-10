"""Vista de Biblia: navegación, traducción paralela y comentario inferior."""

from __future__ import annotations

import html as _html

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QLabel, QMenu, QPushButton, QSpinBox,
    QSplitter, QTextBrowser, QToolButton, QVBoxLayout, QWidget,
)

from ..core.books import Reference, book_name, parse_reference
from ..core.context import AppContext
from ..core.text import to_plain, to_rich
from ..i18n import tr
from .commentary_pane import CommentaryPane
from .theme import document_css, palette


class BiblePane(QWidget):
    reference_changed = Signal(str)
    open_module = Signal(int, str)
    search_requested = Signal(str)
    main_changed = Signal(str)          # rel_path de la biblia principal

    def __init__(self, ctx: AppContext, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.settings = ctx.settings
        self._loading = False
        self._current = Reference(43, 3, 16)
        self._main_rel = ""
        self._secondary_rel = ""
        self._sizes_applied = False
        self._build_ui()
        self.reload_modules()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._sizes_applied:
            self._sizes_applied = True
            total = max(400, self.vsplit.height())
            bottom = max(120, min(int(total * 0.28), 420))
            self.vsplit.setSizes([total - bottom, bottom])

    # ── construcción ─────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        bar = QWidget()
        row = QHBoxLayout(bar)
        row.setContentsMargins(10, 6, 10, 6)
        row.setSpacing(6)

        row.addWidget(QLabel(tr("bible.translation")))
        self.translation = QComboBox()
        self.translation.setMinimumWidth(200)
        self.translation.currentIndexChanged.connect(self._on_translation)
        row.addWidget(self.translation)

        row.addSpacing(8)
        self.book = QComboBox()
        self.book.setMinimumWidth(140)
        self.book.currentIndexChanged.connect(self._on_book)
        row.addWidget(self.book)

        self.chapter = QSpinBox()
        self.chapter.setMinimum(1)
        self.chapter.setMaximum(200)
        self.chapter.setFixedWidth(62)
        self.chapter.valueChanged.connect(self._on_chapter)
        row.addWidget(self.chapter)

        self.btn_prev = QToolButton()
        self.btn_prev.setText("◀")
        self.btn_prev.setToolTip(tr("bible.prev"))
        self.btn_prev.clicked.connect(lambda: self._step(-1))
        row.addWidget(self.btn_prev)

        self.btn_next = QToolButton()
        self.btn_next.setText("▶")
        self.btn_next.setToolTip(tr("bible.next"))
        self.btn_next.clicked.connect(lambda: self._step(1))
        row.addWidget(self.btn_next)

        row.addSpacing(10)
        self.parallel = QCheckBox(tr("bible.parallel"))
        self.parallel.toggled.connect(self._on_parallel)
        row.addWidget(self.parallel)
        self.secondary = QComboBox()
        self.secondary.setMinimumWidth(150)
        self.secondary.currentIndexChanged.connect(self._on_secondary)
        row.addWidget(self.secondary)

        row.addStretch(1)

        self.comments = QCheckBox(tr("bible.comments"))
        self.comments.setChecked(self.settings.show_commentary_inline)
        self.comments.toggled.connect(self._on_comments_toggle)
        row.addWidget(self.comments)

        self.btn_search_sel = QPushButton("🔍")
        self.btn_search_sel.setToolTip(tr("bible.search_word"))
        self.btn_search_sel.clicked.connect(self._search_selection)
        row.addWidget(self.btn_search_sel)

        layout.addWidget(bar)

        self.vsplit = QSplitter(Qt.Vertical)
        self.hsplit = QSplitter(Qt.Horizontal)
        self.primary = self._make_browser()
        self.second = self._make_browser()
        for browser in (self.primary, self.second):
            browser.setMaximumWidth(980)
        self.host_primary = self._center(self.primary)
        self.host_second = self._center(self.second)
        self.hsplit.addWidget(self.host_primary)
        self.hsplit.addWidget(self.host_second)
        self.host_second.hide()

        self.commentary = CommentaryPane(self.ctx)
        self.commentary.open_module.connect(self.open_module)
        self.commentary.setVisible(self.settings.show_commentary_inline)

        self.vsplit.addWidget(self.hsplit)
        self.vsplit.addWidget(self.commentary)
        self.vsplit.setStretchFactor(0, 4)
        self.vsplit.setStretchFactor(1, 1)
        self.vsplit.setSizes([1000 - self.settings.commentary_split, self.settings.commentary_split])
        layout.addWidget(self.vsplit, 1)

    def _make_browser(self) -> QTextBrowser:
        b = QTextBrowser()
        b.setOpenLinks(False)
        b.setOpenExternalLinks(False)
        b.anchorClicked.connect(self._on_anchor)
        b.document().setDefaultStyleSheet(
            document_css(self.settings.theme, self.settings.font_size, self.settings.font_family)
        )
        return b

    @staticmethod
    def _center(browser: QTextBrowser) -> QWidget:
        host = QWidget()
        row = QHBoxLayout(host)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addStretch(1)
        row.addWidget(browser, 10)
        row.addStretch(1)
        return host

    # ── módulos ──────────────────────────────────────────────────────────
    def reload_modules(self) -> None:
        self._loading = True
        bibles = self.ctx.bibles()
        self.translation.clear()
        for mod in bibles:
            label = f"{mod['abbreviation']} — {mod['title']}" if mod["abbreviation"] else mod["title"]
            self.translation.addItem(label[:90], mod["rel_path"])
        idx = self.translation.findData(self._main_rel or self.settings.bible_module)
        self.translation.setCurrentIndex(idx if idx >= 0 else 0)

        self.secondary.clear()
        for mod in bibles:
            self.secondary.addItem(mod["abbreviation"] or mod["title"], mod["rel_path"])
        primary_rel = self.translation.currentData()
        previous_secondary = self._secondary_rel or ""
        default_secondary = previous_secondary
        if not default_secondary:
            candidates = [m for m in bibles if m["rel_path"] != primary_rel]
            pre = set(self.settings.preindex)
            preferred = [m for m in candidates if m["rel_path"] in pre]
            if preferred:
                default_secondary = preferred[0]["rel_path"]
            elif candidates:
                default_secondary = max(candidates, key=lambda m: m["entries"] or 0)["rel_path"]
        idx = self.secondary.findData(default_secondary)
        if idx >= 0:
            self.secondary.setCurrentIndex(idx)
        self._secondary_rel = self.secondary.currentData() or ""
        self._loading = False
        self._main_rel = self.translation.currentData() or ""
        self._rebuild_books()
        self.navigate(self._current)

    def load_module(self, row: dict) -> None:
        """Carga una biblia como recurso principal de la pestaña."""
        self._loading = True
        self.reload_modules()
        idx = self.translation.findData(row["rel_path"])
        if idx >= 0:
            self.translation.setCurrentIndex(idx)
        self._loading = False
        self._main_rel = row["rel_path"]
        self._rebuild_books()
        self.navigate(self._current)

    def commentary_rel(self) -> str:
        return self.commentary.commentary_rel()

    def set_commentary_rel(self, rel: str) -> None:
        self.commentary.set_commentary_rel(rel)

    def _active_module(self) -> dict | None:
        return self.ctx.catalog.by_rel_path(self._main_rel)

    def _rebuild_books(self) -> None:
        row = self._active_module()
        mod = self.ctx.module(row) if row else None
        self._loading = True
        self.book.clear()
        if mod and mod.structure == "bible":
            for book_id in mod.books():
                self.book.addItem(book_name(book_id, self.settings.locale), book_id)
        self._loading = False
        if self.book.count():
            idx = self.book.findData(self._current.book)
            self.book.setCurrentIndex(idx if idx >= 0 else 0)
            self._sync_chapter_bounds()

    def _sync_chapter_bounds(self) -> None:
        row = self._active_module()
        mod = self.ctx.module(row) if row else None
        book_id = self.book.currentData()
        self._loading = True
        if mod and mod.structure == "bible" and book_id:
            total = mod.chapter_count(int(book_id)) or 1
            self.chapter.setMaximum(total)
            self.chapter.setValue(max(1, min(self._current.chapter, total)))
        self._loading = False

    # ── navegación ───────────────────────────────────────────────────────
    def navigate(self, ref: Reference) -> None:
        self._current = ref
        row = self._active_module()
        mod = self.ctx.module(row) if row else None
        if mod is None:
            self.primary.setHtml(f'<p class="muted">{tr("main.no_resource")}</p>')
            return
        self._loading = True
        idx = self.book.findData(ref.book)
        if idx >= 0:
            self.book.setCurrentIndex(idx)
        self._sync_chapter_bounds()
        if ref.chapter:
            self.chapter.setValue(ref.chapter)
        self._loading = False
        self.reload(anchor=ref.verse)

    def _step(self, delta: int) -> None:
        row = self._active_module()
        mod = self.ctx.module(row) if row else None
        if not mod:
            return
        book_id = self.book.currentData()
        chapter = self.chapter.value()
        max_ch = mod.chapter_count(int(book_id)) if book_id else 1
        chapter += delta
        if chapter < 1:
            idx = self.book.currentIndex() - 1
            if idx < 0:
                return
            self.book.setCurrentIndex(idx)
            new_book = self.book.currentData()
            self.chapter.setMaximum(mod.chapter_count(int(new_book)) or 1)
            self.chapter.setValue(self.chapter.maximum())
            return
        if chapter > max_ch:
            idx = self.book.currentIndex() + 1
            if idx >= self.book.count():
                return
            self.book.setCurrentIndex(idx)
            self.chapter.setValue(1)
            return
        self.chapter.setValue(chapter)

    # ── render ───────────────────────────────────────────────────────────
    def reload(self, anchor: int | None = None) -> None:
        if self._loading:
            return
        row = self._active_module()
        mod = self.ctx.module(row) if row else None
        book_id = self.book.currentData()
        chapter = self.chapter.value()
        if mod is None or not book_id:
            return
        self._current = Reference(int(book_id), int(chapter), anchor)
        label = self._current.label(self.settings.locale)
        chapter_label = f"{book_name(int(book_id), self.settings.locale)} {int(chapter)}"
        self.primary.setHtml(self._render_chapter(mod, int(book_id), int(chapter)))

        if self.parallel.isChecked():
            srow = self.ctx.catalog.by_rel_path(self.secondary.currentData() or "")
            smod = self.ctx.module(srow) if srow else None
            if smod:
                self.second.setHtml(self._render_chapter(smod, int(book_id), int(chapter)))

        if self.comments.isChecked():
            self.commentary.set_chapter(int(book_id), int(chapter), chapter_label)

        if anchor:
            self.primary.scrollToAnchor(f"v{anchor}")
        else:
            self.primary.verticalScrollBar().setValue(0)
        self.reference_changed.emit(label)

    def _render_chapter(self, mod, book: int, chapter: int) -> str:
        pages = mod.bible_chapter(book, chapter)
        name = book_name(book, self.settings.locale)
        css = document_css(self.settings.theme, self.settings.font_size, self.settings.font_family)
        pal = palette(self.settings.theme)
        out = [f"<style>{css}</style>"]
        out.append(f'<div class="chapter-title">{_html.escape(name)} {chapter}</div>')
        if not pages:
            out.append(f'<p class="muted">{tr("bible.not_available")}</p>')
            return "".join(out)
        for page in pages:
            out.append(f'<a name="v{page.verse}"></a>')
            body = to_rich(page.raw)
            out.append(
                f'<p class="verse scripture">'
                f'<a class="vnum" href="v:{page.verse}" style="text-decoration:none;">'
                f'<font color="{pal.verse_num}"><b>{page.verse}</b></font></a>'
                f'&nbsp;{body}</p>'
            )
        return "".join(out)

    # ── eventos ──────────────────────────────────────────────────────────
    def _on_translation(self, _index: int) -> None:
        if self._loading:
            return
        rel = self.translation.currentData()
        if rel:
            self._main_rel = rel
            self.settings.bible_module = rel
            self.main_changed.emit(rel)
        self._rebuild_books()
        self.navigate(self._current)

    def _on_book(self, _index: int) -> None:
        if self._loading:
            return
        self._sync_chapter_bounds()
        self._current = Reference(int(self.book.currentData() or 1), 1)
        self.reload()

    def _on_chapter(self, value: int) -> None:
        if self._loading:
            return
        self._current = Reference(int(self.book.currentData() or 1), value)
        self.reload()

    def _on_parallel(self, checked: bool) -> None:
        self.host_second.setVisible(checked)
        if checked:
            self.reload()

    def _on_secondary(self, _index: int) -> None:
        self._secondary_rel = self.secondary.currentData() or ""
        if self.parallel.isChecked():
            self.reload()

    def _on_comments_toggle(self, checked: bool) -> None:
        self.settings.show_commentary_inline = checked
        self.commentary.setVisible(checked)
        if checked:
            self.reload()

    def _on_commentary_closed(self) -> None:
        self.comments.setChecked(False)

    def _search_selection(self) -> None:
        text = self.primary.textCursor().selectedText().strip()
        if text:
            self.search_requested.emit(text)

    def _on_anchor(self, url) -> None:
        scheme = url.scheme()
        text = url.toString()
        if scheme == "v":
            self._verse_menu(int(url.path() or 0))
        elif scheme == "c":
            rest = text[len("c:"):]
            mod_id, _, ref = rest.partition(":")
            if mod_id.isdigit():
                self.open_module.emit(int(mod_id), ref)
        elif scheme == "ref":
            target = parse_reference(url.path() or text[4:])
            if target:
                self.navigate(target)

    def _verse_menu(self, verse: int) -> None:
        if not verse:
            return
        ref = Reference(self._current.book, self._current.chapter, verse)
        menu = QMenu(self)
        act_copy = QAction(tr("bible.copy_verse"), self)
        act_copy.triggered.connect(lambda: self._copy_verse(ref))
        menu.addAction(act_copy)
        act_ref = QAction(ref.label(self.settings.locale), self)
        act_ref.triggered.connect(
            lambda: QGuiApplication.clipboard().setText(ref.label(self.settings.locale))
        )
        menu.addAction(act_ref)
        sel = self.primary.textCursor().selectedText().strip()
        if sel:
            act_search = QAction(f'{tr("bible.search_word")}: «{sel[:30]}»', self)
            act_search.triggered.connect(lambda: self.search_requested.emit(sel))
            menu.addAction(act_search)
        menu.exec(self.primary.mapToGlobal(self.primary.cursor().pos()))

    def _copy_verse(self, ref: Reference) -> None:
        row = self._active_module()
        mod = self.ctx.module(row) if row else None
        if not mod:
            return
        page = mod.bible_verse(ref.book, ref.chapter, ref.verse or 1)
        if page:
            QGuiApplication.clipboard().setText(f"{page.title} — {to_plain(page.raw)}")

    # ── estado / tema ────────────────────────────────────────────────────
    def is_parallel(self) -> bool:
        return self.parallel.isChecked()

    def set_parallel(self, enabled: bool) -> None:
        self.parallel.setChecked(enabled)

    def is_commentary(self) -> bool:
        return self.comments.isChecked()

    def set_commentary(self, enabled: bool) -> None:
        self.comments.setChecked(enabled)

    def parallel_rel(self) -> str:
        return self.secondary.currentData() or ""

    def set_parallel_rel(self, rel: str) -> None:
        idx = self.secondary.findData(rel)
        if idx >= 0:
            self.secondary.setCurrentIndex(idx)
            self._secondary_rel = rel

    def split_sizes(self) -> tuple[int, int]:
        sizes = self.vsplit.sizes()
        return (sizes[0], sizes[1]) if len(sizes) == 2 else (800, 280)

    def set_split_sizes(self, sizes: tuple[int, int]) -> None:
        if sizes and sizes[1] > 90:
            self.vsplit.setSizes(list(sizes))

    def reload_theme(self) -> None:
        css = document_css(self.settings.theme, self.settings.font_size, self.settings.font_family)
        for browser in (self.primary, self.second):
            browser.document().setDefaultStyleSheet(css)
        self.commentary.reload_theme()
        self.reload()
