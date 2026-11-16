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


def build_match(query: str) -> str:
    """User text → FTS5 MATCH expression.

    - Quoted phrases are respected as a phrase.
    - The last term becomes a prefix (search-as-you-type).
    - Terms are combined with AND; `search()` retries with OR if there are no
      results.
    """
    query = (query or "").strip()
    if not query:
        return ""
    phrases = re.findall(r'"([^"]+)"', query)
    rest = re.sub(r'"[^"]+"', " ", query)
    tokens = _TOKEN.findall(rest)
    parts: list[str] = []
    for p in phrases:
        clean = " ".join(_TOKEN.findall(p))
        if clean:
            parts.append(f'"{clean}"')
    for i, tok in enumerate(tokens):
        last = i == len(tokens) - 1 and not phrases
        parts.append(f'"{tok}"*' if last else f'"{tok}"')
    return " AND ".join(parts)


def build_match_or(query: str) -> str:
    query = (query or "").strip()
    if not query:
        return ""
    tokens = _TOKEN.findall(re.sub(r'"[^"]+"', " ", query))
    if not tokens:
        return build_match(query)
    return " OR ".join(f'"{t}"' for t in tokens)


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
               kinds: list[str] | None = None) -> list[dict]:
        if not module_ids:
            return []
        match = build_match(query)
        if not match:
            return []
        rows = self._run_match(match, module_ids, limit, kinds)
        if not rows:
            alt = build_match_or(query)
            if alt and alt != match:
                rows = self._run_match(alt, module_ids, limit, kinds)
        return rows

    def _run_match(self, match: str, module_ids: list[int], limit: int,
                   kinds: list[str] | None) -> list[dict]:
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
