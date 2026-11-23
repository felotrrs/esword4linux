# Index and search (FTS5)

## Principle

**Reading does not depend on the index.** The viewer queries the module and
decrypts what it displays. The index exists only for searching.

Design consequence: the app is usable from the first second even when nothing
has been indexed; search reports `search.no_index` until the relevant modules
are indexed.

## Build scope is explicit

Nothing is indexed at startup. A scan reads metadata only. Indexing runs when
the user asks for it:

- *Index* menu: all categories, pending modules, encrypted modules, or one
  category. The sidebar context menu can index one category or one module.
- `tools/bootstrap.py --all` / `--kind KIND` for the CLI.
- `tools/prepare_encrypted.py` (`make encrypted`) for encrypted modules.

There is no preindex list and no default module set. Each module keeps its own
`pending → indexing → ready | failed` state, so categories can be indexed
independently.

## Schema (`content.db`)

```sql
page(id PK, module_id, kind, ref, title, body, book, chapter, verse, ord)
  UNIQUE(module_id, ref)
page_fts USING fts5(body, title,
                    content='page', content_rowid='id',
                    tokenize="unicode61 remove_diacritics 2")
```

- `content='page'` → external-content FTS5: the text is not duplicated.
- `remove_diacritics 2` → `amor` finds `amór`, `Genesis` = `Génesis`.
- Triggers `page_ai` / `page_ad` / `page_au` keep FTS in sync. Never insert
  into `page_fts` by hand.

## Indexable unit per type

| `kind` | Page | `ref` |
|---|---|---|
| `bible` | one verse | `43:3:16` |
| `commentary` | one verse/chapter/book comment | `43:3:16` / `43:3` / `43` |
| `dictionary`, `lexicon` | one entry | the `Topic` |
| `reference` | one thematic chapter | the `Chapter` |
| `topic` | one topic | the `Title` |
| `devotion` | one day | `03-16` |
| `harmony` | one section (with its parallel passages) | `section` |
| `maps` | one entry (title + caption) | the `Title` |
| `twm` | one topic | the `id` |

## `build_match` — the four modes

User input → MATCH expression. The mode comes from the combo next to the search
box (`core/store.py:MODE_*`):

| Mode | Expression |
|---|---|
| `all` (default) | `"love" AND "of" AND "god"*` — every term; the last is a prefix |
| `any` | `"love" OR "of" OR "god"` — one term is enough |
| `phrase` | `"love of god"` — the words together, in order |
| `regex` | the literal words of the pattern, OR-ed (see below) |

- **`all` is strict**: there is **no silent OR fallback** any more. “All of the
  words” means all; the user who wants a fallback picks “Any of the words”.
- Terms are always quoted: this prevents user-supplied `AND`, `OR`, `NEAR`,
  `*` or `-` from breaking the query.
- **Never** interpolate user text directly into the MATCH SQL.

### Regular expressions

FTS5 has no regex, so the engine uses the standard two-step approach:

1. `regex_literals(pattern)` extracts the literal words (`\bpaz\b` → `paz`,
   `gen.*` → `gen*`, `paz.*genesis` → `paz*` + `genesis*`). Escape classes
   (`\d`, `\w`, `\b`…) are removed before tokenising, so `\bpaz\b` never
   becomes `bpaz`.
2. FTS5 narrows the candidates with those literals **OR-ed** (a superset), then
   `re.search(pattern, body, re.IGNORECASE)` filters the rows in Python and the
   list is trimmed to the limit. Candidates are fetched with a wider cap
   (limit × 10, max 2000).

An invalid pattern returns `note="regex_error"` with `note_detail`; a pattern
without any searchable word returns `note="regex_empty"`. The view shows an
explicit message in both cases — never a silent empty list.

## Indexing state

Lives in `catalog.db`:

```
pending → indexing → ready | failed
```

- `indexer.index_module()` marks `indexing`, writes pages and marks `ready`.
- A failure leaves `failed` + `index_error` (first 400 chars).
- Pages are deleted and reinserted per module: `store.delete_module()`.
- The catalog does not reindex when `size`+`mtime` are unchanged (incremental
  scan). A metadata change that alters type, structure or entry count resets
  the content index to `pending`.

## Search scope

`SearchEngine.indexed_module_ids(kinds)` returns only `ready` modules. The
`SearchView` narrows the search with the filter row; if the scope is empty, the
UI explains that modules must be indexed first.

## Filters (`SearchFilters`)

`SearchView` keeps the filter state; `SearchEngine` owns the semantics:

| Filter | Text intent | Strong intent | Reference intent |
|---|---|---|---|
| `kinds` (type) | restricts the modules | restricts the modules | ignored (navigation shortcut) |
| `module_id` (work) | restricts the module | restricts the module | ignored |
| `book` / `chapter` | SQL predicates on `page` | not applicable → ignored | ignored |
| `book_range` / `chapter_range` | `BETWEEN` predicates on `page` | not applicable → ignored | ignored |

- **No filter selected ⇒ the legacy path is used unchanged** (`scope` argument,
  `indexed_module_ids()`).
- `filters` takes precedence over the legacy `scope` when both are supplied.
- Book and chapter predicates are applied on the row already joined from
  `page_fts`. **No schema change and no reindex**: the columns and
  `idx_page_loc(book, chapter, verse)` already exist. The predicates only
  remove results.
- The UI rule: the Bible filters are **available only** while the type is
  Bible; for any other type they are disabled, cleared and contribute `None`.
  Selecting a Bible work under *All types* does not reveal them.

### Activation hierarchy

`SearchView` enforces it (see `skills/design.md` §5):

```
Testament → Group → Books range → Book → Chapters range → Chapter
```

- Exact ↔ range of the same dimension are **mutually exclusive** (the newest
  wins; the other is disabled and cleared). This is why the engine never sees
  `book` and `book_range` together, nor `chapter` and `chapter_range`.
- A **book range disables the whole chapter dimension**: chapter numbers belong
  to a book, so there is no single numbering across a range.
- Ranges are **forward-only** (`book_to ≥ book_from`, `chapter_to ≥
  chapter_from`).
- The lists narrow themselves: groups ⊂ testament, books ⊂ testament ∩ group,
  and everything ∩ the books the indexed Bibles actually contain (the
  Apocrypha appears only when a Bible carries it).

### `SearchFilters`

```python
SearchFilters(kinds, module_id, book, chapter, book_range, chapter_range)
```

`is_active()` drives the **Reset filters** button and the “Filters:” summary in
the status line. The instance is built from the *visible, enabled* state only:
a disabled control returns `None`, so a stale value can never filter.

### Book, testament and chapter lists

- Book names come from `core/books.py`; the *available* books and chapters come
  from the modules themselves (`EswordModule.books()` and the new
  `EswordModule.chapters(book)`), never from an invented table.
- A specific work: that module only. No work: the **union** over every indexed
  Bible in the effective scope.
- `chapters(book)` is `SELECT DISTINCT Chapter FROM Bible WHERE Book=? ORDER BY
  Chapter` — answered by the module's own `BookChapterVerseIndex` as a covering
  index (≈1 ms, and it never reads the encrypted `Scripture` column). Do **not**
  derive the list from `chapter_count()` (MAX): a gap in the numbering would
  become an invented chapter.
- Testaments and canonical groups live in `books.yaml` (`testaments:`,
  `groups:`, inclusive id ranges) and are exposed as `TESTAMENTS` /
  `BOOK_GROUPS`; `BookRange.label(lang)` gives the localized name.
- The computation runs in a `Worker`, never on the UI thread. Each request
  carries a generation id; `SearchView` applies a result only when its worker is
  still current and its generation is still the newest of its kind. A stale
  answer can never overwrite a newer selection, and `shutdown()` (called from
  `MainWindow.closeEvent`) interrupts the worker before the widgets die.

## Search on demand

The index is **never queried while typing**. `SearchView` keeps an
`_approved_query`:

- **Enter**, the **Search** button and `set_query()` commit the current text
  and search it (a reference navigates only on an explicit action).
- A **filter/mode change** re-runs the *committed* query, never the half-typed
  text.
- While the box holds an uncommitted query, the hint line shows
  `search.press_enter`.

## Result previews and hints

- Hits are rendered as **underlined links** (`.hit a` in the document CSS).
- The results pane is a `RichBrowser`: hovering a hit calls
  `SearchView._resolve_hit()` with `hit:<module_id>:<ref>`, which opens *that*
  module, reads `page_by_ref(ref)` and shows **the passage text of the version
  the hit came from** in the `TipBubble` card (header: “ABBR — Work · Ref”).
  The bubble caches each result, so the second read happens once per hit.
- A hint line under the filters explains an empty library
  (`search.no_library`), a category without indexed modules
  (`search.category_not_indexed`) or a totally empty index (`search.no_index`).
  An empty combo must never look like a broken feature.

## Intents

`src/esword4linux/core/search.py:search()` decides in this order:

1. `parse_reference()` → `intent="reference"` (does not touch FTS, ignores the
   filters and the mode: it is a navigation shortcut).
2. `MODE_REGEX` → compile and validate the pattern before touching the index
   (`regex_error` / `regex_empty`).
3. `^[GH]\d+$` → `intent="strong"`, scope: lexicons + dictionaries (the mode
   applies).
4. everything else → `intent="text"`, FTS with `bm25()` + `snippet()`.

The order matters: `John 3:16` must never reach FTS.

## Performance rules

- Always use `LIMIT`. The UI asks for 200; 80 are shown per group.
- `snippet()` with 24 tokens is enough; raising it multiplies the cost.
- The regex mode fetches up to `limit × 10` candidates (max 2000) because the
  Python filter discards most of them; keep that cap in mind before raising it.
- Indexing a plain Bible takes a few seconds; an encrypted Bible takes longer
  and uses the process pool.
- The full index of a large library can reach millions of pages; **never**
  build it wholesale unless the user explicitly asks.

## Migrating the schema

If `SCHEMA` in `src/esword4linux/core/store.py` changes,
`CREATE TABLE IF NOT EXISTS` will not update an existing database. Delete
`~/.cache/esword4linux/content.db` (it is regenerable) and document the change.
There are no incremental migrations: the index is a cache.
