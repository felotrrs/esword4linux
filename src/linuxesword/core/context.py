"""Contexto compartido de la aplicación (catálogo, índice, módulos abiertos)."""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from .catalog import Catalog
from .esword.module import EswordModule
from .indexer import Indexer
from .search import SearchEngine
from .store import ContentStore
from .strong import StrongIndex


class AppContext:
    MAX_OPEN_MODULES = 12

    def __init__(self, settings):
        self.settings = settings
        self.catalog = Catalog(settings.catalog_db)
        self.store = ContentStore(settings.content_db)
        self.indexer = Indexer(self.catalog, self.store)
        self.search = SearchEngine(self.catalog, self.store)
        self.strong = StrongIndex(self)
        self._open: "OrderedDict[int, EswordModule]" = OrderedDict()

    # ── módulos ──────────────────────────────────────────────────────────
    def module(self, module: int | dict) -> EswordModule | None:
        row = module if isinstance(module, dict) else self.catalog.module(module)
        if not row:
            return None
        mid = row["id"]
        mod = self._open.get(mid)
        if mod is not None:
            self._open.move_to_end(mid)
            return mod
        try:
            mod = EswordModule(row["path"])
        except Exception:
            return None
        self._open[mid] = mod
        while len(self._open) > self.MAX_OPEN_MODULES:
            _, old = self._open.popitem(last=False)
            old.close()
        return mod

    def close_all(self) -> None:
        for mod in self._open.values():
            mod.close()
        self._open.clear()
        self.catalog.close()
        self.store.close()

    # ── conveniencia ─────────────────────────────────────────────────────
    def bibles(self) -> list[dict]:
        return self.catalog.modules(kind="bible")

    def commentaries(self) -> list[dict]:
        return self.catalog.modules(kind="commentary")

    def settings_path(self) -> Path:
        return Path(self.settings.catalog_db).parent
