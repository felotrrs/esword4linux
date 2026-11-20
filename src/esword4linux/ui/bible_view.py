"""Bible view: navigation, multi-version comparison and stacked bottom panel.

The bottom panel switches between **Commentary** and **Strong**. Text markers
(notes `(B)` and numbers `G2316`) are links with a bubble:

* the note and the reference resolve their text **while painting** (they are
  already in memory) → native Qt tooltip;
* the Strong number is resolved **on hover** (an indexed `SELECT`) →
  `RichBrowser` shows it with a cache.
"""

from __future__ import annotations

import html as _html
import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QAction, QCursor, QGuiApplication, QIntValidator,
)
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMenu, QPushButton, QScrollArea, QSizePolicy, QSplitter,
    QStackedWidget, QToolButton, QToolTip, QVBoxLayout, QWidget,
)

from ..core.books import Reference, book_name, parse_reference
from ..core.commentary import best_commentary
from ..core.compare_reader import build_compare_table
from ..core.context import AppContext
from ..core.refchain import parse_reference_chain
from ..core.text import snippet, to_plain, to_rich
from ..i18n import tr
from .bible_combo import fill_bible_combo
from .citation_pane import CitationPane
from .commentary_pane import CommentaryPane
from .compare_view import CompareView
from .rich_browser import RichBrowser
from .strong_pane import StrongPane
from .theme import document_css_for, palette

_STRONG_COLOR = "#8f6bc4"
_STRONG_STYLE = f"color:{_STRONG_COLOR};font-size:80%;text-decoration:none;"
_TAGS_RE = re.compile(r"<[^>]+>")
_SUP_RE = re.compile(r"(?is)<sup>(.*?)</sup>")
_STRONG_IN_TEXT = re.compile(r"\b([GH]\d{1,5})\b")
_REF_A_RE = re.compile(r'<a href="ref:([^"]+)">')




class BiblePane(QWidget):
    reference_changed = Signal(str)
    open_module = Signal(int, str)
    search_requested = Signal(str)
    main_changed = Signal(str)          # rel_path of the main Bible

    def __init__(self, ctx: AppContext, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.settings = ctx.settings
        self._loading = False
        self._current = Reference(1, 1, None)
        self._main_rel = ""
        self._compare_columns: list[str] = []
        self._compare_columns_initialized = False
        self._compare_notice_names: list[str] = []
        self._sizes_applied = False
        self._comments_cache: dict[tuple, dict] = {}
        self._chapter_max = 200
        self._citation_mode = False
        self._build_ui()
        self.reload_modules()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._sizes_applied:
            self._sizes_applied = True
            total = max(400, self.vsplit.height())
            bottom = max(120, min(int(total * 0.28), 420))
            self.vsplit.setSizes([total - bottom, bottom])

    # ── construction ─────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._wrap_toolbar(self._build_toolbar()))

        self.vsplit = QSplitter(Qt.Vertical)
        self.primary = self._make_browser()
        self.primary_host = self._center(self.primary)
        self.citations = CitationPane(self.ctx)
        self.citations.btn_hide.hide()
        self.citations.open_reference.connect(self._open_citation_reference)
        self.compare_view = CompareView(
            self.settings, resolver=self._resolve_tooltip
        )
        self.compare_view.remove_requested.connect(self._remove_compare_column)
        self.compare_view.verse_clicked.connect(self._select_compare_verse)
        self.compare_view.add_requested.connect(
            self._begin_add_compare_column
        )
        self.compare_view.column_changed.connect(
            self._apply_compare_pick
        )
        self.compare_view.anchor_clicked.connect(self._on_compare_anchor)
        self.primary_stack = QStackedWidget()
        self.primary_stack.addWidget(self.primary_host)
        self.primary_stack.addWidget(self.citations)
        self.primary_stack.addWidget(self.compare_view)

        self.commentary = CommentaryPane(self.ctx)
        self.commentary.open_module.connect(self.open_module)
        self.commentary.open_inline.connect(self._show_commentary_inline)
        self.commentary.module_changed.connect(self._on_commentary_changed)
        self.strong = StrongPane(self.ctx)
        self.strong.open_module.connect(self.open_module)
        self.strong.lexicon_changed.connect(self._on_strong_changed)

        self.bottom = QStackedWidget()
        self.bottom.addWidget(self.commentary)
        self.bottom.addWidget(self.strong)

        self.vsplit.addWidget(self.primary_stack)
        self.vsplit.addWidget(self.bottom)
        self.vsplit.setStretchFactor(0, 4)
        self.vsplit.setStretchFactor(1, 1)
        layout.addWidget(self.vsplit, 1)

        page = self.settings.bottom_page
        self._set_bottom_page(page if page in ("commentary", "strong")
                              else "commentary",
                              show=self.settings.show_commentary_inline)

    def _wrap_toolbar(self, bar: QWidget) -> QScrollArea:
        """Keep the toolbar from dictating the window's minimum width.

        The bar has many controls and a rigid ~975 px minimum. Inside a
        layout that minimum becomes the window's minimum, and a window manager
        disables *maximise* when it exceeds the usable screen width. A
        horizontal scroller keeps the bar reachable on narrow windows without
        touching the window's geometry.
        """
        scroll = QScrollArea()
        scroll.setObjectName("bibleBarScroll")
        scroll.setWidget(bar)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        return scroll

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        row = QHBoxLayout(bar)
        row.setContentsMargins(10, 6, 10, 6)
        row.setSpacing(6)

        self.lbl_translation = QLabel(tr("bible.translation"))
        row.addWidget(self.lbl_translation)
        self.translation = QComboBox()
        self.translation.setMinimumWidth(110)
        self.translation.setToolTip(tr("bible.translation_help"))
        self.translation.currentIndexChanged.connect(self._on_translation)
        row.addWidget(self.translation)

        self.citation_input = QLineEdit()
        self.citation_input.setMinimumWidth(60)
        self.citation_input.setMaximumWidth(360)
        self.citation_input.setPlaceholderText(tr("bible.citation_placeholder"))
        self.citation_input.setToolTip(tr("bible.citation_help"))
        self.citation_input.setClearButtonEnabled(True)
        self.citation_input.returnPressed.connect(self._show_citations)
        row.addWidget(self.citation_input, 1)

        self.btn_citation_back = QToolButton()
        self.btn_citation_back.setText("↩")
        self.btn_citation_back.setToolTip(tr("bible.citation_back"))
        self.btn_citation_back.clicked.connect(self._exit_citation_mode)
        self.btn_citation_back.hide()
        row.addWidget(self.btn_citation_back)

        row.addSpacing(8)
        self.book = QComboBox()
        self.book.setMinimumWidth(85)
        self.book.setToolTip(tr("bible.book_help"))
        self.book.currentIndexChanged.connect(self._on_book)
        row.addWidget(self.book)

        self.chapter = QLineEdit()
        self.chapter.setFixedWidth(52)
        self.chapter.setAlignment(Qt.AlignCenter)
        self.chapter.setValidator(QIntValidator(1, 200, self))
        self.chapter.setToolTip(tr("bible.chapter_help"))
        self.chapter.editingFinished.connect(self._on_chapter_edited)
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
        self.parallel.setToolTip(tr("bible.parallel_help"))
        self.parallel.toggled.connect(self._on_parallel)
        row.addWidget(self.parallel)
        self.compare_notice = QLabel("")
        self.compare_notice.setObjectName("matchBadge")
        self.compare_notice.hide()
        row.addWidget(self.compare_notice)

        row.addStretch(1)

        self.btn_commentary = QToolButton()
        self.btn_commentary.setText(tr("bible.bottom_commentary"))
        self.btn_commentary.setCheckable(True)
        self.btn_commentary.setToolTip(tr("bible.bottom_commentary_help"))
        self.btn_commentary.clicked.connect(lambda: self._on_bottom_button("commentary"))
        row.addWidget(self.btn_commentary)

        self.btn_strong = QToolButton()
        self.btn_strong.setText(tr("bible.bottom_strong"))
        self.btn_strong.setCheckable(True)
        self.btn_strong.setToolTip(tr("bible.bottom_strong_help"))
        self.btn_strong.clicked.connect(lambda: self._on_bottom_button("strong"))
        row.addWidget(self.btn_strong)

        self.bottom_group = QButtonGroup(self)
        self.bottom_group.setExclusive(True)
        self.bottom_group.addButton(self.btn_commentary)
        self.bottom_group.addButton(self.btn_strong)

        self.btn_search_sel = QPushButton("🔍")
        self.btn_search_sel.setToolTip(tr("bible.search_word_help"))
        self.btn_search_sel.clicked.connect(self._search_selection)
        row.addWidget(self.btn_search_sel)
        return bar

    def _make_browser(self) -> RichBrowser:
        b = RichBrowser(resolver=self._resolve_tooltip)
        b.setOpenLinks(False)
        b.setOpenExternalLinks(False)
        b.anchorClicked.connect(self._on_anchor)
        b.document().setDefaultStyleSheet(self._css())
        return b

    @staticmethod
    def _center(browser) -> QWidget:
        # No side stretches: the text uses the full panel width.
        # The reading margin comes from the QTextBrowser padding.
        host = QWidget()
        row = QHBoxLayout(host)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addWidget(browser)
        return host

    def _css(self) -> str:
        return document_css_for(self.settings)

    # ── bottom panel ─────────────────────────────────────────────────────
    def _set_bottom_page(self, page: str, show: bool = True) -> None:
        self.bottom.setVisible(show and page in ("commentary", "strong"))
        if page == "commentary":
            self.bottom.setCurrentWidget(self.commentary)
        elif page == "strong":
            self.bottom.setCurrentWidget(self.strong)
        self.bottom_group.setExclusive(False)
        self.btn_commentary.setChecked(show and page == "commentary")
        self.btn_strong.setChecked(show and page == "strong")
        self.bottom_group.setExclusive(True)
        self.settings.show_commentary_inline = show and bool(page)
        if page:
            self.settings.bottom_page = page
        if show and page == "commentary":
            self._refresh_commentary()

    def _on_bottom_button(self, page: str) -> None:
        widget = {
            "commentary": self.commentary,
            "strong": self.strong,
        }.get(page)
        if widget is None:
            return
        if self.bottom.isVisible() and self.bottom.currentWidget() is widget:
            self._set_bottom_page("", show=False)
        else:
            self._set_bottom_page(page, show=True)

    def _show_commentary_inline(self) -> None:
        """Show the matched commentary in the bottom panel and focus it."""
        self._set_bottom_page("commentary", show=True)
        if self._current.verse:
            self.commentary.scroll_to_verse(self._current.verse)

    def _on_commentary_closed(self) -> None:
        self._set_bottom_page("", show=False)

    def _on_strong_closed(self) -> None:
        self._set_bottom_page("", show=False)

    # ── modules ──────────────────────────────────────────────────────────
    def reload_modules(self) -> None:
        self._loading = True
        bibles = self.ctx.bibles()
        fill_bible_combo(
            self.translation, bibles,
            self._main_rel or self.settings.bible_module,
            editable=False,
        )
        self._loading = False
        self._main_rel = self.translation.currentData() or ""
        self._sync_compare_columns(bibles)
        self._rebuild_books()
        self._apply_commentary_match()
        self.navigate(self._current)

    def _column_label(self, rel: str) -> str:
        row = self.ctx.catalog.by_rel_path(rel)
        if row:
            name = row.get("abbreviation") or row.get("title") or rel
            if name != rel:
                return f"{name} ({rel})"
        return rel

    def _show_compare_notice(self, names: list[str]) -> None:
        self._compare_notice_names = list(names)
        if not names:
            self.compare_notice.hide()
            self.compare_notice.setText("")
            self.compare_notice.setToolTip("")
            return
        self.compare_notice.setText(
            tr("compare.columns_unavailable_short", n=len(names))
        )
        self.compare_notice.setToolTip(
            tr("compare.columns_unavailable", names=", ".join(names))
        )
        self.compare_notice.show()

    def _ensure_main_column(self) -> None:
        """The active translation is always column 0 and is never removable."""
        if not self._main_rel:
            return
        old_main = self._compare_columns[0] if self._compare_columns else ""
        rest = [
            rel for rel in self._compare_columns
            if rel not in (self._main_rel, old_main)
        ]
        self._compare_columns = [self._main_rel] + rest

    def _sync_compare_columns(self, bibles: list[dict]) -> None:
        """Drop removed modules and choose a sensible default on first use."""
        valid = {m["rel_path"] for m in bibles}
        filtered: list[str] = []
        dropped: list[str] = []
        for rel in self._compare_columns:
            if rel in valid:
                if rel not in filtered:
                    filtered.append(rel)
            else:
                dropped.append(self._column_label(rel))
        self._compare_columns = filtered

        if dropped:
            self._show_compare_notice(dropped)

        if self._compare_columns_initialized:
            self._ensure_main_column()
            return

        columns: list[str] = []
        if self._main_rel and self._main_rel in valid:
            columns.append(self._main_rel)

        preferred = self.settings.secondary_bible
        if preferred and preferred in valid and preferred not in columns:
            columns.append(preferred)
        else:
            candidates = [
                m for m in bibles
                if m["rel_path"] not in columns
            ]
            if candidates:
                columns.append(
                    max(candidates, key=lambda m: m["entries"] or 0)["rel_path"]
                )
        self._compare_columns = columns
        self._compare_columns_initialized = True
        self._ensure_main_column()

    def load_module(self, row: dict) -> None:
        self._loading = True
        self.reload_modules()
        idx = self.translation.findData(row["rel_path"])
        if idx >= 0:
            self.translation.setCurrentIndex(idx)
        self._loading = False
        self._main_rel = row["rel_path"]
        self._ensure_main_column()
        self.ctx.refs.set_bible(self._main_rel)
        self._rebuild_books()
        self._apply_commentary_match()
        self.navigate(self._current)

    def _apply_commentary_match(self) -> None:
        """Match the commentary with the active Bible (visible heuristic).

        When the main Bible changes, automatically find the best matching
        commentary and load it in the bottom panel. If the matched commentary
        is not in the catalog, show a warning in the matching badge.
        """
        bible = self._active_module()
        if bible is None:
            self.commentary.set_match_badge("")
            self.commentary.set_commentary_rel("")
            return
        mod = self.ctx.module(bible)
        matched = best_commentary(
            bible, self.ctx.commentaries(),
            bible_module=mod, open_module=self.ctx.module,
        )
        if matched is not None:
            self.commentary.set_commentary_rel(matched["rel_path"])
            # Verify that the commentary really exists in the catalog.
            row = self.ctx.catalog.by_rel_path(matched["rel_path"])
            if row is None:
                self.commentary.set_match_badge(
                    tr("commentary.not_found",
                       bible=bible.get("abbreviation") or bible.get("title", ""))
                )
            else:
                self.commentary.set_match_badge(
                    tr("commentary.matched",
                       bible=bible.get("abbreviation") or bible.get("title", "")),
                    matched_rel=matched["rel_path"],
                )
            # Reload the commentary panel to show the new commentary.
            self.commentary.refresh()
        else:
            self.commentary.set_match_badge(
                tr("commentary.no_match")
            )
            self.commentary.set_commentary_rel("")
        self._comments_cache.clear()

    def _active_module(self) -> dict | None:
        return self.ctx.catalog.by_rel_path(self._main_rel)

    def _commentary_mod_row(self) -> dict | None:
        rel = self.commentary.commentary_rel()
        return self.ctx.catalog.by_rel_path(rel) if rel else None

    def _chapter_comments(self, book: int, chapter: int) -> dict:
        row = self._commentary_mod_row()
        if row is None:
            return {}
        key = (row["id"], book, chapter)
        if key not in self._comments_cache:
            mod = self.ctx.module(row)
            self._comments_cache[key] = mod.chapter_comments(book, chapter) if mod else {}
        return self._comments_cache[key]

    # ── navigation ───────────────────────────────────────────────────────
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
            self.chapter.setText(str(ref.chapter))
        self._loading = False
        self.reload(anchor=ref.verse)

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
            self._chapter_max = total
            chapter = max(1, min(self._current.chapter, total))
            self.chapter.setText(str(chapter))
        self._loading = False

    def _step(self, delta: int) -> None:
        row = self._active_module()
        mod = self.ctx.module(row) if row else None
        if not mod:
            return
        book_id = self.book.currentData()
        chapter = self._chapter_value()
        max_ch = mod.chapter_count(int(book_id)) if book_id else 1
        chapter += delta
        if chapter < 1:
            idx = self.book.currentIndex() - 1
            if idx < 0:
                return
            self.book.blockSignals(True)
            self.book.setCurrentIndex(idx)
            self.book.blockSignals(False)
            new_book = self.book.currentData()
            self._chapter_max = mod.chapter_count(int(new_book)) or 1
            self.chapter.setText(str(self._chapter_max))
            self._exit_citation_mode()
            self._on_chapter_edited()
            return
        if chapter > max_ch:
            idx = self.book.currentIndex() + 1
            if idx >= self.book.count():
                return
            self.book.blockSignals(True)
            self.book.setCurrentIndex(idx)
            self.book.blockSignals(False)
            self._chapter_max = mod.chapter_count(int(self.book.currentData())) or 1
            self.chapter.setText("1")
            self._exit_citation_mode()
            self._on_chapter_edited()
            return
        self.chapter.setText(str(chapter))
        self._exit_citation_mode()
        self._on_chapter_edited()

    # ── render ───────────────────────────────────────────────────────────
    def reload(self, anchor: int | None = None) -> None:
        if self._loading:
            return
        row = self._active_module()
        mod = self.ctx.module(row) if row else None
        book_id = self.book.currentData()
        chapter = self._chapter_value()
        if mod is None or not book_id:
            return
        self._current = Reference(int(book_id), int(chapter), anchor)
        label = self._current.label(self.settings.locale)
        self.primary.document().setDefaultStyleSheet(self._css())
        self.primary.setHtml(self._render_chapter(mod, int(book_id), int(chapter)))
        self.primary.clear_cache()

        if self.parallel.isChecked():
            build = build_compare_table(
                self.ctx,
                self._compare_columns,
                int(book_id),
                int(chapter),
            )
            self.compare_view.browser.bible_rel = self._main_rel or None
            self.compare_view.set_build(
                build, bibles=self.ctx.bibles()
            )

        if self.bottom.isVisible():
            if self.bottom.currentWidget() is self.commentary:
                self._refresh_commentary()
            elif self.bottom.currentWidget() is self.strong and self.strong.code:
                self.strong.show_code(self.strong.code)

        if self._citation_mode and self.citations._refs:
            self.citations.show_chain(self.citations._refs, mod)
            self.primary_stack.setCurrentWidget(self.citations)
        elif self.parallel.isChecked():
            self.primary_stack.setCurrentWidget(self.compare_view)
        else:
            self.primary_stack.setCurrentWidget(self.primary_host)

        if self.parallel.isChecked() and not self._citation_mode:
            if anchor:
                self.compare_view.scroll_to_verse(anchor)
        elif anchor:
            self.primary.scrollToAnchor(f"v{anchor}")
        else:
            self.primary.verticalScrollBar().setValue(0)
        self.reference_changed.emit(label)

    def _refresh_commentary(self) -> None:
        book = self._current.book
        chapter = self._current.chapter
        label = f"{book_name(book, self.settings.locale)} {chapter}"
        self.commentary.set_chapter(book, chapter, label)

    def _render_chapter(self, mod, book: int, chapter: int) -> str:
        pages = mod.bible_chapter(book, chapter)
        name = book_name(book, self.settings.locale)
        pal = palette(self.settings.theme)
        out = [f"<style>{self._css()}</style>"]
        out.append(f'<div class="chapter-title">{_html.escape(name)} {chapter}</div>')
        if not pages:
            out.append(f'<p class="muted">{tr("bible.not_available")}</p>')
            return "".join(out)
        for page in pages:
            out.append(f'<a name="v{page.verse}"></a>')
            body = to_rich(page.raw, hint=mod.stem, codepages=mod.codepages)
            body = self._enhance(body, book, chapter, page.verse or 0)
            out.append(
                f'<p class="verse scripture">'
                f'<a class="vnum" href="v:{page.verse}" style="text-decoration:none;">'
                f'<font color="{pal.verse_num}"><b>{page.verse}</b></font></a>'
                f'&nbsp;{body}</p>'
            )
        return "".join(out)

    # ── enrichment: notes, Strong and references ─────────────────────────
    def _enhance(self, html_text: str, book: int, chapter: int, verse: int) -> str:
        """Turn `<sup>`, `<ref>` and Strong numbers into anchors with a bubble."""
        entries = self._chapter_comments(book, chapter).get(verse, []) if verse else []

        pal = palette(self.settings.theme)
        strong_style = f"color:{pal.strong};font-size:82%;text-decoration:none;font-weight:600;"

        def sup(match: re.Match) -> str:
            inner = match.group(1)
            if 'href="strong:' in inner:
                return inner
            plain = _TAGS_RE.sub("", inner).strip()
            hit = _STRONG_IN_TEXT.search(plain)
            if hit:
                code = hit.group(1)
                return (f'<a href="strong:{code}" style="{strong_style}">'
                        f"<sup>{_html.escape(plain)}</sup></a>")
            marker = plain.strip("()[]{} ").strip()
            if not marker or len(marker) > 6 or not entries:
                return match.group(0)
            tip = self._note_text(entries, marker)
            return (
                f'<a href="note:{book}:{chapter}:{verse}:{_html.escape(marker, quote=True)}" '
                f'title="{_html.escape(tip, quote=True)}"><sup>{_html.escape(plain)}</sup></a>'
            )

        html_text = _SUP_RE.sub(sup, html_text)

        def ref(match: re.Match) -> str:
            ref_text = match.group(1)
            tip = self._verse_tooltip(ref_text)
            if not tip:
                return match.group(0)
            return (f'<a href="ref:{ref_text}" '
                    f'title="{_html.escape(tip, quote=True)}">')

        return _REF_A_RE.sub(ref, html_text)

    def _note_text(self, entries, marker: str) -> str:
        row = self._commentary_mod_row()
        mod = self.ctx.module(row) if row else None
        hint = mod.stem if mod else ""
        cps = mod.codepages if mod else None
        parts = [to_plain(e.raw, hint=hint, codepages=cps) for e in entries]
        text = " ".join(p for p in parts if p).strip()
        if not text:
            return tr("tooltip.no_note")
        return snippet(text, 320)

    # ── bubbles ──────────────────────────────────────────────────────────
    def _resolve_tooltip(self, href: str) -> str:
        try:
            if href.startswith("strong:"):
                return self.ctx.strong.tooltip(href[7:])
            if href.startswith("note:"):
                return self._note_tooltip(href[5:])
            if href.startswith("ref:"):
                return self._verse_tooltip(href[4:])
        except Exception:
            return ""
        return ""

    def _note_tooltip(self, payload: str) -> str:
        parts = payload.split(":")
        if len(parts) < 3:
            return ""
        try:
            book, chapter, verse = int(parts[0]), int(parts[1]), int(parts[2])
        except ValueError:
            return ""
        marker = parts[3] if len(parts) > 3 else ""
        entries = self._chapter_comments(book, chapter).get(verse, [])
        if not entries:
            return ""
        text = self._note_text(entries, marker)
        ref = f"{book_name(book, self.settings.locale)} {chapter}:{verse}"
        return f"{tr('tooltip.note', marker=marker, ref=ref)}\n{text}"

    def _verse_tooltip(self, ref_text: str) -> str:
        # A single implementation (ranges, verse cap and formatting) lives in
        # RefResolver; here it is only delegated.
        return self.ctx.refs.verse_tooltip(ref_text)

    def _on_commentary_changed(self, _rel: str) -> None:
        """The chosen commentary changes the notes/bubbles of the chapter."""
        self._comments_cache.clear()
        scroll = self.primary.verticalScrollBar().value()
        self.commentary.browser.clear_cache()
        self.primary.clear_cache()
        self.compare_view.browser.clear_cache()
        if self._current.book and self._current.chapter:
            self.reload()
            self.primary.verticalScrollBar().setValue(scroll)

    def _on_strong_changed(self, _rel: str) -> None:
        """A new lexicon invalidates all already resolved Strong bubbles."""
        RichBrowser.clear_all_caches()
        self.ctx.refs.clear()

    def _set_citation_mode(self, active: bool) -> None:
        self._citation_mode = active
        # Book, chapter and arrows always stay visible: hiding them left the
        # bar with no way back to normal navigation. The ↩ button and the view
        # switch are enough for citation mode.
        self.btn_citation_back.setVisible(active)
        if not active:
            self.primary_stack.setCurrentWidget(
                self.compare_view if self.parallel.isChecked()
                else self.primary_host
            )

    def _exit_citation_mode(self) -> None:
        if getattr(self, "_citation_mode", False):
            self._set_citation_mode(False)

    def _open_citation_reference(self, ref: Reference) -> None:
        self._exit_citation_mode()
        self.navigate(ref)

    def _show_citations(self) -> None:
        self.citation_input.setCursorPosition(0)
        text = self.citation_input.text().strip()
        if not text:
            self._exit_citation_mode()
            return
        result = parse_reference_chain(text)
        mod = self.ctx.module(self._active_module())
        self.citations.show_chain(result.refs, mod)
        self._set_citation_mode(True)
        self.primary_stack.setCurrentWidget(self.citations)
        if not result.refs:
            return
        ref = result.refs[0]
        self._current = ref
        self._loading = True
        idx = self.book.findData(ref.book)
        if idx >= 0:
            self.book.setCurrentIndex(idx)
        self._sync_chapter_bounds()
        self.chapter.setText(str(ref.chapter))
        self._loading = False
        self.reload(anchor=ref.verse)
        self.primary_stack.setCurrentWidget(self.citations)

    # ── resource navigation ──────────────────────────────────────────────
    def _jump_to_note(self, book: int, chapter: int, verse: int, marker: str) -> None:
        if not self._commentary_mod_row():
            self._apply_commentary_match()
        if not self._commentary_mod_row():
            return
        self._set_bottom_page("commentary", show=True)
        self.commentary.set_chapter(book, chapter,
                                    f"{book_name(book, self.settings.locale)} {chapter}")
        self.commentary.scroll_to_verse(verse)
        self.primary.setFocus(Qt.OtherFocusReason)

    def _show_strong(self, code: str) -> None:
        self._set_bottom_page("strong", show=True)
        self.strong.show_code(code)
        self.primary.setFocus(Qt.OtherFocusReason)

    # ── events ───────────────────────────────────────────────────────────
    def _on_translation(self, _index: int) -> None:
        if self._loading:
            return
        rel = self.translation.currentData()
        if rel:
            self._main_rel = rel
            self._ensure_main_column()
            self.settings.bible_module = rel
            self.ctx.refs.set_bible(rel)
            self.main_changed.emit(rel)
        self._rebuild_books()
        self._apply_commentary_match()
        self.navigate(self._current)

    def _on_book(self, _index: int) -> None:
        if self._loading:
            return
        self._exit_citation_mode()
        self._sync_chapter_bounds()
        self._current = Reference(int(self.book.currentData() or 1), 1)
        self.reload()

    def _chapter_value(self) -> int:
        try:
            value = int((self.chapter.text() or "1").strip())
        except ValueError:
            value = 1
        return max(1, min(value, self._chapter_max or 200))

    def _on_chapter_edited(self) -> None:
        if self._loading:
            return
        self._exit_citation_mode()
        value = self._chapter_value()
        self.chapter.setText(str(value))
        self._current = Reference(int(self.book.currentData() or 1), value)
        self.reload()

    def _on_parallel(self, checked: bool) -> None:
        if checked:
            self._exit_citation_mode()
            if not self._compare_columns_initialized:
                self._sync_compare_columns(self.ctx.bibles())
        self.reload()

    def _begin_add_compare_column(self) -> None:
        used = set(self._compare_columns)
        if not any(
            mod["rel_path"] not in used for mod in self.ctx.bibles()
        ):
            QToolTip.showText(QCursor.pos(), tr("compare.all_added"))
            return
        self.compare_view.begin_add()

    def _apply_compare_pick(self, index: int, rel: str) -> None:
        row = self.ctx.catalog.by_rel_path(rel)
        if row is None or row.get("kind") != "bible":
            return

        build = self.compare_view.current_build()
        table = build.table if build is not None else None
        columns = table.columns if table is not None else ()
        draft_index = len(columns) if table is not None else 0
        if table is not None and index == 0:
            return

        if index < len(columns):
            old = columns[index].column.key
            if rel == old:
                self.compare_view.cancel_draft()
                return
            if rel in self._compare_columns:
                return
            try:
                position = self._compare_columns.index(old)
            except ValueError:
                return
            self._compare_columns[position] = rel
        elif self.compare_view.has_draft() and index == draft_index:
            if rel in self._compare_columns:
                return
            self._compare_columns.append(rel)
        else:
            return

        self._compare_columns_initialized = True
        self.compare_view.cancel_draft()
        self.reload()

    def _remove_compare_column(self, index: int) -> None:
        build = self.compare_view.current_build()
        table = build.table if build is not None else None
        if table is not None and index == 0:
            return
        if (self.compare_view.has_draft()
                and index == (len(table.columns) if table is not None else 0)):
            self.compare_view.cancel_draft()
            return
        if table is not None and 0 <= index < len(table.columns):
            rel = table.columns[index].column.key
        elif 0 <= index < len(self._compare_columns):
            rel = self._compare_columns[index]
        else:
            return
        if rel in self._compare_columns:
            self._compare_columns.remove(rel)
            self._compare_columns_initialized = True
            self.reload()

    def _select_compare_verse(self, verse: int) -> None:
        if not verse:
            return
        self._current = Reference(
            self._current.book, self._current.chapter, verse
        )
        if (self.bottom.isVisible()
                and self.bottom.currentWidget() is self.commentary):
            self.commentary.scroll_to_verse(verse)
        self.reference_changed.emit(self._current.label(self.settings.locale))

    def _search_selection(self) -> None:
        if self._citation_mode:
            browser = self.citations.browser
        elif self.parallel.isChecked():
            browser = self.compare_view.browser
        else:
            browser = self.primary
        text = browser.textCursor().selectedText().strip()
        if not text:
            text = self._current.label(self.settings.locale)
        if text:
            self.search_requested.emit(text)

    def _on_compare_anchor(self, url) -> None:
        """Reuse the traditional handlers for ref/strong links only.

        Notes are deliberately not routed from the comparison table: there is
        no per-column commentary selection, so a note cannot be resolved
        safely. ``cmp-*`` anchors belong to ``CompareView``.
        """
        text = url.toString()
        if text.startswith(("ref:", "strong:")):
            self._on_anchor(url)

    def _on_anchor(self, url) -> None:
        scheme = url.scheme()
        text = url.toString()
        if scheme == "v":
            self._verse_menu(int(url.path() or 0))
        elif scheme == "note":
            parts = text[len("note:"):].split(":")
            if len(parts) >= 3:
                try:
                    self._jump_to_note(int(parts[0]), int(parts[1]), int(parts[2]),
                                       parts[3] if len(parts) > 3 else "")
                except ValueError:
                    pass
        elif scheme == "strong":
            self._show_strong(text[len("strong:"):])
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
        note = QAction(tr("bible.note_jump"), self)
        note.triggered.connect(
            lambda: self._jump_to_note(ref.book, ref.chapter, verse, "")
        )
        menu.addAction(note)
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
            QGuiApplication.clipboard().setText(
                f"{page.title} — {to_plain(page.raw, hint=mod.stem, codepages=mod.codepages)}"
            )

    # ── state / theme ────────────────────────────────────────────────────
    def is_parallel(self) -> bool:
        return self.parallel.isChecked()

    def set_parallel(self, enabled: bool) -> None:
        self.parallel.setChecked(enabled)

    def is_commentary(self) -> bool:
        return self.bottom.isVisible()

    def set_commentary(self, enabled: bool) -> None:
        self._set_bottom_page(self.settings.bottom_page or "commentary", show=enabled)

    def compare_columns(self) -> list[str]:
        """Selected translation rel_paths, including the main one if chosen."""
        return list(self._compare_columns)

    def compare_split(self) -> bool:
        """Whether the stacked split was requested for this workspace."""
        return self.compare_view.is_split()

    def set_compare_split(self, split: bool) -> None:
        self.compare_view.set_split(bool(split))

    def set_compare_columns(self, rels: list[str] | None) -> None:
        """Set the table columns, keeping only installed Bibles, no duplicates."""
        selected: list[str] = []
        dropped: list[str] = []
        for rel in rels or []:
            if not rel or rel in selected:
                continue
            row = self.ctx.catalog.by_rel_path(rel)
            if row is not None and row.get("kind") == "bible":
                selected.append(rel)
            else:
                dropped.append(self._column_label(rel))
        self._compare_columns = selected
        self._compare_columns_initialized = True
        self._ensure_main_column()
        self._show_compare_notice(dropped)
        if self.parallel.isChecked():
            self.reload()

    def parallel_rel(self) -> str:
        """Legacy state: first selected column that is not the main Bible."""
        return next(
            (rel for rel in self._compare_columns if rel != self._main_rel),
            "",
        )

    def set_parallel_rel(self, rel: str) -> None:
        """Legacy restore: main Bible plus the old secondary translation."""
        columns = [self._main_rel] if self._main_rel else []
        if rel and rel != self._main_rel:
            columns.append(rel)
        self.set_compare_columns(columns)

    def commentary_rel(self) -> str:
        return self.commentary.commentary_rel()

    def set_commentary_rel(self, rel: str) -> None:
        self.commentary.set_commentary_rel(rel)

    def split_sizes(self) -> tuple[int, int]:
        sizes = self.vsplit.sizes()
        return (sizes[0], sizes[1]) if len(sizes) == 2 else (800, 280)

    def set_split_sizes(self, sizes: tuple[int, int]) -> None:
        if sizes and sizes[1] > 90:
            self.vsplit.setSizes(list(sizes))

    def reload_theme(self) -> None:
        css = self._css()
        self.primary.document().setDefaultStyleSheet(css)
        self.compare_view.reload_theme()
        self.commentary.reload_theme()
        self.strong.reload_theme()
        self.citations.show_chain(self.citations._refs, self.ctx.module(self._active_module()))
        self.reload()

    def retranslate(self) -> None:
        self.lbl_translation.setText(tr("bible.translation"))
        self.translation.setToolTip(tr("bible.translation_help"))
        self.book.setToolTip(tr("bible.book_help"))
        self.chapter.setToolTip(tr("bible.chapter_help"))
        self.parallel.setText(tr("bible.parallel"))
        self.parallel.setToolTip(tr("bible.parallel_help"))
        if self._compare_notice_names:
            self._show_compare_notice(self._compare_notice_names)
        self.btn_prev.setToolTip(tr("bible.prev"))
        self.btn_next.setToolTip(tr("bible.next"))
        self.btn_commentary.setText(tr("bible.bottom_commentary"))
        self.btn_commentary.setToolTip(tr("bible.bottom_commentary_help"))
        self.btn_strong.setText(tr("bible.bottom_strong"))
        self.btn_strong.setToolTip(tr("bible.bottom_strong_help"))
        self.btn_search_sel.setToolTip(tr("bible.search_word_help"))
        self.citation_input.setPlaceholderText(tr("bible.citation_placeholder"))
        self.citation_input.setToolTip(tr("bible.citation_help"))
        self.btn_citation_back.setToolTip(tr("bible.citation_back"))
        self.commentary.retranslate()
        self.strong.retranslate()
        self.citations.retranslate()
        self.compare_view.retranslate()
        self.reload()
