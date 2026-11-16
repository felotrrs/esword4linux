"""Bible view: navigation, parallel translation and stacked bottom panel.

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
    QAction, QGuiApplication, QIntValidator, QStandardItem, QStandardItemModel,
)
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QCompleter, QHBoxLayout, QLabel,
    QLineEdit, QMenu, QPushButton, QSplitter, QStackedWidget, QToolButton,
    QVBoxLayout, QWidget,
)

from ..core.books import Reference, book_name, parse_reference
from ..core.commentary import best_commentary
from ..core.refchain import parse_reference_chain
from ..core.context import AppContext
from ..core.text import snippet, to_plain, to_rich
from ..i18n import tr
from .citation_pane import CitationPane
from .commentary_pane import CommentaryPane
from .rich_browser import RichBrowser
from .strong_pane import StrongPane
from .language import language_label, language_sort_key
from .theme import document_css_for, palette

_STRONG_COLOR = "#8f6bc4"
_STRONG_STYLE = f"color:{_STRONG_COLOR};font-size:80%;text-decoration:none;"
_TAGS_RE = re.compile(r"<[^>]+>")
_SUP_RE = re.compile(r"(?is)<sup>(.*?)</sup>")
_STRONG_IN_TEXT = re.compile(r"\b([GH]\d{1,5})\b")
_REF_A_RE = re.compile(r'<a href="ref:([^"]+)">')


def fill_bible_combo(combo: QComboBox, bibles: list[dict], current_rel: str,
                     *, editable: bool = True) -> None:
    """Fill a Bible combo grouped by language (optionally editable)."""
    combo.blockSignals(True)
    model = QStandardItemModel(combo)
    grouped: dict[str, list[dict]] = {}
    for mod in bibles:
        grouped.setdefault(mod.get("language") or "und", []).append(mod)

    first_selectable = -1
    for code in sorted(grouped, key=language_sort_key):
        items = grouped[code]
        header = QStandardItem(f"— {language_label(code)} ({len(items)}) —")
        header.setEnabled(False)
        header.setSelectable(False)
        header.setData(None, Qt.UserRole)
        font = header.font()
        font.setBold(True)
        header.setFont(font)
        model.appendRow(header)
        for mod in sorted(
            items,
            key=lambda m: ((m.get("abbreviation") or "").lower(),
                           (m.get("title") or "").lower()),
        ):
            label = (
                f"{mod['abbreviation']} — {mod['title']}"
                if mod.get("abbreviation") else (mod.get("title") or "")
            )
            item = QStandardItem(label[:110])
            item.setData(mod["rel_path"], Qt.UserRole)
            item.setToolTip(
                f"{mod.get('title') or ''}\n{language_label(code)}"
            )
            model.appendRow(item)
            if first_selectable < 0:
                first_selectable = model.rowCount() - 1

    combo.setModel(model)
    combo.setEditable(editable)
    combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
    combo.setMaxVisibleItems(20)
    combo.setSizeAdjustPolicy(
        QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
    )
    combo.setMinimumContentsLength(18)
    combo.setMaximumWidth(320)
    if editable:
        completer = QCompleter(model, combo)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        combo.setCompleter(completer)
    idx = combo.findData(current_rel)
    if idx < 0:
        idx = first_selectable
    if idx >= 0:
        combo.setCurrentIndex(idx)
    if editable and combo.lineEdit() is not None:
        # With a long title, QLineEdit leaves the cursor at the end and it
        # looks as if the translation starts with "...titles, notes...".
        combo.lineEdit().setCursorPosition(0)
    combo.blockSignals(False)


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
        self._secondary_rel = ""
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
        layout.addWidget(self._build_toolbar())

        self.vsplit = QSplitter(Qt.Vertical)
        self.hsplit = QSplitter(Qt.Horizontal)
        self.primary = self._make_browser()
        self.second = self._make_browser()
        self.primary_host = self._center(self.primary)
        self.second_host = self._center(self.second)
        self.citations = CitationPane(self.ctx)
        self.citations.btn_hide.hide()
        self.citations.open_reference.connect(self._open_citation_reference)
        self.citations_second = CitationPane(self.ctx)
        self.citations_second.btn_hide.hide()
        self.citations_second.open_reference.connect(self._open_citation_reference)
        self.primary_stack = QStackedWidget()
        self.primary_stack.addWidget(self.primary_host)
        self.primary_stack.addWidget(self.citations)
        self.second_stack = QStackedWidget()
        self.second_stack.addWidget(self.second_host)
        self.second_stack.addWidget(self.citations_second)
        self.hsplit.addWidget(self.primary_stack)
        self.hsplit.addWidget(self.second_stack)
        self.host_second = self.second_stack
        self.host_second.hide()

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

        self.vsplit.addWidget(self.hsplit)
        self.vsplit.addWidget(self.bottom)
        self.vsplit.setStretchFactor(0, 4)
        self.vsplit.setStretchFactor(1, 1)
        layout.addWidget(self.vsplit, 1)

        page = self.settings.bottom_page
        self._set_bottom_page(page if page in ("commentary", "strong")
                              else "commentary",
                              show=self.settings.show_commentary_inline)

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        row = QHBoxLayout(bar)
        row.setContentsMargins(10, 6, 10, 6)
        row.setSpacing(6)

        self.lbl_translation = QLabel(tr("bible.translation"))
        row.addWidget(self.lbl_translation)
        self.translation = QComboBox()
        self.translation.setMinimumWidth(200)
        self.translation.setToolTip(tr("bible.translation_help"))
        self.translation.currentIndexChanged.connect(self._on_translation)
        row.addWidget(self.translation)

        self.citation_input = QLineEdit()
        self.citation_input.setMinimumWidth(220)
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
        self.book.setMinimumWidth(140)
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
        self.secondary = QComboBox()
        self.secondary.setMinimumWidth(150)
        self.secondary.setToolTip(tr("bible.parallel_help"))
        self.secondary.currentIndexChanged.connect(self._on_secondary)
        self.secondary.setVisible(self.parallel.isChecked())
        row.addWidget(self.secondary)

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
        primary_rel = self.translation.currentData()
        previous_secondary = self._secondary_rel or ""
        default_secondary = previous_secondary
        if not default_secondary:
            candidates = [m for m in bibles if m["rel_path"] != primary_rel]
            if candidates:
                default_secondary = max(candidates, key=lambda m: m["entries"] or 0)["rel_path"]
        fill_bible_combo(self.secondary, bibles, default_secondary, editable=False)
        self._secondary_rel = self.secondary.currentData() or ""
        self._loading = False
        self._main_rel = self.translation.currentData() or ""
        self._rebuild_books()
        self._apply_commentary_match()
        self.navigate(self._current)

    def load_module(self, row: dict) -> None:
        self._loading = True
        self.reload_modules()
        idx = self.translation.findData(row["rel_path"])
        if idx >= 0:
            self.translation.setCurrentIndex(idx)
        self._loading = False
        self._main_rel = row["rel_path"]
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
        chapter_label = f"{book_name(int(book_id), self.settings.locale)} {int(chapter)}"
        self.primary.document().setDefaultStyleSheet(self._css())
        self.second.document().setDefaultStyleSheet(self._css())
        self.primary.setHtml(self._render_chapter(mod, int(book_id), int(chapter)))
        self.primary.clear_cache()

        if self.parallel.isChecked():
            srow = self.ctx.catalog.by_rel_path(self.secondary.currentData() or "")
            smod = self.ctx.module(srow) if srow else None
            if smod:
                if self._citation_mode and self.citations._refs:
                    self.citations_second.show_chain(self.citations._refs, smod)
                    self.second_stack.setCurrentWidget(self.citations_second)
                else:
                    self.second.setHtml(
                        self._render_chapter(smod, int(book_id), int(chapter))
                    )
                    self.second_stack.setCurrentWidget(self.second_host)

        if self.bottom.isVisible():
            if self.bottom.currentWidget() is self.commentary:
                self._refresh_commentary()
            elif self.bottom.currentWidget() is self.strong and self.strong.code:
                self.strong.show_code(self.strong.code)

        if self._citation_mode and self.citations._refs:
            self.citations.show_chain(self.citations._refs, mod)
            self.primary_stack.setCurrentWidget(self.citations)
        if anchor:
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
        self.second.clear_cache()
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
            self.primary_stack.setCurrentWidget(self.primary_host)
            self.second_stack.setCurrentWidget(self.second_host)

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
        self.host_second.setVisible(checked)
        self.secondary.setVisible(checked)
        if checked:
            self.reload()

    def _on_secondary(self, _index: int) -> None:
        self._secondary_rel = self.secondary.currentData() or ""
        if self.parallel.isChecked():
            self.reload()

    def _search_selection(self) -> None:
        browser = self.citations.browser if self._citation_mode else self.primary
        text = browser.textCursor().selectedText().strip()
        if not text:
            text = self._current.label(self.settings.locale)
        if text:
            self.search_requested.emit(text)

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

    def parallel_rel(self) -> str:
        return self.secondary.currentData() or ""

    def set_parallel_rel(self, rel: str) -> None:
        idx = self.secondary.findData(rel)
        if idx >= 0:
            self.secondary.setCurrentIndex(idx)
            self._secondary_rel = rel

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
        for browser in (self.primary, self.second):
            browser.document().setDefaultStyleSheet(css)
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
        self.secondary.setToolTip(tr("bible.parallel_help"))
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
        self.citations_second.retranslate()
        self.reload()
