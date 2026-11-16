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

## `build_match`

User input → MATCH expression.

```
"love"              → "love"*
"love of god"       → "love" AND "of" AND "god"*
'"in the beginning"' → "in the beginning"
```

- The **last** term becomes a prefix: search-as-you-type.
- If `AND` returns nothing, `ContentStore.search()` retries with
  `build_match_or` (OR of terms). Do not change this fallback without
  measuring: it is what keeps a multi-word query from coming back empty.
- Terms are always quoted: this prevents user-supplied `AND`, `OR`, `NEAR`,
  `*` or `-` from breaking the query.

**Never** interpolate user text directly into the MATCH SQL.

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
`SearchView` filters by category with the scope combo. If the scope is empty,
the UI explains that modules must be indexed first.

## Intents

`src/esword4linux/core/search.py:search()` decides in this order:

1. `parse_reference()` → `intent="reference"` (does not touch FTS).
2. `^[GH]\d+$` → `intent="strong"`, scope: lexicons + dictionaries.
3. everything else → `intent="text"`, FTS with `bm25()` + `snippet()`.

The order matters: `John 3:16` must never reach FTS.

## Performance rules

- Always use `LIMIT`. The UI asks for 200; 80 are shown per group.
- `snippet()` with 24 tokens is enough; raising it multiplies the cost.
- Indexing a plain Bible takes a few seconds; an encrypted Bible takes longer
  and uses the process pool.
- The full index of a large library can reach millions of pages; **never**
  build it wholesale unless the user explicitly asks.

## Migrating the schema

If `SCHEMA` in `src/esword4linux/core/store.py` changes,
`CREATE TABLE IF NOT EXISTS` will not update an existing database. Delete
`~/.cache/esword4linux/content.db` (it is regenerable) and document the change.
There are no incremental migrations: the index is a cache.
