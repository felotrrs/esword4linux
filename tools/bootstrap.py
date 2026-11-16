#!/usr/bin/env python3
"""Scan the modules folder and optionally build its search index.

By default this tool only scans metadata; indexing is always explicit.

Usage:
    python tools/bootstrap.py --resources DIR [--cache DIR] [--all]
    python tools/bootstrap.py --resources DIR --kind bible --kind commentary
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from esword4linux.config import Settings  # noqa: E402
from esword4linux.core.catalog import KIND_LABELS, Catalog  # noqa: E402
from esword4linux.core.indexer import Indexer  # noqa: E402
from esword4linux.core.search import SearchEngine  # noqa: E402
from esword4linux.core.store import ContentStore  # noqa: E402


def bar(done: int, total: int, label: str) -> None:
    pct = (done / total * 100) if total else 0
    sys.stderr.write(f"\r  [{pct:5.1f}%] {done}/{total} {label[:50]:50}")
    if done >= total:
        sys.stderr.write("\n")
    sys.stderr.flush()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--resources", help="folder containing the e-Sword modules")
    ap.add_argument("--cache", help="cache folder for catalog.db and content.db")
    ap.add_argument("--all", action="store_true", help="index every category")
    ap.add_argument("--kind", action="append", default=[], help="index one category")
    ap.add_argument("--force-scan", action="store_true", help="rescan every file")
    ap.add_argument("--search", action="append", default=[],
                    help="run a search query after indexing")
    args = ap.parse_args()

    settings = Settings.load()
    if args.resources:
        settings.resources_dir = args.resources
    if args.cache:
        settings.cache_dir = args.cache

    resources = settings.resources_path
    if resources is None or not resources.is_dir():
        print("No modules folder selected. Use --resources DIR or choose one "
              "in the application.", file=sys.stderr)
        return 2

    print(f"Modules: {resources}")
    print(f"Cache:   {settings.cache_dir}")

    catalog = Catalog(settings.catalog_db)
    store = ContentStore(settings.content_db)

    t0 = time.time()
    if args.force_scan or catalog.is_empty():
        print("\n== Scanning modules folder ==")
        result = catalog.scan(resources, progress=bar)
        print(
            f"  {result.total} files · {result.added} new · "
            f"{result.updated} updated · {result.skipped} unchanged · "
            f"{result.errors} errors · {result.seconds:.1f}s"
        )
    else:
        print(f"\n== Catalog already exists ({catalog.get_meta('last_scan')}) ==")

    counts = catalog.counts_by_kind()
    print("\n== Modules by category ==")
    for kind, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        label = KIND_LABELS.get(kind, (kind, kind))[1]
        print(f"  {n:4d}  {label}")

    indexer = Indexer(catalog, store)
    if args.all or args.kind:
        kinds = args.kind or [k for k in counts if k != "unknown"]
        for kind in kinds:
            print(f"\n== Indexing category: {kind} ==")
            t = time.time()
            res = indexer.index_kind(kind, progress=bar)
            print(f"  {res['indexed']}/{res['total']} modules · {res['pages']} pages "
                  f"· {res['failed']} failed · {time.time()-t:.1f}s")
    else:
        print("\nCatalog scanned. No modules were indexed.")
        print("Build search indexes later with --all, --kind, or the Index menu.")

    store_total = store.total_pages()
    print(f"\n== Index: {store_total} pages · {store.db_size()/1e6:.1f} MB ==")

    if args.search:
        engine = SearchEngine(catalog, store)
        for query in args.search:
            res = engine.search(query)
            print(f"\n  {query!r} -> intent={res.intent} hits={len(res.hits)} "
                  f"({res.elapsed_ms:.0f} ms) {res.note}")
            for hit in res.hits[:3]:
                print(f"     [{hit.module_abbrev}] {hit.title} — "
                      f"{hit.snippet.replace('<b>','').replace('</b>','')[:90]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
