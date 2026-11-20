"""UI integration tests for the Bible comparison table."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, Qt, QUrl
from PySide6.QtGui import QTextTable
from PySide6.QtWidgets import QApplication

from esword4linux import i18n
from esword4linux.config import Settings
from esword4linux.core.compare import CellStatus, ColumnStatus
from esword4linux.core.esword.module import EswordModule
from esword4linux.i18n import tr
from esword4linux.ui import workspace as workspace_module
from esword4linux.ui.bible_view import BiblePane
from esword4linux.ui.bible_combo import BibleComboBox
from esword4linux.ui.compare_view import (
    VERSE_COL_WIDTH,
    BibleColumnHeader,
    _format_headings,
    column_metrics,
)
from esword4linux.ui.workspace import Workspace

from compare_support import (
    BOOK,
    CHAPTER,
    FakeContext,
    FakeLibrary,
    make_bible,
    row,
)


def _context(tmp_path: Path, specs):
    modules = {}
    rows = []
    for index, (rel, filename, title, abbreviation, data) in enumerate(specs, 1):
        path = tmp_path / filename
        make_bible(path, data)
        modules[rel] = EswordModule(path)
        rows.append(
            row(rel, path, title, abbreviation, module_id=index,
                entries=len(data))
        )
    settings = Settings(
        cache_dir=str(tmp_path / "cache"),
        bible_module=specs[0][0],
        show_commentary_inline=False,
    )
    return FakeContext(settings, rows, modules), modules


def _close(modules) -> None:
    for mod in modules.values():
        mod.close()


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def test_parallel_activation_shows_table_and_reading_roundtrip(app, tmp_path):
    ctx, modules = _context(tmp_path, [
        ("a", "a.bblx", "Alpha", "AAA", [
            (BOOK, CHAPTER, 1, "a1"), (BOOK, CHAPTER, 2, "a2"),
        ]),
        ("b", "b.bblx", "Beta", "BBB", [
            (BOOK, CHAPTER, 1, "b1"), (BOOK, CHAPTER, 2, "b2"),
        ]),
    ])
    pane = BiblePane(ctx)
    pane.resize(1200, 700)
    pane.show()
    app.processEvents()
    try:
        assert pane.primary_stack.currentWidget() is pane.primary_host
        assert "a1" in pane.primary.toPlainText()

        pane.parallel.setChecked(True)
        app.processEvents()

        assert pane.primary_stack.currentWidget() is pane.compare_view
        assert pane.compare_view.current_build() is not None
        assert pane.compare_view.current_build().table.verses == (1, 2)
        text = pane.compare_view.browser.toPlainText()
        assert "a1" in text and "b1" in text

        pane.parallel.setChecked(False)
        app.processEvents()
        assert pane.primary_stack.currentWidget() is pane.primary_host
        assert "a1" in pane.primary.toPlainText()
    finally:
        pane.deleteLater()
        app.processEvents()
        _close(modules)


def test_header_combo_accepts_only_installed_candidates(app, tmp_path):
    ctx, modules = _context(tmp_path, [
        ("a", "a.bblx", "Alpha", "AAA", [(BOOK, CHAPTER, 1, "a1")]),
        ("b", "b.bblx", "Beta", "BBB", [(BOOK, CHAPTER, 1, "b1")]),
    ])
    try:
        header = BibleColumnHeader(
            1,
            [m for m in ctx.bibles() if m["rel_path"] != "a"],
            "b",
        )
        try:
            idx = header.combo.findData("b")
            header.combo.setCurrentIndex(idx)
            assert header.selected_rel() == "b"

            header.combo.setEditText("Beta")
            assert header.selected_rel() == "b"

            header.combo.setEditText("not an installed Bible")
            assert header.selected_rel() == ""

            header.combo.setEditText("AAA — Alpha")
            assert header.selected_rel() == ""

            header.combo.setEditText("")
            app.sendEvent(
                header.combo.lineEdit(), QEvent(QEvent.Type.FocusOut)
            )
            assert header.combo.currentText() == "BBB — Beta"
            assert header.selected_rel() == "b"
        finally:
            header.deleteLater()
    finally:
        _close(modules)


def test_add_change_and_remove_columns_update_table(app, tmp_path):
    ctx, modules = _context(tmp_path, [
        ("a", "a.bblx", "Alpha", "AAA", [(BOOK, CHAPTER, 1, "a1")]),
        ("b", "b.bblx", "Beta", "BBB", [(BOOK, CHAPTER, 1, "b1")]),
        ("c", "c.bblx", "Gamma", "CCC", [(BOOK, CHAPTER, 1, "c1")]),
    ])
    pane = BiblePane(ctx)
    pane.resize(1000, 600)
    pane.show()
    app.processEvents()
    try:
        pane.set_compare_columns(["a"])
        pane.parallel.setChecked(True)
        app.processEvents()
        assert len(pane.compare_view.current_build().table.columns) == 1
        assert tr("compare.add_version") in pane.compare_view.add_button.text()

        pane.compare_view.add_button.click()
        app.processEvents()
        assert pane.compare_view.has_draft()
        draft = pane.compare_view.header_widgets[-1]
        assert isinstance(draft, BibleColumnHeader)
        draft._on_activated(draft.combo.findData("b"))
        app.processEvents()
        assert pane.compare_columns() == ["a", "b"]
        assert len(pane.compare_view.current_build().table.columns) == 2

        header = pane.compare_view.header_widgets[2]
        assert isinstance(header, BibleColumnHeader)
        header._on_activated(header.combo.findData("c"))
        app.processEvents()
        assert pane.compare_columns() == ["a", "c"]
        assert len(pane.compare_view.current_build().table.columns) == 2

        pane._remove_compare_column(1)
        app.processEvents()
        assert pane.compare_columns() == ["a"]
        assert len(pane.compare_view.current_build().table.columns) == 1

        pane.compare_view.begin_add()
        assert pane.compare_view.has_draft()
        pane.compare_view.cancel_draft()
        assert not pane.compare_view.has_draft()
        assert pane.compare_columns() == ["a"]
    finally:
        pane.deleteLater()
        app.processEvents()
        _close(modules)


def test_main_translation_controls_first_locked_column(app, tmp_path):
    ctx, modules = _context(tmp_path, [
        ("a", "a.bblx", "Alpha", "AAA", [(BOOK, CHAPTER, 1, "a1")]),
        ("b", "b.bblx", "Beta", "BBB", [(BOOK, CHAPTER, 1, "b1")]),
    ])
    pane = BiblePane(ctx)
    pane.resize(1000, 600)
    pane.show()
    app.processEvents()
    try:
        pane.set_compare_columns(["a", "b"])
        pane.parallel.setChecked(True)
        app.processEvents()
        assert pane.compare_columns() == ["a", "b"]
        assert pane.compare_view.header_widgets[1].text() == "AAA"

        idx = pane.translation.findData("b")
        pane.translation.setCurrentIndex(idx)
        app.processEvents()

        assert pane.compare_columns()[0] == "b"
        assert pane.compare_view.header_widgets[1].text() == "BBB"
        assert not isinstance(
            pane.compare_view.header_widgets[1], BibleColumnHeader
        )
    finally:
        pane.deleteLater()
        app.processEvents()
        _close(modules)


def test_equal_widths_and_right_aligned_close_header(app, tmp_path):
    ctx, modules = _context(tmp_path, [
        ("a", "a.bblx", "Alpha", "AAA", [(BOOK, CHAPTER, 1, "a1")]),
        ("b", "b.bblx", "Beta", "BBB", [(BOOK, CHAPTER, 1, "b1")]),
    ])
    pane = BiblePane(ctx)
    pane.resize(1200, 700)
    pane.show()
    app.processEvents()
    try:
        pane.set_compare_columns(["a", "b"])
        pane.parallel.setChecked(True)
        app.processEvents()

        doc = pane.compare_view.browser.document()
        table = next(
            frame for frame in doc.rootFrame().childFrames()
            if isinstance(frame, QTextTable)
        )
        widths = [
            length.rawValue()
            for length in table.format().columnWidthConstraints()
        ]
        assert widths[0] < widths[1]
        # The last column absorbs the rounding remainder, so equal automatic
        # widths may differ by one pixel.
        assert abs(widths[1] - widths[2]) <= 1
        assert sum(widths) <= pane.compare_view.browser.viewport().width()

        assert pane.compare_view.header_widgets[0].text() == tr(
            "compare.verse_short"
        )
        chapter_style = pane.compare_view.chapter_label.styleSheet()
        assert ctx.settings.font_family in chapter_style
        assert f"font-size: {ctx.settings.font_size + 8}px" in chapter_style

        main_header = pane.compare_view.header_widgets[1]
        assert not isinstance(main_header, BibleColumnHeader)
        pane._remove_compare_column(0)
        assert pane.compare_columns() == ["a", "b"]
        version_header = pane.compare_view.header_widgets[2]
        assert isinstance(version_header, BibleColumnHeader)
        layout = version_header.layout()
        assert layout.indexOf(version_header.combo) < layout.indexOf(
            version_header.close_button
        )
        assert version_header.close_button.text() == "✕"
        assert isinstance(version_header.combo, BibleComboBox)
        assert version_header.combo.objectName() == "cmpCombo"
        # The caption carries the abbreviation; the clear button would paint
        # over the text of an always-visible header.
        assert not version_header.combo.lineEdit().isClearButtonEnabled()
        assert abs(
            version_header.width()
            - pane.compare_view.header_widgets[1].width()
        ) <= 1
        html = pane.compare_view._html()
        assert 'align="center" valign="middle"' in html
        assert "cmp-row-alt" in html

        pane.compare_view.begin_add()
        app.processEvents()
        doc = pane.compare_view.browser.document()
        table = next(
            frame for frame in doc.rootFrame().childFrames()
            if isinstance(frame, QTextTable)
        )
        widths = [
            length.rawValue()
            for length in table.format().columnWidthConstraints()
        ]
        assert widths[0] < widths[1]
        assert abs(widths[1] - widths[2]) <= 1
        assert abs(widths[2] - widths[3]) <= 1
        pane.compare_view.cancel_draft()
    finally:
        pane.deleteLater()
        app.processEvents()
        _close(modules)


def test_embedded_rtf_headings_are_visually_separated():
    start = "<br><br><b>La creación</b><br><br>En el principio creó Dios."
    out = _format_headings(start)
    assert '<div class="cmp-heading">La creación</div>' in out
    assert "En el principio creó Dios." in out

    end = "Y bendijo Dios.<br><br><b>El hombre en el huerto</b><br>"
    out = _format_headings(end)
    assert "Y bendijo Dios." in out
    assert '<div class="cmp-heading">El hombre en el huerto</div>' in out


def test_compare_anchors_reuse_bible_handlers_and_keep_cmp_actions(
    app, tmp_path, monkeypatch
):
    ctx, modules = _context(tmp_path, [
        ("a", "a.bblx", "Alpha", "AAA", [(BOOK, CHAPTER, 1, "a1")]),
        ("b", "b.bblx", "Beta", "BBB", [(BOOK, CHAPTER, 1, "b1")]),
    ])
    pane = BiblePane(ctx)
    pane.resize(1000, 600)
    pane.show()
    app.processEvents()
    try:
        navigated = []
        strong = []
        notes = []
        monkeypatch.setattr(pane, "navigate", navigated.append)
        monkeypatch.setattr(pane, "_show_strong", strong.append)
        monkeypatch.setattr(pane, "_jump_to_note", lambda *args: notes.append(args))

        pane.compare_view.browser.anchorClicked.emit(QUrl("ref:Gn 1:1"))
        assert len(navigated) == 1

        pane.compare_view.browser.anchorClicked.emit(QUrl("strong:G2316"))
        assert strong == ["G2316"]

        pane.compare_view.browser.anchorClicked.emit(QUrl("note:1:1:1:B"))
        assert notes == []

        pane.compare_view.browser.anchorClicked.emit(QUrl("cmp-verse:2"))
        assert len(navigated) == 1
        assert strong == ["G2316"]
        assert notes == []

        pane.set_compare_columns(["a", "b"])
        pane.parallel.setChecked(True)
        app.processEvents()
        assert pane.compare_columns() == ["a", "b"]
        pane.compare_view.browser.anchorClicked.emit(QUrl("cmp-verse:2"))
        assert pane._current.verse == 2

        close = pane.compare_view.header_widgets[2].close_button
        close.click()
        app.processEvents()
        assert pane.compare_columns() == ["a"]
    finally:
        pane.deleteLater()
        app.processEvents()
        _close(modules)


def test_chapter_change_preserves_selected_columns(app, tmp_path):
    ctx, modules = _context(tmp_path, [
        ("a", "a.bblx", "Alpha", "AAA", [
            (BOOK, 1, 1, "a1"), (BOOK, 2, 1, "a2"),
        ]),
        ("b", "b.bblx", "Beta", "BBB", [
            (BOOK, 1, 1, "b1"), (BOOK, 2, 1, "b2"),
        ]),
    ])
    pane = BiblePane(ctx)
    pane.resize(1000, 600)
    pane.show()
    app.processEvents()
    try:
        pane.set_compare_columns(["a", "b"])
        pane.parallel.setChecked(True)
        app.processEvents()
        pane.chapter.setText("2")
        pane._on_chapter_edited()
        app.processEvents()

        assert pane.compare_columns() == ["a", "b"]
        table = pane.compare_view.current_build().table
        assert table.chapter == 2
        assert table.verses == (1,)
        assert "b2" in pane.compare_view.browser.toPlainText()
    finally:
        pane.deleteLater()
        app.processEvents()
        _close(modules)


def test_missing_book_empty_chapter_and_empty_rows_states(app, tmp_path):
    ctx, modules = _context(tmp_path, [
        ("a", "a.bblx", "Alpha", "AAA", [
            (BOOK, 1, 1, "a1"), (BOOK, 2, 1, "a2"),
            (BOOK, 2, 2, "a22"), (BOOK, 2, 3, "a23"),
        ]),
        ("b", "b.bblx", "Beta", "BBB", [
            (2, 1, 1, "b1"),
        ]),
        ("c", "c.bblx", "Gamma", "CCC", [
            (BOOK, 1, 1, "c1"), (BOOK, 3, 1, "c3"),
        ]),
        ("e", "e.bblx", "Epsilon", "EEE", [
            (BOOK, 2, 1, ""), (BOOK, 2, 2, "   "),
        ]),
    ])
    pane = BiblePane(ctx)
    pane.resize(1200, 700)
    pane.show()
    app.processEvents()
    try:
        pane.set_compare_columns(["a", "b", "c", "e"])
        pane.parallel.setChecked(True)
        pane.chapter.setText("2")
        pane._on_chapter_edited()
        app.processEvents()

        table = pane.compare_view.current_build().table
        assert table.column_state("b").status is ColumnStatus.MISSING_BOOK
        assert table.column_state("c").status is ColumnStatus.EMPTY
        assert table.column_state("c").has_rows is False
        assert table.column_state("e").status is ColumnStatus.EMPTY
        assert table.column_state("e").has_rows is True
        assert table.cell(2, "e").status is CellStatus.EMPTY
        assert table.cell(3, "e").status is CellStatus.MISSING_VERSE
        b_header = pane.compare_view.header_widgets[2]
        c_header = pane.compare_view.header_widgets[3]
        assert b_header.status.toolTip() == tr("compare.missing_book")
        assert c_header.status.toolTip() == tr("compare.empty_column")
    finally:
        pane.deleteLater()
        app.processEvents()
        _close(modules)


def test_duplicate_verse_rows_are_rendered(app, tmp_path):
    ctx, modules = _context(tmp_path, [
        ("a", "a.bblx", "Alpha", "AAA", [(BOOK, CHAPTER, 1, "a1")]),
        ("d", "d.bblx", "Delta", "DDD", [
            (BOOK, CHAPTER, 1, "first"),
            (BOOK, CHAPTER, 1, "second"),
        ]),
    ])
    pane = BiblePane(ctx)
    pane.resize(1000, 600)
    pane.show()
    app.processEvents()
    try:
        pane.set_compare_columns(["a", "d"])
        pane.parallel.setChecked(True)
        app.processEvents()
        cell = pane.compare_view.current_build().table.cell(1, "d")
        assert [page.raw for page in cell.pages] == ["first", "second"]
        text = pane.compare_view.browser.toPlainText()
        assert "first" in text and "second" in text
    finally:
        pane.deleteLater()
        app.processEvents()
        _close(modules)


def test_restored_workspace_warns_about_unavailable_columns(app, tmp_path):
    ctx, modules = _context(tmp_path, [
        ("a", "a.bblx", "Alpha", "AAA", [(BOOK, CHAPTER, 1, "a1")]),
    ])
    dict_row = row(
        "dict", tmp_path / "dict.dctx", "Dictionary", "DIC",
        module_id=2, kind="dictionary",
    )
    ctx.catalog._rows["dict"] = dict_row
    state = {
        "name": "Workspace A",
        "color": "#c9973f",
        "main_rel": "a",
        "parallel": True,
        "compare_columns": ["a", "gone", "dict"],
        "commentary": False,
        "commentary_rel": "",
        "split": [800, 280],
    }
    ws = Workspace(ctx, "Workspace A", "#c9973f")
    try:
        ws.apply_state(state)
        ws.show()
        app.processEvents()

        assert ws.bible.compare_columns() == ["a"]
        assert ws.bible.is_parallel() is True
        assert ws.main_rel == "a"
        assert not ws.bible.compare_notice.isHidden()
        tooltip = ws.bible.compare_notice.toolTip()
        assert "gone" in tooltip
        assert "DIC" in tooltip or "Dictionary" in tooltip

        old_locale = i18n.current()
        try:
            i18n.set_locale("en")
            ws.retranslate()
            assert "unavailable" in ws.bible.compare_notice.text().lower()
            i18n.set_locale("es")
            ws.retranslate()
            assert "no disponible" in ws.bible.compare_notice.text().lower()
        finally:
            i18n.set_locale(old_locale)
            ws.retranslate()
    finally:
        ws.deleteLater()
        app.processEvents()
        _close(modules)


def test_broken_module_does_not_blank_the_comparison(app, tmp_path):
    ctx, modules = _context(tmp_path, [
        ("a", "a.bblx", "Alpha", "AAA", [(BOOK, CHAPTER, 1, "a1")]),
    ])
    broken = row(
        "broken", tmp_path / "broken.bblx", "Broken", "BRK",
        module_id=2, entries=1,
    )
    ctx.catalog._rows["broken"] = broken
    pane = BiblePane(ctx)
    pane.resize(1000, 600)
    pane.show()
    app.processEvents()
    try:
        pane.set_compare_columns(["a", "broken"])
        pane.parallel.setChecked(True)
        app.processEvents()
        build = pane.compare_view.current_build()
        assert build is not None
        assert build.table is not None
        assert [state.column.key for state in build.table.columns] == ["a"]
        assert build.warnings
        assert pane.primary_stack.currentWidget() is pane.compare_view
    finally:
        pane.deleteLater()
        app.processEvents()
        _close(modules)


def test_zero_and_one_column_states(app, tmp_path):
    ctx, modules = _context(tmp_path, [
        ("a", "a.bblx", "Alpha", "AAA", [(BOOK, CHAPTER, 1, "a1")]),
        ("b", "b.bblx", "Beta", "BBB", [(BOOK, CHAPTER, 1, "b1")]),
    ])
    pane = BiblePane(ctx)
    pane.resize(1000, 600)
    pane.show()
    app.processEvents()
    try:
        pane.set_compare_columns([])
        pane.parallel.setChecked(True)
        app.processEvents()
        assert pane.compare_columns() == ["a"]
        assert len(pane.compare_view.current_build().table.columns) == 1

        pane._remove_compare_column(0)
        app.processEvents()
        assert pane.compare_columns() == ["a"]
        assert len(pane.compare_view.current_build().table.columns) == 1
    finally:
        pane.deleteLater()
        app.processEvents()
        _close(modules)


def test_workspace_state_keeps_compare_columns(app, tmp_path):
    ctx, modules = _context(tmp_path, [
        ("a", "a.bblx", "Alpha", "AAA", [(BOOK, CHAPTER, 1, "a1")]),
        ("b", "b.bblx", "Beta", "BBB", [(BOOK, CHAPTER, 1, "b1")]),
    ])
    ws = Workspace(ctx, "Workspace A", "#c9973f")
    try:
        ws.set_main(ctx.catalog.by_rel_path("a"))
        ws.bible.set_compare_columns(["a", "b"])
        ws.bible.set_parallel(True)
        state = ws.state()
        assert state["compare_columns"] == ["a", "b"]
        assert state["parallel"] is True

        restored = Workspace(ctx, "Workspace B", "#4a7fb5")
        try:
            restored.apply_state(state)
            assert restored.bible.compare_columns() == ["a", "b"]
            assert restored.bible.is_parallel() is True
        finally:
            restored.deleteLater()
            app.processEvents()
    finally:
        ws.deleteLater()
        app.processEvents()
        _close(modules)


def test_non_bible_workspace_does_not_use_comparator(app, tmp_path, monkeypatch):
    ctx, modules = _context(tmp_path, [
        ("a", "a.bblx", "Alpha", "AAA", [(BOOK, CHAPTER, 1, "a1")]),
    ])
    dict_row = row(
        "dict", tmp_path / "dict.dctx", "Dictionary", "DIC",
        module_id=2, kind="dictionary",
    )
    ctx.catalog._rows["dict"] = dict_row
    monkeypatch.setattr(workspace_module, "LibraryView", FakeLibrary)

    ws = Workspace(ctx, "Workspace A", "#c9973f")
    ws.set_main(dict_row)
    app.processEvents()
    try:
        assert ws.is_bible() is False
        assert isinstance(ws.stack.currentWidget(), FakeLibrary)
        assert ws.bible.isVisible() is False
    finally:
        ws.deleteLater()
        app.processEvents()
        _close(modules)


# ── column geometry: the header is the column model ──────────────────────
def _specs(*names):
    return [
        (name, f"{name}.bblx", f"Title {name.upper()}", name.upper(),
         [(BOOK, CHAPTER, 1, f"{name}1")])
        for name in names
    ]


def _document_table(view):
    return next(
        frame for frame in view.browser.document().rootFrame().childFrames()
        if isinstance(frame, QTextTable)
    )


def _header_x(view, widget):
    return widget.mapTo(view, widget.rect().topLeft()).x()


def _body_text_x(view, table, column):
    cell = table.cellAt(0, column)
    rect = view.browser.cursorRect(cell.firstCursorPosition())
    return view.browser.mapTo(view, rect.topLeft()).x()


def test_header_cells_sit_exactly_over_their_columns(app, tmp_path):
    ctx, modules = _context(tmp_path, _specs("a", "b", "c"))
    pane = BiblePane(ctx)
    pane.resize(1200, 700)
    pane.show()
    app.processEvents()
    try:
        pane.set_compare_columns(["a", "b", "c"])
        pane.parallel.setChecked(True)
        app.processEvents()

        view = pane.compare_view
        metrics = view._metrics
        assert metrics is not None
        widths = [
            length.rawValue()
            for length in _document_table(view).format().columnWidthConstraints()
        ]
        assert metrics.widths == tuple(int(width) for width in widths)
        assert sum(widths) <= view.browser.viewport().width()

        table = _document_table(view)
        running = 0
        for index, widget in enumerate(view.header_widgets):
            assert widget.width() == metrics.widths[index]
            assert _header_x(view, widget) == running
            running += widget.width()

        # The only gap between a header cell and its body text is the table cell
        # padding, and it is identical for every version column.
        insets = {
            _body_text_x(view, table, index)
            - _header_x(view, view.header_widgets[index])
            for index in range(1, len(view.header_widgets))
        }
        assert len(insets) == 1
    finally:
        pane.deleteLater()
        app.processEvents()
        _close(modules)


def test_single_version_header_follows_its_column(app, tmp_path):
    """With one version the caption must not float in the middle of the strip."""
    ctx, modules = _context(tmp_path, _specs("a"))
    pane = BiblePane(ctx)
    pane.resize(1200, 700)
    pane.show()
    app.processEvents()
    try:
        pane.set_compare_columns(["a"])
        pane.parallel.setChecked(True)
        app.processEvents()

        view = pane.compare_view
        assert view._metrics is not None
        assert len(view.header_widgets) == 2
        verse, main = view.header_widgets

        assert verse.width() == VERSE_COL_WIDTH
        assert _header_x(view, verse) == 0
        assert main.width() == view._metrics.widths[1]
        assert _header_x(view, main) == VERSE_COL_WIDTH
        assert main.alignment() & Qt.AlignmentFlag.AlignLeft
        # The header spans exactly the table, not the whole window.
        assert view.header_host.width() <= view.browser.viewport().width()
    finally:
        pane.deleteLater()
        app.processEvents()
        _close(modules)


def test_many_versions_scroll_and_the_header_follows(app, tmp_path):
    ctx, modules = _context(tmp_path, _specs("a", "b", "c", "d", "e"))
    pane = BiblePane(ctx)
    pane.resize(700, 600)
    pane.show()
    app.processEvents()
    try:
        pane.set_compare_columns(["a", "b", "c", "d", "e"])
        pane.parallel.setChecked(True)
        app.processEvents()

        view = pane.compare_view
        bar = view.browser.horizontalScrollBar()
        assert view._metrics is not None
        assert view._metrics.total > view.browser.viewport().width()
        assert bar.maximum() > 0
        assert view.header_track.x() == 0

        bar.setValue(min(120, bar.maximum()))
        app.processEvents()
        assert bar.value() > 0
        assert view.header_track.x() == -bar.value()
    finally:
        pane.deleteLater()
        app.processEvents()
        _close(modules)


def test_column_metrics_always_fill_the_usable_width():
    assert column_metrics(1000, 1).widths == (46, 954)
    total = column_metrics(1005, 3)
    assert total.total == 1005
    assert sum(total.widths) == 1005
    assert total.widths[0] == VERSE_COL_WIDTH

    # Below the readability floor the table is wider than the viewport.
    narrow = column_metrics(500, 4)
    assert narrow.total == VERSE_COL_WIDTH + 4 * 200
    assert all(width >= 200 for width in narrow.widths[1:])
    assert sum(narrow.widths) == narrow.total


def test_version_combo_owns_its_column_and_has_a_readable_popup(app, tmp_path):
    ctx, modules = _context(tmp_path, _specs("a", "b"))
    pane = BiblePane(ctx)
    pane.resize(1200, 700)
    pane.show()
    app.processEvents()
    try:
        pane.set_compare_columns(["a", "b"])
        pane.parallel.setChecked(True)
        app.processEvents()

        header = pane.compare_view.header_widgets[2]
        # The caption and the caret belong to the column, not to a compact box.
        assert header.combo.width() >= header.width() * 0.8
        assert header.combo.width() + header.close_button.width() <= header.width()
        # The dropdown is independent of the column width, so names are legible.
        assert header.combo.view().minimumWidth() >= 280
        # The closed caption is the full label; the tooltip carries the language.
        assert "—" in header.combo.currentText()
        assert header.combo.toolTip()
    finally:
        pane.deleteLater()
        app.processEvents()
        _close(modules)


def test_adding_a_version_scrolls_the_new_column_into_view(app, tmp_path):
    specs = _specs("a", "b", "c", "d", "e", "f", "g", "h")
    ctx, modules = _context(tmp_path, specs)
    pane = BiblePane(ctx)
    pane.resize(1000, 600)
    pane.show()
    app.processEvents()
    try:
        pane.set_compare_columns([spec[0] for spec in specs])
        pane.parallel.setChecked(True)
        app.processEvents()

        view = pane.compare_view
        bar = view.browser.horizontalScrollBar()
        assert bar.maximum() > 0

        bar.setValue(0)
        app.processEvents()
        view.begin_add()
        for _ in range(6):
            app.processEvents()

        assert bar.value() == bar.maximum()
        draft = view._draft_header
        assert draft is not None
        right = draft.combo.mapTo(view, draft.combo.rect().topRight()).x()
        assert right <= view.browser.viewport().width()
    finally:
        pane.deleteLater()
        app.processEvents()
        _close(modules)


def test_compare_view_never_imposes_a_minimum_width(app, tmp_path):
    """The header strip must not turn its own width into the view minimum.

    A fixed-width strip made the viewport width the minimum of the whole
    view: the splitter could not shrink the content, the window grew on every
    sidebar toggle and the window manager disabled *maximise*.
    """
    ctx, modules = _context(tmp_path, _specs("a", "b", "c"))
    pane = BiblePane(ctx)
    pane.resize(1200, 700)
    pane.show()
    app.processEvents()
    try:
        pane.set_compare_columns(["a", "b", "c"])
        pane.parallel.setChecked(True)
        app.processEvents()

        view = pane.compare_view
        # Without translations the body is an empty message; the strip is what
        # used to leak the width.
        assert view.minimumSizeHint().width() < 300
        assert view.header_host.width() == view.browser.viewport().width()

        pane.resize(700, 700)
        for _ in range(3):
            app.processEvents()
        assert view.minimumSizeHint().width() < 300
        assert view.header_host.width() == view.browser.viewport().width()
        # The strip still sits above the browser, not over it.
        assert view.header_host.geometry().bottom() <= view.browser.geometry().top()
    finally:
        pane.deleteLater()
        app.processEvents()
        _close(modules)


# ── stacked bands (split) ────────────────────────────────────────────────
def _many_specs(*names, verses: int = 40):
    return [
        (name, f"{name}.bblx", f"Title {name.upper()}", name.upper(),
         [(BOOK, CHAPTER, verse, f"{name} verse {verse}")
          for verse in range(1, verses + 1)])
        for name in names
    ]


def _split_view(pane, app):
    pane.parallel.setChecked(True)
    app.processEvents()
    pane.compare_view.split_button.click()
    for _ in range(4):
        app.processEvents()
    return pane.compare_view


def test_split_button_requires_four_versions(app, tmp_path):
    ctx, modules = _context(tmp_path, _specs("a", "b", "c"))
    pane = BiblePane(ctx)
    pane.resize(1000, 700)
    pane.show()
    app.processEvents()
    try:
        pane.set_compare_columns(["a", "b", "c"])
        pane.parallel.setChecked(True)
        app.processEvents()

        view = pane.compare_view
        assert not view.split_button.isEnabled()
        assert tr("compare.split_needs_versions", n=4) in view.split_button.toolTip()
        assert len(view.bands()) == 1
    finally:
        pane.deleteLater()
        app.processEvents()
        _close(modules)


def test_split_balances_an_odd_count_three_plus_two(app, tmp_path):
    specs = _many_specs("a", "b", "c", "d", "e", verses=2)
    ctx, modules = _context(tmp_path, specs)
    pane = BiblePane(ctx)
    pane.resize(1200, 800)
    pane.show()
    app.processEvents()
    try:
        pane.set_compare_columns([spec[0] for spec in specs])
        view = _split_view(pane, app)

        assert view.split_button.isEnabled()
        assert view.split_button.isChecked()
        assert view.is_split() is True
        bands = view.bands()
        assert len(bands) == 2
        # Five versions: three on top; the lower band shows two versions plus
        # one empty column so the vertical grid stays aligned.
        assert len(bands[0].header_widgets) == 1 + 3
        assert len(bands[1].header_widgets) == 1 + 3
        assert bands[0]._metrics.widths == bands[1]._metrics.widths
        # Both bands show the same verses.
        assert bands[0]._verses == bands[1]._verses == [1, 2]
        # One band is above the other.
        assert bands[0].geometry().bottom() <= bands[1].geometry().top()
    finally:
        pane.deleteLater()
        app.processEvents()
        _close(modules)


def test_split_bands_follow_each_other_vertically(app, tmp_path):
    specs = _many_specs("a", "b", "c", "d", verses=40)
    ctx, modules = _context(tmp_path, specs)
    pane = BiblePane(ctx)
    pane.resize(1000, 700)
    pane.show()
    app.processEvents()
    try:
        pane.set_compare_columns([spec[0] for spec in specs])
        view = _split_view(pane, app)
        bands = view.bands()
        assert len(bands) == 2

        top_bar = bands[0].browser.verticalScrollBar()
        assert top_bar.maximum() > 0
        top_bar.setValue(top_bar.maximum() // 2)
        for _ in range(4):
            app.processEvents()

        verse = bands[0].top_verse()
        assert verse > 1
        assert bands[1].top_verse() == verse
    finally:
        pane.deleteLater()
        app.processEvents()
        _close(modules)


def test_adding_a_version_goes_to_the_last_band(app, tmp_path):
    specs = _many_specs("a", "b", "c", "d", verses=2)
    ctx, modules = _context(tmp_path, specs)
    pane = BiblePane(ctx)
    pane.resize(1200, 800)
    pane.show()
    app.processEvents()
    try:
        pane.set_compare_columns([spec[0] for spec in specs])
        view = _split_view(pane, app)
        view.begin_add()
        for _ in range(6):
            app.processEvents()

        draft = view._draft_header
        assert draft is not None
        assert draft in view.bands()[-1].header_widgets
        assert draft not in view.bands()[0].header_widgets
    finally:
        pane.deleteLater()
        app.processEvents()
        _close(modules)


def test_split_state_is_persisted_per_workspace(app, tmp_path):
    specs = _many_specs("a", "b", "c", "d", verses=2)
    ctx, modules = _context(tmp_path, specs)
    ws = Workspace(ctx, "Workspace A", "#c9973f")
    try:
        ws.set_main(ctx.catalog.by_rel_path("a"))
        ws.bible.set_compare_columns([spec[0] for spec in specs])
        ws.bible.set_parallel(True)
        ws.bible.set_compare_split(True)
        state = ws.state()
        assert state["compare_split"] is True

        restored = Workspace(ctx, "Workspace B", "#4a7fb5")
        try:
            restored.apply_state(state)
            assert restored.bible.compare_split() is True
        finally:
            restored.deleteLater()
            app.processEvents()
    finally:
        ws.deleteLater()
        app.processEvents()
        _close(modules)


def test_a_new_version_fills_the_empty_split_column(app, tmp_path):
    """The draft must occupy the free column, not widen the grid.

    With five versions the lower band shows two versions and one empty
    column. Adding a version used to add *another* column and leave two
    holes (4th and 6th positions).
    """
    specs = _many_specs("a", "b", "c", "d", "e", "f", verses=2)
    ctx, modules = _context(tmp_path, specs)
    pane = BiblePane(ctx)
    pane.resize(1200, 800)
    pane.show()
    app.processEvents()
    try:
        pane.set_compare_columns([spec[0] for spec in specs[:5]])
        view = _split_view(pane, app)
        bands = view.bands()
        widths = bands[0]._metrics.widths
        assert len(bands[0].header_widgets) == 1 + 3
        assert len(bands[1].header_widgets) == 1 + 3

        view.begin_add()
        for _ in range(6):
            app.processEvents()
        bands = view.bands()
        # The draft fills the free column: the grid does not grow.
        assert len(bands[0].header_widgets) == 1 + 3
        assert len(bands[1].header_widgets) == 1 + 3
        assert bands[1].header_widgets[-1] is view._draft_header
        assert bands[0]._metrics.widths == bands[1]._metrics.widths == widths

        draft = view._draft_header
        draft._on_activated(draft.combo.findData("f"))
        for _ in range(6):
            app.processEvents()
        bands = view.bands()
        # Six versions: three and three, no free column.
        assert len(bands[0].header_widgets) == 1 + 3
        assert len(bands[1].header_widgets) == 1 + 3
        assert bands[0]._metrics.widths == bands[1]._metrics.widths == widths
    finally:
        pane.deleteLater()
        app.processEvents()
        _close(modules)
