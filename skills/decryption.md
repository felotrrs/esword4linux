# SQLitePlus decryption (Twofish-128)

## What is encrypted

Only modules that contain the `sqliteplus_license` table (also called
SQLitePlus). In a real-world library this is a **subset** of the modules; never
assume that every file is encrypted.

The rest is plain SQLite: there is nothing to decrypt and it must not be passed
through Twofish (useless cost).

## When decryption runs

Decryption is **explicit**, never automatic:

- `make encrypted` (`tools/prepare_encrypted.py`) decrypts and indexes every
  encrypted module that is not `ready` yet; it is idempotent.
- The *Index → Decrypt encrypted modules* menu action does the same from the UI.
- Reading a single displayed record decrypts only that record (lazy read).

A fresh scan stores metadata only. It never decrypts whole modules.

## Schema

```
encrypted blob
   │  Twofish-128-ECB, key "Heb_4:12" (16 bytes, zero padding)
   ▼
9-byte header
   [0]      checksum/bitfield (ignored)
   [1..3]   u24 LE compressedSize   ← 24 bits, not 16!
   [4]      magic 0x1F
   [5..8]   u32 LE expectedSize
   ▼
zlib stream (from byte 9, length compressedSize - 4)
   ▼
decrypted payload (RTF, HTML or plain text)
```

**Documented trap**: reading `compressedSize` as `u16` truncates records whose
zlib stream exceeds 64 KiB (for example, long dictionary articles) and makes
decryption of the whole module fail. Always read it as `u24`.

## Key

`DEFAULT_SQLITEPLUS_KEY = "Heb_4:12"`. It can be overridden per module
(`EswordModule(path, crypt_key=...)`) for third-party modules.

## Performance

Pure-Python Twofish: **~284 records/s per core**.

| Encrypted library | 1 core | Process pool |
|---|---|---|
| Large library | tens of minutes | minutes, scaled by CPU count |

That is why `src/esword4linux/core/indexer.py` uses a `ProcessPoolExecutor` for
encrypted Bibles (`_parallel_decrypt`) and falls back to sequential processing
if the pool fails. The pool is only used for large batches (see
`skills/performance.md`).

**On-demand reading**: displaying one verse decrypts 1 blob (~3 ms). Decrypting
in the UI thread for a single entry is fine; a whole chapter of an encrypted
module (30–40 blobs ≈ 120 ms) is not. Cache the chapter if it becomes
noticeable.

## Rules

1. **Never invent content.** If a blob does not decrypt, it is skipped and
   recorded in `mod.warnings` / `catalog.set_status(..., "failed", ...)`.
   It is never replaced with text from another source.
2. **Do not decrypt columns that are not content.** Only those in
   `CONTENT_COLUMNS` (`Scripture`, `Comments`, `Definition`, `Notes`,
   `Content`, `Devotion`, `Details`, `data`, `Reference`). A `Picture` column
   in a `.mapx` is an image: decrypting it corrupts it.
3. **The core is vendored.** `twofish.py`, `sqliteplus.py`, `rtf.py`,
   `font_codepages.py`, `legacy_translit.py` come from an upstream shared
   library. `make drift` compares hashes when
   `ESWORD4LINUX_VENDOR_ORIGIN` (or `--origin DIR`) is set; otherwise it skips
   cleanly. If you change something, document the reason in
   `docs/CHANGELOG.md`.
4. **`sqliteplus.py` only changes the import** (`from .twofish import
   Twofish128`). Any other change is drift and must be justified.

## Verify

```bash
.venv/bin/python -c "
from esword4linux.core.esword.sqliteplus import self_test
from esword4linux.core.esword.twofish import self_test as t
assert t() and self_test(); print('vectors OK')"

.venv/bin/python -c "
from esword4linux.core.esword.module import EswordModule
m = EswordModule('<MODULES_DIR>/bible.bblx')
print(m.encrypted, m.bible_verse(1, 1, 1).raw)"
```
