"""First-launch module lists: the selectors follow the catalog.

The panes are built before the metadata scan finishes. Their module lists used
to keep the empty catalog they saw at construction time until the next launch:
Bibles worked because ``BiblePane.reload_modules()`` refilled the translation
combo, but the commentary and Strong selectors were never re-read.
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from esword4linux.config import Settings  # noqa: E402
from esword4linux.core.catalog import ScanResult  # noqa: E402
from esword4linux.ui.main_window import MainWindow  # noqa: E402


def _row(i: int, rel: str, kind: str, abbr: str, title: str,
         entries: int = 100) -> dict:
    return {
        "id": i, "path": rel, "rel_path": rel,
        "filename": rel.rsplit("/", 1)[-1],
        "ext": rel.rsplit(".", 1)[-1],
        "structure": kind, "kind": kind, "title": title,
        "abbreviation": abbr, "language": "en", "encrypted": 0,
        "entries": entries, "size": 1000, "mtime": 1.0,
        "index_status": "pending", "duplicate_of": None,
    }


class MutableCatalog:
    """Catalog that is empty at construction and filled by the fake scan."""

    def __init__(self) -> None:
        self.rows: list[dict] = []

    def _visible(self) -> list[dict]:
        return [r for r in self.rows if not r.get("duplicate_of")]

    def counts_by_kind(self) -> dict:
        counts: dict[str, int] = {}
        for row in self._visible():
            counts[row["kind"]] = counts.get(row["kind"], 0) + 1
        return counts

    def status_counts(self) -> dict:
        counts: dict[str, int] = {}
        for row in self._visible():
            status = row.get("index_status") or "pending"
            counts[status] = counts.get(status, 0) + 1
        return counts

    def modules(self, kind=None, include_duplicates=False) -> list[dict]:
        rows = self.rows if include_duplicates else self._visible()
        if kind:
            rows = [r for r in rows if r["kind"] == kind]
        return rows

    def works(self) -> list[dict]:
        return []

    def module(self, module_id):
        return next((r for r in self.rows if r["id"] == module_id), None)

    def by_rel_path(self, rel_path):
        return next((r for r in self.rows if r["rel_path"] == rel_path), None)

    def is_empty(self) -> bool:
        return not self.rows

    def needs_metadata_refresh(self) -> bool:
        return False


class _FakeStore:
    def total_pages(self) -> int:
        return 0

    def db_size(self) -> float:
        return 0.0


class _FakeSearch:
    def __init__(self, catalog: MutableCatalog) -> None:
        self.catalog = catalog

    def indexed_module_ids(self, kinds=None) -> list[int]:
        return [
            r["id"] for r in self.catalog.modules()
            if r.get("index_status") == "ready"
            and (not kinds or r["kind"] in kinds)
        ]

    def search(self, query, scope=None, limit=200, filters=None):
        from esword4linux.core.search import SearchResult

        return SearchResult(query=query or "", intent="empty")

    def group_by_kind(self, hits) -> list:
        return []


class _FakeRefs:
    def set_bible(self, rel: str) -> None:
        pass

    def tooltip(self, href: str, rel_path: str | None = None) -> str:
        return ""

    def verse_tooltip(self, text: str, rel_path: str | None = None) -> str:
        return ""

    def clear(self) -> None:
        pass


class _FakeStrong:
    def __init__(self, catalog: MutableCatalog) -> None:
        self.catalog = catalog

    def tooltip(self, code: str, max_chars: int = 2500) -> str:
        return ""

    def candidates(self) -> list[dict]:
        return self.catalog.modules(kind="lexicon")

    def module(self):
        return None

    def set_default(self, rel: str) -> None:
        pass


class _FakeContext:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.catalog = MutableCatalog()
        self.store = _FakeStore()
        self.search = _FakeSearch(self.catalog)
        self.refs = _FakeRefs()
        self.strong = _FakeStrong(self.catalog)

    def bibles(self) -> list[dict]:
        return self.catalog.modules(kind="bible")

    def commentaries(self) -> list[dict]:
        return self.catalog.modules(kind="commentary")

    def module(self, module):
        return None

    def close_all(self) -> None:
        pass


BIBLE = _row(1, "bible/a.bblx", "bible", "KJV", "King James Version")
COMMENT_ONE = _row(2, "comment/c1.cmtx", "commentary", "CL",
                   "Commentary One", 500)
COMMENT_TWO = _row(3, "comment/c2.cmtx", "commentary", "CM",
                   "Commentary Two", 900)
LEXICON_ONE = _row(4, "lexi/l1.lexi", "lexicon", "SL", "Strong Lexicon", 14000)
DICTIONARY = _row(5, "dict/d1.dctx", "dictionary", "D1", "Test Dictionary")


@pytest.fixture()
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def make_window(app, monkeypatch, tmp_path):
    """A MainWindow whose catalog starts empty, exactly like the first launch."""
    monkeypatch.setattr(MainWindow, "_bootstrap", lambda self: None)
    modules = tmp_path / "modules"
    modules.mkdir()

    def build() -> tuple[MainWindow, _FakeContext]:
        settings = Settings(
            resources_dir=str(modules), cache_dir=str(tmp_path / "cache")
        )
        ctx = _FakeContext(settings)
        window = MainWindow(ctx)
        window.resize(1400, 880)
        window.show()
        for _ in range(4):
            app.processEvents()
        return window, ctx

    return build


def _scan(app, window, ctx, rows) -> None:
    """Simulate the metadata scan finishing: fill the catalog and notify."""
    ctx.catalog.rows = list(rows)
    window._scan_done(ScanResult(total=len(rows), added=len(rows), seconds=0.1))
    for _ in range(4):
        app.processEvents()


def _commentary_combo(window):
    return window.tabs.widget(1).bible.commentary.combo


def test_first_launch_populates_the_commentary_selector(app, make_window):
    window, ctx = make_window()
    try:
        assert _commentary_combo(window).count() == 0
        _scan(app, window, ctx, [BIBLE, COMMENT_ONE, COMMENT_TWO])
        combo = _commentary_combo(window)
        assert combo.count() == 2
        # The default is the commentary with the most entries.
        assert combo.currentData() == COMMENT_TWO["rel_path"]
    finally:
        window.close()
        app.processEvents()


def test_first_launch_without_commentaries_keeps_the_selector_empty(
    app, make_window
):
    window, ctx = make_window()
    try:
        _scan(app, window, ctx, [BIBLE, DICTIONARY])
        combo = _commentary_combo(window)
        assert combo.count() == 0
        assert combo.currentData() is None
        # The panel explains the situation instead of failing.
        assert window.tabs.widget(1).bible.commentary.browser.toPlainText()
    finally:
        window.close()
        app.processEvents()


def test_repeated_refreshes_do_not_duplicate_entries(app, make_window):
    window, ctx = make_window()
    try:
        _scan(app, window, ctx, [BIBLE, COMMENT_ONE, COMMENT_TWO])
        combo = _commentary_combo(window)
        assert combo.count() == 2
        for _ in range(3):
            window._reload_workspaces()
            window._scan_done(
                ScanResult(total=3, added=0, updated=0, seconds=0.1)
            )
            app.processEvents()
        assert combo.count() == 2
        values = [combo.itemData(i) for i in range(combo.count())]
        assert len(values) == len(set(values))
    finally:
        window.close()
        app.processEvents()


def test_rescan_shows_a_new_commentary_without_restarting(app, make_window):
    window, ctx = make_window()
    try:
        _scan(app, window, ctx, [BIBLE, COMMENT_ONE])
        assert _commentary_combo(window).count() == 1
        _scan(app, window, ctx, [BIBLE, COMMENT_ONE, COMMENT_TWO])
        assert _commentary_combo(window).count() == 2
    finally:
        window.close()
        app.processEvents()


def test_switching_between_modes_keeps_the_selector_consistent(app, make_window):
    window, ctx = make_window()
    try:
        _scan(app, window, ctx, [BIBLE, COMMENT_ONE, COMMENT_TWO, DICTIONARY])
        workspace = window.tabs.widget(1)
        assert workspace.bible.commentary.combo.count() == 2

        window.open_resource(DICTIONARY["id"])
        app.processEvents()
        assert not workspace.is_bible()
        assert workspace._library is not None

        window.open_resource(BIBLE["id"])
        app.processEvents()
        assert workspace.is_bible()
        combo = workspace.bible.commentary.combo
        assert combo.count() == 2
        values = [combo.itemData(i) for i in range(combo.count())]
        assert len(values) == len(set(values))
    finally:
        window.close()
        app.processEvents()


def test_strong_lexicon_selector_follows_the_catalog(app, make_window):
    window, ctx = make_window()
    try:
        workspace = window.tabs.widget(1)
        # Only the "Auto" entry before the catalog has any lexicon.
        assert workspace.bible.strong.lexicon.count() == 1
        _scan(app, window, ctx, [BIBLE, LEXICON_ONE])
        # "Auto" + the lexicon.
        assert workspace.bible.strong.lexicon.count() == 2
        assert any(
            workspace.bible.strong.lexicon.itemData(i) == LEXICON_ONE["rel_path"]
            for i in range(workspace.bible.strong.lexicon.count())
        )
    finally:
        window.close()
        app.processEvents()


def test_reference_bible_selector_appears_when_the_catalog_gains_bibles(
    app, empty_settings
):
    """A work opened before any Bible existed gains its selector on refresh.

    Sequence: build the LibraryView with a catalog that has no Bible, complete
    the scan, refresh the *same* instance. The reference-Bible selector must
    appear populated, without reopening the resource.
    """
    from esword4linux.ui.library_view import LibraryView

    ctx = _FakeContext(empty_settings)
    ctx.catalog.rows = [DICTIONARY]
    row = ctx.catalog.by_rel_path(DICTIONARY["rel_path"])
    view = LibraryView(ctx, row)
    try:
        # The view was built when the catalog had no Bible at all.
        assert view._bible_combo is None
        assert view._bible_lbl is None

        # The metadata scan finishes and finds a Bible.
        ctx.catalog.rows = [BIBLE, DICTIONARY]
        view.reload_modules()
        app.processEvents()

        assert view._bible_combo is not None
        assert view._bible_lbl is not None
        # One language heading plus the Bible itself.
        assert view._bible_combo.findData(BIBLE["rel_path"]) >= 0
        assert view._bible_combo.currentData() == BIBLE["rel_path"]
        assert view._bible_combo.currentText().startswith(BIBLE["abbreviation"])
        # The entry re-renders use the reference Bible that just appeared.
        assert view.detail.bible_rel == BIBLE["rel_path"]
    finally:
        view.deleteLater()
        app.processEvents()


def test_reference_bible_selector_is_not_duplicated_by_repeated_refreshes(
    app, empty_settings
):
    from esword4linux.ui.library_view import LibraryView

    ctx = _FakeContext(empty_settings)
    ctx.catalog.rows = [DICTIONARY]
    view = LibraryView(ctx, ctx.catalog.by_rel_path(DICTIONARY["rel_path"]))
    try:
        ctx.catalog.rows = [BIBLE, DICTIONARY]
        view.reload_modules()
        app.processEvents()
        items = view._head_row.count()
        for _ in range(3):
            view.reload_modules()
            app.processEvents()
        # A repeated refresh refills the combo, it never adds a second one.
        assert view._head_row.count() == items
        assert view._bible_combo is not None
        assert view._bible_combo.currentData() == BIBLE["rel_path"]
    finally:
        view.deleteLater()
        app.processEvents()


def test_workspace_refresh_creates_the_reference_bible_selector(
    app, empty_settings
):
    """The application path: _scan_done → Workspace.reload_modules → view."""
    from esword4linux.ui.workspace import Workspace

    ctx = _FakeContext(empty_settings)
    ctx.catalog.rows = [DICTIONARY]
    workspace = Workspace(ctx, "Test", "#000000")
    try:
        workspace.set_main(ctx.catalog.by_rel_path(DICTIONARY["rel_path"]))
        library = workspace._library
        assert library is not None
        assert library._bible_combo is None
        assert workspace._ref_bible_rel == ""

        ctx.catalog.rows = [BIBLE, DICTIONARY]
        workspace.reload_modules()
        app.processEvents()

        assert library._bible_combo is not None
        assert library._bible_combo.currentData() == BIBLE["rel_path"]
        # The workspace learns the reference Bible for its own bubbles.
        assert workspace._ref_bible_rel == BIBLE["rel_path"]
    finally:
        workspace.deleteLater()
        app.processEvents()
