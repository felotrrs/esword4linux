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
        self.kind = KIND_BY_STRUCTURE.get(self.structure, "unknown")

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
        table = {
            "bible": "Bible",
            "commentary": "VerseCommentary" if "VerseCommentary" in self.tables
                          else ("Verses" if "Verses" in self.tables else "BookCommentary"),
            "dictionary": "Dictionary",
            "lexicon": "Lexicon",
            "devotion": "Devotions" if "Devotions" in self.tables else "Devotional",
            "topic": "Topics",
            "harmony": "Parts",
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
    def _decode(self, value, table: str, ident) -> str:
        if value is None:
            return ""
        if isinstance(value, (bytes, bytearray)):
            try:
                return decrypt_payload(bytes(value), self.crypt_key).decode(
                    "utf-8", "replace"
                )
            except SQLitePlusError as exc:
                self.warnings.append(f"{table}/{ident}: no descifrado ({exc})")
                return ""
        return str(value)

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

    def _pages_harmony(self) -> Iterator[Page]:
        sections = {
            r["ID"]: r["Title"]
            for r in self._rows("SELECT ID, Title FROM Sections")
        }
        for row in self._rows("SELECT Section, Part, Reference FROM Parts ORDER BY Section, Part"):
            sec, part = row["Section"], row["Part"]
            yield Page(
                ref=f"{sec}:{part}",
                title=str(sections.get(sec, "") or f"Sección {sec}"),
                raw=self._decode(row["Reference"], "Parts", f"{sec}:{part}"),
                order=int(sec) * 1000 + int(part),
            )

    def _pages_maps(self) -> Iterator[Page]:
        for i, row in enumerate(self._rows(
            "SELECT Title, Details FROM Graphics ORDER BY rowid"
        )):
            title = str(row["Title"] or "")
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
        table = {
            "dictionary": "Dictionary", "lexicon": "Lexicon", "topic": "Topics",
            "reference": "Reference", "maps": "Graphics",
        }.get(self.structure)
        if table:
            col = "Topic" if table in ("Dictionary", "Lexicon") else \
                  ("Chapter" if table == "Reference" else
                   ("Title" if table in ("Topics", "Graphics") else "Topic"))
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
            return [(str(r["k"] or ""), str(r["k"] or "")) for r in self._rows(sql, params)]
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
            return [
                (f"{r['Section']}:{r['Part']}", f"{r['Section']}.{r['Part']}")
                for r in self._rows("SELECT Section, Part FROM Parts ORDER BY Section, Part LIMIT ?", (limit,))
            ]
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
                if len(parts) < 2:
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
                row = self.conn.execute(
                    "SELECT Title, Details FROM Graphics WHERE Title=?", (ref,)
                ).fetchone()
                if not row:
                    return None
                return Page(ref=str(row["Title"]), title=str(row["Title"]),
                            raw=self._decode(row["Details"], "Graphics", ref))
            if self.structure == "harmony":
                sec, _, part = ref.partition(":")
                row = self.conn.execute(
                    "SELECT Section, Part, Reference FROM Parts WHERE Section=? AND Part=?",
                    (int(sec), int(part or 0)),
                ).fetchone()
                if not row:
                    return None
                title = self.conn.execute(
                    "SELECT Title FROM Sections WHERE ID=?", (int(sec),)
                ).fetchone()
                return Page(
                    ref=ref, title=str(title[0] if title else sec),
                    raw=self._decode(row["Reference"], "Parts", ref),
                    order=int(sec) * 1000 + int(part or 0),
                )
        except (ValueError, sqlite3.Error):
            return None
        return self.get_page(ref)

    def map_picture(self, ref: str) -> bytes | None:
        """Imagen de una entrada de mapas (.mapx)."""
        if self.structure != "maps":
            return None
        try:
            row = self.conn.execute(
                "SELECT Picture FROM Graphics WHERE Title=?", (ref,)
            ).fetchone()
        except sqlite3.Error:
            return None
        if not row or not row["Picture"]:
            return None
        return bytes(row["Picture"])

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
    "devotion": "devotion",
    "topic": "topic",
    "harmony": "harmony",
    "maps": "maps",
    "reference": "reference",
    "twm": "twm",
}
