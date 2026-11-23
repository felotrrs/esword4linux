"""Search engine with intent detection.

A single text box understands three intents:

1. **Reference** (`Juan 3:16`, `Sal 23`, `1 Cor 13:4-7`) → jump to the Bible.
2. **Strong** (`G2316`, `H4305`) → search lexicons/dictionaries.
3. **Free text** → FTS5 over the selected scope.

Text search uses `store.search()` (FTS5 + bm25 + snippet) and falls back to OR
if AND returns nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .books import Reference, parse_reference
from .catalog import Catalog
from .store import MODE_ALL, MODE_REGEX, ContentStore, regex_literals

_STRONG_RE = re.compile(r"^[GHgh]\d{1,5}$")


@dataclass(frozen=True)
class SearchFilters:
    """Restrictions applied to a search.

    ``kinds`` and ``module_id`` narrow the module set for every intent.
    ``book``/``book_range``/``chapter``/``chapter_range`` only make sense for
    Bible pages, so they are applied to the text intent and ignored by the
    Strong intent (a Strong number has no book or chapter). The reference
    intent is a navigation shortcut and ignores every filter.
    """

    kinds: tuple[str, ...] = ()
    module_id: int | None = None
    book: int | None = None
    chapter: int | None = None
    book_range: tuple[int, int] | None = None
    chapter_range: tuple[int, int] | None = None

    def is_active(self) -> bool:
        return (bool(self.kinds) or self.module_id is not None
                or self.book is not None or self.chapter is not None
                or self.book_range is not None
                or self.chapter_range is not None)


@dataclass
class SearchHit:
    module_id: int
    module_title: str
    module_abbrev: str
    kind: str
    ref: str
    title: str
    snippet: str
    rank: float = 0.0


@dataclass
class SearchResult:
    query: str
    intent: str = "text"            # text | reference | strong | empty
    reference: Reference | None = None
    hits: list[SearchHit] = field(default_factory=list)
    searched_modules: int = 0
    elapsed_ms: float = 0.0
    note: str = ""
    note_detail: str = ""


class SearchEngine:
    def __init__(self, catalog: Catalog, store: ContentStore):
        self.catalog = catalog
        self.store = store
        self._module_cache: dict[int, dict] = {}

    def _module(self, module_id: int) -> dict:
        if module_id not in self._module_cache:
            self._module_cache[module_id] = self.catalog.module(module_id) or {}
        return self._module_cache[module_id]

    def indexed_module_ids(self, kinds: list[str] | None = None) -> list[int]:
        mods = self.catalog.modules()
        return [
            m["id"] for m in mods
            if m["index_status"] == "ready" and (not kinds or m["kind"] in kinds)
        ]

    # ── main API ─────────────────────────────────────────────────────────
    def search(self, query: str, scope: list[int] | None = None,
               limit: int = 200,
               filters: SearchFilters | None = None,
               mode: str = MODE_ALL) -> SearchResult:
        import time

        started = time.perf_counter()
        query = (query or "").strip()
        if not query:
            return SearchResult(query=query, intent="empty")

        # 1. Biblical reference (a navigation shortcut: filters do not apply)
        ref = parse_reference(query)
        if ref:
            return SearchResult(
                query=query, intent="reference", reference=ref,
                elapsed_ms=(time.perf_counter() - started) * 1000,
                note="referencia",
            )

        # 2. Regular expression: validate before touching the index.
        pattern = None
        if mode == MODE_REGEX:
            try:
                pattern = re.compile(query, re.IGNORECASE)
            except re.error as exc:
                return SearchResult(
                    query=query, intent="text", note="regex_error",
                    note_detail=str(exc),
                    elapsed_ms=(time.perf_counter() - started) * 1000,
                )
            if not regex_literals(query):
                return SearchResult(
                    query=query, intent="text", note="regex_empty",
                    elapsed_ms=(time.perf_counter() - started) * 1000,
                )

        # 3. Strong number
        if _STRONG_RE.match(query):
            ids = self._strong_ids(filters)
            hits = self._collect(query, ids, limit, mode=mode, pattern=pattern)
            return SearchResult(
                query=query, intent="strong", hits=hits,
                searched_modules=len(ids),
                elapsed_ms=(time.perf_counter() - started) * 1000,
                note="strong" if ids else "sin_lexicos_indexados",
            )

        # 4. Free text
        ids = self._text_ids(scope, filters)
        ids = [i for i in ids if self._module(i).get("index_status") == "ready"]
        store_kwargs: dict = {}
        if filters is not None:
            store_kwargs = {
                "kinds": list(filters.kinds) or None,
                "book": filters.book,
                "chapter": filters.chapter,
                "book_range": filters.book_range,
                "chapter_range": filters.chapter_range,
            }
        hits = self._collect(query, ids, limit, mode=mode, pattern=pattern,
                             **store_kwargs)
        return SearchResult(
            query=query, intent="text", hits=hits, searched_modules=len(ids),
            elapsed_ms=(time.perf_counter() - started) * 1000,
            note="" if ids else "sin_indice",
        )

    # ── scope ────────────────────────────────────────────────────────────
    def _text_ids(self, scope: list[int] | None,
                  filters: SearchFilters | None) -> list[int]:
        """Module ids the text search queries.

        Without filters the legacy `scope` argument is honoured exactly as
        before. With filters the engine resolves the scope itself, so the UI
        cannot drift from the query semantics.
        """
        if filters is None:
            return scope if scope else self.indexed_module_ids()
        ids = self.indexed_module_ids(list(filters.kinds) or None)
        if filters.module_id is not None:
            ids = [i for i in ids if i == filters.module_id]
        return ids

    def _strong_ids(self, filters: SearchFilters | None) -> list[int]:
        """Lexicons + dictionaries, narrowed by the type/work filters.

        Book and chapter do not apply: a Strong entry is not a Bible page.
        """
        if filters is None:
            return self.indexed_module_ids(["lexicon", "dictionary"])
        kinds = [
            kind for kind in ("lexicon", "dictionary")
            if not filters.kinds or kind in filters.kinds
        ]
        ids = self.indexed_module_ids(kinds) if kinds else []
        if filters.module_id is not None:
            ids = [i for i in ids if i == filters.module_id]
        return ids

    def _collect(self, query: str, ids: list[int], limit: int,
                 **store_kwargs) -> list[SearchHit]:
        rows = self.store.search(query, ids, limit=limit, **store_kwargs)
        out: list[SearchHit] = []
        for r in rows:
            mod = self._module(r["module_id"])
            out.append(SearchHit(
                module_id=r["module_id"],
                module_title=mod.get("title") or "",
                module_abbrev=mod.get("abbreviation") or "",
                kind=r["kind"],
                ref=r["ref"],
                title=r["title"] or "",
                snippet=r["snip"] or "",
                rank=r["rank"] or 0.0,
            ))
        return out
    def group_by_kind(self, hits: list[SearchHit]) -> dict[str, list[SearchHit]]:
        grouped: dict[str, list[SearchHit]] = {}
        for hit in hits:
            grouped.setdefault(hit.kind, []).append(hit)
        return grouped
