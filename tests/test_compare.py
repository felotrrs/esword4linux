"""Pure verse-alignment tests for the multi-version comparator."""

from __future__ import annotations

import pytest

from esword4linux.core.compare import (
    CellStatus,
    ChapterData,
    ColumnStatus,
    CompareColumn,
    align_chapters,
)
from esword4linux.core.esword.module import Page

BOOK = 1
CHAPTER = 1


def _column(key: str, title: str = "") -> CompareColumn:
    return CompareColumn(key=key, title=title or key, abbreviation=key.upper())


def _page(verse: int | None, raw: str = "text", *, book: int = BOOK,
          chapter: int = CHAPTER) -> Page:
    return Page(
        ref=f"{book}:{chapter}:{verse}",
        title=f"Test {book}:{chapter}:{verse}",
        raw=raw,
        book=book,
        chapter=chapter,
        verse=verse,
    )


def _chapter(
    column: CompareColumn,
    pages: tuple[Page, ...] = (),
    *,
    book_exists: bool | None = None,
    chapter_exists: bool | None = None,
) -> ChapterData:
    return ChapterData(
        column=column,
        book=BOOK,
        chapter=CHAPTER,
        pages=pages,
        book_exists=book_exists,
        chapter_exists=chapter_exists,
    )


def test_same_numbering_aligns_by_verse() -> None:
    table = align_chapters(BOOK, CHAPTER, [
        _chapter(_column("a"), (_page(1, "a1"), _page(2, "a2"), _page(3, "a3"))),
        _chapter(_column("b"), (_page(1, "b1"), _page(2, "b2"), _page(3, "b3"))),
    ])

    assert table.verses == (1, 2, 3)
    assert [state.status for state in table.columns] == [
        ColumnStatus.PRESENT,
        ColumnStatus.PRESENT,
    ]
    assert table.cell(2, "a").pages[0].raw == "a2"
    assert table.cell(2, "b").pages[0].raw == "b2"


def test_different_verse_counts_leave_a_gap() -> None:
    table = align_chapters(BOOK, CHAPTER, [
        _chapter(_column("a"), (_page(1, "a1"), _page(2, "a2"), _page(3, "a3"))),
        _chapter(_column("b"), (_page(1, "b1"), _page(2, "b2"))),
    ])

    assert table.verses == (1, 2, 3)
    assert table.cell(2, "b").status is CellStatus.PRESENT
    assert table.cell(3, "b").status is CellStatus.MISSING_VERSE
    assert table.cell(3, "b").pages == ()


def test_missing_verse_in_the_middle_does_not_shift_content() -> None:
    table = align_chapters(BOOK, CHAPTER, [
        _chapter(_column("a"), (_page(1, "a1"), _page(2, "a2"), _page(3, "a3"))),
        _chapter(_column("b"), (_page(1, "b1"), _page(3, "b3"))),
    ])

    assert table.verses == (1, 2, 3)
    assert table.cell(2, "b").status is CellStatus.MISSING_VERSE
    assert table.cell(3, "b").status is CellStatus.PRESENT
    assert table.cell(3, "b").pages[0].raw == "b3"


def test_numbering_differences_are_aligned_numerically() -> None:
    table = align_chapters(BOOK, CHAPTER, [
        _chapter(_column("a"), (
            _page(1, "a1"), _page(2, "a2"), _page(3, "a3"), _page(4, "a4"),
        )),
        _chapter(_column("b"), (
            _page(1, "b1"), _page(2, "b2"), _page(4, "b4"), _page(5, "b5"),
        )),
    ])

    assert table.verses == (1, 2, 3, 4, 5)
    assert table.cell(3, "a").status is CellStatus.PRESENT
    assert table.cell(3, "b").status is CellStatus.MISSING_VERSE
    assert table.cell(4, "a").status is CellStatus.PRESENT
    assert table.cell(4, "b").status is CellStatus.PRESENT
    assert table.cell(5, "a").status is CellStatus.MISSING_VERSE
    assert table.cell(5, "b").status is CellStatus.PRESENT


def test_verse_zero_is_preserved_and_sorted_first() -> None:
    table = align_chapters(BOOK, CHAPTER, [
        _chapter(_column("a"), (_page(0, "a0"), _page(1, "a1"))),
        _chapter(_column("b"), (_page(1, "b1"),)),
    ])

    assert table.verses == (0, 1)
    assert table.cell(0, "a").status is CellStatus.PRESENT
    assert table.cell(0, "a").pages[0].raw == "a0"
    assert table.cell(0, "b").status is CellStatus.MISSING_VERSE


def test_duplicate_rows_are_preserved_in_source_order() -> None:
    table = align_chapters(BOOK, CHAPTER, [
        _chapter(_column("a"), (_page(1, "first"), _page(1, "second"))),
        _chapter(_column("b"), (_page(1, "b1"),)),
    ])

    cell = table.cell(1, "a")
    assert cell.status is CellStatus.PRESENT
    assert [page.raw for page in cell.pages] == ["first", "second"]


def test_duplicate_rows_with_empty_content_are_not_discarded() -> None:
    table = align_chapters(BOOK, CHAPTER, [
        _chapter(_column("a"), (_page(1, ""), _page(1, "second"))),
    ])

    cell = table.cell(1, "a")
    assert cell.status is CellStatus.PRESENT
    assert [page.raw for page in cell.pages] == ["", "second"]


def test_missing_chapter_is_a_column_state_and_cell_state() -> None:
    table = align_chapters(BOOK, CHAPTER, [
        _chapter(_column("a"), (_page(1, "a1"),)),
        _chapter(_column("b"), (), book_exists=True, chapter_exists=False),
    ])

    assert table.column_state("b").status is ColumnStatus.MISSING_CHAPTER
    assert table.cell(1, "b").status is CellStatus.MISSING_CHAPTER


def test_chapter_existence_is_inferred_from_pages_when_unknown() -> None:
    table = align_chapters(BOOK, CHAPTER, [
        _chapter(_column("a"), (_page(1, "a1"),)),
        _chapter(_column("b"), (), book_exists=True),
    ])

    assert table.column_state("b").status is ColumnStatus.MISSING_CHAPTER
    assert table.cell(1, "b").status is CellStatus.MISSING_CHAPTER


def test_duplicate_order_follows_the_supplied_source_order() -> None:
    table = align_chapters(BOOK, CHAPTER, [
        _chapter(_column("a"), (_page(1, "second"), _page(1, "first"))),
    ])

    assert [page.raw for page in table.cell(1, "a").pages] == ["second", "first"]


def test_missing_book_is_a_column_state_and_cell_state() -> None:
    table = align_chapters(BOOK, CHAPTER, [
        _chapter(_column("a"), (_page(1, "a1"),)),
        _chapter(_column("b"), (), book_exists=False),
    ])

    assert table.column_state("b").status is ColumnStatus.MISSING_BOOK
    assert table.cell(1, "b").status is CellStatus.MISSING_BOOK


def test_existing_chapter_without_rows_is_empty_not_missing() -> None:
    table = align_chapters(BOOK, CHAPTER, [
        _chapter(_column("a"), (_page(1, "a1"), _page(2, "a2"))),
        _chapter(_column("b"), (), book_exists=True, chapter_exists=True),
    ])

    state = table.column_state("b")
    assert state.status is ColumnStatus.EMPTY
    assert state.has_rows is False
    assert table.cell(1, "b").status is CellStatus.EMPTY
    assert table.cell(2, "b").status is CellStatus.EMPTY


def test_existing_chapter_with_empty_rows_is_empty() -> None:
    table = align_chapters(BOOK, CHAPTER, [
        _chapter(_column("a"), (_page(1, "a1"), _page(2, "a2"))),
        _chapter(_column("b"), (_page(1, ""), _page(2, "   "))),
    ])

    state = table.column_state("b")
    assert state.status is ColumnStatus.EMPTY
    assert state.has_rows is True
    assert table.cell(1, "b").status is CellStatus.EMPTY
    assert table.cell(2, "b").status is CellStatus.EMPTY


def test_empty_rows_do_not_hide_a_missing_verse() -> None:
    """Regression: a chapter with rows all empty is not the same as no rows."""
    table = align_chapters(BOOK, CHAPTER, [
        _chapter(_column("a"), (
            _page(1, "a1"), _page(2, "a2"), _page(3, "a3"),
        )),
        _chapter(_column("b"), (_page(1, ""), _page(2, "   "))),
    ])

    state = table.column_state("b")
    assert state.status is ColumnStatus.EMPTY
    assert state.has_rows is True
    assert table.cell(1, "b").status is CellStatus.EMPTY
    assert table.cell(2, "b").status is CellStatus.EMPTY
    assert table.cell(3, "b").status is CellStatus.MISSING_VERSE


def test_mixed_empty_and_present_rows_are_distinguished() -> None:
    table = align_chapters(BOOK, CHAPTER, [
        _chapter(_column("a"), (_page(1, "a1"), _page(2, "a2"), _page(3, "a3"))),
        _chapter(_column("b"), (_page(1, ""), _page(2, "b2"))),
    ])

    assert table.column_state("b").status is ColumnStatus.PRESENT
    assert table.cell(1, "b").status is CellStatus.EMPTY
    assert table.cell(2, "b").status is CellStatus.PRESENT
    assert table.cell(3, "b").status is CellStatus.MISSING_VERSE


def test_deterministic_row_and_duplicate_order() -> None:
    chapters = [
        _chapter(_column("a"), (
            _page(3, "a3"),
            _page(1, "a1-first"),
            _page(2, "a2"),
            _page(1, "a1-second"),
        )),
        _chapter(_column("b"), (_page(1, "b1"),)),
    ]

    first = align_chapters(BOOK, CHAPTER, chapters)
    second = align_chapters(BOOK, CHAPTER, chapters)

    assert first == second
    assert first.verses == (1, 2, 3)
    assert [page.raw for page in first.cell(1, "a").pages] == [
        "a1-first", "a1-second",
    ]


def test_single_version_is_supported() -> None:
    table = align_chapters(BOOK, CHAPTER, [
        _chapter(_column("a"), (_page(1, "a1"), _page(2, "a2"))),
    ])

    assert table.verses == (1, 2)
    assert len(table.columns) == 1
    assert [len(row.cells) for row in table.rows] == [1, 1]
    assert table.cell(1, "a").status is CellStatus.PRESENT


def test_multiple_versions_keep_column_order_and_provenance() -> None:
    table = align_chapters(BOOK, CHAPTER, [
        _chapter(_column("a"), (_page(1, "a1"), _page(2, "a2"), _page(3, "a3"))),
        _chapter(_column("b"), (_page(1, "b1"), _page(3, "b3"))),
        _chapter(_column("c"), (_page(2, "c2"),)),
        _chapter(_column("d"), (), book_exists=False),
    ])

    assert table.verses == (1, 2, 3)
    assert [state.column.key for state in table.columns] == ["a", "b", "c", "d"]
    assert [len(row.cells) for row in table.rows] == [4, 4, 4]
    assert table.cell(2, "b").status is CellStatus.MISSING_VERSE
    assert table.cell(2, "c").status is CellStatus.PRESENT
    assert table.cell(2, "d").status is CellStatus.MISSING_BOOK


def test_all_columns_missing_produces_no_rows() -> None:
    table = align_chapters(BOOK, CHAPTER, [
        _chapter(_column("a"), (), book_exists=False),
        _chapter(_column("b"), (), book_exists=True, chapter_exists=False),
    ])

    assert table.rows == ()
    assert [state.status for state in table.columns] == [
        ColumnStatus.MISSING_BOOK,
        ColumnStatus.MISSING_CHAPTER,
    ]


def test_whitespace_only_content_is_empty() -> None:
    table = align_chapters(BOOK, CHAPTER, [
        _chapter(_column("a"), (_page(1, " \n\t "),)),
    ])

    assert table.column_state("a").status is ColumnStatus.EMPTY
    assert table.cell(1, "a").status is CellStatus.EMPTY


def test_markup_is_raw_content_not_interpreted_here() -> None:
    table = align_chapters(BOOK, CHAPTER, [
        _chapter(_column("a"), (_page(1, "<p></p>"),)),
    ])

    assert table.column_state("a").status is ColumnStatus.PRESENT
    assert table.cell(1, "a").status is CellStatus.PRESENT


def test_column_label_falls_back_to_key() -> None:
    assert CompareColumn("a").label == "a"
    assert CompareColumn("a", title="Title").label == "Title"
    assert CompareColumn("a", title="Title", abbreviation="AB").label == "AB"


def test_unknown_lookups_return_none() -> None:
    table = align_chapters(BOOK, CHAPTER, [
        _chapter(_column("a"), (_page(1, "a1"),)),
    ])

    assert table.column_state("missing") is None
    assert table.cell(99, "a") is None
    assert table.cell(1, "missing") is None
    assert table.rows[0].cell("missing") is None


def test_no_columns_is_rejected() -> None:
    with pytest.raises(ValueError, match="at least one"):
        align_chapters(BOOK, CHAPTER, [])


def test_duplicate_column_keys_are_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate column key"):
        align_chapters(BOOK, CHAPTER, [
            _chapter(_column("a"), (_page(1, "a1"),)),
            _chapter(_column("a"), (_page(1, "a2"),)),
        ])


def test_column_must_match_the_requested_reference() -> None:
    data = ChapterData(
        column=_column("a"),
        book=2,
        chapter=CHAPTER,
        pages=(_page(1, "a1"),),
    )
    with pytest.raises(ValueError, match="refers to 2:1"):
        align_chapters(BOOK, CHAPTER, [data])


def test_book_existence_is_inferred_from_pages() -> None:
    table = align_chapters(BOOK, CHAPTER, [
        _chapter(_column("a"), (_page(1, "a1"),)),
    ])

    assert table.column_state("a").status is ColumnStatus.PRESENT


def test_book_existence_must_be_explicit_when_there_are_no_pages() -> None:
    with pytest.raises(ValueError, match="book_exists must be explicit"):
        align_chapters(BOOK, CHAPTER, [
            _chapter(_column("a"), (), chapter_exists=True),
        ])


def test_page_without_verse_is_rejected() -> None:
    with pytest.raises(ValueError, match="integer verse"):
        align_chapters(BOOK, CHAPTER, [
            _chapter(_column("a"), (_page(None, "a1"),)),
        ])


@pytest.mark.parametrize("verse", [True, False])
def test_boolean_verse_is_rejected(verse: bool) -> None:
    with pytest.raises(ValueError, match="integer verse"):
        align_chapters(BOOK, CHAPTER, [
            _chapter(_column("a"), (_page(verse, "a1"),)),
        ])


def test_page_from_another_book_is_rejected() -> None:
    with pytest.raises(ValueError, match="belongs to book 2"):
        align_chapters(BOOK, CHAPTER, [
            _chapter(_column("a"), (_page(1, "a1", book=2),)),
        ])


def test_page_from_another_chapter_is_rejected() -> None:
    with pytest.raises(ValueError, match="belongs to chapter 2"):
        align_chapters(BOOK, CHAPTER, [
            _chapter(_column("a"), (_page(1, "a1", chapter=2),)),
        ])


def test_missing_book_with_pages_is_rejected() -> None:
    with pytest.raises(ValueError, match="book is missing"):
        align_chapters(BOOK, CHAPTER, [
            _chapter(_column("a"), (_page(1, "a1"),), book_exists=False),
        ])


def test_missing_chapter_with_pages_is_rejected() -> None:
    with pytest.raises(ValueError, match="chapter is missing"):
        align_chapters(BOOK, CHAPTER, [
            _chapter(_column("a"), (_page(1, "a1"),), chapter_exists=False),
        ])


@pytest.mark.parametrize("key", ["", "   "])
def test_empty_column_key_is_rejected(key: str) -> None:
    with pytest.raises(ValueError, match="non-empty"):
        CompareColumn(key)
