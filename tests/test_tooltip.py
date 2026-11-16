"""Bubbles: full text, verse cap and adjustable width."""

from __future__ import annotations

import math
import os
from types import SimpleNamespace

import pytest

from esword4linux.core.refresolver import MAX_VERSES, RefResolver


class _Page:
    def __init__(self, verse: int, text: str):
        self.verse = verse
        self.raw = text
        self.title = f"Juan 3:{verse}"


class _FakeModule:
    structure = "bible"
    stem = ""
    codepages = None

    def __init__(self, pages):
        self.pages = pages

    def bible_chapter(self, _book, _chapter):
        return list(self.pages)

    def bible_verse(self, _book, _chapter, verse):
        return next((p for p in self.pages if p.verse == verse), None)


class _FakeCatalog:
    row = {
        "rel_path": "BIBLIAS/test.bblx",
        "abbreviation": "RV1960",
        "title": "Biblia de prueba",
    }

    def by_rel_path(self, rel):
        return self.row if rel else None


def _resolver(pages) -> RefResolver:
    module = _FakeModule(pages)
    ctx = SimpleNamespace(
        settings=SimpleNamespace(
            reference_bible="", bible_module="BIBLIAS/test.bblx", locale="es",
        ),
        catalog=_FakeCatalog(),
        module=lambda _row: module,
        bibles=lambda: [_FakeCatalog.row],
        strong=None,
    )
    return RefResolver(ctx)


def test_single_verse_is_not_truncated():
    body = "Porque de tal manera amó Dios al mundo. " * 12
    out = _resolver([_Page(16, body)]).verse_tooltip("Juan 3:16")
    assert out.startswith("📖 Juan 3:16 (RV1960)")
    assert body.strip() in out
    assert "…" not in out


def test_verse_range_includes_every_verse():
    pages = [_Page(v, f"texto {v}") for v in range(16, 19)]
    out = _resolver(pages).verse_tooltip("Juan 3:16-18")
    for verse in (16, 17, 18):
        assert f"{verse} texto {verse}" in out


def test_chapter_is_capped_to_max_verses():
    pages = [_Page(v, f"texto {v}") for v in range(1, 31)]
    out = _resolver(pages).verse_tooltip("Juan 3")
    assert f"{MAX_VERSES} texto {MAX_VERSES}" in out
    assert f"{MAX_VERSES + 1} texto {MAX_VERSES + 1}" not in out
    assert "… (+20 verses)" in out


def test_bubble_width_grows_and_is_capped():
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QApplication

    from esword4linux.ui.tooltip import MAX_WIDTH, TipBubble

    app = QApplication.instance() or QApplication([])
    bubble = TipBubble()
    bubble.show_html(QPoint(100, 100), "📖 Juan 3:16 (RV1960)\nCorto.")
    short_width, short_height = bubble.width(), bubble.height()

    long_text = (
        "📖 Juan 3:16 (RV1960)\n"
        + ("Porque de tal manera amó Dios al mundo. " * 30)
    )
    bubble.show_html(QPoint(100, 100), long_text)
    assert bubble.width() > short_width
    assert bubble.width() <= MAX_WIDTH
    assert bubble.height() > short_height


def test_strong_header_uses_abbreviation_not_full_title():
    from esword4linux.core.strong import StrongIndex

    strong = StrongIndex.__new__(StrongIndex)
    strong.lookup = lambda _code: "texto de la entrada " * 100
    strong._resolve_page = lambda _code: (
        {
            "abbreviation": "Strong-Ultra",
            "title": "Strong-Ultra MULTILÉXICO (COMPENDIO EXEGÉTICO) " * 3,
        },
        None,
        None,
    )
    strong.label = lambda: "Strong-Ultra · título larguísimo"
    out = strong.tooltip("H430")
    header = out.split("\n", 1)[0]
    assert header == "H430 · Strong-Ultra"
    assert "COMPENDIO EXEGÉTICO" not in header


def test_bible_browser_fills_the_available_width():
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QWidget

    from esword4linux.ui.bible_view import BiblePane

    app = QApplication.instance() or QApplication([])
    browser = QWidget()
    host = BiblePane._center(browser)
    layout = host.layout()
    assert layout.count() == 1
    assert layout.itemAt(0).widget() is browser
    host.resize(1000, 200)
    host.show()
    app.processEvents()
    assert browser.width() == host.width()


def test_bubble_height_never_clips_last_line():
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QApplication

    from esword4linux.ui.theme import stylesheet
    from esword4linux.ui.tooltip import BOTTOM_EXTRA, PAD_V, TipBubble

    app = QApplication.instance() or QApplication([])
    previous = app.styleSheet()
    try:
        # The global QSS is what used to clip the QTextBrowser.
        app.setStyleSheet(stylesheet("dark", 15))
        bubble = TipBubble()
        lines = [f"{i} Línea de prueba con texto suficiente para envolver." for i in range(1, 13)]
        bubble.show_html(QPoint(50, 50), "📖 Prueba 1:1 (RV)\n" + "\n".join(lines))
        app.processEvents()
        doc_h = math.ceil(
            bubble.document().documentLayout().documentSize().height()
        )
        assert bubble.content_height >= doc_h
        assert bubble.height() >= doc_h + 2 * PAD_V + BOTTOM_EXTRA
        last = bubble.document().lastBlock()
        bottom = bubble.document().documentLayout().blockBoundingRect(last).bottom()
        assert bottom <= bubble.content_height + 1
    finally:
        app.setStyleSheet(previous)


def test_bubble_keeps_hebrew_line_visible():
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QApplication

    from esword4linux.ui.tooltip import TipBubble

    app = QApplication.instance() or QApplication([])
    bubble = TipBubble()
    bubble.show_html(
        QPoint(50, 50),
        "H8609 · Strong (Esp)\nתָּפַר\ntafár\nraíz primaria; coser:- coser.",
    )
    app.processEvents()
    doc = bubble.document()
    assert "תָּפַר" in doc.toPlainText()
    assert doc.blockCount() == 4  # header + word + transliteration + definition
    last = doc.lastBlock()
    bottom = doc.documentLayout().blockBoundingRect(last).bottom()
    assert bottom <= bubble.content_height + 1


def test_strong_tooltip_preserves_source_lines():
    from esword4linux.core.strong import StrongIndex

    strong = StrongIndex.__new__(StrongIndex)
    strong.lookup = lambda _code: "תָּפַר\ntafár\nraíz primaria; coser:- coser."
    strong._resolve_page = lambda _code: (
        {"abbreviation": "Strong (Esp)", "title": "Diccionario Strong"},
        None,
        None,
    )
    strong.label = lambda: "Strong (Esp) · Diccionario Strong"
    out = strong.tooltip("H8609")
    assert out.split("\n", 1)[0] == "H8609 · Strong (Esp)"
    assert "\nתָּפַר\ntafár\nraíz primaria" in out


def test_rich_browser_clear_all_caches():
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from esword4linux.ui.rich_browser import RichBrowser

    app = QApplication.instance() or QApplication([])
    first, second = RichBrowser(), RichBrowser()
    first._cache["ref:Juan 3:16"] = "viejo"
    second._cache["strong:G26"] = "viejo"
    RichBrowser.clear_all_caches()
    assert first._cache == {}
    assert second._cache == {}


def test_rich_browser_removes_single_quoted_titles():
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from esword4linux.ui.rich_browser import RichBrowser

    app = QApplication.instance() or QApplication([])
    browser = RichBrowser()
    browser.setHtml(
        "<a href=\"ref:Juan 3:16\" title='linea\nlineb'>Juan 3:16</a>"
    )
    assert browser._titles["ref:Juan 3:16"] == "linea\nlineb"
    assert "title=" not in browser.toHtml()


def test_bubble_body_has_no_blank_lines_or_tags():
    from esword4linux.ui.tooltip import to_bubble_html

    html = to_bubble_html("Cabecera\nuno\n\n</p>dos   \ntres\n")
    assert '<div class="ln">uno</div>' in html
    assert '<div class="ln">dos</div>' in html
    assert '<div class="ln">tres</div>' in html
    assert "<br>" not in html
    assert "</p>" not in html
    assert "\n\n" not in html
