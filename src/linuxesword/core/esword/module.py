"""Lector de módulos e-Sword (SQLite, readonly).

Diseño: el tipo de módulo se decide por la ESTRUCTURA (tablas presentes), no
por la extensión. En este corpus hay `.refx` que son Tópicos y `.cmtx` que
usan el esquema antiguo de comentarios, así que la extensión miente.

El módulo nunca se modifica: se abre con `mode=ro`.
"""

from __future__ import annotations

import sqlite3
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from ..legacy_scripts import codepages_from_samples
from .font_codepages import font_codepages_for
from .sqliteplus import DEFAULT_SQLITEPLUS_KEY, SQLitePlusError, decrypt_payload

# kind → (tabla principal, columna de contenido)
CONTENT_COLUMNS: dict[str, str] = {
    "Bible": "Scripture",
    "Verses": "Comments",
    "Books": "Comments",
    "Chapters": "Comments",
    "VerseCommentary": "Comments",
    "ChapterCommentary": "Comments",
    "BookCommentary": "Comments",
    "Dictionary": "Definition",
    "Lexicon": "Definition",
    "Devotions": "Devotion",
    "Devotional": "Devotion",
    "Topics": "Notes",
    "Reference": "Content",
    "Parts": "Reference",
    "Graphics": "Details",
    "content": "data",
}

ESWORD_EXTS = {
    ".bblx", ".bbli", ".cmtx", ".cmti", ".dctx", ".dcti", ".devx", ".topx",
    ".topi", ".refx", ".refi", ".harx", ".mapx", ".twm", ".lexi", ".lexx",
    ".lanx", ".en", ".es", ".fr", ".pt",
}


@dataclass
class Page:
    """Una entrada lógica del módulo (versículo, artículo, tema, mapa...)."""

    ref: str
    title: str
    raw: str = ""
    book: int | None = None
    chapter: int | None = None
    verse: int | None = None
    order: int = 0


def _uri(path: Path) -> str:
    quoted = urllib.parse.quote(str(path.resolve()), safe="/")
    return f"file:{quoted}?mode=ro"


class ModuleError(Exception):
    pass


class EswordModule:
    """Un módulo e-Sword abierto."""

    def __init__(self, path: str | Path, crypt_key: str | bytes | None = None):
        self.path = Path(path)
        self.crypt_key = crypt_key or DEFAULT_SQLITEPLUS_KEY
        self.warnings: list[str] = []
        self._details: dict | None = None
        self._codepages: dict[int, str] | None = None
        self._graphics_index: dict[str, int] | None = None
        if not self.path.is_file():
            raise ModuleError(f"no existe: {self.path}")
        try:
            self.conn = sqlite3.connect(_uri(self.path), uri=True, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self.tables = {
                r[0] for r in self.conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
        except sqlite3.Error as exc:
            raise ModuleError(f"no se pudo abrir {self.path.name}: {exc}") from exc
        self.structure = self._detect_structure()
        self.kind = self._detect_kind()

    # ── ciclo de vida ────────────────────────────────────────────────────
    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # ── introspección ────────────────────────────────────────────────────
    def _detect_structure(self) -> str:
        t = self.tables
        if "Bible" in t:
            return "bible"
        if "Verses" in t or "VerseCommentary" in t or "BookCommentary" in t \
                or "ChapterCommentary" in t:
            return "commentary"
        if "Dictionary" in t:
            return "dictionary"
        if "Lexicon" in t:
            return "lexicon"
        if "Devotions" in t or "Devotional" in t:
            return "devotion"
        if "Sections" in t and "Parts" in t:
            return "harmony"
        if "Graphics" in t:
            return "maps"
        if "Reference" in t:
            return "reference"
        if "Topics" in t:
            return "topic"
        if "topics" in t:
            return "twm"
        return "unknown"

    def _detect_kind(self) -> str:
        """Determina la categoría lógica del módulo analizando estructura y contenido."""
        if self.structure == "reference":
            return self._classify_reference()
        if self.structure == "twm":
            return self._classify_twm()
        if self.structure == "topic":
            return self._classify_topic()
        return KIND_BY_STRUCTURE.get(self.structure, "unknown")

    def _classify_reference(self) -> str:
        """Distingue entre referencias cruzadas bíblicas y libros/tratados."""
        try:
            import re
            rows = self.conn.execute("SELECT Chapter FROM Reference LIMIT 40").fetchall()
            if not rows:
                return "reference"
            verse_like = 0
            for r in rows:
                val = str(r[0] or "").strip()
                if re.match(r"^\d+:\d+(?::\d+)?$", val):
                    verse_like += 1
            if verse_like / len(rows) >= 0.4:
                return "reference"
            return "book"
        except Exception:
            return "reference"

    def _classify_twm(self) -> str:
        """Clasifica un módulo TWM según su contenido (diccionario, libro o tópico)."""
        try:
            import re
            rows = self.conn.execute(
                "SELECT name, value FROM config WHERE name IN ('title', 'type', 'description', 'subject')"
            ).fetchall()
            cfg = {str(r[0]).lower(): str(r[1] or "").lower() for r in rows}
            text = " ".join(cfg.values()) + " " + self.path.stem.lower()

            dict_keywords = (
                "diccionario", "dictionary", "lexicon", "lexico", "vocabulario",
                "glosario", "hitchcock", "strong", "concordancia", "definicion"
            )
            if any(k in text for k in dict_keywords) or cfg.get("type") in ("dict", "dictionary"):
                return "dictionary"

            book_keywords = ("libro", "book", "tratado", "manual", "historia", "comentario", "commentary")
            if any(k in text for k in book_keywords) or cfg.get("type") in ("book", "commentary"):
                return "book"

            cur = self.conn.execute("SELECT subject FROM topics LIMIT 35")
            subjects = [str(r[0] or "").strip() for r in cur.fetchall()]
            if subjects:
                avg_len = sum(len(s) for s in subjects) / len(subjects)
                if avg_len <= 16:
                    return "dictionary"
                if any(re.match(r"^(?:cap[íi]tulo|cap\.?|secci[óo]n)\s+\d+", s, re.I) for s in subjects):
                    return "book"
            return "topic"
        except Exception:
            return "topic"

    def _classify_topic(self) -> str:
        try:
            det = self.details()
            title = (det.get("Title") or det.get("Description") or self.path.stem).lower()
            if any(k in title for k in ("libro de ", "tratado de ", "manual de ", "biografía de ", "historia de ")):
                return "book"
            return "topic"
        except Exception:
            return "topic"

    @property
    def encrypted(self) -> bool:
        return "sqliteplus_license" in self.tables

    def details(self) -> dict:
        if self._details is not None:
            return self._details
        out: dict = {}
        if "Details" in self.tables:
            try:
                row = self.conn.execute("SELECT * FROM Details LIMIT 1").fetchone()
            except sqlite3.Error:
                row = None
            if row is not None:
                out = {k: row[k] for k in row.keys()}
        if "config" in self.tables:
            try:
                rows = self.conn.execute(
                    "SELECT name, value FROM config WHERE name IN ('title','abbreviation','description')"
                ).fetchall()
                for name, value in rows:
                    out.setdefault(name, value)
            except sqlite3.Error:
                pass
        self._details = out
        return out

    @property
    def codepages(self) -> dict[int, str]:
        """Codepages legacy del módulo: registro vendorizado o detección."""
        if self._codepages is not None:
            return self._codepages
        known = font_codepages_for(self.stem)
        self._codepages = known if known else self._detect_codepages()
        return self._codepages

    def _detect_codepages(self) -> dict[int, str]:
        table = {
            "bible": "Bible", "commentary": None, "dictionary": "Dictionary",
            "lexicon": "Lexicon", "devotion": None, "topic": "Topics",
            "reference": "Reference", "maps": "Graphics", "harmony": "Parts",
        }.get(self.structure)
        if self.structure == "commentary":
            specs = self._comment_specs()
            table = specs[0][0] if specs else None
        if not table:
            return {}
        col = CONTENT_COLUMNS.get(table)
        if not col:
            return {}
        samples: list[str] = []
        try:
            rows = self.conn.execute(
                f'SELECT "{col}" FROM "{table}" WHERE "{col}" IS NOT NULL LIMIT 60'
            )
            for (value,) in rows:
                samples.append(self._decode(value, table, "?"))
        except sqlite3.Error:
            return {}
        return codepages_from_samples(samples)

    @property
    def stem(self) -> str:
        """Stem del archivo: hint para codepages/transliteraciones legacy."""
        return self.path.stem

    @property
    def title(self) -> str:
        d = self.details()
        for key in ("Title", "Description", "title", "description"):
            val = d.get(key)
            if val:
                return str(val).strip()
        return self.path.stem

    @property
    def abbreviation(self) -> str:
        d = self.details()
        for key in ("Abbreviation", "abbreviation"):
            val = d.get(key)
            if val:
                return str(val).strip()
        return self.path.stem[:14]

    @property
    def description(self) -> str:
        d = self.details()
        for key in ("Information", "Comments", "description"):
            val = d.get(key)
            if val:
                return str(val)
        return ""

    def count_entries(self) -> int:
        # Un comentario puede tener solo comentarios de libro (ABN-Manley,
        # Pearlman, Willmington): elegir la primera tabla existente devolvía 0
        # y el catálogo ocultaba el módulo. Se suman todas las tablas reales.
        if self.structure == "commentary":
            total = 0
            for table, _level in self._comment_specs():
                try:
                    total += int(self.conn.execute(
                        f'SELECT COUNT(*) FROM "{table}"'
                    ).fetchone()[0])
                except sqlite3.Error:
                    pass
            return total
        # La unidad navegable de una armonía es la sección (un acontecimiento
        # con sus pasajes paralelos), no cada fila de `Parts`.
        if self.structure == "harmony":
            try:
                total = int(self.conn.execute(
                    "SELECT COUNT(DISTINCT Section) FROM Parts"
                ).fetchone()[0])
                if total:
                    return total
                return int(self.conn.execute(
                    "SELECT COUNT(*) FROM Sections"
                ).fetchone()[0])
            except sqlite3.Error:
                return 0
        table = {
            "bible": "Bible",
            "dictionary": "Dictionary",
            "lexicon": "Lexicon",
            "devotion": "Devotions" if "Devotions" in self.tables else "Devotional",
            "topic": "Topics",
            "maps": "Graphics",
            "reference": "Reference",
            "twm": "topics",
        }.get(self.structure)
        if not table or table not in self.tables:
            return 0
        try:
            return int(self.conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
        except sqlite3.Error:
            return 0

    # ── descifrado ───────────────────────────────────────────────────────
    @staticmethod
    def _text_value(value) -> str:
        """Texto de una columna que puede venir como bytes legacy.

        En `.mapx` antiguos el título se guarda como UTF-16LE sin BOM dentro de
        una columna BLOB. `str(bytes)` produce ``b'1\\x000\\x00...'`` y rompe
        tanto la lista como la búsqueda posterior por título.
        """
        if value is None:
            return ""
        if isinstance(value, (bytes, bytearray)):
            from ..text import decode_raw
            return decode_raw(bytes(value))
        return str(value)

    def _decode(self, value, table: str, ident) -> str:
        if value is None:
            return ""
        if isinstance(value, (bytes, bytearray)):
            try:
                return decrypt_payload(bytes(value), self.crypt_key).decode(
                    "utf-8", "replace"
                )
            except SQLitePlusError:
                # Algunos `.mapx` guardan la leyenda cifrada pero SIN comprimir
                # (texto RTF UTF-16LE). El descifrador SQLitePlus estándar
                # intenta descomprimir zlib y falla; se decodifica aparte.
                if table == "Graphics":
                    text = self._decode_uncompressed_sqliteplus(bytes(value))
                    if text is not None:
                        return text
                # No es un blob SQLitePlus cifrado: decodificar como texto
                # plano (puede ser UTF-16LE, UTF-8 o latin-1).
                from ..text import decode_raw
                return decode_raw(value)
        return str(value)

    def _decode_uncompressed_sqliteplus(self, blob: bytes) -> str | None:
        """Descifra un blob SQLitePlus sin zlib (texto plano UTF-16LE/UTF-8).

        Formato observado en `map_larkin_es.mapx`: cabecera de 5 bytes
        (checksum, tamaño u24, magia ``0x1F``) seguida del texto RTF sin
        comprimir, rellenado a bloques de 16 bytes. Devuelve ``None`` si el
        blob no sigue este formato.
        """
        if not blob:
            return None
        from ..text import decode_raw
        from .sqliteplus import _derive_key
        from .twofish import Twofish128

        try:
            tf = Twofish128(_derive_key(self.crypt_key))
            plain = bytearray()
            for offset in range(0, len(blob), 16):
                plain += tf.decrypt_block(
                    blob[offset:offset + 16].ljust(16, b"\x00")
                )
            if len(plain) < 5 or plain[4] != 0x1F:
                return None
            size = plain[1] | (plain[2] << 8) | (plain[3] << 16)
            if size <= 0 or size > len(plain) - 5:
                return None
            payload = bytes(plain[5:5 + size])
            if len(payload) % 2:
                payload = payload[:-1]  # UTF-16LE truncado: descartar resto
            return decode_raw(payload)
        except Exception:
            return None

    @staticmethod
    def _clean_title(value) -> str:
        """Título de una entrada sin RTF/HTML y en una sola línea."""
        from ..text import to_plain

        return " ".join(to_plain(value).split())

    def _rows(self, sql: str, params: tuple = ()) -> Iterator[sqlite3.Row]:
        try:
            yield from self.conn.execute(sql, params)
        except sqlite3.Error as exc:
            raise ModuleError(f"{self.path.name}: {exc}") from exc

    # ── páginas (unidad indexable) ───────────────────────────────────────
    def iter_pages(self) -> Iterator[Page]:
        handler = getattr(self, f"_pages_{self.structure}", None)
        if handler is None:
            return
        yield from handler()

    def _pages_bible(self) -> Iterator[Page]:
        from ..books import book_name

        for row in self._rows(
            "SELECT Book, Chapter, Verse, Scripture FROM Bible "
            "ORDER BY Book, Chapter, Verse"
        ):
            b, c, v = row["Book"], row["Chapter"], row["Verse"]
            yield Page(
                ref=f"{b}:{c}:{v}",
                title=f"{book_name(b)} {c}:{v}",
                raw=self._decode(row["Scripture"], "Bible", f"{b}:{c}:{v}"),
                book=b, chapter=c, verse=v, order=b * 1_000_000 + c * 1_000 + v,
            )

    def _columns(self, table: str) -> set[str]:
        try:
            return {r[1] for r in self.conn.execute(f'PRAGMA table_info("{table}")')}
        except sqlite3.Error:
            return set()

    def _comment_specs(self) -> list[tuple[str, str]]:
        """Tablas de comentario y su nivel: verse | range | chapter | book.

        Los nombres de tabla no bastan: e-Sword usa `VerseCommentary` en el
        esquema antiguo y `Verses` en el moderno, pero `Verses` puede ser
        (Book, Chapter, Verse) o (Book, ChapterBegin, ChapterEnd, VerseBegin,
        VerseEnd). Se decide por columnas.
        """
        specs: list[tuple[str, str]] = []
        for table in ("Verses", "VerseCommentary"):
            if table in self.tables:
                cols = self._columns(table)
                if {"Book", "Chapter", "Verse", "Comments"} <= cols:
                    specs.append((table, "verse"))
                elif {"Book", "ChapterBegin", "VerseBegin", "Comments"} <= cols:
                    specs.append((table, "range"))
        for table in ("Chapters", "ChapterCommentary"):
            if table in self.tables and {"Book", "Chapter", "Comments"} <= self._columns(table):
                specs.append((table, "chapter"))
        for table in ("Books", "BookCommentary"):
            if table in self.tables and {"Book", "Comments"} <= self._columns(table):
                specs.append((table, "book"))
        return specs

    def _pages_commentary(self) -> Iterator[Page]:
        from ..books import book_name

        for table, level in self._comment_specs():
            if level == "verse":
                for row in self._rows(
                    f'SELECT Book, Chapter, Verse, Comments FROM "{table}" '
                    "ORDER BY Book, Chapter, Verse"
                ):
                    b, c, v = row["Book"], row["Chapter"], row["Verse"]
                    ref = f"{b}:{c}:{v}"
                    yield Page(
                        ref=ref, title=f"{book_name(b)} {c}:{v}",
                        raw=self._decode(row["Comments"], table, ref),
                        book=b, chapter=c, verse=v,
                        order=b * 1_000_000 + c * 1_000 + v,
                    )
            elif level == "range":
                for row in self._rows(
                    f'SELECT Book, ChapterBegin, ChapterEnd, VerseBegin, VerseEnd, Comments '
                    f'FROM "{table}" ORDER BY Book, ChapterBegin, VerseBegin'
                ):
                    b = row["Book"]
                    cb = row["ChapterBegin"]
                    vb = row["VerseBegin"] or 0
                    ce = row["ChapterEnd"] or cb
                    ve = row["VerseEnd"]
                    if ce == cb and ve and ve != vb:
                        label = f"{book_name(b)} {cb}:{vb}-{ve}"
                        ref = f"{b}:{cb}:{vb}-{ve}"
                    else:
                        label = f"{book_name(b)} {cb}:{vb}"
                        ref = f"{b}:{cb}:{vb}"
                    yield Page(
                        ref=ref, title=label,
                        raw=self._decode(row["Comments"], table, ref),
                        book=b, chapter=cb, verse=vb,
                        order=b * 1_000_000 + cb * 1_000 + vb,
                    )
            elif level == "chapter":
                for row in self._rows(
                    f'SELECT Book, Chapter, Comments FROM "{table}" ORDER BY Book, Chapter'
                ):
                    b, c = row["Book"], row["Chapter"]
                    ref = f"{b}:{c}"
                    yield Page(
                        ref=ref, title=f"{book_name(b)} {c}",
                        raw=self._decode(row["Comments"], table, ref),
                        book=b, chapter=c, verse=None,
                        order=b * 1_000_000 + c * 1_000,
                    )
            elif level == "book":
                for row in self._rows(
                    f'SELECT Book, Comments FROM "{table}" ORDER BY Book'
                ):
                    b = row["Book"]
                    yield Page(
                        ref=str(b), title=book_name(b),
                        raw=self._decode(row["Comments"], table, b),
                        book=b, order=b * 1_000_000,
                    )

    def _pages_dictionary(self) -> Iterator[Page]:
        yield from self._pages_topic_table("Dictionary", "Definition")

    def _pages_lexicon(self) -> Iterator[Page]:
        yield from self._pages_topic_table("Lexicon", "Definition")

    def _pages_topic_table(self, table: str, column: str) -> Iterator[Page]:
        for i, row in enumerate(self._rows(
            f'SELECT Topic, "{column}" FROM "{table}" ORDER BY Topic'
        )):
            topic = row["Topic"] or ""
            yield Page(
                ref=str(topic), title=str(topic),
                raw=self._decode(row[column], table, topic), order=i,
            )

    def _pages_reference(self) -> Iterator[Page]:
        for i, row in enumerate(self._rows(
            "SELECT Chapter, Content FROM Reference ORDER BY rowid"
        )):
            chapter = str(row["Chapter"] or "")
            yield Page(
                ref=chapter, title=chapter,
                raw=self._decode(row["Content"], "Reference", chapter), order=i,
            )

    def _pages_topic(self) -> Iterator[Page]:
        for i, row in enumerate(self._rows(
            "SELECT Title, Notes FROM Topics ORDER BY Title"
        )):
            title = str(row["Title"] or "")
            yield Page(
                ref=title, title=title,
                raw=self._decode(row["Notes"], "Topics", title), order=i,
            )

    def _pages_devotion(self) -> Iterator[Page]:
        table = "Devotions" if "Devotions" in self.tables else "Devotional"
        for row in self._rows(f'SELECT Month, Day, Devotion FROM "{table}" ORDER BY Month, Day'):
            m, d = row["Month"], row["Day"]
            yield Page(
                ref=f"{m:02d}-{d:02d}", title=f"{m:02d}/{d:02d}",
                raw=self._decode(row["Devotion"], table, f"{m}-{d}"),
                order=int(m) * 100 + int(d),
            )

    def _harmony_section_key(self, value) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def _harmony_titles(self) -> dict[str, str]:
        return {
            str(row["ID"]): self._clean_title(row["Title"])
            for row in self._rows("SELECT ID, Title FROM Sections")
        }

    def _harmony_groups(self) -> dict[str, list[str]]:
        """Referencias de `Parts` agrupadas por sección, sin duplicados.

        `Parts` tiene una fila por referencia, así que varias filas comparten
        ``(Section, Part)``. La entrada navegable es la sección completa; de
        otro modo la lista mostraba el mismo registro varias veces y el índice
        FTS5 solo conservaba el último (la clave es ``ref``).
        """
        groups: dict[str, list[str]] = {}
        for row in self._rows(
            "SELECT Section, Part, Reference FROM Parts "
            "ORDER BY CAST(Section AS INTEGER), CAST(Part AS INTEGER), rowid"
        ):
            sec = str(row["Section"])
            ref = self._decode(row["Reference"], "Parts", sec).strip()
            if not ref:
                continue
            bucket = groups.setdefault(sec, [])
            if ref not in bucket:
                bucket.append(ref)
        return groups

    def _pages_harmony(self) -> Iterator[Page]:
        titles = self._harmony_titles()
        groups = self._harmony_groups()
        for sec in sorted(groups, key=self._harmony_section_key):
            yield Page(
                ref=sec,
                title=titles.get(sec) or f"Sección {sec}",
                raw="\n".join(groups[sec]),
                order=self._harmony_section_key(sec),
            )

    def _pages_maps(self) -> Iterator[Page]:
        for i, row in enumerate(self._rows(
            "SELECT Title, Details FROM Graphics ORDER BY rowid"
        )):
            title = self._text_value(row["Title"])
            yield Page(
                ref=title, title=title,
                raw=self._decode(row["Details"], "Graphics", title), order=i,
            )

    def _pages_twm(self) -> Iterator[Page]:
        sql = (
            "SELECT t.id, t.subject, c.data FROM topics t "
            "LEFT JOIN content c ON c.topic_id = t.id ORDER BY t.rel_order, t.id"
        )
        for row in self._rows(sql):
            subject = str(row["subject"] or "")
            yield Page(
                ref=str(row["id"]), title=subject,
                raw=self._decode(row["data"], "content", row["id"]),
                order=int(row["id"]),
            )

    # ── consultas para la UI ─────────────────────────────────────────────
    def bible_chapter(self, book: int, chapter: int) -> list[Page]:
        from ..books import book_name

        pages = []
        for row in self._rows(
            "SELECT Book, Chapter, Verse, Scripture FROM Bible "
            "WHERE Book=? AND Chapter=? ORDER BY Verse",
            (book, chapter),
        ):
            avg = self._decode(row["Scripture"], "Bible", f"{book}:{chapter}:{row['Verse']}")
            pages.append(Page(
                ref=f"{book}:{chapter}:{row['Verse']}",
                title=f"{book_name(book)} {chapter}:{row['Verse']}",
                raw=avg, book=book, chapter=chapter, verse=row["Verse"],
                order=row["Verse"],
            ))
        return pages

    def bible_verse(self, book: int, chapter: int, verse: int) -> Page | None:
        rows = list(self._rows(
            "SELECT Book, Chapter, Verse, Scripture FROM Bible "
            "WHERE Book=? AND Chapter=? AND Verse=?",
            (book, chapter, verse),
        ))
        if not rows:
            return None
        row = rows[0]
        from ..books import book_name
        return Page(
            ref=f"{book}:{chapter}:{verse}",
            title=f"{book_name(book)} {chapter}:{verse}",
            raw=self._decode(row["Scripture"], "Bible", f"{book}:{chapter}:{verse}"),
            book=book, chapter=chapter, verse=verse,
        )

    def list_entries(self, prefix: str = "", limit: int = 5000,
                     contains: bool = False) -> list[tuple[str, str]]:
        """Lista (ref, título) sin descifrar contenido — para el índice A-Z.

        `contains=True` se usa para el cuadro de filtro (coincidencia en
        cualquier posición); por defecto el prefijo alimenta el salto A-Z.
        """
        if self.structure == "maps":
            # El título puede ser BLOB UTF-16LE: LIKE no lo puede comparar
            # contra el texto que teclea el usuario.  Son pocas entradas
            # (decenas), así que se decodifican y ordenan en memoria.
            needle = prefix.casefold()
            titles: list[str] = []
            for row in self._rows("SELECT Title FROM Graphics"):
                title = self._text_value(row["Title"])
                if needle:
                    haystack = title.casefold()
                    if contains:
                        if needle not in haystack:
                            continue
                    elif not haystack.startswith(needle):
                        continue
                titles.append(title)
            titles.sort(key=str.casefold)
            return [(title, title) for title in titles[:limit]]
        table = {
            "dictionary": "Dictionary", "lexicon": "Lexicon", "topic": "Topics",
            "reference": "Reference",
        }.get(self.structure)
        if table:
            col = "Topic" if table in ("Dictionary", "Lexicon") else \
                  ("Chapter" if table == "Reference" else "Title")
            sql = f'SELECT "{col}" AS k FROM "{table}"'
            params: tuple = ()
            if prefix:
                if contains:
                    sql += f' WHERE "{col}" LIKE ? COLLATE NOCASE'
                    params = (f"%{prefix}%",)
                else:
                    sql += f' WHERE "{col}" LIKE ? COLLATE NOCASE'
                    params = (prefix + "%",)
            sql += " ORDER BY k LIMIT ?"
            params += (limit,)
            out: list[tuple[str, str]] = []
            for r in self._rows(sql, params):
                k = r["k"]
                if isinstance(k, (bytes, bytearray)):
                    from ..text import decode_raw
                    k = decode_raw(k)
                out.append((str(k or ""), str(k or "")))
            return out
        if self.structure == "devotion":
            table = "Devotions" if "Devotions" in self.tables else "Devotional"
            return [
                (f"{r['Month']:02d}-{r['Day']:02d}", f"{r['Month']:02d}/{r['Day']:02d}")
                for r in self._rows(f'SELECT Month, Day FROM "{table}" ORDER BY Month, Day')
            ]
        if self.structure == "twm":
            return [
                (str(r["id"]), str(r["subject"] or ""))
                for r in self._rows("SELECT id, subject FROM topics ORDER BY rel_order, id LIMIT ?", (limit,))
            ]
        if self.structure == "harmony":
            titles = self._harmony_titles()
            sections = sorted(
                {str(r["Section"]) for r in self._rows("SELECT Section FROM Parts")},
                key=self._harmony_section_key,
            )
            needle = prefix.casefold()
            out: list[tuple[str, str]] = []
            for sec in sections:
                title = titles.get(sec) or f"Sección {sec}"
                if needle:
                    haystack = f"{title} {sec}".casefold()
                    if contains:
                        if needle not in haystack:
                            continue
                    elif not haystack.startswith(needle):
                        continue
                out.append((sec, title))
            return out[:limit]
        if self.structure == "commentary":
            from ..books import book_name

            out: list[tuple[str, str]] = []
            for table, level in self._comment_specs():
                if level == "verse":
                    out.extend(
                        (f"{r['Book']}:{r['Chapter']}:{r['Verse']}",
                         f"{book_name(r['Book'])} {r['Chapter']}:{r['Verse']}")
                        for r in self._rows(
                            f'SELECT Book, Chapter, Verse FROM "{table}" '
                            "ORDER BY Book, Chapter, Verse LIMIT ?", (limit,)
                        )
                    )
                elif level == "range":
                    out.extend(
                        (f"{r['Book']}:{r['ChapterBegin']}:{r['VerseBegin']}",
                         f"{book_name(r['Book'])} {r['ChapterBegin']}:{r['VerseBegin']}")
                        for r in self._rows(
                            f'SELECT Book, ChapterBegin, VerseBegin FROM "{table}" '
                            "ORDER BY Book, ChapterBegin, VerseBegin LIMIT ?", (limit,)
                        )
                    )
                elif level == "chapter":
                    out.extend(
                        (f"{r['Book']}:{r['Chapter']}",
                         f"{book_name(r['Book'])} {r['Chapter']}")
                        for r in self._rows(
                            f'SELECT Book, Chapter FROM "{table}" '
                            "ORDER BY Book, Chapter LIMIT ?", (limit,)
                        )
                    )
                elif level == "book":
                    out.extend(
                        (str(r["Book"]), book_name(r["Book"]))
                        for r in self._rows(
                            f'SELECT Book FROM "{table}" ORDER BY Book LIMIT ?', (limit,)
                        )
                    )
            return out[:limit]
        return []

    def get_page(self, ref: str) -> Page | None:
        """Recupera una página por referencia (para el visor de detalle)."""
        gen = self.iter_pages()
        for page in gen:
            if page.ref == ref:
                return page
        return None

    def page_by_ref(self, ref: str) -> Page | None:
        """Consulta directa por referencia (sin recorrer el módulo)."""
        from ..books import book_name

        try:
            if self.structure == "bible":
                parts = ref.split(":")
                if len(parts) == 3:
                    return self.bible_verse(int(parts[0]), int(parts[1]), int(parts[2]))
                return None
            if self.structure in ("dictionary", "lexicon"):
                table = "Dictionary" if self.structure == "dictionary" else "Lexicon"
                row = self.conn.execute(
                    f'SELECT Topic, Definition FROM "{table}" WHERE Topic=?', (ref,)
                ).fetchone()
                if not row:
                    return None
                return Page(ref=str(row["Topic"]), title=str(row["Topic"]),
                            raw=self._decode(row["Definition"], table, ref))
            if self.structure == "reference":
                row = self.conn.execute(
                    "SELECT Chapter, Content FROM Reference WHERE Chapter=?", (ref,)
                ).fetchone()
                if not row:
                    return None
                return Page(ref=str(row["Chapter"]), title=str(row["Chapter"]),
                            raw=self._decode(row["Content"], "Reference", ref))
            if self.structure == "topic":
                row = self.conn.execute(
                    "SELECT Title, Notes FROM Topics WHERE Title=?", (ref,)
                ).fetchone()
                if not row:
                    return None
                return Page(ref=str(row["Title"]), title=str(row["Title"]),
                            raw=self._decode(row["Notes"], "Topics", ref))
            if self.structure == "devotion":
                table = "Devotions" if "Devotions" in self.tables else "Devotional"
                m, _, d = ref.partition("-")
                row = self.conn.execute(
                    f'SELECT Month, Day, Devotion FROM "{table}" WHERE Month=? AND Day=?',
                    (int(m), int(d or 0)),
                ).fetchone()
                if not row:
                    return None
                return Page(ref=ref, title=f"{row['Month']:02d}/{row['Day']:02d}",
                            raw=self._decode(row["Devotion"], table, ref))
            if self.structure == "commentary":
                parts = ref.split(":")
                if len(parts) == 1:
                    # Comentarios de libro (ABN-Manley, Pearlman, Willmington):
                    # el ref es solo el número de libro, sin capítulo.
                    try:
                        b = int(parts[0])
                    except ValueError:
                        return None
                    for table, level in self._comment_specs():
                        if level != "book":
                            continue
                        row = self.conn.execute(
                            f'SELECT Comments FROM "{table}" WHERE Book=?', (b,)
                        ).fetchone()
                        if row:
                            return Page(
                                ref=str(b), title=book_name(b),
                                raw=self._decode(row["Comments"], table, b),
                                book=b, order=b * 1_000_000,
                            )
                    return None
                try:
                    b = int(parts[0])
                    c = int(parts[1])
                    v = int(parts[2].split("-")[0]) if len(parts) > 2 else 0
                except ValueError:
                    return None
                comments = self.chapter_comments(b, c)
                if v:
                    for page in comments.get(v, []):
                        return page
                for page in comments.get(0, []):
                    return page
                for key in sorted(comments):
                    if comments[key]:
                        return comments[key][0]
                return None
            if self.structure == "twm":
                row = self.conn.execute(
                    "SELECT t.id, t.subject, c.data FROM topics t "
                    "LEFT JOIN content c ON c.topic_id=t.id WHERE t.id=?", (int(ref),),
                ).fetchone()
                if not row:
                    return None
                return Page(ref=str(row["id"]), title=str(row["subject"] or ""),
                            raw=self._decode(row["data"], "content", ref))
            if self.structure == "maps":
                rowid = self._graphics_rowid(ref)
                if rowid is None:
                    return None
                row = self.conn.execute(
                    "SELECT Title, Details FROM Graphics WHERE rowid=?", (rowid,)
                ).fetchone()
                if not row:
                    return None
                title = self._text_value(row["Title"])
                return Page(ref=title, title=title,
                            raw=self._decode(row["Details"], "Graphics", title))
            if self.structure == "harmony":
                # Compatibilidad: acepta tanto `sección` como el antiguo
                # `sección:parte`; la entrada navegable es la sección completa.
                sec = ref.partition(":")[0].strip()
                if not sec:
                    return None
                row = self.conn.execute(
                    "SELECT ID, Title FROM Sections WHERE ID=?", (sec,)
                ).fetchone()
                groups = self._harmony_groups()
                key = str(row["ID"]) if row is not None else sec
                references = groups.get(key)
                if not references:
                    return None
                title = (
                    self._clean_title(row["Title"]) if row is not None else ""
                ) or f"Sección {key}"
                return Page(
                    ref=key, title=title, raw="\n".join(references),
                    order=self._harmony_section_key(key),
                )
        except (ValueError, sqlite3.Error):
            return None
        return self.get_page(ref)

    def _graphics_rowid(self, ref: str) -> int | None:
        """rowid de una entrada de `Graphics` a partir de su título decodificado."""
        if self._graphics_index is None:
            index: dict[str, int] = {}
            for row in self._rows("SELECT rowid, Title FROM Graphics ORDER BY rowid"):
                title = self._text_value(row["Title"])
                index.setdefault(title, int(row["rowid"]))
            self._graphics_index = index
        return self._graphics_index.get(ref)

    @staticmethod
    def _unwrap_picture(data: bytes) -> bytes:
        """Quita la cabecera propia de algunos `.mapx` (``lt\\0\\0`` + tamaño).

        Algunos módulos guardan la imagen como ``lt`` + 4 bytes + BMP.  Qt no
        reconoce ese envoltorio y la entrada se mostraba como «sin imagen».
        """
        if len(data) > 8 and data.startswith(b"lt\x00\x00"):
            return data[8:]
        return data

    def map_picture(self, ref: str) -> bytes | None:
        """Imagen de una entrada de mapas (.mapx)."""
        if self.structure != "maps":
            return None
        rowid = self._graphics_rowid(ref)
        if rowid is None:
            return None
        try:
            row = self.conn.execute(
                "SELECT Picture FROM Graphics WHERE rowid=?", (rowid,)
            ).fetchone()
        except sqlite3.Error:
            return None
        if not row or not row["Picture"]:
            return None
        return self._unwrap_picture(bytes(row["Picture"]))

    def pages_for_verse(self, book: int, chapter: int, verse: int) -> list[Page]:
        """Comentarios que aplican a un versículo (para mostrar junto al texto)."""
        out: list[Page] = []
        if "VerseCommentary" in self.tables:
            for row in self._rows(
                "SELECT Book, ChapterBegin, VerseBegin, ChapterEnd, VerseEnd, Comments "
                "FROM VerseCommentary WHERE Book=? AND ChapterBegin=? "
                "ORDER BY VerseBegin", (book, chapter),
            ):
                vb = row["VerseBegin"] or 0
                ve = row["VerseEnd"] or vb
                ce = row["ChapterEnd"] or row["ChapterBegin"]
                if ce != chapter:
                    continue
                if vb <= verse <= ve:
                    ref = f"{book}:{chapter}:{vb}"
                    out.append(Page(
                        ref=ref, title=f"{chapter}:{vb}",
                        raw=self._decode(row["Comments"], "VerseCommentary", ref),
                        book=book, chapter=chapter, verse=vb, order=vb,
                    ))
        if not out and "ChapterCommentary" in self.tables:
            for row in self._rows(
                "SELECT Comments FROM ChapterCommentary WHERE Book=? AND Chapter=?",
                (book, chapter),
            ):
                ref = f"{book}:{chapter}"
                out.append(Page(
                    ref=ref, title=f"Cap. {chapter}",
                    raw=self._decode(row["Comments"], "ChapterCommentary", ref),
                    book=book, chapter=chapter,
                ))
        if not out and "Verses" in self.tables:
            for row in self._rows(
                "SELECT Comments FROM Verses WHERE Book=? AND Chapter=? AND Verse=?",
                (book, chapter, verse),
            ):
                ref = f"{book}:{chapter}:{verse}"
                out.append(Page(
                    ref=ref, title=f"{chapter}:{verse}",
                    raw=self._decode(row["Comments"], "Verses", ref),
                    book=book, chapter=chapter, verse=verse,
                ))
        return out

    def books(self) -> list[int]:
        """IDs de libro presentes en el módulo (orden canónico)."""
        if self.structure != "bible":
            return []
        return [
            int(r[0]) for r in self.conn.execute(
                "SELECT DISTINCT Book FROM Bible ORDER BY Book"
            )
        ]

    def chapter_comments(self, book: int, chapter: int) -> dict[int, list[Page]]:
        """Comentarios de un capítulo agrupados por versículo.

        Clave 0 = comentario de capítulo/libro (aplica a todo el capítulo).
        Una sola consulta por tabla: mostrar un capítulo no debe hacer N queries.
        """
        out: dict[int, list[Page]] = {}

        def push(key: int, page: Page) -> None:
            out.setdefault(key, []).append(page)

        for table, level in self._comment_specs():
            if level == "verse":
                for row in self._rows(
                    f'SELECT Chapter, Verse, Comments FROM "{table}" '
                    "WHERE Book=? AND Chapter=? ORDER BY Verse", (book, chapter),
                ):
                    v = int(row["Verse"] or 0)
                    ref = f"{book}:{chapter}:{v}"
                    push(v, Page(
                        ref=ref, title=f"{chapter}:{v}",
                        raw=self._decode(row["Comments"], table, ref),
                        book=book, chapter=chapter, verse=v, order=v,
                    ))
            elif level == "range":
                for row in self._rows(
                    f'SELECT ChapterBegin, ChapterEnd, VerseBegin, VerseEnd, Comments '
                    f'FROM "{table}" WHERE Book=? AND ChapterBegin<=? '
                    f"AND (ChapterEnd IS NULL OR ChapterEnd>=?) "
                    "ORDER BY ChapterBegin, VerseBegin", (book, chapter, chapter),
                ):
                    cb = int(row["ChapterBegin"] or 0)
                    vb = int(row["VerseBegin"] or 0)
                    key = vb if cb == chapter else 0
                    ref = f"{book}:{chapter}:{vb}" if cb == chapter else f"{book}:{chapter}"
                    push(key, Page(
                        ref=ref, title=f"{chapter}:{vb}" if cb == chapter else f"Cap. {chapter}",
                        raw=self._decode(row["Comments"], table, ref),
                        book=book, chapter=chapter, verse=vb if cb == chapter else None,
                        order=key,
                    ))
            elif level == "chapter":
                for row in self._rows(
                    f'SELECT Comments FROM "{table}" WHERE Book=? AND Chapter=?',
                    (book, chapter),
                ):
                    ref = f"{book}:{chapter}"
                    push(0, Page(
                        ref=ref, title=f"Cap. {chapter}",
                        raw=self._decode(row["Comments"], table, ref),
                        book=book, chapter=chapter, order=0,
                    ))
            elif level == "book":
                for row in self._rows(
                    f'SELECT Comments FROM "{table}" WHERE Book=?', (book,),
                ):
                    ref = str(book)
                    push(0, Page(
                        ref=ref, title=f"Libro {book}",
                        raw=self._decode(row["Comments"], table, ref),
                        book=book, order=0,
                    ))
        return out

    def chapter_count(self, book: int) -> int:
        if self.structure != "bible":
            return 0
        row = self.conn.execute(
            "SELECT MAX(Chapter) FROM Bible WHERE Book=?", (book,)
        ).fetchone()
        return int(row[0] or 0)

    def verse_count(self, book: int, chapter: int) -> int:
        if self.structure != "bible":
            return 0
        row = self.conn.execute(
            "SELECT MAX(Verse) FROM Bible WHERE Book=? AND Chapter=?", (book, chapter)
        ).fetchone()
        return int(row[0] or 0)


KIND_BY_STRUCTURE = {
    "bible": "bible",
    "commentary": "commentary",
    "dictionary": "dictionary",
    "lexicon": "lexicon",
    "book": "book",
    "devotion": "devotion",
    "topic": "topic",
    "harmony": "harmony",
    "maps": "maps",
    "reference": "reference",
    "twm": "twm",
}
