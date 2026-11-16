# Performance — budgets and measurements

## Budgets

Measured on the maintainer's reference machine. Treat the budget as the limit,
not the expected value.

| Operation | Budget | Measured |
|---|---|---|
| Start the app and show the Bible | < 1.5 s | ~1 s (no index) |
| Change chapter | < 60 ms | ~10–25 ms |
| Search tens of thousands of indexed pages | < 100 ms | ~10–20 ms |
| Incremental scan | < 1 s | ~0.1 s |
| Cold scan | < 10 s | a few seconds |
| Index a plain Bible | < 15 s | a few seconds |
| Index an encrypted Bible | < 30 s | depends on size and CPU count; uses the pool |
| Show a chapter with commentary | < 100 ms | ~30 ms |

If a change makes a budget more than 2× worse, justify it in the PR or revert
it.

## Where time goes

1. **Twofish decryption** (pure Python, ~284 records/s/core). This is the only
   real cost. It is parallelized with `ProcessPoolExecutor` in
   `src/esword4linux/core/indexer.py:_parallel_decrypt`, with
   `workers = min(16, cpus-1)` and `chunks = ceil(n/workers)`. Pickling the
   blobs is negligible compared with decryption.
2. **RTF → text** while indexing. ~0.15 ms per verse. Acceptable.
3. **FTS5**: insertion fires the triggers. Several seconds for tens of
   thousands of verses.

## Rules

1. **Do not decrypt what will not be used.** `iter_pages()` is a generator;
   the viewer uses `bible_chapter()` / `page_by_ref()`, not `iter_pages()`.
2. **Never index at startup.** There is no preindex list and no default module
   set. Indexing and decryption are explicit: *Index* menu, sidebar context
   menu or the CLI tools. `make scan` only scans metadata; `make encrypted`
   decrypts and indexes encrypted modules on request.
3. **Pool only for large batches.** `_parallel_decrypt` falls back to
   sequential when `len(blobs) < 2000`: starting the pool costs ~1 s and does
   not pay off for small batches.
4. **One query per chapter, not per verse.** `chapter_comments()`.
5. **Always `LIMIT`** in lists and searches.
6. **Cache in the XDG cache directory, never in the modules folder.** The
   catalog and index live in `~/.cache/esword4linux` (honoring
   `XDG_CACHE_HOME`). They are regenerable; the user's modules are read-only.
7. **Tests use isolated paths.** A test cache is a temporary directory, and
   real-module tests read `ESWORD4LINUX_TEST_CORPUS`; tests never measure
   against the developer's cache.

## Measuring

```bash
# Metadata scan with timings (indexing is opt-in)
.venv/bin/python tools/bootstrap.py --resources <MODULES_DIR>

# Add --all, or --kind bible --kind commentary, to index explicitly.
```

```bash
# Search timing
.venv/bin/python - <<'PY'
from esword4linux.config import Settings
from esword4linux.core.context import AppContext
ctx = AppContext(Settings.load())
for q in ["love", "faith", "beginning", "John 3:16"]:
    r = ctx.search.search(q)
    print(f"{q!r:16} {r.intent:9} {len(r.hits):4} hits  {r.elapsed_ms:6.1f} ms")
PY
```

## Cache size

| Library | Pages | `content.db` |
|---|---|---|
| A few modules | tens of thousands | ~25 MB |
| A large library (estimated) | millions | ~1–2 GB |

`content.db` is **regenerable**: if it is corrupted or the schema changes,
delete it and rebuild the parts you need.
