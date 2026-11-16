"""Catalog of the resources folder.

Scans the selectable folder, classifies each module by its SQL structure and
stores metadata in `catalog.db`. The scan is incremental: if a file has not
changed (mtime + size) it is not opened again.

Nothing is ever written to the resources folder.
"""

from __future__ import annotations

import hashlib
import html as _html
import os
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
    "book": ("Libros", "Books"),
    "devotion": ("Devocionales", "Devotionals"),
    "topic": ("Tópicos", "Topics"),
    "reference": ("Referencias", "References"),
    "harmony": ("Armonías", "Harmonies"),
    "maps": ("Mapas", "Maps"),
    "twm": ("TWM", "TWM"),
    "unknown": ("Sin clasificar", "Unclassified"),
}

# Folders that are never indexed (duplicate quarantine, VCS, junk).
EXCLUDED_DIRS = {
    "_duplicados", ".git", "__pycache__", ".cache", ".trash", ".Trash-1000",
    "System Volume Information", "$RECYCLE.BIN", "lost+found",
}

# e-Sword system/localization files that are not study modules:
# `headings.*` are Bible headings and `localize.lanx` the language tables of
# the e-Sword application. They have no navigable content.
EXCLUDED_FILES = {
    "headings.es", "headings_en.en", "headings_fr.fr", "headings_pt.pt",
    "localize.lanx",
}

KIND_ORDER = [
    "bible", "commentary", "dictionary", "lexicon", "book", "devotion", "topic",
    "reference", "harmony", "maps", "twm", "unknown",
]

# Role of a module within a work (for the "By work" view).
ROLE_LABELS = {
    "bible": ("Texto", "Text"),
    "commentary": ("Notas", "Notes"),
    "dictionary": ("Diccionario", "Dictionary"),
    "lexicon": ("Léxico", "Lexicon"),
    "book": ("Libro", "Book"),
    "devotion": ("Devocional", "Devotional"),
    "topic": ("Tópicos", "Topics"),
    "reference": ("Referencia", "Reference"),
    "harmony": ("Armonía", "Harmony"),
    "maps": ("Mapas", "Maps"),
    "twm": ("TWM", "TWM"),
    "unknown": ("Otro", "Other"),
}


def work_key(title: str) -> str:
    """Base key for grouping by work (normalized title, without year or accents)."""
    text = unicodedata.normalize("NFD", (title or "").lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"\(\s*\d{4}\s*\)", " ", text)
    text = re.sub(r"\b(1[89]\d{2}|20\d{2})\b", " ", text)
    text = re.sub(r"[^a-z0-9ñ]+", " ", text).strip()
    return re.sub(r"\s+", " ", text)


def work_year(title: str) -> str:
    match = re.search(r"\b(1[89]\d{2}|20\d{2})\b", title or "")
    return match.group(1) if match else ""

# Version of the metadata block that depends on language and type detection.
# Changing it makes the next scan reprocess all modules (without touching
# content indexes).
METADATA_VERSION = "2026-11-15-clasificacion"

LANGUAGE_ORDER = ["es", "en", "fr", "pt", "de", "it", "la", "grc", "hbo", "und"]

_FILENAME_LANG = {
    "es": "es", "spa": "es",
    "en": "en", "eng": "en",
    "fr": "fr", "fra": "fr",
    "pt": "pt", "por": "pt",
    "grc": "grc", "greek": "grc",
    "hbo": "hbo", "hebrew": "hbo",
}

_LANG_WORDS = {
    # Function words and distinctive editorial vocabulary. Book and author
    # names are excluded: they are shared proper nouns and added noise
    # (e.g. «John Strange» looked English).
    "es": frozenset("""
        el la los las de del que y a en un una unos unas al se con por para su
        sus lo como mas pero este esta estos estas entre cuando muy sin sobre
        tambien me hasta hay donde quien desde todo todos nos durante uno les ni
        contra otros ese eso ante ellos esto mi mis tu tus ella estar estoy estas
        estamos estan nuestro nuestra nuestros nuestras vuestro vuestra vuestros
        vuestras esos esas aquel aquella atlas mapa mapas biblia comentario
        diccionario testamento version reina valera espanol sagrada escritura
        evangelio cristo cristiano cristiana iglesia senor dios jesus espiritu
        gracia fe amor vida muerte pecado salvacion doctrina teologia sermon
        sermones bosquejo bosquejos estudio expositor auxiliar biblico devocional
        oracion codigo analisis morfologico glosario nombres notas traduccion
        texto original nuevo nueva antiguo antigua palabra palabras lengua lenguas
        hebreo griego
    """.split()),
    "en": frozenset("""
        the and of to in is that it for with as was on be by this are or from at
        not have had but they you we he she his her their which will would can
        could should may might must about into through these those there what
        when where who how all any both each few more most other some such no nor
        only own same so than too very just holy bible king james english new old
        testament version standard american revised international living amplified
        commentary dictionary lexicon concordance atlas maps devotion daily morning
        evening through gospel christ christian church lord god jesus spirit grace
        faith love life death sin salvation doctrine theology sermon sermons
        study expositor biblical devotional prayer
    """.split()),
    "fr": frozenset("""
        le la les de des du un une et en est que qui dans pour pas sur au aux
        avec ce cette ces il elle ils elles nous vous je tu son sa ses leur leurs
        plus mais ou comme tout tous etre avoir fait dit bible commentaire
        dictionnaire testament version segond ostervald martineau francais sainte
        ecriture evangile christ chretien eglise seigneur dieu jesus esprit grace
        foi amour vie mort peche salut doctrine theologie sermon etude
    """.split()),
    "pt": frozenset("""
        o a os as de do da dos das um uma uns umas e em no na nos nas por para
        com que se ao aos seu sua seus suas ele ela eles elas nos vos eu tu nao
        mais mas como quando onde muito tambem ja foi ser ter esta sao biblia
        comentario dicionario testamento versao almeida portugues sagrada
        escritura evangelho cristo cristao igreja senhor deus jesus espirito
        graca fe amor vida morte pecado salvacao doutrina teologia sermao estudo
        devocional oracao
    """.split()),
    "de": frozenset("""
        der die das und in den von zu mit sich des auf fur ist im dem nicht ein
        eine als auch an werden aus er hat dass sie nach wird bei einer um am
        sind noch wie einem uber einen so zum war haben nur oder aber vor zur bis
        mehr durch man sein wurde sei welche bibel kommentar worterbuch testament
        version luther elberfelder schlachter deutsch heilige schrift evangelium
        christ christlich kirche herr gott jesus geist gnade glaube liebe leben
        tod sunde erlosung lehre theologie predigt studie
    """.split()),
    "it": frozenset("""
        il lo la i gli le di del della dei delle un uno una e ed in nel nella per
        con su che chi non piu ma come quando dove molto anche gia fu essere avere
        questo questa questi queste suo sua loro bibbia commentario dizionario
        testamento versione riveduta luzzi diodati italiano sacra scrittura
        vangelo cristo cristiano chiesa signore dio gesu spirito grazia fede
        amore vita morte peccato salvezza dottrina teologia sermone studio
    """.split()),
    "la": frozenset("""
        et in est non ad de cum per qui quae quod ut si sed a ab ex hoc haec id
        eius eorum christus deus dominus spiritus sanctus biblia testamentum
        vulgata latin latina
    """.split()),
}


def _filename_language(filename: str) -> str:
    """Last language marker in the filename (``_es``, ``_en``…)."""
    suffix = Path(filename).suffix.lower().lstrip(".")
    if suffix in _FILENAME_LANG:
        return _FILENAME_LANG[suffix]
    tokens = [t for t in re.split(r"[_\-. ]+", Path(filename).stem.lower()) if t]
    for token in reversed(tokens):
        if token in _FILENAME_LANG:
            return _FILENAME_LANG[token]
    return ""


def _language_counts(text: str) -> dict[str, int]:
    counts = {code: 0 for code in LANGUAGE_ORDER}
    # e-Sword descriptions may carry HTML with lang="es-ES"; their
    # attributes are not content text.
    clean = _html.unescape(re.sub(r"(?is)<[^>]+>", " ", text or ""))
    clean = unicodedata.normalize("NFD", clean)
    clean = "".join(ch for ch in clean if unicodedata.category(ch) != "Mn")
    low = clean.lower()
    # 1–2 letter words overlap between languages ("a", "de", "es"…).
    tokens = [t for t in re.findall(r"[^\W\d_]+", low, flags=re.UNICODE)
              if len(t) >= 3]
    token_set = set(tokens)
    for code, words in _LANG_WORDS.items():
        hits = token_set & words
        if hits:
            counts[code] += sum(tokens.count(word) for word in hits)
    # Typographic marks and alphabets.
    if re.search(r"[áéíóúñ¿¡]", low):
        counts["es"] += 2
    if re.search(r"[ãõç]", low):
        counts["pt"] += 2
    if re.search(r"[œ]", low):
        counts["fr"] += 2
    if re.search(r"[äöüß]", low):
        counts["de"] += 2
    letters = [ch for ch in text if ch.isalpha()]
    if letters:
        greek = sum(1 for ch in letters if "\u0370" <= ch <= "\u03ff"
                    or "\u1f00" <= ch <= "\u1fff")
        hebrew = sum(1 for ch in letters if "\u0590" <= ch <= "\u05ff")
        if greek / len(letters) >= 0.25:
            counts["grc"] += 20
        if hebrew / len(letters) >= 0.25:
            counts["hbo"] += 20
    return counts


def detect_language(title: str, abbreviation: str, filename: str,
                    description: str = "", sample: str = "",
                    allow_original: bool = True) -> str:
    """Module language: metadata + filename and, if needed, a sample.

    The order of the signals is deliberate: a title such as «Spanish
    Reina-Valera» is in Spanish even if it contains English words. Author names
    («Smith», «Strong») are **not** a language signal.
    """
    # e-Sword's description may be a huge license HTML in another language; it
    # is not a reliable signal of the content. Title + abbreviation are.
    meta = f"{title} {abbreviation}"
    counts = _language_counts(meta)
    low_meta = _html.unescape(re.sub(r"(?is)<[^>]+>", " ", meta)).lower()
    marker = _filename_language(filename)
    if marker:
        # Secondary hint: it must not override a title clearly in another language.
        counts[marker] += 1
    sample_counts = _language_counts(sample) if sample else {}
    if sample:
        for code, value in sample_counts.items():
            counts[code] += min(value, 60)
    # Original languages: the title is the only signal in encrypted modules
    # (a sample cannot be read without decrypting them). If the sample is already
    # clearly Spanish/English/etc., Greek/Hebrew is not forced by the title.
    if allow_original:
        if re.search(r"\b(greek|griego|septuagint|lxx|textus receptus|byzantine|gnt)\b",
                     low_meta):
            counts["grc"] += 24
        if re.search(r"\b(hebrew|hebreo|tanach|tanakh|masoretic|bhs|biblia hebraica)\b",
                     low_meta):
            counts["hbo"] += 24
    best = max(LANGUAGE_ORDER, key=lambda code: (counts.get(code, 0),
                                                -LANGUAGE_ORDER.index(code)))
    if counts.get(best, 0) <= 0:
        return marker or "und"
    return best


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
    removed: int = 0
    seconds: float = 0.0


class Catalog:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        try:
            self.conn.execute(
                "UPDATE module SET kind = 'dictionary' WHERE kind = 'twm' "
                "AND (lower(title) LIKE '%diccionario%' OR lower(rel_path) LIKE '%diccionario%')"
            )
            self.conn.commit()
        except Exception:
            pass
        self.conn.commit()

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass

    # ── scanning ─────────────────────────────────────────────────────────
    def scan(self, resources_dir: str | Path, progress=None) -> ScanResult:
        """Indexes metadata for every module in the folder."""
        root = Path(resources_dir)
        started = time.time()
        result = ScanResult()
        if not root.is_dir():
            raise FileNotFoundError(f"resources folder does not exist: {root}")

        files = sorted(self._walk_modules(root))
        result.total = len(files)
        force_meta = self.needs_metadata_refresh()
        existing = {
            r["path"]: (r["size"], r["mtime"], r["index_status"],
                        r["kind"], r["structure"], r["entries"])
            for r in self.conn.execute(
                "SELECT path, size, mtime, index_status, kind, structure, entries "
                "FROM module"
            )
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
            if (not force_meta and prev and prev[0] == stat.st_size
                    and abs(prev[1] - stat.st_mtime) < 1):
                result.skipped += 1
                continue
            try:
                meta = self._probe(path)
            except Exception:
                result.errors += 1
                continue
            status = prev[2] if prev else "pending"
            if prev and (prev[0] != stat.st_size):
                status = "pending"  # the file changed: reindex
            # If the classification or the entry count changed (e.g. a new
            # version groups harmonies better), the old FTS5 index no longer
            # represents the module: it must be rebuilt.
            if prev and (prev[3] != meta["kind"]
                         or prev[4] != meta["structure"]
                         or prev[5] != meta["entries"]):
                status = "pending"
            self._upsert(key, root, path, stat, meta, status)
            if prev:
                result.updated += 1
            else:
                result.added += 1

        result.removed = self._purge_missing({str(p) for p in files})
        self._mark_duplicates()
        self.conn.commit()
        result.seconds = time.time() - started
        self.set_meta("last_scan", time.strftime("%Y-%m-%dT%H:%M:%S"))
        self.set_meta("resources_dir", str(root))
        self.set_meta("metadata_version", METADATA_VERSION)
        return result

    def _walk_modules(self, root: Path) -> list[Path]:
        """Walks the folder skipping `_duplicados`, VCS and hidden folders."""
        out: list[Path] = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [
                d for d in dirnames
                if d not in EXCLUDED_DIRS and not d.startswith(".")
            ]
            for fn in filenames:
                if fn in EXCLUDED_FILES:
                    continue
                path = Path(dirpath) / fn
                if path.suffix.lower() in ESWORD_EXTS and path.is_file():
                    out.append(path)
        return out

    def _purge_missing(self, existing: set[str]) -> int:
        """Removes from the catalog the modules that are no longer on disk."""
        rows = self.conn.execute("SELECT id, path FROM module").fetchall()
        removed = 0
        for row in rows:
            if row["path"] not in existing:
                self.conn.execute("DELETE FROM module WHERE id=?", (row["id"],))
                removed += 1
        return removed

    @staticmethod
    def _language_sample(mod) -> str:
        """Short content sample to break a language tie.

        Only for readable modules: decrypting every encrypted one just for this
        would cost more than it contributes.
        """
        if mod.encrypted or mod.structure in ("maps", "unknown", "twm"):
            return ""
        from .text import to_plain

        parts: list[str] = []
        try:
            for i, page in enumerate(mod.iter_pages()):
                if i >= 2:
                    break
                text = to_plain(page.raw, hint=mod.stem, codepages=mod.codepages).strip()
                if text:
                    parts.append(text[:1200])
        except Exception:
            return ""
        return " ".join(parts)

    def _probe(self, path: Path) -> dict:
        with EswordModule(path) as mod:
            title = mod.title
            abbreviation = mod.abbreviation
            structure = mod.structure
            kind = mod.kind
            # A complete work in the LIBROS/ folder with a reference
            # structure is a book, not a loose cross-reference.
            if structure == "reference" and path.parent.name.lower() == "libros":
                kind = "book"
            # A TWM module whose title reveals that it is a dictionary is
            # cataloged as a dictionary so it does not remain an orphan category
            # (a single item under «TWM»). The module is not modified, only
            # its classification.
            if structure == "twm" and "diccionario" in f"{title} {abbreviation}".lower():
                kind = "dictionary"
            # Some commentaries are distributed with a dictionary schema
            # (one entry per chapter). The structure is still
            # `dictionary`, but in the catalog they are Commentaries.
            if structure == "dictionary":
                identidad = f"{title} {abbreviation}".lower()
                if re.search(r"\b(comentario|commentary)\b", identidad):
                    kind = "commentary"
            return {
                "structure": structure,
                "kind": kind,
                "title": title,
                "abbreviation": abbreviation,
                "language": detect_language(
                    title, mod.abbreviation, path.name,
                    description=mod.description,
                    sample=self._language_sample(mod),
                    allow_original=mod.kind in ("bible", "commentary", "harmony"),
                ),
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

    # ── queries ──────────────────────────────────────────────────────────
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

    def works(self) -> list[dict]:
        """Groups the visible modules by work.

        A work may have several modules: the Bible and its notes, the
        dictionary and its lexicon, two editions of the same text…

        The year in the title is used to **separate editions** (RV1960 ≠ RV1995)
        only when several years coexist within the same base title.
        """
        base_groups: dict[str, list[dict]] = {}
        for mod in self.modules():
            base_groups.setdefault(work_key(mod["title"]), []).append(mod)

        order = {kind: i for i, kind in enumerate(KIND_ORDER)}
        out: list[dict] = []

        def emit(key: str, items: list[dict]) -> None:
            items.sort(key=lambda m: (order.get(m["kind"], 99), m["title"].lower()))
            kinds = sorted({m["kind"] for m in items}, key=lambda k: order.get(k, 99))
            out.append({
                "key": key,
                "title": items[0]["title"],
                "modules": items,
                "kinds": kinds,
            })

        for base, items in base_groups.items():
            years = {work_year(m["title"]) for m in items if work_year(m["title"])}
            if len(years) <= 1:
                emit(base, items)
                continue
            subgroups: dict[str, list[dict]] = {}
            for mod in items:
                subgroups.setdefault(work_year(mod["title"]), []).append(mod)
            for year, sub in subgroups.items():
                emit(f"{base}#{year}" if year else base, sub)

        out.sort(key=lambda w: w["title"].lower())
        return out

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

    def needs_metadata_refresh(self) -> bool:
        return self.get_meta("metadata_version") != METADATA_VERSION

    def is_empty(self) -> bool:
        return self.conn.execute("SELECT COUNT(*) FROM module").fetchone()[0] == 0
