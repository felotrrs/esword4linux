"""Read Bible chapters for the multi-version comparison view.

This is the small data-access adapter between :class:`AppContext` /
:class:`EswordModule` and the pure alignment core in :mod:`compare`. It owns
the explicit metadata checks (book exists, chapter exists) and the stable
duplicate order; the UI never runs SQLite queries for the comparison table.

No Qt, no HTML and no writes to the modules folder live here.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from .compare import (
    ChapterData,
    CompareColumn,
    CompareTable,
    align_chapters,
)
from .context import AppContext
from .esword.module import Page

__all__ = [
    "CompareBuild",
    "CompareSource",
    "build_compare_table",
]


@dataclass(frozen=True)
class CompareSource:
    """Display metadata for one compared version."""

    column: CompareColumn
    hint: str = ""
    codepages: Mapping[int, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CompareBuild:
    """Result of reading and aligning one chapter across versions."""

    table: CompareTable | None
    sources: dict[str, CompareSource]
    warnings: tuple[str, ...] = ()


def _invalid_page(
    pages: Sequence[Page],
    book: int,
    chapter: int,
) -> str | None:
    """Return the first contract violation, mirroring ``align_chapters``."""
    for page in pages:
        if not isinstance(page.verse, int) or isinstance(page.verse, bool):
            return f"verse {page.verse!r} is not an integer"
        if page.book is not None and page.book != book:
            return f"page belongs to book {page.book}, expected {book}"
        if page.chapter is not None and page.chapter != chapter:
            return f"page belongs to chapter {page.chapter}, expected {chapter}"
    return None


def build_compare_table(
    ctx: AppContext,
    rel_paths: Sequence[str],
    book: int,
    chapter: int,
) -> CompareBuild:
    """Read ``rel_paths`` and align them by verse.

    ``book_exists`` comes from :meth:`EswordModule.books`. ``chapter_exists``
    is explicit: a chapter is considered present when it has rows or when its
    number is within the book's ``chapter_count`` range. A chapter inside that
    range with no rows is therefore an existing empty chapter; a chapter above
    the range is missing. This is the only chapter metadata the e-Sword
    ``Bible`` schema exposes.

    A module that cannot be read is represented as a missing-book or
    missing-chapter column and adds a warning. The caller still receives a
    table for the remaining versions, so one bad module never blanks the UI.
    """
    chapters: list[ChapterData] = []
    sources: dict[str, CompareSource] = {}
    warnings: list[str] = []

    for rel_path in rel_paths:
        row = ctx.catalog.by_rel_path(rel_path)
        if row is None or row.get("kind") != "bible":
            warnings.append(f"{rel_path}: not an installed Bible")
            continue

        mod = ctx.module(row)
        if mod is None:
            warnings.append(f"{rel_path}: module could not be opened")
            continue

        if getattr(mod, "structure", "") != "bible":
            warnings.append(f"{rel_path}: unexpected module structure")
            continue

        column = CompareColumn(
            key=rel_path,
            title=row.get("title") or "",
            abbreviation=row.get("abbreviation") or "",
        )
        sources[rel_path] = CompareSource(
            column=column,
            hint=getattr(mod, "stem", ""),
            codepages=dict(getattr(mod, "codepages", {}) or {}),
        )

        try:
            book_exists = book in mod.books()
        except Exception as exc:
            warnings.append(f"{rel_path}: could not read book list: {exc}")
            book_exists = False

        if not book_exists:
            chapters.append(ChapterData(
                column=column,
                book=book,
                chapter=chapter,
                pages=(),
                book_exists=False,
                chapter_exists=False,
            ))
            continue

        pages: tuple[Page, ...] = ()
        try:
            pages = tuple(mod.bible_chapter_stable(book, chapter))
        except Exception as exc:
            warnings.append(f"{rel_path}: could not read chapter: {exc}")

        invalid = _invalid_page(pages, book, chapter)
        if invalid:
            label = row.get("abbreviation") or row.get("title") or rel_path
            warnings.append(
                f"{label} ({rel_path}): invalid chapter data ({invalid}); "
                "column omitted"
            )
            sources.pop(rel_path, None)
            continue

        if pages:
            chapter_exists = True
        else:
            try:
                max_chapter = mod.chapter_count(book)
            except Exception as exc:
                warnings.append(f"{rel_path}: could not read chapter count: {exc}")
                max_chapter = 0
            chapter_exists = 1 <= chapter <= int(max_chapter or 0)

        chapters.append(ChapterData(
            column=column,
            book=book,
            chapter=chapter,
            pages=pages,
            book_exists=True,
            chapter_exists=chapter_exists,
        ))

    if not chapters:
        return CompareBuild(table=None, sources=sources, warnings=tuple(warnings))

    try:
        table = align_chapters(book, chapter, chapters)
    except Exception as exc:
        warnings.append(f"could not align chapter: {exc}")
        table = None

    return CompareBuild(
        table=table,
        sources=sources,
        warnings=tuple(warnings),
    )
