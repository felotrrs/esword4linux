#!/usr/bin/env python3
"""Descifra e indexa todos los módulos cifrados (SQLitePlus).

Se ejecuta una sola vez: deja los módulos cifrados listos para consultarse y
buscarse. Es idempotente; los ya indexados se omiten.

Uso:
    python tools/prepare_encrypted.py [--force]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from linuxesword.config import Settings  # noqa: E402
from linuxesword.core.catalog import Catalog  # noqa: E402
from linuxesword.core.indexer import Indexer  # noqa: E402
from linuxesword.core.store import ContentStore  # noqa: E402


def bar(done: int, total: int, label: str) -> None:
    pct = (done / total * 100) if total else 0
    sys.stderr.write(f"\r  [{pct:5.1f}%] {done}/{total} {label[:55]:55}")
    if done >= total:
        sys.stderr.write("\n")
    sys.stderr.flush()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="reindexar aunque estén listos")
    args = ap.parse_args()

    settings = Settings.load()
    catalog = Catalog(settings.catalog_db)
    store = ContentStore(settings.content_db)

    encrypted = [m for m in catalog.modules() if m["encrypted"]]
    pending = encrypted if args.force else [m for m in encrypted if m["index_status"] != "ready"]

    print(f"Módulos cifrados: {len(encrypted)} · pendientes: {len(pending)}")
    if not pending:
        print("Todos listos.")
        return 0

    indexer = Indexer(catalog, store)
    total_pages = 0
    failed = []
    started = time.time()
    for i, mod in enumerate(pending, 1):
        print(f"\n[{i}/{len(pending)}] {mod['title'][:60]}")
        print(f"        {mod['entries']} entradas · {mod['size']/1e6:.1f} MB · {mod['rel_path']}")
        t0 = time.time()
        n = indexer.index_module(mod, progress=bar)
        if n:
            total_pages += n
            print(f"        → {n} páginas en {time.time()-t0:.1f}s")
        else:
            err = catalog.module(mod["id"]).get("index_error")
            failed.append((mod["rel_path"], err))
            print(f"        !! fallo: {err}")

    elapsed = time.time() - started
    print(f"\n=== {len(pending)-len(failed)}/{len(pending)} módulos · "
          f"{total_pages} páginas · {elapsed/60:.1f} min ===")
    if failed:
        print("Fallidos:")
        for rel, err in failed:
            print(f"  - {rel}: {err}")
    if not failed:
        settings.encrypted_ready = True
        settings.save()
    print(f"Índice total: {store.total_pages()} páginas · {store.db_size()/1e6:.0f} MB")
    catalog.close()
    store.close()
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
