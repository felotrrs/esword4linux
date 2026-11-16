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
    # El test asume el panel visible; no depender de la preferencia persistida.
    ctx.settings.library_list_visible = True
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
        if not pane.book.count():
            pytest.skip("No hay biblias accesibles en el corpus para probar navegación")
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


def test_sidebar_filter_buttons_stay_together_on_the_left():
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
        kind, language = sidebar.btn_kind_filter, sidebar.btn_language_filter
        gap = language.x() - (kind.x() + kind.width())
        assert 0 <= gap <= 24, f"separación excesiva entre filtros: {gap}px"
        assert kind.x() <= 30, f"el primer filtro no está a la izquierda: {kind.x()}px"
    finally:
        sidebar.deleteLater()
        ctx.close_all()
        Settings.save = original_save


def test_match_badge_shows_commentary_inline_without_dialog():
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from linuxesword.ui.bible_view import BiblePane

    app = QApplication.instance() or QApplication([])
    original_save = Settings.save
    Settings.save = lambda self: None
    ctx = AppContext(Settings.load())
    pane = BiblePane(ctx)
    pane.resize(1200, 700)
    pane.show()
    app.processEvents()
    try:
        modules = ctx.commentaries()
        if not modules:
            pytest.skip("sin comentarios en el corpus")
        pane._set_bottom_page("", show=False)
        rel = pane.commentary.commentary_rel() or modules[0]["rel_path"]
        pane.commentary.set_match_badge("RV1960", rel)
        opened: list[tuple] = []
        inline: list[bool] = []
        pane.commentary.open_module.connect(lambda *a: opened.append(a))
        pane.commentary.open_inline.connect(lambda: inline.append(True))
        pane.commentary._open_matched_commentary()
        app.processEvents()
        assert inline == [True]
        assert opened == []
        assert pane.bottom.isVisible()
        assert pane.bottom.currentWidget() is pane.commentary
    finally:
        pane.deleteLater()
        ctx.close_all()
        Settings.save = original_save


def test_preferences_dialog_updates_every_typography_role():
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from linuxesword.ui.preferences_dialog import PreferencesDialog

    app = QApplication.instance() or QApplication([])
    original_save = Settings.save
    Settings.save = lambda self: None
    ctx = AppContext(Settings.load())
    dialog = PreferencesDialog(ctx)
    try:
        # Las fuentes se eligen en un combo normal, no en una caja de texto.
        assert not dialog.ui_family.isEditable()
        assert not dialog.reading_family.isEditable()
        assert not dialog.content_family.isEditable()
        assert dialog.ui_family.count() >= 3
        dialog.ui_size.setValue(15)
        dialog.reading_size.setValue(19)
        dialog.content_size.setValue(12)
        dialog.theme.setCurrentIndex(dialog.theme.findData("dark"))
        dialog.language.setCurrentIndex(dialog.language.findData("en"))
        dialog._update_preview()
        assert "19px" in dialog.preview.document().toHtml()
        assert "#f0e9db" in dialog.preview.document().toHtml()
        dialog._accept()
        assert ctx.settings.ui_font_size == 15
        assert ctx.settings.font_size == 19
        assert ctx.settings.content_font_size == 12
        assert ctx.settings.theme == "dark"
        assert ctx.settings.locale == "en"
    finally:
        dialog.deleteLater()
        ctx.close_all()
        Settings.save = original_save
