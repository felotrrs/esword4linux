"""Motor de búsqueda con detección de intención.

Una sola caja de texto entiende tres intenciones:

1. **Referencia** (`Juan 3:16`, `Sal 23`, `1 Cor 13:4-7`) → salta a la Biblia.
2. **Strong** (`G2316`, `H4305`) → busca en léxicos/diccionarios.
3. **Texto libre** → FTS5 sobre el alcance seleccionado.

La búsqueda de texto usa `store.search()` (FTS5 + bm25 + snippet) y cae a OR
si el AND no devuelve nada.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .books import Reference, parse_reference
from .catalog import Catalog
from .store import ContentStore

_STRONG_RE = re.compile(r"^[GHgh]\d{1,5}$")


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

    # ── API principal ────────────────────────────────────────────────────
    def search(self, query: str, scope: list[int] | None = None,
               limit: int = 200) -> SearchResult:
        import time

        started = time.perf_counter()
        query = (query or "").strip()
        if not query:
            return SearchResult(query=query, intent="empty")

        # 1. Referencia bíblica
        ref = parse_reference(query)
        if ref:
            return SearchResult(
                query=query, intent="reference", reference=ref,
                elapsed_ms=(time.perf_counter() - started) * 1000,
                note="referencia",
            )

        # 2. Número Strong
        if _STRONG_RE.match(query):
            ids = self.indexed_module_ids(["lexicon", "dictionary"])
            hits = self._collect(query, ids, limit)
            return SearchResult(
                query=query, intent="strong", hits=hits,
                searched_modules=len(ids),
                elapsed_ms=(time.perf_counter() - started) * 1000,
                note="strong" if ids else "sin_lexicos_indexados",
            )

        # 3. Texto libre
        ids = scope if scope else self.indexed_module_ids()
        ids = [i for i in ids if self._module(i).get("index_status") == "ready"]
        hits = self._collect(query, ids, limit)
        return SearchResult(
            query=query, intent="text", hits=hits, searched_modules=len(ids),
            elapsed_ms=(time.perf_counter() - started) * 1000,
            note="" if ids else "sin_indice",
        )

    def _collect(self, query: str, ids: list[int], limit: int) -> list[SearchHit]:
        rows = self.store.search(query, ids, limit=limit)
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
