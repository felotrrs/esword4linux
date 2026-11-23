"""Window-level layout tests: sidebar band and window minimum size.

These guard two regressions that only appear with a real window:

* closing the app with the resources panel collapsed and reopening it left an
  empty band where the panel used to be, because the splitter kept its own
  copy of the sizes;
* showing the panel raised the window's minimum width above the usable screen
  width, so the window manager disabled *maximise*.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QScrollArea

from esword4linux.config import Settings
from esword4linux.ui.bible_view import BiblePane
from esword4linux.ui.main_window import (
    SIDEBAR_HANDLE_WIDTH,
    SIDEBAR_MIN_WIDTH,
    MainWindow,
)

#: A window whose minimum is wider than this cannot be maximised on the
#: common 1024/1280 px screens once the window manager panels are discounted.
SMALL_SCREEN_WIDTH = 800


class _FakeCatalog:
    def counts_by_kind(self) -> dict:
        return {}

    def status_counts(self) -> dict:
        return {}

    def modules(self, kind=None, include_duplicates=False) -> list[dict]:
        return []

    def works(self) -> list[dict]:
        return []

    def module(self, module_id):
        return None

    def by_rel_path(self, rel_path):
        return None

    def is_empty(self) -> bool:
        return False

    def needs_metadata_refresh(self) -> bool:
        return False


class _FakeStore:
    def total_pages(self) -> int:
        return 0

    def db_size(self) -> float:
        return 0.0


class _FakeSearch:
    def indexed_module_ids(self, kinds=None) -> list[int]:
        return []

    def search(self, *args, **kwargs) -> list:
        return []

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
    def tooltip(self, code: str, max_chars: int = 2500) -> str:
        return ""

    def candidates(self) -> list[dict]:
        return []

    def module(self):
        return None

    def set_default(self, rel: str) -> None:
        pass


class _FakeContext:
    """Just enough context to build a ``MainWindow`` without a catalog."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.catalog = _FakeCatalog()
        self.store = _FakeStore()
        self.search = _FakeSearch()
        self.refs = _FakeRefs()
        self.strong = _FakeStrong()

    def bibles(self) -> list[dict]:
        return []

    def commentaries(self) -> list[dict]:
        return []

    def module(self, module):
        return None

    def close_all(self) -> None:
        pass


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def make_window(app, monkeypatch, tmp_path):
    """Build a MainWindow without the scheduled metadata scan."""
    monkeypatch.setattr(MainWindow, "_bootstrap", lambda self: None)
    modules = tmp_path / "modules"
    modules.mkdir()

    def build(visible: bool = True) -> MainWindow:
        settings = Settings(
            resources_dir=str(modules),
            cache_dir=str(tmp_path / "cache"),
            sidebar_visible=visible,
        )
        window = MainWindow(_FakeContext(settings))
        window.resize(1400, 880)
        window.show()
        for _ in range(4):
            app.processEvents()
        return window

    return build


def test_collapsed_startup_leaves_no_empty_band(app, make_window):
    window = make_window(visible=False)
    try:
        assert not window.sidebar.isVisible()
        # The splitter and the dock must agree: a stale splitter size paints an
        # empty band where the panel used to be.
        sizes = window._split.sizes()
        assert sizes[0] <= SIDEBAR_HANDLE_WIDTH + 1
        assert window.sidebar_dock.width() <= SIDEBAR_HANDLE_WIDTH + 1
    finally:
        window.close()
        app.processEvents()


def test_toggling_keeps_splitter_and_dock_in_sync(app, make_window):
    window = make_window(visible=True)
    try:
        for _ in range(3):
            window.toggle_sidebar()
            app.processEvents()
            sizes = window._split.sizes()
            assert window.sidebar_dock.width() == sizes[0]
            if window.sidebar.isVisible():
                assert sizes[0] >= SIDEBAR_MIN_WIDTH
    finally:
        window.close()
        app.processEvents()


def test_window_minimum_stays_maximisable(app, make_window):
    window = make_window(visible=False)
    try:
        assert window.minimumSizeHint().width() <= SMALL_SCREEN_WIDTH
        window.toggle_sidebar()
        app.processEvents()
        assert window.sidebar.isVisible()
        assert window.minimumSizeHint().width() <= SMALL_SCREEN_WIDTH
    finally:
        window.close()
        app.processEvents()


def test_toolbar_wraps_instead_of_forcing_a_wide_window(app, make_window):
    window = make_window(visible=True)
    try:
        from esword4linux.ui.flow_layout import FlowLayout

        bible = window.tabs.widget(1).bible
        assert isinstance(bible, BiblePane)
        # The toolbar is a wrapping flow: its minimum width is the widest
        # control, not the sum of all of them (~975 px before).
        assert isinstance(bible.toolbar.layout(), FlowLayout)
        assert bible.toolbar.minimumSizeHint().width() < 400
        assert bible.toolbar.layout().hasHeightForWidth()
    finally:
        window.close()
        app.processEvents()


def test_toggling_does_not_resize_the_window(app, make_window):
    """The sidebar toggle must never change the window width.

    A child that turns its width into a minimum makes the splitter give it
    more space on every toggle, so the window grows without control.
    """
    window = make_window(visible=True)
    try:
        width = window.width()
        for _ in range(3):
            window.toggle_sidebar()
            app.processEvents()
            assert window.width() == width
    finally:
        window.close()
        app.processEvents()
