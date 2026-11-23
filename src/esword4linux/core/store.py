"""Content index (SQLite + FTS5).

A single `content.db` file. Each indexed module stores its pages here;
`page_fts` is an external-content FTS5 table with synchronization triggers.
The stored text is ALWAYS plain (no RTF/HTML): rich rendering is read from the
original module at display time.
"""

from __future__ import annotations

import re
import sqlite3
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS page (
    id        INTEGER PRIMARY KEY,
    module_id INTEGER NOT NULL,
    kind      TEXT NOT NULL,
    ref       TEXT NOT NULL,
    title     TEXT,
    body      TEXT,
    book      INTEGER,
    chapter   INTEGER,
    verse     INTEGER,
    ord       INTEGER
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_page_unique ON page(module_id, ref);
CREATE INDEX IF NOT EXISTS idx_page_module ON page(module_id);
CREATE INDEX IF NOT EXISTS idx_page_loc ON page(book, chapter, verse);

CREATE VIRTUAL TABLE IF NOT EXISTS page_fts USING fts5(
    body, title,
    content='page',
    content_rowid='id',
    tokenize="unicode61 remove_diacritics 2"
);

CREATE TRIGGER IF NOT EXISTS page_ai AFTER INSERT ON page BEGIN
  INSERT INTO page_fts(rowid, body, title) VALUES (new.id, new.body, new.title);
END;
CREATE TRIGGER IF NOT EXISTS page_ad AFTER DELETE ON page BEGIN
  INSERT INTO page_fts(page_fts, rowid, body, title)
    VALUES ('delete', old.id, old.body, old.title);
END;
CREATE TRIGGER IF NOT EXISTS page_au AFTER UPDATE ON page BEGIN
  INSERT INTO page_fts(page_fts, rowid, body, title)
    VALUES ('delete', old.id, old.body, old.title);
  INSERT INTO page_fts(rowid, body, title) VALUES (new.id, new.body, new.title);
END;

CREATE TABLE IF NOT EXISTS index_meta (
    module_id INTEGER PRIMARY KEY,
    pages     INTEGER DEFAULT 0,
    built_at  REAL
);
"""

_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)

#: How the words of a query are combined. The UI offers exactly these four.
MODE_ALL = "all"        # every term must appear (default)
MODE_ANY = "any"        # one term is enough
MODE_PHRASE = "phrase"  # the exact phrase
MODE_REGEX = "regex"    # a regular expression (FTS5 seeds, Python decides)
SEARCH_MODES = (MODE_ALL, MODE_ANY, MODE_PHRASE, MODE_REGEX)


def _words(query: str) -> list[str]:
    """Tokens of a phrase: the quoted parts are kept together."""
    phrases = re.findall(r'"([^"]+)"', query or "")
    rest = re.sub(r'"[^"]+"', " ", query or "")
    tokens = [t for t in _TOKEN.findall(rest)]
    words: list[str] = []
    for phrase in phrases:
        clean = " ".join(_TOKEN.findall(phrase))
        if clean:
            words.append(clean)
    words.extend(tokens)
    return words


def build_match(query: str, mode: str = MODE_ALL) -> str:
    """User text → FTS5 MATCH expression for the selected mode.

    - ``all``: quoted terms joined with AND, the last one a prefix (the user is
      typing it). No OR fallback any more: «all of the words» means all.
    - ``any``: quoted terms joined with OR.
    - ``phrase``: the whole query as a single quoted phrase.
    - ``regex``: the literal words found in the pattern, OR-ed (a safe
      superset; :func:`regex_hit` applies the expression itself).
    """
    query = (query or "").strip()
    if not query:
        return ""
    if mode == MODE_PHRASE:
        clean = " ".join(_TOKEN.findall(query))
        return f'"{clean}"' if clean else ""
    if mode == MODE_REGEX:
        parts = []
        for word, prefix in regex_literals(query):
            term = f'"{word}"*' if prefix else f'"{word}"'
            if term not in parts:
                parts.append(term)
        return " OR ".join(parts)
    if mode == MODE_ANY:
        words = _words(query)
        return " OR ".join(f'"{w}"' for w in words) if words else ""
    # MODE_ALL — unchanged behaviour.
    phrases = re.findall(r'"([^"]+)"', query)
    rest = re.sub(r'"[^"]+"', " ", query)
    tokens = _TOKEN.findall(rest)
    parts: list[str] = []
    for phrase in phrases:
        clean = " ".join(_TOKEN.findall(phrase))
        if clean:
            parts.append(f'"{clean}"')
    for i, tok in enumerate(tokens):
        last = i == len(tokens) - 1 and not phrases
        parts.append(f'"{tok}"*' if last else f'"{tok}"')
    return " AND ".join(parts)


def build_match_or(query: str) -> str:
    """OR of the query terms (the «any of the words» shape, no prefixes)."""
    query = (query or "").strip()
    if not query:
        return ""
    tokens = _TOKEN.findall(re.sub(r'"[^"]+"', " ", query))
    if not tokens:
        return build_match(query)
    return " OR ".join(f'"{t}"' for t in tokens)


def regex_literals(pattern: str) -> list[tuple[str, bool]]:
    """(word, is_prefix) pairs found in a regular expression.

    A word is a *prefix* candidate when a quantifier follows it or when it is
    followed/preceded by ``.*``; that only widens the FTS5 seed set. The
    expression is still the final judge, so the result is exact.
    """
    out: list[tuple[str, bool]] = []
    seen: set[str] = set()
    # Escape classes (\d, \w, \b…) are not literal words: drop them before
    # tokenising so «\bpaz\b» yields «paz» and not «bpaz».
    text = re.sub(r"\\[A-Za-z]", " ", pattern or "")
    for match in _TOKEN.finditer(text):
        word = match.group(0)
        if word in seen:
            continue
        seen.add(word)
        after = text[match.end():match.end() + 1]
        following = text[match.end():match.end() + 2]
        pre = text[max(0, match.start() - 2):match.start()]
        prefix = (
            after in ("*", "+", "{")
            or following.startswith(".*") or following.startswith(".+")
            or pre.endswith(".*")
        )
        out.append((word, prefix))
    return out


def regex_hit(pattern, row: dict) -> bool:
    """True when the compiled *pattern* matches the page text."""
    for value in (row.get("body"), row.get("title")):
        if value and pattern.search(value):
            return True
    return False


class ContentStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass

    # ── writing ──────────────────────────────────────────────────────────
    def delete_module(self, module_id: int) -> None:
        self.conn.execute("DELETE FROM page WHERE module_id=?", (module_id,))
        self.conn.execute("DELETE FROM index_meta WHERE module_id=?", (module_id,))
        self.conn.commit()

    def add_pages(self, module_id: int, kind: str, pages: list[dict]) -> int:
        """pages: dicts with ref,title,body,book,chapter,verse,ord."""
        rows = [
            (module_id, kind, p["ref"], p.get("title") or "", p.get("body") or "",
             p.get("book"), p.get("chapter"), p.get("verse"), p.get("ord") or 0)
            for p in pages
        ]
        self.conn.executemany(
            "INSERT OR REPLACE INTO page "
            "(module_id, kind, ref, title, body, book, chapter, verse, ord) "
            "VALUES (?,?,?,?,?,?,?,?,?)", rows,
        )
        self.conn.execute(
            "INSERT INTO index_meta(module_id, pages, built_at) VALUES(?,?,?) "
            "ON CONFLICT(module_id) DO UPDATE SET pages=excluded.pages, built_at=excluded.built_at",
            (module_id, len(rows), time.time()),
        )
        self.conn.commit()
        return len(rows)

    # ── querying ─────────────────────────────────────────────────────────
    def search(self, query: str, module_ids: list[int], limit: int = 200,
               kinds: list[str] | None = None,
               book: int | None = None,
               chapter: int | None = None,
               book_range: tuple[int, int] | None = None,
               chapter_range: tuple[int, int] | None = None,
               mode: str = MODE_ALL,
               pattern=None) -> list[dict]:
        if not module_ids:
            return []
        match = build_match(query, mode)
        if not match:
            return []
        # The regex mode filters the FTS5 candidates in Python, so it needs a
        # wider window; the final list is trimmed to `limit` below.
        fetch = limit
        if mode == MODE_REGEX:
            fetch = min(2000, max(limit, limit * 10))
        rows = self._run_match(
            match, module_ids, fetch, kinds, book, chapter,
            book_range, chapter_range,
        )
        if mode == MODE_REGEX and pattern is not None:
            rows = [row for row in rows if regex_hit(pattern, row)][:limit]
        return rows

    def _run_match(self, match: str, module_ids: list[int], limit: int,
                   kinds: list[str] | None,
                   book: int | None = None,
                   chapter: int | None = None,
                   book_range: tuple[int, int] | None = None,
                   chapter_range: tuple[int, int] | None = None) -> list[dict]:
        placeholders = ",".join("?" * len(module_ids))
        sql = (
            "SELECT p.id, p.module_id, p.kind, p.ref, p.title, p.body, "
            "p.book, p.chapter, p.verse, "
            "bm25(page_fts) AS rank, "
            "snippet(page_fts, 0, '<b>', '</b>', '…', 24) AS snip "
            "FROM page_fts JOIN page p ON p.id = page_fts.rowid "
            f"WHERE page_fts MATCH ? AND p.module_id IN ({placeholders})"
        )
        params: list = [match, *module_ids]
        if kinds:
            sql += " AND p.kind IN (" + ",".join("?" * len(kinds)) + ")"
            params.extend(kinds)
        # Bible-only restrictions. The columns already exist in `page` and are
        # indexed by idx_page_loc(book, chapter, verse): no schema change and
        # no reindex. They are applied to the joined row, so they only remove
        # results, never block.
        if book is not None:
            sql += " AND p.book = ?"
            params.append(int(book))
        if book_range is not None:
            lo, hi = book_range
            sql += " AND p.book BETWEEN ? AND ?"
            params.extend((int(lo), int(hi)))
        if chapter is not None:
            sql += " AND p.chapter = ?"
            params.append(int(chapter))
        if chapter_range is not None:
            lo, hi = chapter_range
            sql += " AND p.chapter BETWEEN ? AND ?"
            params.extend((int(lo), int(hi)))
        sql += " ORDER BY rank LIMIT ?"
        params.append(limit)
        try:
            return [dict(r) for r in self.conn.execute(sql, params)]
        except sqlite3.OperationalError:
            return []

    def count_pages(self, module_id: int) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) FROM page WHERE module_id=?", (module_id,)
        ).fetchone()
        return int(row[0] or 0)

    def page(self, module_id: int, ref: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM page WHERE module_id=? AND ref=?", (module_id, ref)
        ).fetchone()
        return dict(row) if row else None

    def total_pages(self) -> int:
        return int(self.conn.execute("SELECT COUNT(*) FROM page").fetchone()[0])

    def db_size(self) -> int:
        try:
            return self.db_path.stat().st_size
        except OSError:
            return 0

    def purge_unknown(self, known_ids: set[int]) -> None:
        """Deletes pages of modules that no longer exist in the catalog."""
        if not known_ids:
            return
        rows = self.conn.execute("SELECT DISTINCT module_id FROM page").fetchall()
        for r in rows:
            if r[0] not in known_ids:
                self.delete_module(r[0])
