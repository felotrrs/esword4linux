"""Libros bíblicos (IDs e-Sword) y parser de referencias.

e-Sword numera los libros 1..66 (Génesis..Apocalipsis) y 67..73 para los
deuterocanónicos que traen algunas ediciones. La numeración es la del módulo,
no la de la UI: aquí solo se traduce ID → nombre.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# (id, nombre_es, abrev_es, nombre_en, abrev_en)
BOOKS: list[tuple[int, str, tuple[str, ...], str, tuple[str, ...]]] = [
    (1, "Génesis", ("gn", "gen", "génesis", "genesis"), "Genesis", ("gen", "ge")),
    (2, "Éxodo", ("ex", "éxodo", "exodo"), "Exodus", ("exod", "exo")),
    (3, "Levítico", ("lv", "lev", "levítico", "levitico"), "Leviticus", ("lev", "lv")),
    (4, "Números", ("nm", "num", "números", "numeros"), "Numbers", ("num", "nu")),
    (5, "Deuteronomio", ("dt", "deut", "deuteronomio"), "Deuteronomy", ("deut", "dt")),
    (6, "Josué", ("jos", "josué", "josue"), "Joshua", ("josh", "jos")),
    (7, "Jueces", ("jue", "jueces", "jdg"), "Judges", ("judg", "jdg")),
    (8, "Rut", ("rt", "rut", "ruth"), "Ruth", ("ruth", "ru")),
    (9, "1 Samuel", ("1s", "1sa", "1sam", "1 samuel"), "1 Samuel", ("1sam", "1sa")),
    (10, "2 Samuel", ("2s", "2sa", "2sam", "2 samuel"), "2 Samuel", ("2sam", "2sa")),
    (11, "1 Reyes", ("1r", "1re", "1reyes", "1 reyes"), "1 Kings", ("1kgs", "1ki")),
    (12, "2 Reyes", ("2r", "2re", "2reyes", "2 reyes"), "2 Kings", ("2kgs", "2ki")),
    (13, "1 Crónicas", ("1cr", "1cro", "1crónicas", "1cronicas"), "1 Chronicles", ("1chr", "1ch")),
    (14, "2 Crónicas", ("2cr", "2cro", "2crónicas", "2cronicas"), "2 Chronicles", ("2chr", "2ch")),
    (15, "Esdras", ("esd", "ezra"), "Ezra", ("ezra", "ezr")),
    (16, "Nehemías", ("neh", "nehemías", "nehemias"), "Nehemiah", ("neh", "ne")),
    (17, "Ester", ("est", "ester", "esth"), "Esther", ("esth", "est")),
    (18, "Job", ("job",), "Job", ("job", "jb")),
    (19, "Salmos", ("sal", "salmo", "ps", "psa", "salmos"), "Psalms", ("ps", "psa", "psalm")),
    (20, "Proverbios", ("pr", "prov", "proverbios"), "Proverbs", ("prov", "pr")),
    (21, "Eclesiastés", ("ec", "ecl", "eclesiastés", "eclesiastes", "eccl"), "Ecclesiastes", ("eccl", "ecc")),
    (22, "Cantares", ("cnt", "cant", "cantares", "song"), "Song of Solomon", ("song", "sos")),
    (23, "Isaías", ("is", "isa", "isaías", "isaias"), "Isaiah", ("isa", "is")),
    (24, "Jeremías", ("jer", "jeremías", "jeremias"), "Jeremiah", ("jer", "je")),
    (25, "Lamentaciones", ("lm", "lam", "lamentaciones"), "Lamentations", ("lam", "la")),
    (26, "Ezequiel", ("ez", "eze", "ezequiel"), "Ezekiel", ("ezek", "eze")),
    (27, "Daniel", ("dn", "dan", "daniel"), "Daniel", ("dan", "da")),
    (28, "Oseas", ("os", "ose", "oseas"), "Hosea", ("hos", "ho")),
    (29, "Joel", ("jl", "joel"), "Joel", ("joel", "joe")),
    (30, "Amós", ("am", "amos", "amós"), "Amos", ("amos", "am")),
    (31, "Obadías", ("ob", "oba", "obadías", "obadias"), "Obadiah", ("obad", "ob")),
    (32, "Jonás", ("jon", "jonás", "jonas"), "Jonah", ("jonah", "jon")),
    (33, "Miqueas", ("mi", "miq", "miqueas"), "Micah", ("mic", "mi")),
    (34, "Nahúm", ("nah", "nahúm", "nahum", "na"), "Nahum", ("nah", "na")),
    (35, "Habacuc", ("hab", "habacuc", "hb"), "Habakkuk", ("hab", "hb")),
    (36, "Sofonías", ("sof", "sofonías", "sofonias", "zep"), "Zephaniah", ("zeph", "zep")),
    (37, "Hageo", ("hag", "hageo"), "Haggai", ("hag", "hg")),
    (38, "Zacarías", ("zac", "zacarías", "zacarias", "zec"), "Zechariah", ("zech", "zec")),
    (39, "Malaquías", ("mal", "malaquías", "malaquias"), "Malachi", ("mal", "ml")),
    (40, "Mateo", ("mt", "mat", "mateo"), "Matthew", ("matt", "mt")),
    (41, "Marcos", ("mr", "mar", "marcos", "mc"), "Mark", ("mark", "mk")),
    (42, "Lucas", ("lc", "luc", "lucas"), "Luke", ("luke", "lk")),
    (43, "Juan", ("jn", "juan", "john"), "John", ("john", "jn")),
    (44, "Hechos", ("hch", "hech", "hechos", "acts"), "Acts", ("acts", "ac")),
    (45, "Romanos", ("ro", "rom", "romanos"), "Romans", ("rom", "ro")),
    (46, "1 Corintios", ("1co", "1cor", "1 corintios"), "1 Corinthians", ("1cor", "1co")),
    (47, "2 Corintios", ("2co", "2cor", "2 corintios"), "2 Corinthians", ("2cor", "2co")),
    (48, "Gálatas", ("ga", "gal", "gálatas", "galatas"), "Galatians", ("gal", "ga")),
    (49, "Efesios", ("ef", "efe", "efesios"), "Ephesians", ("eph", "ep")),
    (50, "Filipenses", ("fil", "flp", "filipenses"), "Philippians", ("phil", "php")),
    (51, "Colosenses", ("col", "colosenses"), "Colossians", ("col", "co")),
    (52, "1 Tesalonicenses", ("1ts", "1tes", "1 tesalonicenses"), "1 Thessalonians", ("1thess", "1th")),
    (53, "2 Tesalonicenses", ("2ts", "2tes", "2 tesalonicenses"), "2 Thessalonians", ("2thess", "2th")),
    (54, "1 Timoteo", ("1ti", "1tim", "1 timoteo"), "1 Timothy", ("1tim", "1ti")),
    (55, "2 Timoteo", ("2ti", "2tim", "2 timoteo"), "2 Timothy", ("2tim", "2ti")),
    (56, "Tito", ("tit", "tito"), "Titus", ("titus", "tit")),
    (57, "Filemón", ("flm", "filemón", "filemon", "phlm"), "Philemon", ("phlm", "phm")),
    (58, "Hebreos", ("he", "heb", "hebreos"), "Hebrews", ("heb", "he")),
    (59, "Santiago", ("stg", "sant", "santiago", "jas"), "James", ("jas", "jm")),
    (60, "1 Pedro", ("1p", "1pe", "1ped", "1 pedro"), "1 Peter", ("1pet", "1pe")),
    (61, "2 Pedro", ("2p", "2pe", "2ped", "2 pedro"), "2 Peter", ("2pet", "2pe")),
    (62, "1 Juan", ("1jn", "1juan", "1 juan"), "1 John", ("1john", "1jn")),
    (63, "2 Juan", ("2jn", "2juan", "2 juan"), "2 John", ("2john", "2jn")),
    (64, "3 Juan", ("3jn", "3juan", "3 juan"), "3 John", ("3john", "3jn")),
    (65, "Judas", ("jud", "judas", "jude"), "Jude", ("jude", "jud")),
    (66, "Apocalipsis", ("ap", "apo", "apoc", "apocalipsis", "rev"), "Revelation", ("rev", "re")),
    # Deuterocanónicos (solo presentes en algunas ediciones)
    (67, "Tobit", ("tob", "tobit", "tb"), "Tobit", ("tob", "tb")),
    (68, "Judit", ("jdt", "judit", "judith"), "Judith", ("jdt",)),
    (69, "Sabiduría", ("sab", "sabiduría", "sabiduria", "wis"), "Wisdom", ("wis", "ws")),
    (70, "Eclesiástico", ("eclo", "sir", "sirácide", "siracide"), "Sirach", ("sir", "ecclus")),
    (71, "Baruc", ("bar", "baruc"), "Baruch", ("bar",)),
    (72, "1 Macabeos", ("1mac", "1m", "1 macabeos"), "1 Maccabees", ("1macc", "1ma")),
    (73, "2 Macabeos", ("2mac", "2m", "2 macabeos"), "2 Maccabees", ("2macc", "2ma")),
]

_BY_ID = {b[0]: b for b in BOOKS}


def normalize(text: str) -> str:
    """minúsculas, sin acentos, sin puntuación de referencia."""
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"[.\s]+", " ", text).strip()


def book_name(book_id: int, lang: str = "es") -> str:
    b = _BY_ID.get(book_id)
    if not b:
        return f"Libro {book_id}"
    return b[1] if lang == "es" else b[3]


def book_abbrev(book_id: int, lang: str = "es") -> str:
    b = _BY_ID.get(book_id)
    if not b:
        return str(book_id)
    return b[2][0] if lang == "es" else b[4][0]


def all_books() -> list[dict]:
    return [
        {"id": b[0], "es": b[1], "en": b[3], "abbrev_es": b[2][0], "abbrev_en": b[4][0]}
        for b in BOOKS
    ]


# Índice alias → id (se construye una vez; cubre nombres y abreviaturas es/en)
_ALIAS: dict[str, int] = {}
for _b in BOOKS:
    _ALIAS.setdefault(normalize(_b[1]), _b[0])
    _ALIAS.setdefault(normalize(_b[3]), _b[0])
    for _a in _b[2] + _b[4]:
        _ALIAS.setdefault(normalize(_a), _b[0])
# Alias frecuentes que no salen del nombre canónico
_ALIAS.update({
    "salmo": 19, "salmos": 19, "psalm": 19, "psalms": 19,
    "cantar de los cantares": 22, "cantares": 22, "song of songs": 22,
    "hechos de los apostoles": 44, "apocalipsis de juan": 66,
    # formas inglesas cortas que aparecen en citas de módulos
    "act": 44, "exo": 2, "deut": 5, "josh": 6, "judg": 7, "prov": 20,
    "eccl": 21, "isa": 23, "jer": 24, "lam": 25, "ezek": 26, "dan": 27,
    "hos": 28, "obad": 31, "jonah": 32, "mic": 33, "zech": 38, "mal": 39,
    "matt": 40, "rom": 45, "gal": 48, "eph": 49, "col": 51, "thess": 52,
    "tim": 54, "titus": 56, "phlm": 57, "jas": 59, "pet": 60, "rev": 66,
    "1a corintios": 46, "2a corintios": 47, "1a de corintios": 46,
    "1a pedro": 60, "2a pedro": 61, "1a juan": 62, "2a juan": 63, "3a juan": 64,
    "1a tesalonicenses": 52, "2a tesalonicenses": 53,
    "1a timoteo": 54, "2a timoteo": 55,
})


@dataclass(frozen=True)
class Reference:
    book: int
    chapter: int
    verse: int | None = None
    verse_end: int | None = None

    def label(self, lang: str = "es") -> str:
        name = book_name(self.book, lang)
        if self.verse is None:
            return f"{name} {self.chapter}"
        if self.verse_end and self.verse_end != self.verse:
            return f"{name} {self.chapter}:{self.verse}-{self.verse_end}"
        return f"{name} {self.chapter}:{self.verse}"


_REF_RE = re.compile(
    r"^\s*(?P<book>(?:[1-3]\s*)?[^\d:]+?)\s*"
    r"(?P<chapter>\d{1,3})"
    r"(?:\s*[:.,]\s*(?P<verse>\d{1,3})(?:\s*[-–]\s*(?P<vend>\d{1,3}))?)?"
    r"\s*$",
    re.IGNORECASE,
)


def parse_reference(text: str) -> Reference | None:
    """Parsea 'Juan 3:16', '1 Cor 13:4-7', 'Sal 23', 'Jn 3.16'."""
    if not text:
        return None
    m = _REF_RE.match(text.strip())
    if not m:
        return None
    book_key = normalize(m.group("book")).replace(" ", "")
    book_id = _ALIAS.get(book_key)
    if book_id is None:
        # fallback: quitar espacios también en el alias normalizado
        for alias, bid in _ALIAS.items():
            if alias.replace(" ", "") == book_key:
                book_id = bid
                break
    if book_id is None:
        return None
    chapter = int(m.group("chapter"))
    if chapter < 1 or chapter > 200:
        return None
    verse = int(m.group("verse")) if m.group("verse") else None
    vend = int(m.group("vend")) if m.group("vend") else None
    return Reference(book_id, chapter, verse, vend)


def looks_like_reference(text: str) -> bool:
    return parse_reference(text) is not None
