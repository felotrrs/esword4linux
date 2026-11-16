"""Chains of biblical citations: ``Gn23:1-6, 2:5-7, 3:4-5; Mar 2:1, Jn3:16``.

Port adapted from ``_parse_referencias_compuestas`` in the Bible project. Returns
canonical references so that the Bible view can retrieve the collection of
passages from the active version.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .books import Reference, parse_reference, resolve_book

_SEP_RE = re.compile(r"[;,]")


@dataclass
class ChainResult:
    refs: list[Reference] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def _split_parts(text: str) -> list[str]:
    """Splits on ``;``/``,`` respecting parentheses."""
    parts: list[str] = []
    cur: list[str] = []
    depth = 0
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch in ";," and depth == 0:
            part = "".join(cur).strip()
            if part:
                parts.append(part)
            cur = []
            continue
        cur.append(ch)
    part = "".join(cur).strip()
    if part:
        parts.append(part)
    return parts


def _book_from_head(head: str) -> int | None:
    head = (head or "").strip()
    if not head:
        return None
    book = resolve_book(head)
    if book is not None:
        return book
    match = re.match(r"^(.*?)\s+\d{1,3}(?:\s*[-–]\s*\d{1,3})?$", head)
    if match:
        return resolve_book(match.group(1))
    return None


def _chapter_spec(part: str, book: int, chapter: int,
                  last_had_verse: bool, paren_mode: bool) -> Reference | None:
    """Spec without a book: ``c:v-v``, ``v-v`` or ``c``."""
    part = part.strip()
    match = re.fullmatch(
        r"(\d{1,3})\s*[:.]\s*(\d{1,3})(?:\s*[-–]\s*(\d{1,3}))?", part
    )
    if match:
        ch = int(match.group(1))
        verse = int(match.group(2))
        end = int(match.group(3)) if match.group(3) else None
        if end is not None and end < verse:
            # «Mateo 3:5-4»: from 3:5 to the end of chapter 4.
            return Reference(book, ch, verse, None, end)
        return Reference(book, ch, verse, end)

    match = re.fullmatch(r"(\d{1,3})(?:\s*[-–]\s*(\d{1,3}))?", part)
    if not match:
        return None
    first = int(match.group(1))
    end = int(match.group(2)) if match.group(2) else None
    if last_had_verse and not paren_mode:
        # Continuation of a verse list: «Sal 23:1,3,5».
        return Reference(book, chapter, first, end)
    # New chapter (or chapter range) after a chapter group.
    return Reference(book, first, None, None, end)


def parse_reference_chain(text: str) -> ChainResult:
    """Parses a citation chain and returns references + ignored segments."""
    result = ChainResult()
    if not text or not text.strip():
        return result

    current_book: int | None = None
    current_chapter = 1
    last_had_verse = False
    paren_mode = False

    for part in _split_parts(text):
        raw = part.strip()
        if not raw:
            continue

        if "(" in raw and ")" in raw:
            head, inner = raw.split("(", 1)
            inner = inner.rsplit(")", 1)[0]
            head_book = _book_from_head(head)
            if head_book is not None:
                current_book = head_book
            if current_book is None:
                result.skipped.append(raw)
                continue
            paren_chapter: int | None = None
            for spec in _split_parts(inner):
                match = re.fullmatch(
                    r"(\d{1,3})\s*[:.]\s*(\d{1,3})(?:\s*[-–]\s*(\d{1,3}))?",
                    spec.strip(),
                )
                if match:
                    paren_chapter = int(match.group(1))
                    verse = int(match.group(2))
                    end = int(match.group(3)) if match.group(3) else None
                    result.refs.append(
                        Reference(current_book, paren_chapter, verse, end)
                    )
                    continue
                match = re.fullmatch(
                    r"(\d{1,3})(?:\s*[-–]\s*(\d{1,3}))?", spec.strip()
                )
                if not match:
                    result.skipped.append(spec)
                    continue
                first = int(match.group(1))
                end = int(match.group(2)) if match.group(2) else None
                if paren_chapter is not None:
                    result.refs.append(
                        Reference(current_book, paren_chapter, first, end)
                    )
                else:
                    result.refs.append(Reference(current_book, first, None, None, end))
            paren_mode = True
            continue

        ref = parse_reference(raw)
        if ref is not None:
            if ref.verse is not None and ref.verse_end is not None \
                    and ref.verse_end < ref.verse:
                ref = Reference(ref.book, ref.chapter, ref.verse, None, ref.verse_end)
            result.refs.append(ref)
            current_book = ref.book
            current_chapter = ref.chapter
            last_had_verse = ref.verse is not None
            paren_mode = False
            continue

        if current_book is None:
            result.skipped.append(raw)
            continue

        spec = _chapter_spec(raw, current_book, current_chapter,
                             last_had_verse, paren_mode)
        if spec is None:
            result.skipped.append(raw)
            continue
        result.refs.append(spec)
        current_chapter = spec.chapter
        last_had_verse = spec.verse is not None
        paren_mode = False

    return result
