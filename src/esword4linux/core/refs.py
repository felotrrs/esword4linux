"""Detection of biblical references inside module text.

Port of `admin/src/lib/bible_refs.ts` from the `bible` project, adapted to the
alias registry of `core/books.yaml` (single source: golden rule #5). It is used
for the bubbles of `<ref>` and to link loose citations.

Formats that appear in the sources:

    "Ex. 32.1–6"      "Ex. 7.8ss"       "(He. 5.4; 7.11)"
    "(Ex. 4:14, 27-30)"  "Exo_28:1; Heb_5:4"   "(Ex. 32:4; Ps. 106:19)"
    "Jn 3,16"          "I Samuel 1:1"     "Génesis 1-3"

Continuations (`, 27-30`, `; 7.11`) produce one span per sub-reference,
so that each one has its own bubble.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .books import book_name, resolve_book

# Library entries can be very long: scanning only the beginning left citations
# at the end unlinked. 200 k is the same ceiling used by the Bible project for
# web rendering.
SCAN_CHARS = 200_000
DEFAULT_LIMIT = 200

_LETTERS = (
    "A-Za-zÁÉÍÓÚÜÑáéíóúüñ"
    "ÀÂÃÄÅÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞßàâãäåçèéêëìíîïðñòóôõöøùúûüýþÿ"
)
_NUM_PREFIX = (
    r"(?:[1-3]\s*(?:ª|º|°|ra|ro|era|er|st|nd|rd|th|a|o)?\.?\s*(?:(?:de|del)\s+)?"
    r"|(?-i:I{1,3})\.?\s*"
    r"|(?:primera|primer|segunda|segundo|tercera|tercer|first|second|third|"
    r"premier|premiere|deuxieme|seconde|troisieme|primeiro|primeira|"
    r"segundo|segunda|terceiro|terceira)\s+(?:de\s+|del\s+|of\s+|the\s+)?"
    r"|(?:s\.?|san|santa|santo)\s+)"
)
_BOOK_TOKEN = (
    rf"(?:{_NUM_PREFIX}[{_LETTERS}]{{1,}}\.?"
    rf"|[{_LETTERS}]{{2,}}\.?)"
)

# Book + chapter. The book accepts a numeric/Roman/word prefix and a final
# period ("He.", "1 Cor.", "I Samuel"); the chapter may come after "_".
_SPAN_RE = re.compile(
    rf"(?<![\w])(?P<book>{_BOOK_TOKEN})\s*_?\s*(?P<chapter>\d{{1,3}})",
    re.IGNORECASE,
)
_BOOK_AHEAD_RE = re.compile(rf"^(?:{_BOOK_TOKEN})", re.IGNORECASE)
_VERSE_RE = re.compile(r"(?:\s*[.:,]\s*|\s+)(\d{1,3})")
_RANGE_RE = re.compile(r"\s*[-–—]\s*(\d{1,3})")
_SUFFIX_RE = re.compile(r"\s*(ss|ff|s|f|[a-c])\b", re.IGNORECASE)
_SEP_RE = re.compile(r"\s*([,;])\s*")
_CONT_REF_RE = re.compile(
    r"(\d{1,3})\s*[.:,]\s*(\d{1,3})"
    r"(?:\s*[-–—]\s*(\d{1,3}))?"
    r"(?:\s*(ss|ff|s|f|[a-c]))?",
    re.IGNORECASE,
)
_CONT_VS_RE = re.compile(
    r"(\d{1,3})(?:\s*[-–—]\s*(\d{1,3}))?"
    r"(?:\s*(ss|ff|s|f|[a-c]))?",
    re.IGNORECASE,
)
_CHAPTER_RANGE_RE = re.compile(r"\s*[-–—]\s*(\d{1,3})")
_PREV_WORD_RE = re.compile(rf"([{_LETTERS}]+)\s+$")
_ORPHAN_PREFIX_RE = re.compile(
    r"((?:[1-4]|(?-i:I{1,3})|primera|primer|segunda|segundo|tercera|tercer|"
    r"first|second|third|premier|premiere|deuxieme|seconde|troisieme|"
    r"primeiro|primeira|segundo|segunda|terceiro|terceira)\s*)$",
    re.IGNORECASE,
)


def _extend_book(text: str, start: int, token: str,
                 book_id: int | None) -> tuple[int, int | None, str]:
    """Tries to make the book name include preceding words.

    This way «The Wisdom of Solomon», «Cantar de los Cantares» or
    «Hechos de los Apóstoles» are recognized without building a giant alias
    alternation. Returns (start, id, token) preferring the longest phrase that
    resolves.
    """
    best_start, best_id, best_token = start, book_id, token
    cursor = start
    phrase = token
    for _ in range(6):
        match = _PREV_WORD_RE.search(text[:cursor])
        if not match:
            break
        word_start = match.start(1)
        phrase = text[word_start:cursor] + phrase
        new_id = resolve_book(phrase)
        if new_id is not None:
            best_start, best_id, best_token = word_start, new_id, phrase
        cursor = word_start
    return best_start, best_id, best_token


@dataclass(frozen=True)
class RefSpan:
    start: int
    end: int
    text: str          # original substring (what is shown)
    ref_text: str      # normalized reference (canonical, for lookup)


def _build(book: int, chapter: int, verse: int | None,
           end: int | None, chapter_end: int | None = None) -> str:
    name = book_name(book, "es")
    if verse is None:
        if chapter_end and chapter_end != chapter:
            return f"{name} {chapter}-{chapter_end}"
        return f"{name} {chapter}"
    if end is not None and end != verse:
        return f"{name} {chapter}:{verse}-{end}"
    return f"{name} {chapter}:{verse}"


def find_reference_spans(text: str, limit: int = DEFAULT_LIMIT) -> list[RefSpan]:
    """Returns the detected references, in order and without overlaps."""
    if not text or len(text) < 4:
        return []
    text = text[:SCAN_CHARS]
    spans: list[RefSpan] = []
    pos = 0
    while len(spans) < limit:
        match = _SPAN_RE.search(text, pos)
        if not match:
            break
        raw_book = match.group("book")
        book_id = resolve_book(raw_book)
        start, book_id, book_text = _extend_book(
            text, match.start(), raw_book, book_id
        )
        if book_id is None:
            pos = match.start() + 1
            continue

        # «1 Esdras», «3 Macc»…: books that e-Sword does not include (only 1–73).
        # The final part is not linked as if it were Esdras/Maccabees.
        before = text[max(0, start - 24):start]
        orphan = _ORPHAN_PREFIX_RE.search(before)
        if orphan:
            combined = orphan.group(1) + book_text
            if resolve_book(combined) is None:
                pos = match.end()
                continue

        chapter = int(match.group("chapter"))
        if not 1 <= chapter <= 200:
            pos = match.start() + 1
            continue

        i = match.end()
        verse: int | None = None
        end: int | None = None
        vm = _VERSE_RE.match(text, i)
        if vm:
            verse = int(vm.group(1))
            i = vm.end()
            rm = _RANGE_RE.match(text, i)
            if rm:
                end = int(rm.group(1))
                i = rm.end()
            sm = _SUFFIX_RE.match(text, i)
            if sm:
                i = sm.end()
        else:
            cr = _CHAPTER_RANGE_RE.match(text, i)
            if cr:
                chapter_end = int(cr.group(1))
                i = cr.end()
                spans.append(RefSpan(
                    start, i, text[start:i],
                    _build(book_id, chapter, None, None, chapter_end),
                ))
                pos = i
                continue

        spans.append(RefSpan(
            start, i, text[start:i],
            _build(book_id, chapter, verse, end),
        ))
        if len(spans) >= limit:
            break

        # List continuations: `, 27-30` (same chapter) /
        # `; 7.11` (new chapter). If what follows is another book, it is cut.
        cur_chapter = chapter
        cur = i
        while len(spans) < limit:
            sep = _SEP_RE.match(text, cur)
            if not sep:
                break
            after = sep.end()
            ahead = _BOOK_AHEAD_RE.match(text, after)
            if ahead and resolve_book(ahead.group(0)) is not None:
                break
            cref = _CONT_REF_RE.match(text, after)
            vref = None if cref else _CONT_VS_RE.match(text, after)
            mm = cref or vref
            if not mm:
                break
            if cref:
                new_chapter = int(cref.group(1))
                new_verse = int(cref.group(2))
                new_end = int(cref.group(3)) if cref.group(3) else None
            else:
                new_chapter = cur_chapter
                new_verse = int(vref.group(1))
                new_end = int(vref.group(2)) if vref.group(2) else None
            spans.append(RefSpan(
                after, mm.end(), text[after:mm.end()],
                _build(book_id, new_chapter, new_verse, new_end),
            ))
            cur_chapter = new_chapter
            cur = mm.end()
        pos = max(cur, i)
    return spans


def link_references(html_text: str, max_links: int = DEFAULT_LIMIT) -> str:
    """Wraps loose citations of already sanitized HTML in `<a href="ref:…">`.

    It only acts on plain text (never inside a tag nor inside an
    existing `<a>`).
    """
    if not html_text:
        return html_text
    out: list[str] = []
    depth_a = 0
    for token in re.split(r"(<[^>]{1,400}>)", html_text):
        if token.startswith("<"):
            low = token.lower()
            if low.startswith("<a "):
                depth_a += 1
            elif low.startswith("</a"):
                depth_a = max(0, depth_a - 1)
            out.append(token)
            continue
        if depth_a:
            out.append(token)
            continue
        chunk_out: list[str] = []
        last = 0
        for i, span in enumerate(find_reference_spans(token, limit=max_links)):
            if i >= max_links:
                break
            chunk_out.append(token[last:span.start])
            chunk_out.append(
                f'<a href="ref:{_escape(span.ref_text)}">{span.text}</a>'
            )
            last = span.end
        chunk_out.append(token[last:])
        out.append("".join(chunk_out))
    return "".join(out)


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")
