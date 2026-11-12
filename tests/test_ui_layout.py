"""Anchos mínimos y paneles recuperables."""

from __future__ import annotations

import os

import pytest

from linuxesword.config import Settings
from linuxesword.core.context import AppContext


def test_library_term_list_has_minimum_and_toggle():
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from linuxesword.ui.library_view import (
        DETAIL_MIN_WIDTH, HANDLE_WIDTH, LIST_MIN_WIDTH, LibraryView,
    )

    app = QApplication.instance() or QApplication([])
    original_save = Settings.save
    Settings.save = lambda self: None
    ctx = AppContext(Settings.load())
    row = next((m for m in ctx.catalog.modules(kind="dictionary")), None)
    if row is None:
        ctx.close_all()
        Settings.save = original_save
        pytest.skip("corpus no disponible")
    view = LibraryView(ctx, row)
    view.resize(1000, 600)
    view.show()
    app.processEvents()
    try:
        assert view.left.minimumWidth() >= LIST_MIN_WIDTH
        assert view.detail.minimumWidth() >= DETAIL_MIN_WIDTH
        assert not view.split.childrenCollapsible()
        view.split.setSizes([0, 1000])
        app.processEvents()
        assert view.left.width() >= LIST_MIN_WIDTH
        view.handle.click()
        assert not view.left.isVisible()
        assert view.left_dock.width() <= HANDLE_WIDTH + 2
        view.handle.click()
        assert view.left.isVisible()
    finally:
        view.deleteLater()
        ctx.close_all()
        Settings.save = original_save


def test_translation_combo_groups_versions():
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QComboBox

    from linuxesword.ui.bible_view import fill_bible_combo

    app = QApplication.instance() or QApplication([])
    combo = QComboBox()
    bibles = [
        {"rel_path": "a", "language": "es", "abbreviation": "AAA", "title": "Alfa"},
        {"rel_path": "b", "language": "en", "abbreviation": "BBB", "title": "Beta"},
    ]
    fill_bible_combo(combo, bibles, "b", editable=False)
    assert not combo.isEditable()
    assert combo.count() == 4  # cabecera ES + ítem + cabecera EN + ítem
    assert combo.itemData(0) is None
    assert combo.currentData() == "b"


def test_search_enter_on_reference_jumps_immediately():
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from linuxesword.ui.search_view import SearchView

    app = QApplication.instance() or QApplication([])
    ctx = AppContext(Settings.load())
    view = SearchView(ctx)
    emitted: list[str] = []
    view.go_reference.connect(emitted.append)
    try:
        view.query.setText("Juan 3:16")
        view.run_search(explicit=False)
        assert emitted == []
        view.run_search(explicit=True)
        assert emitted and "3:16" in emitted[0]
    finally:
        view.deleteLater()
        ctx.close_all()


def test_sidebar_multi_grouping_and_kind_filter():
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from linuxesword.ui.sidebar import Sidebar

    app = QApplication.instance() or QApplication([])
    original_save = Settings.save
    Settings.save = lambda self: None
    ctx = AppContext(Settings.load())
    sidebar = Sidebar(ctx)
    try:
        sidebar.set_mode("kind")
        sidebar.group_combos[1].setCurrentIndex(
            sidebar.group_combos[1].findData("language")
        )
        assert ctx.settings.sidebar_grouping == ["kind", "language"]
        top = sidebar.tree.topLevelItem(0)
        assert top is not None and top.childCount() > 0
        sidebar._toggle_kind_filter("dictionary", True)
        assert ctx.settings.sidebar_kind_filters == ["dictionary"]
        assert sidebar.tree.topLevelItemCount() == 1
        assert "Diccionario" in sidebar.tree.topLevelItem(0).text(0)
        sidebar._clear_kind_filters()
    finally:
        sidebar.deleteLater()
        ctx.close_all()
        Settings.save = original_save


def test_citation_view_replaces_main_bible_and_back_returns():
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from linuxesword.ui.bible_view import BiblePane

    app = QApplication.instance() or QApplication([])
    ctx = AppContext(Settings.load())
    pane = BiblePane(ctx)
    pane.resize(1200, 700)
    pane.show()
    app.processEvents()
    try:
        before = pane.chapter.text()
        pane._step(1)
        app.processEvents()
        assert pane.chapter.text() != before
        pane.citation_input.setText("Juan 3:16; 4:1")
        pane._show_citations()
        app.processEvents()
        assert pane._citation_mode
        # Libro, capítulo y flechas nunca se ocultan: siempre hay que poder
        # volver a la navegación normal.
        assert pane.book.isVisible()
        assert pane.chapter.isVisible()
        assert pane.btn_prev.isVisible()
        assert pane.btn_next.isVisible()
        assert pane.btn_citation_back.isVisible()
        pane._exit_citation_mode()
        app.processEvents()
        assert not pane._citation_mode
        assert pane.book.isVisible()
        assert pane.chapter.isVisible()
        assert not pane.btn_citation_back.isVisible()
    finally:
        pane.deleteLater()
        ctx.close_all()


def test_sidebar_filter_is_a_full_width_section_title():
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from linuxesword.ui.sidebar import Sidebar

    app = QApplication.instance() or QApplication([])
    original_save = Settings.save
    Settings.save = lambda self: None
    ctx = AppContext(Settings.load())
    sidebar = Sidebar(ctx)
    sidebar.resize(260, 800)
    sidebar.show()
    app.processEvents()
    try:
        assert sidebar.filter_label.isVisible()
        assert sidebar.filter_label.width() > sidebar.btn_kind_filter.width() * 2
        assert sidebar.filter_label.width() > sidebar.btn_language_filter.width() * 2
    finally:
        sidebar.deleteLater()
        ctx.close_all()
        Settings.save = original_save
