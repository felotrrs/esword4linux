"""Vista de Biblia: navegación, traducción paralela y comentarios en línea."""

from __future__ import annotations

import html as _html

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QLabel, QMenu, QPushButton, QSpinBox,
    QSplitter, QTextBrowser, QToolButton, QVBoxLayout, QWidget,
)

from ..core.books import Reference, book_name
from ..core.context import AppContext
from ..core.text import snippet, to_plain, to_rich
from ..i18n import tr
from .theme import document_css, palette


class BibleView(QWidget):
    reference_changed = Signal(str)
    open_module = Signal(int, str)
    search_requested = Signal(str)

    def __init__(self, ctx: AppContext, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.settings = ctx.settings
        self._loading = False
        self._current = Reference(43, 3, 16)

        self._build_ui()
        self.reload_modules()

    # ── construcción ─────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        bar = QWidget()
        bar.setObjectName("bibleBar")
        row = QHBoxLayout(bar)
        row.setContentsMargins(10, 6, 10, 6)
        row.setSpacing(6)

        row.addWidget(QLabel(tr("bible.translation")))
        self.translation = QComboBox()
        self.translation.setMinimumWidth(210)
        self.translation.currentIndexChanged.connect(self._on_translation)
        row.addWidget(self.translation)

        row.addSpacing(8)
        self.book = QComboBox()
        self.book.setMinimumWidth(150)
        self.book.currentIndexChanged.connect(self._on_book)
        row.addWidget(self.book)

        self.chapter = QSpinBox()
        self.chapter.setMinimum(1)
        self.chapter.setMaximum(200)
        self.chapter.setFixedWidth(64)
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
        self.secondary.setMinimumWidth(170)
        self.secondary.currentIndexChanged.connect(lambda _=0: self.reload())
        row.addWidget(self.secondary)

        row.addStretch(1)

        self.comments = QCheckBox(tr("bible.comments"))
        self.comments.setChecked(self.settings.show_commentary_inline)
        self.comments.toggled.connect(self._on_comments_toggle)
        row.addWidget(self.comments)
        self.commentary = QComboBox()
        self.commentary.setMinimumWidth(190)
        self.commentary.currentIndexChanged.connect(lambda _=0: self.reload())
        row.addWidget(self.commentary)

        self.btn_search_sel = QPushButton("🔍")
        self.btn_search_sel.setToolTip(tr("bible.search_word"))
        self.btn_search_sel.clicked.connect(self._search_selection)
        row.addWidget(self.btn_search_sel)

        layout.addWidget(bar)

        self.splitter = QSplitter(Qt.Horizontal)
        self.primary = self._make_browser()
        self.second = self._make_browser()
        for browser in (self.primary, self.second):
            browser.setMaximumWidth(920)
        self.host_primary = self._center(browser=self.primary)
        self.host_second = self._center(browser=self.second)
        self.splitter.addWidget(self.host_primary)
        self.splitter.addWidget(self.host_second)
        self.host_second.hide()
        layout.addWidget(self.splitter, 1)

    @staticmethod
    def _center(browser: QTextBrowser) -> QWidget:
        """Columna de lectura centrada y limitada (líneas de ~90 caracteres)."""
        host = QWidget()
        row = QHBoxLayout(host)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addStretch(1)
        row.addWidget(browser, 10)
        row.addStretch(1)
        return host

    def _make_browser(self) -> QTextBrowser:
        b = QTextBrowser()
        b.setOpenLinks(False)
        b.setOpenExternalLinks(False)
        b.anchorClicked.connect(self._on_anchor)
        b.document().setDefaultStyleSheet(
            document_css(self.settings.theme, self.settings.font_size, self.settings.font_family)
        )
        return b

    # ── carga de módulos ─────────────────────────────────────────────────
    def reload_modules(self) -> None:
        self._loading = True
        current_bible = self.settings.bible_module
        self.translation.clear()
        for mod in self.ctx.bibles():
            label = f"{mod['abbreviation']} — {mod['title']}" if mod["abbreviation"] else mod["title"]
            self.translation.addItem(label[:90], mod["rel_path"])
            if mod["rel_path"] == current_bible:
                self.translation.setCurrentIndex(self.translation.count() - 1)

        self.secondary.clear()
        bibles = self.ctx.bibles()
        for mod in bibles:
            self.secondary.addItem(mod["abbreviation"] or mod["title"], mod["rel_path"])
        # Paralela por defecto: la biblia más completa que no sea la principal.
        primary_rel = self.translation.currentData()
        default_secondary = self.settings.secondary_bible
        if not default_secondary:
            candidates = [m for m in bibles if m["rel_path"] != primary_rel]
            if candidates:
                default_secondary = max(candidates, key=lambda m: m["entries"] or 0)["rel_path"]
        idx = self.secondary.findData(default_secondary)
        if idx >= 0:
            self.secondary.setCurrentIndex(idx)

        self.commentary.clear()
        self.commentary.addItem(tr("bible.comments_none"), "")
        for mod in self.ctx.commentaries():
            label = f"{mod['abbreviation']} — {mod['title']}" if mod["abbreviation"] else mod["title"]
            self.commentary.addItem(label[:80], mod["rel_path"])
        wanted = self.settings.commentary_modules[0] if self.settings.commentary_modules else ""
        if not wanted:
            # 1) el comentario pre-indexado por defecto
            pre = set(self.settings.preindex)
            for mod in self.ctx.commentaries():
                if mod["rel_path"] in pre:
                    wanted = mod["rel_path"]
                    break
        if not wanted:
            # 2) el comentario con más entradas (más cobertura por versículo)
            mods = self.ctx.commentaries()
            if mods:
                wanted = max(mods, key=lambda m: m["entries"] or 0)["rel_path"]
        idx = self.commentary.findData(wanted)
        if idx >= 0:
            self.commentary.setCurrentIndex(idx)

        self._loading = False
        self._rebuild_books()
        self.navigate(self._current)

    def _active_module(self) -> dict | None:
        return self.ctx.catalog.by_rel_path(self.translation.currentData() or "")

    def _commentary_module(self) -> dict | None:
        rel = self.commentary.currentData() or ""
        return self.ctx.catalog.by_rel_path(rel) if rel else None

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
            self.primary.setHtml(f'<p class="muted">{tr("search.no_index")}</p>')
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
        self.primary.setHtml(self._render_chapter(mod, int(book_id), int(chapter), with_comments=True))

        if self.parallel.isChecked():
            srow = self.ctx.catalog.by_rel_path(self.secondary.currentData() or "")
            smod = self.ctx.module(srow) if srow else None
            if smod:
                self.second.setHtml(self._render_chapter(smod, int(book_id), int(chapter), with_comments=False))
        if anchor:
            self.primary.scrollToAnchor(f"v{anchor}")
        else:
            self.primary.verticalScrollBar().setValue(0)
        self.reference_changed.emit(self._current.label(self.settings.locale))

    def _render_chapter(self, mod, book: int, chapter: int, with_comments: bool) -> str:
        pages = mod.bible_chapter(book, chapter)
        name = book_name(book, self.settings.locale)
        css = document_css(self.settings.theme, self.settings.font_size, self.settings.font_family)
        pal = palette(self.settings.theme)
        out = [f"<style>{css}</style>"]
        out.append(f'<div class="chapter-title">{_html.escape(name)} {chapter}</div>')
        if not pages:
            out.append(f'<p class="muted">{tr("bible.not_available")}</p>')
            return "".join(out)

        comments: dict[int, list[tuple[str, str, str]]] = {}
        cm = self._commentary_module() if with_comments and self.comments.isChecked() else None
        if cm:
            cmod = self.ctx.module(cm)
            if cmod:
                for verse, entries in cmod.chapter_comments(book, chapter).items():
                    comments[verse] = [
                        (cm["abbreviation"] or cm["title"], e.ref, to_plain(e.raw))
                        for e in entries
                    ]

        for page in pages:
            out.append(f'<a name="v{page.verse}"></a>')
            body = to_rich(page.raw)
            out.append(
                f'<p class="verse scripture">'
                f'<a class="vnum" href="v:{page.verse}" style="text-decoration:none;">'
                f'<font color="{pal.verse_num}"><b>{page.verse}</b></font></a>'
                f'&nbsp;{body}</p>'
            )
            for abbrev, ref, plain in comments.get(page.verse or 0, []):
                short = snippet(plain, 620)
                more = (
                    f' &nbsp;<a href="c:{cm["id"]}:{_html.escape(ref, quote=True)}">'
                    f'{tr("bible.read_more")}</a>'
                )
                out.append(
                    f'<table width="97%" cellspacing="0" cellpadding="7" '
                    f'style="margin-left:26px; margin-bottom:13px; '
                    f'background-color:{pal.comment_bg};">'
                    f'<tr><td style="border-left:3px solid {pal.accent};">'
                    f'<span class="ctag">{_html.escape(abbrev)}</span><br>'
                    f"{_html.escape(short)}{more}</td></tr></table>"
                )
        if with_comments and self.comments.isChecked() and cm and not comments:
            out.append(f'<p class="muted">{tr("bible.comments_none")}</p>')
        return "".join(out)

    # ── eventos ──────────────────────────────────────────────────────────
    def _on_translation(self, _index: int) -> None:
        if self._loading:
            return
        rel = self.translation.currentData()
        if rel:
            self.settings.bible_module = rel
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

    def _on_comments_toggle(self, checked: bool) -> None:
        self.settings.show_commentary_inline = checked
        self.reload()

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
            from ..core.books import parse_reference

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
            text = f"{page.title} — {to_plain(page.raw)}"
            QGuiApplication.clipboard().setText(text)

    def _search_selection(self) -> None:
        text = self.primary.textCursor().selectedText().strip()
        if text:
            self.search_requested.emit(text)
