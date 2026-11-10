"""Catálogo de la carpeta de recursos.

Escanea la carpeta seleccionable, clasifica cada módulo por su estructura SQL y
guarda metadatos en `catalog.db`. El escaneo es incremental: si un archivo no
cambió (mtime + tamaño) no se vuelve a abrir.

Nunca se escribe en la carpeta de recursos.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .esword.module import ESWORD_EXTS, EswordModule

SCHEMA = """
CREATE TABLE IF NOT EXISTS module (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    path         TEXT UNIQUE NOT NULL,
    rel_path     TEXT NOT NULL,
    filename     TEXT NOT NULL,
    ext          TEXT,
    structure    TEXT,
    kind         TEXT,
    title        TEXT,
    abbreviation TEXT,
    language     TEXT DEFAULT 'es',
    encrypted    INTEGER DEFAULT 0,
    entries      INTEGER DEFAULT 0,
    size         INTEGER DEFAULT 0,
    mtime        REAL DEFAULT 0,
    fingerprint  TEXT,
    duplicate_of INTEGER,
    index_status TEXT DEFAULT 'pending',
    index_error  TEXT,
    indexed_at   REAL
);
CREATE INDEX IF NOT EXISTS idx_module_kind ON module(kind);
CREATE INDEX IF NOT EXISTS idx_module_status ON module(index_status);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""

KIND_LABELS = {
    "bible": ("Biblias", "Bibles"),
    "commentary": ("Comentarios", "Commentaries"),
    "dictionary": ("Diccionarios", "Dictionaries"),
    "lexicon": ("Léxicos", "Lexicons"),
    "devotion": ("Devocionales", "Devotionals"),
    "topic": ("Tópicos", "Topics"),
    "reference": ("Referencias", "References"),
    "harmony": ("Armonías", "Harmonies"),
    "maps": ("Mapas", "Maps"),
    "twm": ("TWM", "TWM"),
    "unknown": ("Sin clasificar", "Unclassified"),
}

KIND_ORDER = [
    "bible", "commentary", "dictionary", "lexicon", "devotion", "topic",
    "reference", "harmony", "maps", "twm", "unknown",
]

_EN_HINTS = re.compile(
    r"\b(holy bible|king james|english|new international|new american|"
    r"new living|amplified|standard version|good news|world english|"
    r"webster|darby|young|american standard|revised standard|wycliffe|"
    r"tyndale|coverdale|geneva bible|bishops|douay|rheims|challoner|knox|"
    r"weymouth|moffatt|goodspeed|fausset|ellicott|pulpit|expositor|keil|"
    r"delitzsch|tregelles|tischendorf|westcott|smith|strong's|vine's|thayer|"
    r"gesenius|brown-driver|briggs|josephus|antiquities|wars of the jews|"
    r"treasury of david|morning and evening|bible dictionary|bible atlas)\b",
    re.I,
)
_ES_HINTS = re.compile(r"[áéíóúñ¿¡ÁÉÍÓÚÑ]", re.UNICODE)


def detect_language(title: str, abbreviation: str, filename: str) -> str:
    text = f"{title} {abbreviation} {filename}"
    if _EN_HINTS.search(text):
        return "en"
    if _ES_HINTS.search(text):
        return "es"
    low = text.lower()
    if any(w in low for w in (" diccionario", " comentario", " biblia", " teologia",
                              " evangelio", " reina", " valera", " version")):
        return "es"
    return "en" if any(w in low for w in (" dictionary", " commentary", " bible ")) else "es"


def _fingerprint(path: Path, size: int) -> str:
    h = hashlib.sha1(str(size).encode())
    try:
        with open(path, "rb") as fh:
            h.update(fh.read(65536))
    except OSError:
        pass
    return h.hexdigest()


@dataclass
class ScanResult:
    total: int = 0
    added: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    seconds: float = 0.0


class Catalog:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass

    # ── escaneo ──────────────────────────────────────────────────────────
    def scan(self, resources_dir: str | Path, progress=None) -> ScanResult:
        """Indexa metadatos de todos los módulos de la carpeta."""
        root = Path(resources_dir)
        started = time.time()
        result = ScanResult()
        if not root.is_dir():
            raise FileNotFoundError(f"carpeta de recursos inexistente: {root}")

        files = sorted(
            p for p in root.rglob("*")
            if p.is_file() and p.suffix.lower() in ESWORD_EXTS
        )
        result.total = len(files)
        existing = {
            r["path"]: (r["size"], r["mtime"], r["index_status"])
            for r in self.conn.execute("SELECT path, size, mtime, index_status FROM module")
        }

        for i, path in enumerate(files, 1):
            if progress and i % 25 == 0:
                progress(i, len(files), path.name)
            try:
                stat = path.stat()
            except OSError:
                result.errors += 1
                continue
            key = str(path)
            prev = existing.get(key)
            if prev and prev[0] == stat.st_size and abs(prev[1] - stat.st_mtime) < 1:
                result.skipped += 1
                continue
            try:
                meta = self._probe(path)
            except Exception:
                result.errors += 1
                continue
            status = prev[2] if prev else "pending"
            if prev and (prev[0] != stat.st_size):
                status = "pending"  # el archivo cambió: reindexar
            self._upsert(key, root, path, stat, meta, status)
            if prev:
                result.updated += 1
            else:
                result.added += 1

        self._mark_duplicates()
        self.conn.commit()
        result.seconds = time.time() - started
        self.set_meta("last_scan", time.strftime("%Y-%m-%dT%H:%M:%S"))
        self.set_meta("resources_dir", str(root))
        return result

    def _probe(self, path: Path) -> dict:
        with EswordModule(path) as mod:
            title = mod.title
            return {
                "structure": mod.structure,
                "kind": mod.kind,
                "title": title,
                "abbreviation": mod.abbreviation,
                "language": detect_language(title, mod.abbreviation, path.name),
                "encrypted": int(mod.encrypted),
                "entries": mod.count_entries(),
            }

    def _upsert(self, key, root, path, stat, meta, status) -> None:
        rel = str(path.relative_to(root))
        self.conn.execute(
            """
            INSERT INTO module (path, rel_path, filename, ext, structure, kind, title,
                                abbreviation, language, encrypted, entries, size, mtime,
                                fingerprint, index_status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(path) DO UPDATE SET
                rel_path=excluded.rel_path, filename=excluded.filename, ext=excluded.ext,
                structure=excluded.structure, kind=excluded.kind, title=excluded.title,
                abbreviation=excluded.abbreviation, language=excluded.language,
                encrypted=excluded.encrypted, entries=excluded.entries, size=excluded.size,
                mtime=excluded.mtime, fingerprint=excluded.fingerprint,
                index_status=excluded.index_status
            """,
            (key, rel, path.name, path.suffix.lower(), meta["structure"], meta["kind"],
             meta["title"], meta["abbreviation"], meta["language"], meta["encrypted"],
             meta["entries"], stat.st_size, stat.st_mtime,
             _fingerprint(path, stat.st_size), status),
        )

    def _mark_duplicates(self) -> None:
        self.conn.execute("UPDATE module SET duplicate_of = NULL")
        self.conn.execute(
            """
            UPDATE module SET duplicate_of = (
                SELECT m2.id FROM module m2
                WHERE m2.fingerprint = module.fingerprint AND m2.id < module.id
                ORDER BY m2.id LIMIT 1
            )
            WHERE EXISTS (
                SELECT 1 FROM module m2
                WHERE m2.fingerprint = module.fingerprint AND m2.id < module.id
            )
            """
        )
        self.conn.commit()

    # ── consultas ────────────────────────────────────────────────────────
    def modules(self, kind: str | None = None, include_duplicates: bool = False) -> list[dict]:
        sql = "SELECT * FROM module WHERE 1=1"
        params: list = []
        if kind:
            sql += " AND kind=?"
            params.append(kind)
        if not include_duplicates:
            sql += " AND duplicate_of IS NULL"
        sql += " ORDER BY title COLLATE NOCASE"
        return [dict(r) for r in self.conn.execute(sql, params)]

    def module(self, module_id: int) -> dict | None:
        row = self.conn.execute("SELECT * FROM module WHERE id=?", (module_id,)).fetchone()
        return dict(row) if row else None

    def by_rel_path(self, rel_path: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM module WHERE rel_path=?", (rel_path,)
        ).fetchone()
        return dict(row) if row else None

    def counts_by_kind(self, include_duplicates: bool = False) -> dict[str, int]:
        where = "" if include_duplicates else " WHERE duplicate_of IS NULL"
        return {
            r["kind"]: r["n"]
            for r in self.conn.execute(
                f"SELECT kind, COUNT(*) AS n FROM module{where} GROUP BY kind"
            )
        }

    def status_counts(self) -> dict[str, int]:
        return {
            r["index_status"]: r["n"]
            for r in self.conn.execute(
                "SELECT index_status, COUNT(*) AS n FROM module "
                "WHERE duplicate_of IS NULL GROUP BY index_status"
            )
        }

    def set_status(self, module_id: int, status: str, error: str | None = None,
                   entries: int | None = None) -> None:
        self.conn.execute(
            "UPDATE module SET index_status=?, index_error=?, indexed_at=? "
            "WHERE id=?",
            (status, error, time.time() if status == "ready" else None, module_id),
        )
        if entries is not None:
            self.conn.execute("UPDATE module SET entries=? WHERE id=?", (entries, module_id))
        self.conn.commit()

    def set_meta(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO meta(key, value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value)
        )
        self.conn.commit()

    def get_meta(self, key: str) -> str | None:
        row = self.conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None

    def is_empty(self) -> bool:
        return self.conn.execute("SELECT COUNT(*) FROM module").fetchone()[0] == 0
