"""Indexador: módulo e-Sword → páginas planas → FTS5.

La indexación es **bajo demanda por categoría**. La lectura de una biblia o de
una entrada nunca depende del índice: el visor consulta el módulo directamente
y descifra solo los registros que muestra. El índice existe únicamente para
buscar.

Los módulos cifrados (SQLitePlus/Twofish) son el único coste real; para las
biblias se descifra en paralelo con un pool de procesos.
"""

from __future__ import annotations

import math
import os
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from .catalog import KIND_ORDER, Catalog
from .esword.module import EswordModule
from .store import ContentStore
from .text import to_plain


# ── worker de descifrado (nivel de módulo: debe ser picklable) ───────────
def _decrypt_chunk(args: tuple[list[bytes], str]) -> list[str]:
    from .esword.sqliteplus import decrypt_payload

    blobs, key = args
    out: list[str] = []
    for blob in blobs:
        try:
            out.append(decrypt_payload(bytes(blob), key).decode("utf-8", "replace"))
        except Exception:
            out.append("")
    return out


def _parallel_decrypt(blobs: list, key: str, workers: int | None = None) -> list[str]:
    """Descifra blobs en paralelo preservando el orden. Fallback secuencial."""
    if not blobs:
        return []
    workers = workers or max(1, min(16, (os.cpu_count() or 4) - 1))
    if workers <= 1 or len(blobs) < 2000:
        return _decrypt_chunk((blobs, key))
    size = math.ceil(len(blobs) / workers)
    chunks = [blobs[i:i + size] for i in range(0, len(blobs), size)]
    try:
        with ProcessPoolExecutor(max_workers=min(workers, len(chunks))) as ex:
            results = list(ex.map(_decrypt_chunk, [(c, key) for c in chunks]))
        return [x for chunk in results for x in chunk]
    except Exception:
        return _decrypt_chunk((blobs, key))


def _page_dict(page, plain: str | None = None, hint: str = "", codepages=None) -> dict:
    return {
        "ref": page.ref,
        "title": page.title,
        "body": plain if plain is not None else to_plain(page.raw, hint=hint, codepages=codepages),
        "book": page.book,
        "chapter": page.chapter,
        "verse": page.verse,
        "ord": page.order,
    }


class Indexer:
    def __init__(self, catalog: Catalog, store: ContentStore):
        self.catalog = catalog
        self.store = store

    # ── un módulo ────────────────────────────────────────────────────────
    def index_module(self, module: dict, progress=None) -> int:
        module_id = module["id"]
        path = Path(module["path"])
        self.catalog.set_status(module_id, "indexing")
        started = time.time()
        try:
            with EswordModule(path) as mod:
                if mod.kind == "unknown":
                    self.catalog.set_status(module_id, "skipped", "sin tipo de contenido")
                    return 0
                if mod.kind == "bible" and mod.encrypted:
                    pages = self._bible_pages_parallel(mod, progress)
                else:
                    pages = self._pages_sequential(mod, progress)

            self.store.delete_module(module_id)
            n = self.store.add_pages(module_id, mod_kind_of(module), pages)
            self.catalog.set_status(module_id, "ready", None, entries=n)
            if mod.warnings:
                self.catalog.set_meta(
                    f"warnings:{module_id}",
                    f"{len(mod.warnings)} registros omitidos: {mod.warnings[0]}",
                )
            return n
        except Exception as exc:  # noqa: BLE001 — se reporta en la UI
            self.catalog.set_status(module_id, "failed", str(exc)[:400])
            return 0
        finally:
            _ = time.time() - started

    def _pages_sequential(self, mod: EswordModule, progress=None) -> list[dict]:
        out: list[dict] = []
        total = 0
        for i, page in enumerate(mod.iter_pages(), 1):
            out.append(_page_dict(page, hint=mod.stem, codepages=mod.codepages))
            if progress and i % 500 == 0:
                progress(i, 0, page.title)
        return out

    def _bible_pages_parallel(self, mod: EswordModule, progress=None) -> list[dict]:
        if progress:
            progress(0, 1, "descifrando…")
        rows = list(mod.conn.execute(
            "SELECT Book, Chapter, Verse, Scripture FROM Bible ORDER BY Book, Chapter, Verse"
        ))
        from .books import book_name

        blobs = [r["Scripture"] for r in rows]
        texts = _parallel_decrypt(blobs, str(mod.crypt_key))
        if progress:
            progress(1, 1, "indexando…")
        out = []
        for row, raw in zip(rows, texts):
            b, c, v = row["Book"], row["Chapter"], row["Verse"]
            out.append({
                "ref": f"{b}:{c}:{v}",
                "title": f"{book_name(b)} {c}:{v}",
                "body": to_plain(raw, hint=mod.stem, codepages=mod.codepages),
                "book": b, "chapter": c, "verse": v,
                "ord": b * 1_000_000 + c * 1_000 + v,
            })
        if not any(out):
            # módulo cifrado con clave distinta: no se inventa contenido
            raise RuntimeError("descifrado vacío (clave SQLitePlus incorrecta?)")
        return out

    # ── categorías ───────────────────────────────────────────────────────
    def index_kind(self, kind: str, progress=None) -> dict:
        mods = self.catalog.modules(kind=kind)
        result = {"kind": kind, "total": len(mods), "indexed": 0, "pages": 0,
                  "failed": 0, "errors": []}
        for i, mod in enumerate(mods, 1):
            if progress:
                progress(i, len(mods), mod["title"][:60])
            if mod["kind"] == "unknown":
                continue
            n = self.index_module(mod, progress=None)
            if n:
                result["indexed"] += 1
                result["pages"] += n
            else:
                result["failed"] += 1
                result["errors"].append(mod["rel_path"])
        return result

    def index_paths(self, rel_paths: list[str], progress=None) -> dict:
        mods = [m for p in rel_paths if (m := self.catalog.by_rel_path(p))]
        result = {"total": len(mods), "indexed": 0, "pages": 0, "failed": 0, "errors": []}
        for i, mod in enumerate(mods, 1):
            if progress:
                progress(i, len(mods), mod["title"][:60])
            n = self.index_module(mod)
            if n:
                result["indexed"] += 1
                result["pages"] += n
            else:
                result["failed"] += 1
                result["errors"].append(mod["rel_path"])
        return result

    def index_all(self, progress=None) -> dict:
        return self.index_kind_list(KIND_ORDER, progress)

    def index_kind_list(self, kinds: list[str], progress=None) -> dict:
        mods = [m for k in kinds for m in self.catalog.modules(kind=k)]
        result = {"total": len(mods), "indexed": 0, "pages": 0, "failed": 0, "errors": []}
        for i, mod in enumerate(mods, 1):
            if progress:
                progress(i, len(mods), mod["title"][:60])
            n = self.index_module(mod)
            if n:
                result["indexed"] += 1
                result["pages"] += n
            else:
                result["failed"] += 1
                result["errors"].append(mod["rel_path"])
        return result

    # ── estado ───────────────────────────────────────────────────────────
    def pending_modules(self) -> list[dict]:
        return [
            m for m in self.catalog.modules()
            if m["index_status"] in ("pending", "failed") and m["kind"] != "unknown"
        ]

    def is_ready(self, module_id: int) -> bool:
        mod = self.catalog.module(module_id)
        return bool(mod and mod["index_status"] == "ready")


def mod_kind_of(module: dict) -> str:
    return module.get("kind") or "unknown"
