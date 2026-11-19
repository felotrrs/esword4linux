"""Verse-aligned comparison of Bible chapters across versions.

This module is pure logic: it has no Qt widgets, no SQLite connection and no
HTML. The caller supplies one :class:`ChapterData` per version, already read
from a module, and receives a :class:`CompareTable` that can be rendered by a
later UI phase.

Alignment is **numeric**, by ``(book, chapter, verse)``. Two versions can use
different verse numbering or omit verses; a verse that is absent from one
version is a gap, never a reason to shift the remaining content. The module
does not claim that two rows with the same verse number are semantically
equivalent.

Special cases
-------------
* ``verse == 0`` is preserved and sorted before verse 1.
* Several ``Page`` objects with the same verse are kept in the order in which
  the caller supplied them. The caller must use a stable source order. The
  current :meth:`EswordModule.bible_chapter` query uses ``ORDER BY Verse``,
  which is not a total order when duplicate rows exist. All e-Sword ``Bible``
  tables observed in the corpus have an implicit ``rowid`` (and most also have
  a ``(Book, Chapter, Verse)`` index); a loader that needs a contractual order
  should use ``ORDER BY Verse, rowid`` (or an equivalent stable tiebreaker).
  This phase deliberately does not change the reader.
* A missing book, a missing chapter, a missing verse and empty content are
  different states. The caller must set ``book_exists`` and
  ``chapter_exists`` from the module metadata; ``chapter_exists=None`` is
  inferred from the presence of pages (no pages means missing chapter).
* Empty content means that ``Page.raw`` is empty or whitespace. RTF/HTML is
  not parsed here: a non-empty markup string is considered content. Rendering
  decides later whether it is visually empty.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from .esword.module import Page

__all__ = [
    "CellStatus",
    "ChapterData",
    "ColumnStatus",
    "CompareCell",
    "CompareColumn",
    "CompareColumnState",
    "CompareRow",
    "CompareTable",
    "align_chapters",
]


class ColumnStatus(str, Enum):
    """State of a whole translation column for the requested chapter."""

    PRESENT = "present"
    EMPTY = "empty"
    MISSING_CHAPTER = "missing_chapter"
    MISSING_BOOK = "missing_book"


class CellStatus(str, Enum):
    """State of one translation cell inside a verse row."""

    PRESENT = "present"
    EMPTY = "empty"
    MISSING_VERSE = "missing_verse"
    MISSING_CHAPTER = "missing_chapter"
    MISSING_BOOK = "missing_book"


@dataclass(frozen=True)
class CompareColumn:
    """Identity of one translation column.

    ``key`` must be stable and unique in a comparison; the module ``rel_path``
    is the natural value. ``title`` and ``abbreviation`` are display metadata.
    """

    key: str
    title: str = ""
    abbreviation: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or not self.key.strip():
            raise ValueError("CompareColumn.key must be a non-empty string")

    @property
    def label(self) -> str:
        """Best short label available, without requiring UI knowledge."""
        return self.abbreviation or self.title or self.key


@dataclass(frozen=True)
class ChapterData:
    """One version's chapter, as returned by the module reader.

    ``pages`` must be in stable source order. Duplicate pages for the same
    verse are allowed and preserved. ``book_exists`` comes from
    :meth:`EswordModule.books`. ``None`` means "not supplied": it is inferred
    as ``True`` only when there are pages, and rejected when there are no
    pages. This avoids silently treating an unknown book as present.
    ``chapter_exists`` can be supplied explicitly when the reader knows it.
    When it is ``None``, pages are the only evidence: no pages means the
    chapter is missing.
    """

    column: CompareColumn
    book: int
    chapter: int
    pages: Sequence[Page] = ()
    book_exists: bool | None = None
    chapter_exists: bool | None = None


@dataclass(frozen=True)
class CompareColumnState:
    """A column together with its chapter-level state.

    ``has_rows`` distinguishes an existing chapter with no rows (``False``)
    from a chapter whose rows all have empty content (``True``). Both have
    ``status == EMPTY``, but only the first one makes every cell EMPTY; the
    second one still has MISSING_VERSE cells for verses without a row.
    """

    column: CompareColumn
    status: ColumnStatus
    has_rows: bool = False


@dataclass(frozen=True)
class CompareCell:
    """One version's content for one verse.

    ``pages`` contains every source row for this verse and version, in the
    order supplied by the caller. An empty tuple means the verse is absent or
    the column has no content, according to ``status``.
    """

    column: CompareColumn
    status: CellStatus
    pages: tuple[Page, ...] = ()


@dataclass(frozen=True)
class CompareRow:
    """A verse number and one cell per column, in column order."""

    verse: int
    cells: tuple[CompareCell, ...]

    def cell(self, column_key: str) -> CompareCell | None:
        """Return the cell for ``column_key``, or ``None`` if unknown."""
        for cell in self.cells:
            if cell.column.key == column_key:
                return cell
        return None


@dataclass(frozen=True)
class CompareTable:
    """Result of aligning one chapter across several versions."""

    book: int
    chapter: int
    columns: tuple[CompareColumnState, ...]
    rows: tuple[CompareRow, ...]

    @property
    def verses(self) -> tuple[int, ...]:
        """Verse numbers in rendered order."""
        return tuple(row.verse for row in self.rows)

    def column_state(self, column_key: str) -> CompareColumnState | None:
        """Return the state for ``column_key``, or ``None`` if unknown."""
        for state in self.columns:
            if state.column.key == column_key:
                return state
        return None

    def cell(self, verse: int, column_key: str) -> CompareCell | None:
        """Return the cell at ``verse``/``column_key``, or ``None``."""
        for row in self.rows:
            if row.verse != verse:
                continue
            return row.cell(column_key)
        return None


def align_chapters(
    book: int,
    chapter: int,
    chapters: Sequence[ChapterData],
) -> CompareTable:
    """Align the chapters of several versions by verse number.

    Parameters
    ----------
    book, chapter:
        Target reference. Every :class:`ChapterData` must match it.
    chapters:
        One entry per version, in the desired column order. At least one is
        required. Column keys must be unique.

    Returns
    -------
    CompareTable
        Rows sorted by verse number. For each row, cells follow the input
        column order. Duplicate source rows for the same verse are preserved
        in the order in which they appear in ``ChapterData.pages``.

    Raises
    ------
    ValueError
        If there are no columns, a key is duplicated, a column refers to a
        different book/chapter, a page has no verse, a page belongs to another
        book/chapter, ``book_exists`` is omitted when there are no pages, or
        the existence flags contradict the supplied pages.
    """
    if not chapters:
        raise ValueError("at least one chapter is required")

    seen: set[str] = set()
    prepared: list[
        tuple[ChapterData, tuple[Page, ...], dict[int, list[Page]], ColumnStatus]
    ] = []

    for data in chapters:
        key = data.column.key
        if key in seen:
            raise ValueError(f"duplicate column key: {key!r}")
        seen.add(key)

        if data.book != book or data.chapter != chapter:
            raise ValueError(
                f"column {key!r} refers to {data.book}:{data.chapter}, "
                f"expected {book}:{chapter}"
            )

        pages = tuple(data.pages)
        book_exists = data.book_exists
        if book_exists is None:
            if not pages:
                raise ValueError(
                    f"column {key!r}: book_exists must be explicit when there "
                    "are no pages"
                )
            book_exists = True

        if not book_exists and pages:
            raise ValueError(
                f"column {key!r} says the book is missing but supplied pages"
            )

        has_chapter = (
            bool(pages) if data.chapter_exists is None else bool(data.chapter_exists)
        )
        if not has_chapter and pages:
            raise ValueError(
                f"column {key!r} says the chapter is missing but supplied pages"
            )

        grouped = _group_pages(pages, key, book, chapter)
        status = _column_status(book_exists, has_chapter, pages)
        prepared.append((data, pages, grouped, status))

    verses = sorted(
        {verse for _, _, grouped, _ in prepared for verse in grouped}
    )

    rows: list[CompareRow] = []
    for verse in verses:
        cells: list[CompareCell] = []
        for data, pages, grouped, column_status in prepared:
            cell_pages = tuple(grouped.get(verse, ()))
            cells.append(
                CompareCell(
                    column=data.column,
                    status=_cell_status(
                        column_status,
                        cell_pages,
                        chapter_has_rows=bool(pages),
                    ),
                    pages=cell_pages,
                )
            )
        rows.append(CompareRow(verse=verse, cells=tuple(cells)))

    columns = tuple(
        CompareColumnState(
            column=data.column,
            status=status,
            has_rows=bool(pages),
        )
        for data, pages, _grouped, status in prepared
    )
    return CompareTable(
        book=book,
        chapter=chapter,
        columns=columns,
        rows=tuple(rows),
    )


def _group_pages(
    pages: tuple[Page, ...],
    column_key: str,
    book: int,
    chapter: int,
) -> dict[int, list[Page]]:
    """Group pages by verse, preserving the caller's order inside each verse."""
    grouped: dict[int, list[Page]] = {}
    for page in pages:
        if not isinstance(page.verse, int) or isinstance(page.verse, bool):
            raise ValueError(
                f"column {column_key!r}: page without an integer verse"
            )
        if page.book is not None and page.book != book:
            raise ValueError(
                f"column {column_key!r}: page belongs to book {page.book}, "
                f"expected {book}"
            )
        if page.chapter is not None and page.chapter != chapter:
            raise ValueError(
                f"column {column_key!r}: page belongs to chapter "
                f"{page.chapter}, expected {chapter}"
            )
        grouped.setdefault(page.verse, []).append(page)
    return grouped


def _column_status(
    book_exists: bool,
    chapter_exists: bool,
    pages: tuple[Page, ...],
) -> ColumnStatus:
    if not book_exists:
        return ColumnStatus.MISSING_BOOK
    if not chapter_exists:
        return ColumnStatus.MISSING_CHAPTER
    if not pages:
        return ColumnStatus.EMPTY
    if any(not _is_empty(page) for page in pages):
        return ColumnStatus.PRESENT
    return ColumnStatus.EMPTY


def _cell_status(
    column_status: ColumnStatus,
    pages: tuple[Page, ...],
    *,
    chapter_has_rows: bool,
) -> CellStatus:
    if column_status is ColumnStatus.MISSING_BOOK:
        return CellStatus.MISSING_BOOK
    if column_status is ColumnStatus.MISSING_CHAPTER:
        return CellStatus.MISSING_CHAPTER
    if not pages:
        # A chapter with no rows at all is EMPTY for every verse. A chapter
        # that has rows (even if all their content is empty) still has a
        # MISSING_VERSE for a verse number without a row.
        if not chapter_has_rows:
            return CellStatus.EMPTY
        return CellStatus.MISSING_VERSE
    if any(not _is_empty(page) for page in pages):
        return CellStatus.PRESENT
    return CellStatus.EMPTY


def _is_empty(page: Page) -> bool:
    """Whether the source text is empty or whitespace.

    Markup is intentionally not interpreted here. A string such as ``<p></p>``
    is non-empty raw content; the renderer may still decide that it looks
    empty.
    """
    return not (page.raw or "").strip()
