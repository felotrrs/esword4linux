"""Advanced search filters: type, work, book and chapter.

Corpus-free: the catalog rows, the FTS5 index and the modules are synthetic and
live in ``tmp_path``. Nothing here touches the user's configuration, the user's
cache or a real e-Sword module.
"""

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from esword4linux.config import Settings  # noqa: E402
from esword4linux.core.context import AppContext  # noqa: E402
from esword4linux.core.search import SearchFilters  # noqa: E402
from esword4linux.i18n import tr  # noqa: E402
from esword4linux.ui.search_view import SearchView  # noqa: E402

# ── synthetic modules ────────────────────────────────────────────────────
# Bible A: Genesis (1,2,3) + Exodus (1).
# Bible B: Genesis (1) + Numbers (1,3) — chapter 2 does not exist on purpose,
# to prove that the selector never invents a chapter.
BIBLE_A = [(1, 1, 1, "uno"), (1, 2, 1, "dos"), (1, 3, 1, "tres"),
           (2, 1, 1, "cuatro")]
BIBLE_B = [(1, 1, 1, "uno"), (4, 1, 1, "uno"), (4, 3, 1, "tres")]


def _make_bible_module(path: Path, rows: list[tuple[int, int, int, str]]) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "CREATE TABLE Bible (Book INT, Chapter INT, Verse INT, Scripture TEXT)"
        )
        conn.execute(
            "CREATE INDEX BookChapterVerseIndex ON Bible (Book, Chapter, Verse)"
        )
        conn.executemany(
            "INSERT INTO Bible (Book, Chapter, Verse, Scripture) VALUES (?,?,?,?)",
            rows,
        )
        conn.commit()
    finally:
        conn.close()


def _add_module(catalog, *, module_id: int, rel_path: str, path: Path,
                kind: str, title: str, abbreviation: str,
                entries: int = 10, status: str = "ready") -> None:
    catalog.conn.execute(
        "INSERT INTO module(id, path, rel_path, filename, ext, structure, kind, "
        "title, abbreviation, language, encrypted, entries, size, mtime, "
        "index_status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (module_id, str(path), rel_path, Path(rel_path).name,
         Path(rel_path).suffix.lstrip("."), kind, kind, title, abbreviation,
         "en", 0, entries, 1000, 1.0, status),
    )
    catalog.conn.commit()


def _pages(pages: list[tuple], kind: str) -> list[dict]:
    out = []
    for page in pages:
        if kind == "bible" or kind == "commentary":
            book, chapter, verse, body = page
            out.append({
                "ref": f"{book}:{chapter}:{verse}", "title": f"{book} {chapter}",
                "body": body, "book": book, "chapter": chapter, "verse": verse,
                "ord": 0,
            })
        else:
            ref, body = page
            out.append({
                "ref": ref, "title": ref, "body": body,
                "book": None, "chapter": None, "verse": None, "ord": 0,
            })
    return out


@pytest.fixture()
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def env(app, tmp_path):
    """AppContext with a real catalog, a real FTS5 index and fake modules."""
    modules = tmp_path / "modules"
    modules.mkdir()
    settings = Settings(resources_dir=str(modules),
                        cache_dir=str(tmp_path / "cache"))
    ctx = AppContext(settings)

    bible_a = modules / "a.bblx"
    bible_b = modules / "b.bblx"
    _make_bible_module(bible_a, BIBLE_A)
    _make_bible_module(bible_b, BIBLE_B)

    catalog = ctx.catalog
    _add_module(catalog, module_id=1, rel_path="a.bblx", path=bible_a,
                kind="bible", title="Bible A", abbreviation="AAA", entries=4)
    _add_module(catalog, module_id=2, rel_path="b.bblx", path=bible_b,
                kind="bible", title="Bible B", abbreviation="BBB", entries=3)
    _add_module(catalog, module_id=3, rel_path="d.dctx", path=modules / "d.dctx",
                kind="dictionary", title="Dictionary", abbreviation="DDD")
    _add_module(catalog, module_id=4, rel_path="c.cmtx", path=modules / "c.cmtx",
                kind="commentary", title="Commentary", abbreviation="CCC")
    _add_module(catalog, module_id=5, rel_path="l.lexi", path=modules / "l.lexi",
                kind="lexicon", title="Lexicon", abbreviation="LLL")

    ctx.store.add_pages(1, "bible", _pages([
        (1, 1, 1, "la paz de dios"),
        (1, 2, 1, "paz en el camino"),
        (1, 3, 1, "paz y luz"),
        (2, 1, 1, "paz de exodo"),
    ], "bible"))
    ctx.store.add_pages(2, "bible", _pages([
        (1, 1, 1, "paz en genesis"),
        (4, 1, 1, "paz en numeros"),
        (4, 3, 1, "paz numeros tres"),
    ], "bible"))
    ctx.store.add_pages(3, "dictionary", _pages([
        ("Paz", "paz shalom amor"),
        ("Dios", "g2316 el dios supremo"),
    ], "dictionary"))
    ctx.store.add_pages(4, "commentary", _pages([
        (1, 1, 1, "paz comentada"),
    ], "commentary"))
    ctx.store.add_pages(5, "lexicon", _pages([
        ("G2316", "g2316 deos dios"),
    ], "lexicon"))
    try:
        yield ctx
    finally:
        ctx.close_all()


# ── engine: text search ──────────────────────────────────────────────────
def test_unfiltered_search_reaches_every_module(env):
    result = env.search.search("paz")
    assert result.intent == "text"
    assert len(result.hits) == 9            # 4 + 3 + dictionary + commentary
    assert result.searched_modules == 5
    assert {h.module_id for h in result.hits} == {1, 2, 3, 4}


def test_filter_by_type(env):
    result = env.search.search("paz", filters=SearchFilters(kinds=("dictionary",)))
    assert {h.module_id for h in result.hits} == {3}
    assert len(result.hits) == 1


def test_filter_by_work(env):
    result = env.search.search("paz", filters=SearchFilters(module_id=2))
    assert {h.module_id for h in result.hits} == {2}
    assert len(result.hits) == 3


def test_filter_by_book(env):
    result = env.search.search(
        "paz", filters=SearchFilters(kinds=("bible",), book=1)
    )
    assert {h.module_id for h in result.hits} == {1, 2}
    assert len(result.hits) == 4            # A: 3 pages, B: 1 page


def test_filter_by_chapter(env):
    result = env.search.search(
        "paz", filters=SearchFilters(kinds=("bible",), book=1, chapter=2)
    )
    assert [(h.module_id, h.ref) for h in result.hits] == [(1, "1:2:1")]


def test_combined_filters(env):
    result = env.search.search(
        "paz",
        filters=SearchFilters(kinds=("bible",), module_id=1, book=2, chapter=1),
    )
    assert [(h.module_id, h.ref) for h in result.hits] == [(1, "2:1:1")]


# ── engine: Strong branch ────────────────────────────────────────────────
def test_strong_without_filters_is_unchanged(env):
    result = env.search.search("G2316")
    assert result.intent == "strong"
    assert {h.module_id for h in result.hits} == {3, 5}
    assert result.searched_modules == 2      # lexicon + dictionary


def test_strong_with_bible_type_returns_nothing(env):
    result = env.search.search("G2316", filters=SearchFilters(kinds=("bible",)))
    assert result.intent == "strong"
    assert result.hits == []
    assert result.searched_modules == 0


def test_strong_with_dictionary_type_excludes_lexicons(env):
    result = env.search.search(
        "G2316", filters=SearchFilters(kinds=("dictionary",))
    )
    assert {h.module_id for h in result.hits} == {3}


def test_strong_with_a_specific_work(env):
    result = env.search.search("G2316", filters=SearchFilters(module_id=5))
    assert {h.module_id for h in result.hits} == {5}


def test_strong_ignores_book_and_chapter(env):
    base = env.search.search("G2316", filters=SearchFilters(module_id=5))
    filtered = env.search.search(
        "G2316", filters=SearchFilters(module_id=5, book=1, chapter=1)
    )
    assert [(h.module_id, h.ref) for h in filtered.hits] == \
        [(h.module_id, h.ref) for h in base.hits]


# ── engine: existing semantics preserved ─────────────────────────────────
def test_reference_navigation_is_unchanged(env):
    result = env.search.search("Juan 3:16")
    assert result.intent == "reference"
    assert result.reference.book == 43 and result.reference.chapter == 3
    # The reference intent is a navigation shortcut: filters do not apply.
    filtered = env.search.search(
        "Juan 3:16", filters=SearchFilters(kinds=("bible",), book=1, chapter=1)
    )
    assert filtered.intent == "reference"
    assert filtered.reference == result.reference


def test_legacy_scope_argument_is_backward_compatible(env):
    scoped = env.search.search("paz", scope=[1])
    assert {h.module_id for h in scoped.hits} == {1}
    assert len(scoped.hits) == 4
    everything = env.search.search("paz")
    assert len(everything.hits) == 9


def test_filters_take_precedence_over_the_legacy_scope(env):
    result = env.search.search(
        "paz", scope=[1], filters=SearchFilters(module_id=3)
    )
    assert {h.module_id for h in result.hits} == {3}


# ── UI ───────────────────────────────────────────────────────────────────
@pytest.fixture()
def view(app, env):
    search = SearchView(env)
    search.resize(1200, 700)
    search.show()
    for _ in range(3):
        app.processEvents()
    try:
        yield search
    finally:
        search.shutdown()
        search.deleteLater()
        app.processEvents()


def _wait_lists(view: SearchView, app, timeout: float = 5.0) -> bool:
    """Wait until the background book/chapter requests are done."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        idle = (view._books_worker is None
                and view._pending_books is None
                and view._pending_chapters is None)
        if idle:
            app.processEvents()
            if (view._books_worker is None and view._pending_books is None
                    and view._pending_chapters is None):
                return True
        time.sleep(0.005)
    return False


def _select(combo, data) -> None:
    index = combo.findData(data)
    if index < 0:            # Qt cannot compare tuple data
        index = next(
            (i for i in range(combo.count()) if combo.itemData(i) == data), -1
        )
    assert index >= 0, f"{data!r} is not in the combo"
    combo.setCurrentIndex(index)


def _values(combo) -> list:
    return [combo.itemData(i) for i in range(combo.count()) if combo.itemData(i)
            is not None]


def test_bible_filters_follow_the_activation_matrix(app, view):
    # All types: visible but disabled, and they contribute nothing.
    assert view.book_filter.isVisible()
    assert view.chapter_filter.isVisible()
    assert not view.book_filter.isEnabled()
    assert not view.chapter_filter.isEnabled()
    # Bible
    _select(view.type_filter, "bible")
    app.processEvents()
    assert view.book_filter.isVisible()
    assert view.book_filter.isEnabled()
    assert view.chapter_filter.isVisible()
    assert not view.chapter_filter.isEnabled()
    assert _wait_lists(view, app)
    _select(view.book_filter, 1)
    app.processEvents()
    assert view.chapter_filter.isVisible()
    assert view.chapter_filter.isEnabled()
    # Dictionary / commentary: still visible, disabled and cleared
    for kind in ("dictionary", "commentary"):
        _select(view.type_filter, kind)
        app.processEvents()
        assert view.book_filter.isVisible()
        assert view.chapter_filter.isVisible()
        assert not view.book_filter.isEnabled()
        assert not view.chapter_filter.isEnabled()
        filters = view.filters()
        assert filters.book is None and filters.chapter is None


def test_book_list_is_the_union_of_the_scope(app, view):
    _select(view.type_filter, "bible")
    app.processEvents()
    assert _wait_lists(view, app)
    # Bible A has 1,2; Bible B has 1,4.
    assert _values(view.book_filter) == [1, 2, 4]


def test_book_list_of_a_specific_work_is_exclusive(app, view):
    _select(view.type_filter, "bible")
    app.processEvents()
    assert _wait_lists(view, app)
    _select(view.work_filter, 2)          # Bible B
    app.processEvents()
    assert _wait_lists(view, app)
    assert _values(view.book_filter) == [1, 4]


def test_chapters_come_from_the_selected_work(app, view):
    _select(view.type_filter, "bible")
    app.processEvents()
    assert _wait_lists(view, app)
    _select(view.work_filter, 2)          # Bible B
    app.processEvents()
    assert _wait_lists(view, app)
    _select(view.book_filter, 4)          # Numbers: chapters 1 and 3, no 2
    app.processEvents()
    assert _wait_lists(view, app)
    assert _values(view.chapter_filter) == [1, 3]


def test_chapter_union_never_invents_a_chapter(app, view):
    _select(view.type_filter, "bible")
    app.processEvents()
    assert _wait_lists(view, app)
    _select(view.book_filter, 4)          # only Bible B has Numbers
    app.processEvents()
    assert _wait_lists(view, app)
    assert _values(view.chapter_filter) == [1, 3]


def test_type_change_invalidates_the_dependent_filters(app, view):
    _select(view.type_filter, "bible")
    app.processEvents()
    assert _wait_lists(view, app)
    _select(view.work_filter, 1)
    app.processEvents()
    assert _wait_lists(view, app)
    _select(view.book_filter, 2)
    app.processEvents()
    assert _wait_lists(view, app)
    _select(view.chapter_filter, 1)
    app.processEvents()
    filters = view.filters()
    assert (filters.module_id, filters.book, filters.chapter) == (1, 2, 1)

    _select(view.type_filter, "dictionary")
    app.processEvents()
    filters = view.filters()
    assert filters.kinds == ("dictionary",)
    assert filters.module_id is None
    assert filters.book is None and filters.chapter is None


def test_work_change_invalidates_the_book(app, view):
    _select(view.type_filter, "bible")
    app.processEvents()
    assert _wait_lists(view, app)
    _select(view.work_filter, 2)          # Bible B: books 1 and 4
    app.processEvents()
    assert _wait_lists(view, app)
    _select(view.book_filter, 4)
    app.processEvents()
    assert _wait_lists(view, app)
    assert view.filters().book == 4

    _select(view.work_filter, 1)          # Bible A has no Numbers
    app.processEvents()
    assert _wait_lists(view, app)
    assert view.filters().book is None


def test_book_change_invalidates_the_chapter(app, view):
    _select(view.type_filter, "bible")
    app.processEvents()
    assert _wait_lists(view, app)
    _select(view.work_filter, 1)
    app.processEvents()
    assert _wait_lists(view, app)
    _select(view.book_filter, 1)          # Genesis: 1,2,3
    app.processEvents()
    assert _wait_lists(view, app)
    _select(view.chapter_filter, 2)
    app.processEvents()
    assert view.filters().chapter == 2

    _select(view.book_filter, 2)          # Exodus
    app.processEvents()
    assert _wait_lists(view, app)
    assert view.filters().chapter is None


def test_bible_work_under_all_types_does_not_reveal_bible_filters(app, view):
    _select(view.work_filter, 1)          # Bible A, type still "All types"
    app.processEvents()
    assert _wait_lists(view, app)
    # Visible at all times, never activated by the work selection.
    assert view.book_filter.isVisible()
    assert view.chapter_filter.isVisible()
    assert not view.book_filter.isEnabled()
    assert not view.chapter_filter.isEnabled()
    filters = view.filters()
    assert filters.kinds == ()
    assert filters.module_id == 1
    assert filters.book is None and filters.chapter is None


def test_reset_clears_every_filter(app, view):
    _select(view.type_filter, "bible")
    app.processEvents()
    assert _wait_lists(view, app)
    _select(view.work_filter, 1)
    app.processEvents()
    assert _wait_lists(view, app)
    _select(view.book_filter, 2)
    app.processEvents()
    assert _wait_lists(view, app)
    _select(view.chapter_filter, 1)
    app.processEvents()
    assert view.filters().is_active()
    assert view.btn_reset.isEnabled()

    view.btn_reset.click()
    app.processEvents()
    filters = view.filters()
    assert not filters.is_active()
    assert view.type_filter.currentData() == ""
    assert not view.btn_reset.isEnabled()
    assert not view.book_filter.isEnabled()
    assert view.book_filter.isVisible()


def test_empty_results_without_filters(app, view):
    view.set_query("zzzz-no-match")
    assert tr("search.no_results", q="zzzz-no-match") in \
        view.results.toPlainText()


def test_empty_results_with_filters(app, view):
    _select(view.type_filter, "dictionary")
    app.processEvents()
    view.set_query("zzzz-no-match")
    assert tr("search.no_results_filtered", q="zzzz-no-match") in \
        view.results.toPlainText()


def test_ui_without_filters_returns_the_engine_results(app, view, env):
    view.set_query("paz")
    assert view.results.toHtml().count('href="hit:') == \
        len(env.search.search("paz").hits)


def test_language_change_keeps_the_selection_and_translates_the_books(
    app, view, env
):
    from esword4linux import i18n
    from esword4linux.core.books import book_name

    _select(view.type_filter, "bible")
    app.processEvents()
    assert _wait_lists(view, app)
    _select(view.book_filter, 1)
    app.processEvents()
    assert _wait_lists(view, app)
    _select(view.chapter_filter, 2)
    app.processEvents()

    old_locale = env.settings.locale
    try:
        env.settings.locale = "es"
        i18n.set_locale("es")
        view.retranslate()
        app.processEvents()
        filters = view.filters()
        assert (filters.book, filters.chapter) == (1, 2)
        assert view.book_filter.currentText() == book_name(1, "es")
        assert view.type_filter.currentText() == tr("kind.bible")
        # A book list refresh that keeps the book keeps the chapter list too.
        assert _values(view.chapter_filter) == [1, 2, 3]
    finally:
        env.settings.locale = old_locale
        i18n.set_locale(old_locale)
        view.retranslate()
        app.processEvents()


# ── worker lifecycle ─────────────────────────────────────────────────────
def test_stale_book_result_is_discarded(app, view):
    _select(view.type_filter, "bible")
    app.processEvents()
    assert _wait_lists(view, app)
    stale = view._gen_books - 1
    view._on_worker_done(("books", stale, [99]))
    assert 99 not in view._books
    view._on_worker_done(("books", view._gen_books, [1, 2]))
    assert view._books == [1, 2]


def test_result_after_shutdown_is_ignored(app, view):
    _select(view.type_filter, "bible")
    app.processEvents()
    assert _wait_lists(view, app)
    before = list(view._books)
    view.shutdown()
    view._on_worker_done(("books", view._gen_books, [99]))
    assert view._books == before


def test_a_missing_module_is_skipped(tmp_path):
    present = tmp_path / "present.bblx"
    _make_bible_module(present, [(1, 1, 1, "x"), (2, 1, 1, "y")])
    missing = tmp_path / "removed.bblx"
    kind, gen, values = SearchView._compute_lists(
        7, "books", [(1, str(missing)), (2, str(present))], None
    )
    assert (kind, gen, values) == ("books", 7, [1, 2])


def test_an_unreadable_module_is_skipped(tmp_path):
    broken = tmp_path / "broken.bblx"
    broken.write_bytes(b"this is not a sqlite database")
    kind, gen, values = SearchView._compute_lists(
        3, "books", [(1, str(broken))], None
    )
    assert (kind, gen, values) == ("books", 3, [])


def test_shutdown_while_a_worker_runs_is_safe(app, view):
    _select(view.type_filter, "bible")
    app.processEvents()
    view.shutdown()                       # interrupts and waits if needed
    assert view._books_worker is None
    app.processEvents()


# ── filter row: fixed layout and progressive activation ─────────────────
CONTROLS = ("type_filter", "work_filter", "book_filter", "chapter_filter")


def _slot(view, widget) -> tuple[int, int]:
    """(line, x) of a control inside the filter bar (flow layout)."""
    bar = view._filter_flow.parentWidget()
    point = widget.mapTo(bar, QPoint(0, 0))
    return point.y(), point.x()


def _geometry(view) -> dict:
    return {
        name: _slot(view, getattr(view, name))
        for name in ("type_filter", "work_filter", "book_filter",
                     "chapter_filter", "btn_reset")
    }


def test_all_filter_controls_are_always_visible(app, view):
    for kind in ("", "bible", "dictionary", "commentary"):
        if kind:
            _select(view.type_filter, kind)
        app.processEvents()
        for name in CONTROLS:
            widget = getattr(view, name)
            assert widget.isVisible(), f"{name} must stay visible for {kind!r}"
        assert view.btn_reset.isVisible()
    assert _wait_lists(view, app)


def test_filter_controls_keep_their_slot_across_states(app, view):
    _select(view.type_filter, "bible")
    app.processEvents()
    assert _wait_lists(view, app)
    expected = {name: _slot(view, getattr(view, name)) for name in CONTROLS}
    for kind in ("", "dictionary", "commentary", "bible"):
        if kind:
            _select(view.type_filter, kind)
        app.processEvents()
        assert _wait_lists(view, app)
        for name in CONTROLS:
            assert _slot(view, getattr(view, name)) == expected[name], (
                f"{name} moved for type {kind!r}"
            )
    # Every control stays on the first line, in the reading order
    # Type → Work → Book → Chapter, before Reset.
    lines = {line for line, _x in expected.values()}
    assert lines == {expected["type_filter"][0]}
    xs = [expected[name][1] for name in CONTROLS]
    assert xs == sorted(xs)
    assert xs[-1] < _slot(view, view.btn_reset)[1]


def test_filter_controls_keep_their_geometry_across_states(app, view):
    app.processEvents()
    baseline = _geometry(view)
    for kind in ("bible", "dictionary", "commentary", "", "bible"):
        if kind:
            _select(view.type_filter, kind)
        app.processEvents()
        assert _wait_lists(view, app)
        assert _geometry(view) == baseline, f"geometry changed for {kind!r}"


def test_book_and_chapter_enablement_follows_the_rules(app, view):
    # All: both disabled
    assert not view.book_filter.isEnabled()
    assert not view.chapter_filter.isEnabled()
    # Bible: book enabled, chapter disabled until a book is chosen
    _select(view.type_filter, "bible")
    app.processEvents()
    assert _wait_lists(view, app)
    assert view.book_filter.isEnabled()
    assert not view.chapter_filter.isEnabled()
    # Bible + book: both enabled
    _select(view.book_filter, 1)
    app.processEvents()
    assert _wait_lists(view, app)
    assert view.book_filter.isEnabled()
    assert view.chapter_filter.isEnabled()
    # Back to All: both disabled and cleared
    _select(view.type_filter, "")
    app.processEvents()
    assert not view.book_filter.isEnabled()
    assert not view.chapter_filter.isEnabled()
    assert view.book_filter.currentData() is None
    assert view.chapter_filter.currentData() is None
    # Other types
    for kind in ("dictionary", "commentary"):
        _select(view.type_filter, kind)
        app.processEvents()
        assert not view.book_filter.isEnabled()
        assert not view.chapter_filter.isEnabled()


def test_disabled_controls_do_not_contribute_to_the_filters(app, view):
    _select(view.type_filter, "bible")
    app.processEvents()
    assert _wait_lists(view, app)
    _select(view.book_filter, 1)
    app.processEvents()
    assert _wait_lists(view, app)
    _select(view.chapter_filter, 2)
    app.processEvents()
    assert view.filters().book == 1 and view.filters().chapter == 2
    # Switching the type clears them even before the combos are rebuilt.
    _select(view.type_filter, "dictionary")
    app.processEvents()
    filters = view.filters()
    assert filters.kinds == ("dictionary",)
    assert filters.book is None and filters.chapter is None
    assert view.book_filter.isVisible() and view.chapter_filter.isVisible()


def test_repeated_switching_between_all_and_bible_keeps_the_layout_stable(
    app, view
):
    app.processEvents()
    baseline = _geometry(view)
    slots = {name: _slot(view, getattr(view, name)) for name in CONTROLS}
    for _ in range(5):
        _select(view.type_filter, "bible")
        app.processEvents()
        assert _wait_lists(view, app)
        _select(view.type_filter, "")
        app.processEvents()
    assert _geometry(view) == baseline
    for name in CONTROLS:
        assert _slot(view, getattr(view, name)) == slots[name]


def test_reset_keeps_the_layout_stable(app, view):
    _select(view.type_filter, "bible")
    app.processEvents()
    assert _wait_lists(view, app)
    _select(view.book_filter, 1)
    app.processEvents()
    assert _wait_lists(view, app)
    app.processEvents()
    before = _geometry(view)
    view.btn_reset.click()
    app.processEvents()
    assert _geometry(view) == before
    assert not view.book_filter.isEnabled()
    assert not view.chapter_filter.isEnabled()


def test_narrow_width_wraps_instead_of_hiding_controls(app, view):
    view.resize(1300, view.height())
    app.processEvents()
    app.processEvents()
    first_line = _slot(view, view.type_filter)[0]
    assert _slot(view, view.book_filter)[0] == first_line
    assert _slot(view, view.btn_reset)[0] == first_line

    view.resize(620, view.height())
    app.processEvents()
    app.processEvents()
    # The groups wrap to lower lines, keeping the reading order, and every
    # control stays visible inside the bar (no clipping, no scroller).
    order = (view.type_filter, view.work_filter, view.book_filter,
             view.chapter_filter, view.btn_reset)
    slots = [_slot(view, widget) for widget in order]
    assert slots[0][0] < slots[2][0]        # Book is not on the type's line
    assert len({line for line, _x in slots}) >= 2
    for (line_a, x_a), (line_b, x_b) in zip(slots, slots[1:]):
        assert (line_a, x_a) < (line_b, x_b)   # reading order preserved
    for name in CONTROLS:
        assert getattr(view, name).isVisible()
    from esword4linux.ui.search_view import BOOK_WIDTH, CHAPTER_WIDTH

    assert view.book_filter.width() == BOOK_WIDTH
    assert view.chapter_filter.width() == CHAPTER_WIDTH

    # Back to a wide window: one single line again.
    view.resize(1300, view.height())
    app.processEvents()
    app.processEvents()
    assert _slot(view, view.book_filter)[0] == _slot(view, view.type_filter)[0]
    assert _slot(view, view.btn_reset)[0] == _slot(view, view.type_filter)[0]


# ── search on demand (no search while typing) ───────────────────────────
@pytest.fixture()
def counted_search(env, monkeypatch):
    """Count the queries that actually reach the search engine."""
    calls: list[str] = []
    original = env.search.search

    def spy(query, *args, **kwargs):
        calls.append(query)
        return original(query, *args, **kwargs)

    monkeypatch.setattr(env.search, "search", spy)
    return calls


def test_typing_does_not_search(app, view, counted_search):
    view.query.setText("paz")
    for _ in range(3):
        app.processEvents()
    assert counted_search == []
    # The hint tells the user what is missing instead of searching silently.
    assert view.hint.isVisible()
    assert view.hint.text() == tr("search.press_enter")


def test_enter_runs_the_search(app, view, counted_search):
    view.query.setText("paz")
    app.processEvents()
    view.query.returnPressed.emit()
    app.processEvents()
    assert counted_search == ["paz"]
    assert tr("search.press_enter") != view.hint.text()


def test_search_button_runs_the_search(app, view, counted_search):
    view.query.setText("paz")
    app.processEvents()
    view.btn.click()
    app.processEvents()
    assert counted_search == ["paz"]


def test_clearing_the_box_drops_the_committed_query(
    app, view, counted_search
):
    view.set_query("paz")
    app.processEvents()
    assert counted_search == ["paz"]
    view.query.clear()
    app.processEvents()
    # Back to the welcome screen, and no extra query is sent.
    assert counted_search == ["paz"]
    assert view.info.text() == ""


def test_unapproved_text_is_never_searched(app, view, counted_search):
    view.set_query("paz")
    app.processEvents()
    assert counted_search == ["paz"]
    counted_search.clear()

    view.query.setText("pazzz")          # a typo, not committed
    app.processEvents()
    _select(view.type_filter, "dictionary")   # a deliberate filter change
    app.processEvents()
    # The filter re-runs the committed query, never the half-typed text.
    assert counted_search == ["paz"]


# ── fixed layout at any window width ────────────────────────────────────
def _label_combo_gaps(view) -> dict:
    pairs = (
        ("type_label", "type_filter"),
        ("work_label", "work_filter"),
        ("book_label", "book_filter"),
        ("chapter_label", "chapter_filter"),
    )
    gaps = {}
    for label_name, combo_name in pairs:
        label = getattr(view, label_name)
        combo = getattr(view, combo_name)
        gaps[combo_name] = combo.x() - (label.x() + label.width())
    return gaps


def test_filter_controls_keep_their_geometry_when_the_window_grows(
    app, view
):
    from esword4linux.ui.search_view import FILTER_SPACING

    view.resize(1200, view.height())
    for _ in range(3):
        app.processEvents()
    base = _geometry(view)
    base_gaps = _label_combo_gaps(view)
    # Every label sits right before its control, at the layout spacing.
    assert all(gap == FILTER_SPACING for gap in base_gaps.values()), base_gaps

    view.resize(1600, view.height())
    for _ in range(3):
        app.processEvents()
    # Growing the window must not move or resize any control, and must not
    # open a gap between a label and its combo.
    assert _geometry(view) == base
    assert _label_combo_gaps(view) == base_gaps


def test_disabled_controls_have_a_visible_state(app, view):
    from esword4linux.ui.theme import stylesheet

    # All types: the Bible controls are inactive...
    assert not view.book_filter.isEnabled()
    assert not view.chapter_filter.isEnabled()
    assert not view.book_label.isEnabled()
    assert not view.chapter_label.isEnabled()
    # ...and the object names are the ones the disabled rules target, so the
    # labels dim with their combo and the frame fades.
    for name in CONTROLS:
        assert getattr(view, name).objectName() == "filterCombo"
    for name in ("type_label", "work_label", "book_label", "chapter_label"):
        assert getattr(view, name).objectName() == "appSubtitle"
    css = stylesheet("light", 13, "Noto Sans")
    assert "QComboBox#filterCombo:disabled" in css
    assert "QLabel#appSubtitle:disabled" in css


# ── search modes ────────────────────────────────────────────────────────
def test_mode_all_requires_every_word(env):
    from esword4linux.core.store import MODE_ALL

    result = env.search.search("paz genesis", mode=MODE_ALL)
    assert [(h.module_id, h.ref) for h in result.hits] == [(2, "1:1:1")]
    # Strict: «all» no longer falls back to «any».
    assert env.search.search("paz zzzz", mode=MODE_ALL).hits == []


def test_mode_any_accepts_a_single_word(env):
    from esword4linux.core.store import MODE_ANY

    result = env.search.search("genesis shalom", mode=MODE_ANY)
    assert {h.module_id for h in result.hits} == {2, 3}
    assert len(result.hits) == 2


def test_mode_phrase_matches_only_the_exact_phrase(env):
    from esword4linux.core.store import MODE_PHRASE

    hit = env.search.search("paz en genesis", mode=MODE_PHRASE)
    assert [(h.module_id, h.ref) for h in hit.hits] == [(2, "1:1:1")]
    # Same words, different order: no phrase.
    assert env.search.search("genesis paz", mode=MODE_PHRASE).hits == []


def test_mode_regex_is_applied_by_the_engine(env):
    from esword4linux.core.store import MODE_REGEX

    result = env.search.search(r"paz.*genesis", mode=MODE_REGEX)
    assert [(h.module_id, h.ref) for h in result.hits] == [(2, "1:1:1")]
    # A prefix expression works because the literal is seeded as a prefix.
    result = env.search.search(r"gen.*", mode=MODE_REGEX)
    assert {h.module_id for h in result.hits} == {2}
    # A word-boundary expression does not become «bpaz».
    assert env.search.search(r"\bpaz\b", mode=MODE_REGEX).hits


def test_mode_regex_reports_an_invalid_expression(env):
    from esword4linux.core.store import MODE_REGEX

    result = env.search.search("(paz", mode=MODE_REGEX)
    assert result.note == "regex_error"
    assert result.note_detail
    assert result.hits == []


def test_mode_regex_needs_a_searchable_word(env):
    from esword4linux.core.store import MODE_REGEX

    result = env.search.search(r"\d+", mode=MODE_REGEX)
    assert result.note == "regex_empty"
    assert result.hits == []


# ── Bible ranges ────────────────────────────────────────────────────────
def test_book_range_restricts_the_search(env):
    result = env.search.search("paz", filters=SearchFilters(book_range=(1, 1)))
    # Genesis pages of both Bibles plus the commentary on Genesis 1.
    assert {h.module_id for h in result.hits} == {1, 2, 4}
    assert len(result.hits) == 5          # book 1 only

    result = env.search.search("paz", filters=SearchFilters(book_range=(4, 4)))
    assert {h.module_id for h in result.hits} == {2}
    assert len(result.hits) == 2          # Numbers 1 and 3


def test_chapter_range_restricts_the_search(env):
    result = env.search.search(
        "paz", filters=SearchFilters(book_range=(1, 1), chapter_range=(2, 2))
    )
    assert [(h.module_id, h.ref) for h in result.hits] == [(1, "1:2:1")]


def test_empty_range_intersection_returns_nothing(env):
    result = env.search.search(
        "paz", filters=SearchFilters(book=1, book_range=(2, 4))
    )
    assert result.hits == []


def test_book_and_group_data_cover_the_whole_canon():
    from esword4linux.core.books import BOOK_GROUPS, TESTAMENTS

    assert [(t.start, t.end) for t in TESTAMENTS] == [(1, 39), (40, 66)]
    # The groups tile the 73 books without gaps or overlaps.
    covered = sorted(b for g in BOOK_GROUPS for b in g.books())
    assert covered == list(range(1, 74))
    assert all(g.label("es") and g.label("en") for g in BOOK_GROUPS)


# ── UI: advanced ranges, library hints and the hover toast ──────────────
def test_advanced_row_maps_the_ranges(app, view):
    _select(view.type_filter, "bible")
    app.processEvents()
    assert _wait_lists(view, app)
    assert not view._advanced_bar.isVisible()
    view.advanced.setChecked(True)
    app.processEvents()
    assert view._advanced_bar.isVisible()
    # The testaments and groups offered come from the indexed Bibles (1,2,4).
    testaments = [view.testament_filter.itemData(i)
                  for i in range(view.testament_filter.count())]
    assert (1, 39) in testaments and (40, 66) not in testaments
    groups = [view.group_filter.itemData(i)
              for i in range(view.group_filter.count())]
    assert (1, 5) in groups and (67, 73) not in groups

    _select(view.testament_filter, (1, 39))
    app.processEvents()
    assert view.filters().book_range == (1, 39)
    _select(view.group_filter, (1, 5))
    app.processEvents()
    assert view.filters().book_range == (1, 5)
    _select(view.book_from, 1)
    app.processEvents()
    # The *to* selector only offers books from the *from* one onwards.
    to_books = [view.book_to.itemData(i)
                for i in range(view.book_to.count())]
    assert to_books == [None, 1, 2, 4]
    _select(view.book_to, 2)
    app.processEvents()
    assert view.filters().book_range == (1, 2)
    # A book range and the exact Book filter are mutually exclusive.
    assert not view.book_filter.isEnabled()
    assert view.filters().book is None

    # Clearing the range gives the Book filter back.
    _select(view.testament_filter, None)
    _select(view.group_filter, None)
    _select(view.book_from, None)
    _select(view.book_to, None)
    app.processEvents()
    assert view.filters().book_range is None
    assert view.book_filter.isEnabled()


def test_exact_book_and_chapter_ranges_are_exclusive(app, view):
    _select(view.type_filter, "bible")
    app.processEvents()
    assert _wait_lists(view, app)
    view.advanced.setChecked(True)
    app.processEvents()

    # An exact Book disables and clears the book ranges.
    _select(view.book_filter, 1)
    app.processEvents()
    assert _wait_lists(view, app)
    for combo in (view.testament_filter, view.group_filter,
                  view.book_from, view.book_to):
        assert not combo.isEnabled()
        assert combo.currentData() is None
    assert view.book_filter.isEnabled()
    assert view.filters().book_range is None

    # The chapter range works with a book, and excludes the exact Chapter.
    assert view.chapter_from.isEnabled() and view.chapter_to.isEnabled()
    _select(view.chapter_from, 2)
    app.processEvents()
    to_chapters = [view.chapter_to.itemData(i)
                   for i in range(view.chapter_to.count())]
    assert to_chapters[0] is None and 1 not in to_chapters
    _select(view.chapter_to, 3)
    app.processEvents()
    assert view.filters().chapter_range == (2, 3)
    assert not view.chapter_filter.isEnabled()
    assert view.filters().chapter is None

    # Clearing the range gives the Chapter filter back.
    _select(view.chapter_from, None)
    _select(view.chapter_to, None)
    app.processEvents()
    assert view.filters().chapter_range is None
    assert view.chapter_filter.isEnabled()


def test_exact_chapter_disables_the_chapter_range(app, view):
    _select(view.type_filter, "bible")
    app.processEvents()
    assert _wait_lists(view, app)
    view.advanced.setChecked(True)
    app.processEvents()
    _select(view.book_filter, 1)
    app.processEvents()
    assert _wait_lists(view, app)
    _select(view.chapter_filter, 2)
    app.processEvents()
    assert not view.chapter_from.isEnabled()
    assert not view.chapter_to.isEnabled()
    assert view.chapter_from.currentData() is None


def test_advanced_row_disappears_for_non_bibles(app, view):
    _select(view.type_filter, "bible")
    app.processEvents()
    assert _wait_lists(view, app)
    view.advanced.setChecked(True)
    app.processEvents()
    assert view._advanced_bar.isVisible()
    _select(view.type_filter, "dictionary")
    app.processEvents()
    assert not view._advanced_bar.isVisible()
    assert not view.advanced.isEnabled()
    filters = view.filters()
    assert filters.book_range is None and filters.chapter_range is None


def test_hint_explains_an_empty_library(app, tmp_path):
    from esword4linux.config import Settings
    from esword4linux.core.context import AppContext
    from esword4linux.ui.search_view import SearchView

    ctx = AppContext(Settings(resources_dir="", cache_dir=str(tmp_path / "c2")))
    try:
        empty = SearchView(ctx)
        try:
            empty.show()
            app.processEvents()
            assert empty.hint.isVisible()
            assert empty.hint.text() == tr("search.no_library")
        finally:
            empty.shutdown()
            empty.deleteLater()
    finally:
        ctx.close_all()


def test_hint_explains_a_category_that_is_not_indexed(app, view):
    # A maps module exists in the catalog but was never indexed.
    from esword4linux.core.search import SearchFilters as _F  # noqa: F401

    row = {
        "id": 99, "path": "/nonexistent/maps.mapx",
        "rel_path": "maps.mapx", "filename": "maps.mapx", "ext": "mapx",
        "structure": "maps", "kind": "maps", "title": "Maps",
        "abbreviation": "MP", "language": "en", "encrypted": 0,
        "entries": 3, "size": 10, "mtime": 1.0,
        "index_status": "pending", "duplicate_of": None,
    }
    view.ctx.catalog.conn.execute(
        "INSERT INTO module(path, rel_path, filename, ext, structure, kind, "
        "title, abbreviation, language, encrypted, entries, size, mtime, "
        "index_status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (row["path"], row["rel_path"], row["filename"], row["ext"],
         row["structure"], row["kind"], row["title"], row["abbreviation"],
         row["language"], 0, row["entries"], row["size"], row["mtime"],
         "pending"),
    )
    view.ctx.catalog.conn.commit()
    view.refresh_filters()
    _select(view.type_filter, "maps")
    app.processEvents()
    assert view.hint.isVisible()
    assert view.hint.text() == tr("search.category_not_indexed")


def test_hit_links_expose_the_passage_for_the_hover_toast(app, view):
    _select(view.type_filter, "bible")
    app.processEvents()
    assert _wait_lists(view, app)
    view.set_query("paz")
    app.processEvents()
    html = view.results.toHtml()
    assert 'href="hit:' in html
    # The second read: the passage of the module the hit came from.
    text = view._resolve_hit("hit:1:1:2:1")
    head, _, body = text.partition("\n")
    assert "AAA" in head and "2:1" in head
    # The text comes from the module itself, not from the index snippet.
    assert body.strip() == "dos"
    # The bubble machinery accepts result links.
    from esword4linux.ui.rich_browser import RESOLVABLE

    assert "hit:" in RESOLVABLE


def test_result_links_are_underlined(env):
    from esword4linux.ui.theme import document_css

    css = document_css("light", 15, "Noto Serif")
    hit_rule = [line for line in css.splitlines() if ".hit a " in line]
    assert hit_rule and "underline" in hit_rule[0]


def test_mode_combo_passes_the_mode_to_the_engine(app, view, counted_search):
    view.query.setText("paz")
    view.query.returnPressed.emit()
    app.processEvents()
    assert counted_search == ["paz"]
    from esword4linux.core.store import MODE_ANY, MODE_PHRASE, MODE_REGEX

    for mode in (MODE_ANY, MODE_PHRASE, MODE_REGEX):
        _select(view.mode_filter, mode)
        app.processEvents()
        assert view._mode() == mode
    # Every mode re-runs the committed query.
    assert counted_search.count("paz") >= 4
