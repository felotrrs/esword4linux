"""Synthetic SQLite tests for chapter reading and comparator alignment.

The fixtures are generated in ``tmp_path`` with harmless placeholder text.
They are never committed and never written to the user's modules folder.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from esword4linux.core.compare import (
    CellStatus,
    ChapterData,
    ColumnStatus,
    CompareColumn,
    align_chapters,
)
from esword4linux.core.esword.module import EswordModule, Page

BOOK = 1
CHAPTER = 1


def _make_bible(path: Path, rows: list[tuple[int, int, int, str]]) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "CREATE TABLE Bible (Book INT, Chapter INT, Verse INT, Scripture TEXT)"
        )
        conn.execute(
            "CREATE INDEX BookChapterVerseIndex ON Bible (Book, Chapter, Verse)"
        )
        conn.executemany(
            "INSERT INTO Bible (Book, Chapter, Verse, Scripture) VALUES (?, ?, ?, ?)",
            rows,
        )
        conn.commit()
    finally:
        conn.close()


def _ordered_pages(mod: EswordModule, book: int, chapter: int) -> tuple[Page, ...]:
    """Read a chapter with the stable tiebreaker recommended for a loader."""
    rows = mod.conn.execute(
        "SELECT Book, Chapter, Verse, Scripture FROM Bible "
        "WHERE Book=? AND Chapter=? ORDER BY Verse, rowid",
        (book, chapter),
    ).fetchall()
    return tuple(
        Page(
            ref=f"{book}:{chapter}:{row['Verse']}",
            title=f"Test {book}:{chapter}:{row['Verse']}",
            raw=mod._decode(
                row["Scripture"], "Bible", f"{book}:{chapter}:{row['Verse']}"
            ),
            book=book,
            chapter=chapter,
            verse=row["Verse"],
            order=row["Verse"],
        )
        for row in rows
    )


def _column(key: str) -> CompareColumn:
    return CompareColumn(key=key, title=key, abbreviation=key.upper())


def test_bible_chapter_exposes_every_duplicate_row(tmp_path: Path) -> None:
    path = tmp_path / "duplicates.bblx"
    _make_bible(path, [
        (BOOK, CHAPTER, 0, "cero"),
        (BOOK, CHAPTER, 1, "primero"),
        (BOOK, CHAPTER, 1, "segundo"),
        (BOOK, CHAPTER, 2, ""),
        (BOOK, CHAPTER, 3, "tercero"),
        (2, CHAPTER, 1, "otro libro"),
    ])

    with EswordModule(path) as mod:
        pages = mod.bible_chapter(BOOK, CHAPTER)

    assert len(pages) == 5
    assert sorted(page.verse for page in pages) == [0, 1, 1, 2, 3]
    assert sum(1 for page in pages if page.verse == 1) == 2
    assert {page.raw for page in pages if page.verse == 1} == {"primero", "segundo"}


def test_rowid_is_the_available_stable_tiebreaker(tmp_path: Path) -> None:
    path = tmp_path / "rowid.bblx"
    _make_bible(path, [
        (BOOK, CHAPTER, 1, "primero"),
        (BOOK, CHAPTER, 1, "segundo"),
        (BOOK, CHAPTER, 2, "segundo versiculo"),
        (BOOK, CHAPTER, 0, "cero"),
    ])

    with EswordModule(path) as mod:
        rows = mod.conn.execute(
            "SELECT Verse, Scripture FROM Bible "
            "WHERE Book=? AND Chapter=? ORDER BY Verse, rowid",
            (BOOK, CHAPTER),
        ).fetchall()

    assert [(row["Verse"], row["Scripture"]) for row in rows] == [
        (0, "cero"),
        (1, "primero"),
        (1, "segundo"),
        (2, "segundo versiculo"),
    ]


def test_bible_chapter_stable_orders_duplicates_by_rowid(tmp_path: Path) -> None:
    path = tmp_path / "stable.bblx"
    _make_bible(path, [
        (BOOK, CHAPTER, 1, "primero"),
        (BOOK, CHAPTER, 1, "segundo"),
        (BOOK, CHAPTER, 2, "tercero"),
    ])

    with EswordModule(path) as mod:
        stable = mod.bible_chapter_stable(BOOK, CHAPTER)
        traditional = mod.bible_chapter(BOOK, CHAPTER)

    assert [(page.verse, page.raw) for page in stable] == [
        (1, "primero"),
        (1, "segundo"),
        (2, "tercero"),
    ]
    assert len(traditional) == 3
    assert {page.raw for page in traditional} == {"primero", "segundo", "tercero"}


def test_alignment_reads_two_synthetic_modules(tmp_path: Path) -> None:
    path_a = tmp_path / "a.bblx"
    path_b = tmp_path / "b.bblx"
    _make_bible(path_a, [
        (BOOK, CHAPTER, 0, "a0"),
        (BOOK, CHAPTER, 1, "a1-first"),
        (BOOK, CHAPTER, 1, "a1-second"),
        (BOOK, CHAPTER, 2, ""),
        (BOOK, CHAPTER, 3, "a3"),
    ])
    _make_bible(path_b, [
        (BOOK, CHAPTER, 1, "b1"),
        (BOOK, CHAPTER, 3, "b3"),
    ])

    with EswordModule(path_a) as mod_a, EswordModule(path_b) as mod_b:
        pages_a = _ordered_pages(mod_a, BOOK, CHAPTER)
        pages_b = _ordered_pages(mod_b, BOOK, CHAPTER)

    table = align_chapters(BOOK, CHAPTER, [
        ChapterData(
            column=_column("a"),
            book=BOOK,
            chapter=CHAPTER,
            pages=pages_a,
            chapter_exists=True,
        ),
        ChapterData(
            column=_column("b"),
            book=BOOK,
            chapter=CHAPTER,
            pages=pages_b,
            chapter_exists=True,
        ),
    ])

    assert table.verses == (0, 1, 2, 3)
    assert table.column_state("a").status is ColumnStatus.PRESENT
    assert table.column_state("b").status is ColumnStatus.PRESENT
    assert [page.raw for page in table.cell(1, "a").pages] == [
        "a1-first", "a1-second",
    ]
    assert table.cell(2, "a").status is CellStatus.EMPTY
    assert table.cell(2, "b").status is CellStatus.MISSING_VERSE
    assert table.cell(0, "b").status is CellStatus.MISSING_VERSE
    assert table.cell(3, "b").status is CellStatus.PRESENT


def test_reader_can_report_missing_book_and_missing_chapter(tmp_path: Path) -> None:
    path = tmp_path / "missing.bblx"
    _make_bible(path, [(BOOK, CHAPTER, 1, "texto")])

    with EswordModule(path) as mod:
        assert mod.books() == [BOOK]
        assert mod.bible_chapter(3, CHAPTER) == []
        assert mod.bible_chapter(BOOK, 2) == []

        missing_book = ChapterData(
            column=_column("book"),
            book=3,
            chapter=CHAPTER,
            pages=(),
            book_exists=False,
        )
        missing_chapter = ChapterData(
            column=_column("chapter"),
            book=BOOK,
            chapter=2,
            pages=(),
            book_exists=True,
            chapter_exists=False,
        )

    table = align_chapters(3, CHAPTER, [missing_book])
    assert table.columns[0].status is ColumnStatus.MISSING_BOOK

    table = align_chapters(BOOK, 2, [missing_chapter])
    assert table.columns[0].status is ColumnStatus.MISSING_CHAPTER


def test_bible_verse_returns_only_one_of_the_duplicates(tmp_path: Path) -> None:
    path = tmp_path / "one-verse.bblx"
    _make_bible(path, [
        (BOOK, CHAPTER, 1, "primero"),
        (BOOK, CHAPTER, 1, "segundo"),
    ])

    with EswordModule(path) as mod:
        page = mod.bible_verse(BOOK, CHAPTER, 1)

    assert page is not None
    assert page.raw in {"primero", "segundo"}


def test_reading_a_module_does_not_modify_it(tmp_path: Path) -> None:
    path = tmp_path / "readonly.bblx"
    _make_bible(path, [(BOOK, CHAPTER, 1, "texto")])
    before = path.read_bytes()

    with EswordModule(path) as mod:
        mod.bible_chapter(BOOK, CHAPTER)
        mod.bible_chapter_stable(BOOK, CHAPTER)
        mod.books()

    assert path.read_bytes() == before
