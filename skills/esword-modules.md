# e-Sword modules — reading and classification

## Fundamental fact

**All** modern e-Sword modules are SQLite databases. There is no proprietary
binary format to parse: open the SQLite file and inspect its tables.

```
$ file bible.bblx
SQLite 3.x database ... UTF-16 little endian
```

## The extension lies

Real-world collections contain:

- `.refx` files with a `Topics` table → they are **Topics**, not References.
- `.cmtx` files with `VerseCommentary` → the **old** commentary schema, not
  the new one (`Books`/`Chapters`/`Verses`).
- `.bbli` files → same structure as `.bblx`, but with `Scripture` stored as
  TEXT (unencrypted).

That is why `EswordModule._detect_structure()` decides by tables, in this order:

| Structure | Tables | `kind` |
|---|---|---|
| `bible` | `Bible` | `bible` |
| `commentary` | `Verses` \| `VerseCommentary` \| `BookCommentary` \| `ChapterCommentary` | `commentary` |
| `dictionary` | `Dictionary` | `dictionary` |
| `lexicon` | `Lexicon` | `lexicon` |
| `devotion` | `Devotions` \| `Devotional` | `devotion` |
| `harmony` | `Sections` + `Parts` | `harmony` |
| `maps` | `Graphics` | `maps` |
| `reference` | `Reference` | `reference` (biblical citations) \| `book` (book chapters) |
| `topic` | `Topics` | `topic` \| `book` |
| `twm` | `topics` (+ `config`, `content`) | `dictionary` \| `book` \| `topic` |

**Catalog exception**: some commentaries are distributed with the dictionary
schema (`Dictionary`, one entry per chapter). `Catalog._probe()` catalogs them
as `commentary` when the title or abbreviation contains
"comentario"/"commentary"; the structure read from the module remains
`dictionary`.

**Content heuristic**: `EswordModule._detect_kind()` inspects the actual table
contents:

- In `Reference`, if `Chapter` entries are biblical citations
  (`book:chapter:verse`), the kind is `reference`; if they are literary
  chapters or treatises, it is classified as `book`.
- In `twm`, the contents of `config` and the terms in `topics` decide whether
  it is a `dictionary`, a `book` or a `topic`.
- Modules with 0 entries, or only UI tables (`localize`, `headings`), are
  hidden by default in the UI.

**Order matters**: `topics` (TWM) and `Topics` (topic) differ only by the case
of the name and by the presence of `config`.

## Metadata

`Details` has no fixed schema:

- `.bblx` / `.cmti` / `.refi` / `.dctx` → `Title, Abbreviation, Information, Version`
- `.devx` / `.harx` / `.mapx` → `Description, Abbreviation, Comments, Version`
- `.twm` → no `Details`; the title lives in `config` (`name='title'`)

`EswordModule.details()` normalizes this: it looks for `Title` and falls back to
`Description`, and `Information` falls back to `Comments`.

## Adding a new type

1. Add detection in `_detect_structure()` **before** the structures that could
   collide by table name.
2. Add `_pages_<structure>()` producing `Page(ref, title, raw, order)`.
3. Add the entry to `src/esword4linux/core/catalog.py:KIND_LABELS` and
   `KIND_ORDER` (the single source).
4. Add `page_by_ref()` so the viewer does not have to walk the whole module.
5. Add `list_entries()` if the viewer needs a navigable index.
6. Add the case to `iter_pages()` (dispatch) — it is implicit by name.
7. Test it in `tests/test_module.py` against a real module from
   `ESWORD4LINUX_TEST_CORPUS` (the test skips when the variable is unset), or
   with a small synthetic module.

## Queries: never walk a module for one entry

`get_page(ref)` iterates the whole module: it is the **fallback**. Use
`page_by_ref(ref)` and `bible_chapter(book, chapter)`, which issue a direct
`SELECT`. A large dictionary (tens of thousands of entries) cannot scan every
row each time the user types a letter.

## Maps and illustrations (`.mapx`)

`Graphics` stores `Title`, `Details` (legend) and `Picture` (image BLOB). Three
real-world quirks are already handled in `EswordModule`:

- **UTF-16LE BLOB titles**: in some map modules, later entries store `Title` as
  bytes. Decode it with `_text_value()` and locate the row by `rowid`
  (`_graphics_rowid()`); a `WHERE Title=?` against the decoded text finds
  nothing.
- **`lt\0\0` + size wrapper**: some modules prepend 8 bytes to a BMP.
  `_unwrap_picture()` strips them so Qt can load the image.
- **Encrypted legend without zlib**: some map modules encrypt `Details` with
  SQLitePlus but store uncompressed UTF-16LE RTF (a 5-byte header with magic
  `0x1F`). `decrypt_payload()` fails while looking for the zlib stream;
  `_decode_uncompressed_sqliteplus()` recognizes that format and returns the
  text.

## Commentaries with only `BookCommentary`

Some commentaries have empty `VerseCommentary`/`ChapterCommentary` tables and
keep all the text in `BookCommentary`. Two rules:

- `count_entries()` sums **all** tables in `_comment_specs()`, not only the
  first one that exists (previously it returned 0 and the catalog hid the
  module).
- `page_by_ref()` accepts single-part refs (`"43"`) for book commentaries, in
  addition to `"43:3"` and `"43:3:16"`.

## Harmonies (`.harx`)

`Parts` has **one row per reference**, so several rows share a
`(Section, Part)`. The navigable unit is the **section**: one `Page` per
`Section`, with the cleaned title (no RTF) and all its references in `raw`
(deduplicated, one per line). `list_entries()` returns one entry per section
and `page_by_ref("3")` reconstructs it. The old `"3:1"` is accepted as an
alias, but the canonical `ref` is the section.

## Expected errors

| Error | Cause | Policy |
|---|---|---|
| `ModuleError` (cannot open the file) | file moved or corrupted | the catalog marks it `failed`; the UI stays alive |
| Empty entry after decryption | different SQLitePlus key | skipped with a warning; **never** backfilled |
| `0` entries | empty module at the source | the UI shows `lib.empty` |

## Duplicates

`tools/deduplicate.py` groups by size and confirms with **sha256**. The
`keep_score` decides which copy is kept:

1. canonical folder for the type (`BIBLES`/`COMMENTARIES`/`DICTIONARIES`/`BOOKS`) +30;
2. normalized e-Sword filename (`bible_`, `comment_`, `dicc_`…) +20;
3. similarity between filename and internal title ×12;
4. the more descriptive name (length) as a tiebreaker.

`--apply` moves redundant copies to `_duplicados/<date>/` and writes a
manifest (path, sha256, kept copy). It never deletes by default. The report
written by `--write-report` goes to `reports/duplicates.md`.

`Catalog.scan()` **excludes** `_duplicados/` (and VCS/hidden folders) and
purges rows for modules that are no longer on disk. The order matters:
**purge first, then `_mark_duplicates()`**. Reversed, `duplicate_of` values
dangle from deleted rows and the module disappears from the sidebar for no
reason.

## Strong lexicon with fallback

`StrongIndex._resolve_page(code)` tries the selected lexicon and, if it lacks
the entry, walks the candidates. A Hebrew-only lexicon therefore does not leave
Greek numbers empty (`G2316`). The tooltip shows the abbreviation of the
lexicon that supplied the entry, not the selected one.
