"""Panel de citas múltiples: colección de pasajes de la cadena introducida."""

from __future__ import annotations

import html as _html

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from ..core.books import Reference, book_name
from ..core.context import AppContext
from ..core.text import to_plain
from ..i18n import tr
from .rich_browser import RichBrowser
from .theme import document_css_for, palette

MAX_VERSES = 250


class CitationPane(QWidget):
    """Lista agrupada de versículos recuperados de una cadena de citas."""

    open_reference = Signal(object)

    def __init__(self, ctx: AppContext, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.settings = ctx.settings
        self._refs: list[Reference] = []
        self._refs_count = 0
        self.setMinimumHeight(120)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        head = QWidget()
        row = QHBoxLayout(head)
        row.setContentsMargins(12, 5, 10, 5)
        row.setSpacing(8)
        self.title_label = QLabel(tr("bible.citations"))
        self.title_label.setObjectName("sectionTitle")
        row.addWidget(self.title_label)
        self.count = QLabel("")
        self.count.setObjectName("matchBadge")
        row.addWidget(self.count)
        row.addStretch(1)
        self.btn_hide = QPushButton("✕")
        self.btn_hide.setFixedWidth(30)
        self.btn_hide.setToolTip(tr("bible.bottom_hide"))
        self.btn_hide.clicked.connect(self._hide)
        row.addWidget(self.btn_hide)
        layout.addWidget(head)

        self.browser = RichBrowser(resolver=self.ctx.refs.tooltip)
        self.browser.setOpenLinks(False)
        self.browser.setOpenExternalLinks(False)
        self.browser.anchorClicked.connect(self._on_anchor)
        self.browser.document().setDefaultStyleSheet(
            document_css_for(self.settings)
        )
        layout.addWidget(self.browser, 1)

    def _hide(self) -> None:
        parent = self.parent()
        while parent is not None and not hasattr(parent, "_on_citations_closed"):
            parent = parent.parent()
        if parent is not None:
            parent._on_citations_closed()

    def retranslate(self) -> None:
        self.title_label.setText(tr("bible.citations"))
        self.btn_hide.setToolTip(tr("bible.bottom_hide"))
        if self._refs:
            self.count.setText(tr("bible.citations_count", n=self._refs_count))
        else:
            self.clear()

    def clear(self) -> None:
        self._refs = []
        self.browser.setHtml(f'<p class="muted">{tr("bible.citations_empty")}</p>')
        self.count.setText("")

    def show_chain(self, refs: list[Reference], mod) -> None:
        self._refs = list(refs)
        self.browser.document().setDefaultStyleSheet(
            document_css_for(self.settings)
        )
        if not refs:
            self.clear()
            return
        if mod is None:
            self.browser.setHtml(f'<p class="muted">{tr("main.no_resource")}</p>')
            self.count.setText("")
            return

        pal = palette(self.settings.theme)
        out = [f"<style>{document_css_for(self.settings)}</style>"]
        grouped: dict[tuple[int, int], list] = {}
        missing: list[str] = []
        total = 0
        for ref in refs:
            pages = self._pages(mod, ref)
            if not pages:
                missing.append(ref.label(self.settings.locale))
                continue
            for page in pages:
                if total >= MAX_VERSES:
                    break
                key = (page.book or ref.book, page.chapter)
                grouped.setdefault(key, []).append(page)
                total += 1
        for (book, chapter), pages in grouped.items():
            header = f"{book_name(book, self.settings.locale)} {chapter}"
            out.append(f'<div class="group">{_html.escape(header)}</div>')
            seen = set()
            for page in pages:
                if page.verse is not None and page.verse in seen:
                    continue
                seen.add(page.verse)
                text = to_plain(page.raw, hint=mod.stem, codepages=mod.codepages)
                href = f"cit:{book}:{chapter}:{page.verse or 0}"
                out.append(
                    f'<div class="hit"><a href="{href}" '
                    f'style="color:{pal.accent};text-decoration:none;">'
                    f'<b>{page.verse or ""}</b></a> '
                    f'{_html.escape(text)}</div>'
                )
        for label in missing:
            out.append(
                f'<div class="hit"><span class="muted">'
                f'{_html.escape(label)} · {tr("bible.citations_missing")}</span></div>'
            )
        if total >= MAX_VERSES:
            out.append(f'<p class="muted">{tr("bible.citations_capped", n=MAX_VERSES)}</p>')
        self.browser.setHtml("".join(out))
        self.browser.verticalScrollBar().setValue(0)
        self._refs_count = total
        self.count.setText(tr("bible.citations_count", n=total))

    def _pages(self, mod, ref: Reference):
        if ref.chapter_end and ref.chapter_end >= ref.chapter:
            pages = []
            for chapter in range(ref.chapter, ref.chapter_end + 1):
                chapter_pages = mod.bible_chapter(ref.book, chapter)
                if chapter == ref.chapter and ref.verse:
                    chapter_pages = [
                        page for page in chapter_pages
                        if page.verse and page.verse >= ref.verse
                    ]
                pages.extend(chapter_pages)
            return pages
        if ref.verse is not None:
            if ref.verse_end and ref.verse_end >= ref.verse:
                return [
                    page for page in mod.bible_chapter(ref.book, ref.chapter)
                    if page.verse and ref.verse <= page.verse <= ref.verse_end
                ]
            page = mod.bible_verse(ref.book, ref.chapter, ref.verse)
            return [page] if page is not None else []
        return mod.bible_chapter(ref.book, ref.chapter)

    def _on_anchor(self, url) -> None:
        if url.scheme() != "cit":
            return
        parts = (url.path() or url.toString()[4:]).split(":")
        if len(parts) < 3:
            return
        try:
            book, chapter, verse = (int(parts[0]), int(parts[1]), int(parts[2]))
        except ValueError:
            return
        self.open_reference.emit(Reference(book, chapter, verse or None))
