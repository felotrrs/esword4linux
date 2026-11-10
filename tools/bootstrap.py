#!/usr/bin/env python3
"""Bootstrap de linuxEsword: escanea la carpeta de recursos y pre-indexa la base.

Uso:
    python tools/bootstrap.py [--resources DIR] [--cache DIR] [--all] [--kind KIND]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from linuxesword.config import Settings  # noqa: E402
from linuxesword.core.catalog import KIND_LABELS, Catalog  # noqa: E402
from linuxesword.core.indexer import Indexer  # noqa: E402
from linuxesword.core.search import SearchEngine  # noqa: E402
from linuxesword.core.store import ContentStore  # noqa: E402


def bar(done: int, total: int, label: str) -> None:
    pct = (done / total * 100) if total else 0
    sys.stderr.write(f"\r  [{pct:5.1f}%] {done}/{total} {label[:50]:50}")
    if done >= total:
        sys.stderr.write("\n")
    sys.stderr.flush()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--resources")
    ap.add_argument("--cache")
    ap.add_argument("--all", action="store_true", help="indexar todas las categorías")
    ap.add_argument("--kind", action="append", default=[])
    ap.add_argument("--force-scan", action="store_true")
    args = ap.parse_args()

    settings = Settings.load()
    if args.resources:
        settings.resources_dir = args.resources
    if args.cache:
        settings.cache_dir = args.cache

    print(f"Recursos: {settings.resources_dir}")
    print(f"Cache:    {settings.cache_dir}")

    catalog = Catalog(settings.catalog_db)
    store = ContentStore(settings.content_db)

    t0 = time.time()
    if args.force_scan or catalog.is_empty():
        print("\n== Escaneando carpeta de recursos ==")
        result = catalog.scan(settings.resources_path, progress=bar)
        print(
            f"  {result.total} archivos · {result.added} nuevos · "
            f"{result.updated} actualizados · {result.skipped} sin cambios · "
            f"{result.errors} errores · {result.seconds:.1f}s"
        )
    else:
        print(f"\n== Catálogo ya existente ({catalog.get_meta('last_scan')}) ==")

    counts = catalog.counts_by_kind()
    print("\n== Módulos por categoría ==")
    for kind, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        label = KIND_LABELS.get(kind, (kind, kind))[0]
        print(f"  {n:4d}  {label}")

    indexer = Indexer(catalog, store)
    pending_pre = [
        m for m in catalog.modules()
        if m["rel_path"] in settings.preindex and m["index_status"] != "ready"
    ]

    if args.all or args.kind:
        kinds = args.kind or [k for k in counts if k != "unknown"]
        for kind in kinds:
            print(f"\n== Indexando categoría: {kind} ==")
            t = time.time()
            res = indexer.index_kind(kind, progress=bar)
            print(f"  {res['indexed']}/{res['total']} módulos · {res['pages']} páginas "
                  f"· {res['failed']} fallidos · {time.time()-t:.1f}s")
    elif pending_pre:
        print(f"\n== Pre-indexando {len(pending_pre)} módulos base ==")
        t = time.time()
        for mod in pending_pre:
            print(f"  · {mod['title'][:60]} ({mod['entries']} entradas, "
                  f"{'cifrado' if mod['encrypted'] else 'plano'})")
            n = indexer.index_module(mod, progress=bar)
            if not n:
                err = catalog.module(mod["id"]).get("index_error")
                print(f"    !! fallo: {err}")
            print(f"    → {n} páginas en {time.time()-t:.1f}s")
            t = time.time()

    store_total = store.total_pages()
    print(f"\n== Índice: {store_total} páginas · {store.db_size()/1e6:.1f} MB ==")

    engine = SearchEngine(catalog, store)
    for q in ["Juan 3:16", "amor", "fe", "G2316", "principio"]:
        res = engine.search(q)
        print(f"\n  '{q}' → intención={res.intent} hits={len(res.hits)} "
              f"({res.elapsed_ms:.0f} ms) {res.note}")
        for hit in res.hits[:3]:
            print(f"     [{hit.module_abbrev}] {hit.title} — "
                  f"{hit.snippet.replace('<b>','').replace('</b>','')[:90]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
