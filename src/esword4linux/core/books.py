"""Biblical books (e-Sword IDs) and reference parser.

The canonical table lives in ``books.yaml``: IDs 1–73, names in several languages
and aliases from different editorial traditions. This module only loads,
normalizes and resolves; it does not define its own lists (golden rule #5).

Numbering is the module's, not the UI's: here it only maps ID → name.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

_BOOKS_YAML = Path(__file__).with_name("books.yaml")

_PREFIX_WORDS = {
    "primera": 1, "primer": 1, "first": 1, "premier": 1, "premiere": 1,
    "primeira": 1, "primeiro": 1,
    "segunda": 2, "segundo": 2, "second": 2, "deuxieme": 2, "seconde": 2,
    "tercera": 3, "tercer": 3, "third": 3, "troisieme": 3,
    "terceira": 3, "terceiro": 3,
}
_ROMAN = {"i": 1, "ii": 2, "iii": 3}


def normalize(text: str) -> str:
    """lowercase, no accents, no reference punctuation."""
    text = unicodedata.normalize("NFD", str(text).lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"[.\s_]+", " ", text).strip()


def _clean(text: str) -> str:
    """Normalized alias: also strips dots and surplus whitespace."""
    return normalize(text).strip(" .,;:")


def _add_alias(alias: str, book_id: int) -> None:
    key = _clean(alias)
    if not key:
        return
    # With and without spaces: "1 corintios" and "1corintios".
    _ALIAS.setdefault(key, book_id)
    _ALIAS.setdefault(key.replace(" ", ""), book_id)


def _load_yaml() -> dict:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - depends on packaging
        raise RuntimeError(
            "PyYAML is missing: install the dependencies with «pip install -e .»"
        ) from exc
    try:
        with _BOOKS_YAML.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except OSError as exc:
        raise RuntimeError(f"Could not read {_BOOKS_YAML}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("books"), dict):
        raise ValueError(f"{_BOOKS_YAML}: missing the «books» key")
    return data


_NAMES: dict[int, dict[str, str]] = {}
_ABBREV: dict[int, dict[str, tuple[str, ...]]] = {}
_ALIAS: dict[str, int] = {}
_FAMILY_ALIAS: dict[str, str] = {}
_FAMILY_BOOKS: dict[str, dict[int, int]] = {}


@dataclass(frozen=True)
class BookRange:
    """A named, inclusive range of e-Sword book ids (testament or group)."""

    key: str
    names: dict[str, str]
    start: int
    end: int

    def label(self, lang: str = "es") -> str:
        return (self.names.get(lang) or self.names.get("es")
                or self.names.get("en") or self.key)

    def books(self) -> range:
        return range(self.start, self.end + 1)


#: Loaded from ``books.yaml`` (single source of truth for the books).
TESTAMENTS: list[BookRange] = []
BOOK_GROUPS: list[BookRange] = []


def _load_ranges(section, target: list[BookRange]) -> None:
    for key, spec in (section or {}).items():
        if not isinstance(spec, dict):
            continue
        try:
            start = int(spec["start"])
            end = int(spec["end"])
        except (KeyError, TypeError, ValueError):
            continue
        if end < start:
            continue
        names = {
            str(lang): str(value)
            for lang, value in (spec.get("names") or {}).items()
        }
        target.append(BookRange(str(key), names, start, end))


def _load() -> None:
    data = _load_yaml()
    _load_ranges(data.get("testaments"), TESTAMENTS)
    _load_ranges(data.get("groups"), BOOK_GROUPS)

    for family, spec in (data.get("families") or {}).items():
        if not isinstance(spec, dict):
            continue
        books = {
            int(number): int(book_id)
            for number, book_id in (spec.get("books") or {}).items()
        }
        if not books:
            continue
        _FAMILY_BOOKS[str(family)] = books
        default = spec.get("default")
        for alias in spec.get("aliases") or []:
            key = _clean(alias)
            if not key:
                continue
            _FAMILY_ALIAS.setdefault(key, str(family))
            _FAMILY_ALIAS.setdefault(key.replace(" ", ""), str(family))
            # The form without a number resolves to the first book of the
            # series, except in families where it collides with another book
            # (the epistles of John).
            if default is not None:
                _add_alias(alias, int(default))

    for key, entry in data["books"].items():
        if not isinstance(entry, dict) or "id" not in entry:
            continue
        book_id = int(entry["id"])
        names = {
            str(lang): str(value)
            for lang, value in (entry.get("names") or {}).items()
        }
        abbrevs = {
            str(lang): tuple(str(value) for value in values if value)
            for lang, values in (entry.get("abbreviations") or {}).items()
        }
        _NAMES[book_id] = names
        _ABBREV[book_id] = abbrevs

        # The canonical name and the abbreviations are also valid aliases.
        for value in names.values():
            _add_alias(value, book_id)
        for values in abbrevs.values():
            for value in values:
                _add_alias(value, book_id)
        for values in (entry.get("aliases") or {}).values():
            for value in values:
                _add_alias(value, book_id)
        _add_alias(str(key), book_id)


_load()

# (id, name_es, abbreviations_es, name_en, abbreviations_en)
BOOKS: list[tuple[int, str, tuple[str, ...], str, tuple[str, ...]]] = [
    (
        book_id,
        _NAMES[book_id].get("es") or _NAMES[book_id].get("en") or f"Libro {book_id}",
        _ABBREV.get(book_id, {}).get("es", ()),
        _NAMES[book_id].get("en") or _NAMES[book_id].get("es") or f"Book {book_id}",
        _ABBREV.get(book_id, {}).get("en", ()),
    )
    for book_id in sorted(_NAMES)
]


def book_name(book_id: int, lang: str = "es") -> str:
    names = _NAMES.get(book_id)
    fallback = "Book" if lang == "en" else "Libro"
    if not names:
        return f"{fallback} {book_id}"
    return names.get(lang) or names.get("es") or names.get("en") or f"{fallback} {book_id}"


def book_abbrev(book_id: int, lang: str = "es") -> str:
    abbrevs = _ABBREV.get(book_id, {})
    values = abbrevs.get(lang) or abbrevs.get("es") or abbrevs.get("en") or ()
    return values[0] if values else str(book_id)


def all_books() -> list[dict]:
    return [
        {
            "id": b[0], "es": b[1], "en": b[3],
            "abbrev_es": b[2][0] if b[2] else b[1],
            "abbrev_en": b[4][0] if b[4] else b[3],
        }
        for b in BOOKS
    ]


def _split_prefix(text: str) -> tuple[int | None, str]:
    """Splits «1», «1a», «1ra», «I», «Primera de»… from the book name."""
    value = _clean(text)

    # 1 Samuel / 1a Corintios / 1ra Timoteo / 1st John / 2º Reyes
    match = re.match(
        r"^([1-3])\s*(?:ª|º|°|ra|ro|era|er|st|nd|rd|th|a|o)?\.?\s*(.+)$",
        value,
    )
    if match and match.group(2).strip():
        rest = re.sub(r"^(?:de|del)\s+", "", match.group(2).strip())
        return int(match.group(1)), rest

    # I Samuel / II Reyes / III Juan
    match = re.match(r"^(i{1,3})\.?\s+(.+)$", value)
    if match and match.group(1) in _ROMAN:
        return _ROMAN[match.group(1)], match.group(2).strip()

    # Primera de Corintios / Second Peter / Deuxième Épître…
    match = re.match(
        r"^(primera|primer|segunda|segundo|tercera|tercer|first|second|third|"
        r"premier|premiere|deuxieme|seconde|troisieme|primeiro|primeira|"
        r"segundo|segunda|terceiro|terceira)\s+"
        r"(?:de\s+|del\s+|of\s+|the\s+)?(.+)$",
        value,
    )
    if match:
        return _PREFIX_WORDS[match.group(1)], match.group(2).strip()

    return None, value


def resolve_book(text: str) -> int | None:
    """Book alias (in any language/abbreviation) → e-Sword ID."""
    if not text:
        return None
    key = _clean(text)
    book_id = _ALIAS.get(key)
    if book_id is None:
        book_id = _ALIAS.get(key.replace(" ", ""))
    if book_id is not None:
        return book_id

    prefix, rest = _split_prefix(key)
    if prefix is not None:
        rest_key = _clean(rest)
        family = _FAMILY_ALIAS.get(rest_key) or _FAMILY_ALIAS.get(
            rest_key.replace(" ", "")
        )
        if family:
            book_id = _FAMILY_BOOKS.get(family, {}).get(prefix)
            if book_id is not None:
                return book_id

    # Honorifics common in Spanish: «S. Juan», «San Juan», «Santa…».
    match = re.match(r"^(?:san|santa|santo|s)\.?\s+(.+)$", key)
    if match:
        return resolve_book(match.group(1))
    return None


@dataclass(frozen=True)
class Reference:
    book: int
    chapter: int
    verse: int | None = None
    verse_end: int | None = None
    chapter_end: int | None = None

    def label(self, lang: str = "es") -> str:
        name = book_name(self.book, lang)
        if self.verse is None:
            if self.chapter_end and self.chapter_end != self.chapter:
                return f"{name} {self.chapter}-{self.chapter_end}"
            return f"{name} {self.chapter}"
        if self.verse_end and self.verse_end != self.verse:
            return f"{name} {self.chapter}:{self.verse}-{self.verse_end}"
        return f"{name} {self.chapter}:{self.verse}"


_REF_RE = re.compile(
    r"^\s*(?P<book>.*?)\s*"
    r"(?P<chapter>\d{1,3})"
    r"(?:\s*[-–—]\s*(?P<chend>\d{1,3}))?"
    r"(?:\s*(?:[:.,]|\s)\s*(?P<verse>\d{1,3})"
    r"(?:\s*[-–—]\s*(?P<vend>\d{1,3}))?"
    r")?"
    r"\s*(?:ss|ff|s|f|[a-c])?\s*$",
    re.IGNORECASE,
)


def parse_reference(text: str) -> Reference | None:
    """Parse references such as «Juan 3:16», «1 Cor 13:4-7», «Jn 3,16», «Génesis 1-3»…"""
    if not text:
        return None
    match = _REF_RE.match(str(text).strip())
    if not match:
        return None
    book_id = resolve_book(match.group("book"))
    if book_id is None:
        return None
    chapter = int(match.group("chapter"))
    if not 1 <= chapter <= 200:
        return None
    chapter_end = int(match.group("chend")) if match.group("chend") else None
    verse = int(match.group("verse")) if match.group("verse") else None
    verse_end = int(match.group("vend")) if match.group("vend") else None
    if verse is not None:
        chapter_end = None
    return Reference(book_id, chapter, verse, verse_end, chapter_end)


def looks_like_reference(text: str) -> bool:
    return parse_reference(text) is not None
