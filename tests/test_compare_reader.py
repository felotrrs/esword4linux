"""Data-access adapter tests for the multi-version comparator."""

from __future__ import annotations

from pathlib import Path

from esword4linux.config import Settings
from esword4linux.core.compare import CellStatus, ColumnStatus
from esword4linux.core.compare_reader import build_compare_table
from esword4linux.core.esword.module import EswordModule

from compare_support import FakeContext, make_bible, row

BOOK = 1
CHAPTER = 1


def _context(tmp_path: Path, specs):
    modules: dict[str, EswordModule] = {}
    rows: list[dict] = []
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
        bible_module=specs[0][0] if specs else "",
    )
    return FakeContext(settings, rows, modules), modules


def _close(modules) -> None:
    for mod in modules.values():
        mod.close()


def test_build_aligns_and_exposes_sources(tmp_path: Path) -> None:
    ctx, modules = _context(tmp_path, [
        ("a", "a.bblx", "Alpha", "AAA", [
            (BOOK, CHAPTER, 1, "a1"),
            (BOOK, CHAPTER, 2, "a2"),
            (BOOK, CHAPTER, 3, "a3"),
        ]),
        ("b", "b.bblx", "Beta", "BBB", [
            (BOOK, CHAPTER, 1, "b1"),
            (BOOK, CHAPTER, 3, "b3"),
        ]),
    ])
    try:
        build = build_compare_table(ctx, ["a", "b"], BOOK, CHAPTER)
    finally:
        _close(modules)

    assert build.table is not None
    assert build.table.verses == (1, 2, 3)
    assert build.table.column_state("a").status is ColumnStatus.PRESENT
    assert build.table.cell(2, "b").status is CellStatus.MISSING_VERSE
    assert set(build.sources) == {"a", "b"}
    assert build.sources["a"].hint == "a"
    assert build.warnings == ()


def test_missing_book_is_explicit(tmp_path: Path) -> None:
    ctx, modules = _context(tmp_path, [
        ("a", "a.bblx", "Alpha", "AAA", [(BOOK, CHAPTER, 1, "a1")]),
        ("c", "c.bblx", "Gamma", "CCC", [(2, CHAPTER, 1, "c1")]),
    ])
    try:
        build = build_compare_table(ctx, ["a", "c"], BOOK, CHAPTER)
    finally:
        _close(modules)

    assert build.table is not None
    assert build.table.column_state("c").status is ColumnStatus.MISSING_BOOK
    assert build.table.cell(1, "c").status is CellStatus.MISSING_BOOK


def test_existing_empty_chapter_differs_from_missing_chapter(tmp_path: Path) -> None:
    ctx, modules = _context(tmp_path, [
        ("d", "d.bblx", "Delta", "DDD", [
            (BOOK, 1, 1, "d1"),
            (BOOK, 3, 1, "d3"),
        ]),
    ])
    try:
        empty = build_compare_table(ctx, ["d"], BOOK, 2)
        missing = build_compare_table(ctx, ["d"], BOOK, 4)
    finally:
        _close(modules)

    assert empty.table is not None
    assert empty.table.column_state("d").status is ColumnStatus.EMPTY
    assert empty.table.column_state("d").has_rows is False

    assert missing.table is not None
    assert missing.table.column_state("d").status is ColumnStatus.MISSING_CHAPTER


def test_empty_rows_with_missing_verse(tmp_path: Path) -> None:
    ctx, modules = _context(tmp_path, [
        ("a", "a.bblx", "Alpha", "AAA", [
            (BOOK, CHAPTER, 1, "a1"),
            (BOOK, CHAPTER, 2, "a2"),
            (BOOK, CHAPTER, 3, "a3"),
        ]),
        ("e", "e.bblx", "Epsilon", "EEE", [
            (BOOK, CHAPTER, 1, ""),
            (BOOK, CHAPTER, 2, "   "),
        ]),
    ])
    try:
        build = build_compare_table(ctx, ["a", "e"], BOOK, CHAPTER)
    finally:
        _close(modules)

    assert build.table is not None
    state = build.table.column_state("e")
    assert state.status is ColumnStatus.EMPTY
    assert state.has_rows is True
    assert build.table.cell(1, "e").status is CellStatus.EMPTY
    assert build.table.cell(3, "e").status is CellStatus.MISSING_VERSE


def test_duplicate_rows_use_stable_order(tmp_path: Path) -> None:
    ctx, modules = _context(tmp_path, [
        ("f", "f.bblx", "Zeta", "FFF", [
            (BOOK, CHAPTER, 1, "first"),
            (BOOK, CHAPTER, 1, "second"),
            (BOOK, CHAPTER, 2, "third"),
        ]),
        ("a", "a.bblx", "Alpha", "AAA", [(BOOK, CHAPTER, 1, "a1")]),
    ])
    try:
        build = build_compare_table(ctx, ["f", "a"], BOOK, CHAPTER)
    finally:
        _close(modules)

    assert build.table is not None
    cell = build.table.cell(1, "f")
    assert [page.raw for page in cell.pages] == ["first", "second"]


def test_malformed_page_is_isolated_to_its_column(tmp_path: Path) -> None:
    ctx, modules = _context(tmp_path, [
        ("a", "a.bblx", "Alpha", "AAA", [
            (BOOK, CHAPTER, 1, "a1"),
            (BOOK, CHAPTER, 2, "a2"),
            (BOOK, CHAPTER, 3, "a3"),
        ]),
        ("bad", "bad.bblx", "Bad", "BAD", [
            (BOOK, CHAPTER, None, "invalid"),
        ]),
        ("c", "c.bblx", "Gamma", "CCC", [
            (BOOK, CHAPTER, 1, "c1"),
            (BOOK, CHAPTER, 3, "c3"),
        ]),
    ])
    try:
        build = build_compare_table(ctx, ["a", "bad", "c"], BOOK, CHAPTER)
    finally:
        _close(modules)

    assert build.table is not None
    assert [state.column.key for state in build.table.columns] == ["a", "c"]
    assert build.table.verses == (1, 2, 3)
    assert build.table.cell(2, "a").status is CellStatus.PRESENT
    assert build.table.cell(2, "c").status is CellStatus.MISSING_VERSE
    assert any("BAD" in warning and "bad" in warning for warning in build.warnings)


def test_all_malformed_columns_return_controlled_empty_state(tmp_path: Path) -> None:
    ctx, modules = _context(tmp_path, [
        ("bad", "bad.bblx", "Bad", "BAD", [(BOOK, CHAPTER, None, "invalid")]),
        ("bad2", "bad2.bblx", "Bad2", "BAD2", [(BOOK, CHAPTER, None, "invalid")]),
    ])
    try:
        build = build_compare_table(ctx, ["bad", "bad2"], BOOK, CHAPTER)
    finally:
        _close(modules)

    assert build.table is None
    assert build.sources == {}
    assert len(build.warnings) == 2
    assert all("column omitted" in warning for warning in build.warnings)


def test_broken_module_is_a_warning_not_a_crash(tmp_path: Path) -> None:
    class BrokenBible:
        structure = "bible"
        stem = "broken"
        codepages = {}

        def books(self):
            raise RuntimeError("broken metadata")

        def chapter_count(self, book):
            return 0

        def close(self):
            pass

    ctx, modules = _context(tmp_path, [
        ("a", "a.bblx", "Alpha", "AAA", [(BOOK, CHAPTER, 1, "a1")]),
    ])
    broken_row = row(
        "broken", tmp_path / "broken.bblx", "Broken", "BRK",
        module_id=99, entries=1,
    )
    ctx.catalog._rows["broken"] = broken_row
    ctx._modules["broken"] = BrokenBible()
    try:
        build = build_compare_table(ctx, ["a", "broken"], BOOK, CHAPTER)
    finally:
        _close(modules)

    assert build.table is not None
    assert build.table.column_state("a").status is ColumnStatus.PRESENT
    assert build.table.column_state("broken").status is ColumnStatus.MISSING_BOOK
    assert build.warnings


def test_unexpected_structure_is_skipped_with_warning(tmp_path: Path) -> None:
    class WrongStructure:
        structure = "dictionary"
        stem = "wrong"
        codepages = {}

        def close(self):
            pass

    ctx, modules = _context(tmp_path, [
        ("a", "a.bblx", "Alpha", "AAA", [(BOOK, CHAPTER, 1, "a1")]),
    ])
    wrong = row(
        "wrong", tmp_path / "wrong.bblx", "Wrong", "WRG",
        module_id=2, entries=1,
    )
    ctx.catalog._rows["wrong"] = wrong
    ctx._modules["wrong"] = WrongStructure()
    try:
        build = build_compare_table(ctx, ["a", "wrong"], BOOK, CHAPTER)
    finally:
        _close(modules)

    assert build.table is not None
    assert [state.column.key for state in build.table.columns] == ["a"]
    assert build.warnings


def test_invalid_kind_is_skipped_with_warning(tmp_path: Path) -> None:
    ctx, modules = _context(tmp_path, [
        ("a", "a.bblx", "Alpha", "AAA", [(BOOK, CHAPTER, 1, "a1")]),
    ])
    other = row(
        "dict", tmp_path / "dict.dctx", "Dictionary", "DIC",
        module_id=2, kind="dictionary",
    )
    ctx.catalog._rows["dict"] = other
    try:
        build = build_compare_table(ctx, ["a", "dict"], BOOK, CHAPTER)
    finally:
        _close(modules)

    assert build.table is not None
    assert [state.column.key for state in build.table.columns] == ["a"]
    assert build.warnings


def test_no_columns_returns_no_table(tmp_path: Path) -> None:
    ctx, modules = _context(tmp_path, [
        ("a", "a.bblx", "Alpha", "AAA", [(BOOK, CHAPTER, 1, "a1")]),
    ])
    try:
        build = build_compare_table(ctx, [], BOOK, CHAPTER)
    finally:
        _close(modules)

    assert build.table is None
    assert build.sources == {}
    assert build.warnings == ()
