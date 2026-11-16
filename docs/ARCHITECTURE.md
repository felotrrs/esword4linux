# esword4linux architecture

## Public release

esword4linux distributes **no e-Sword module content**: no Bibles, commentaries,
dictionaries, lexicons, maps or any other module is bundled with the application
or downloaded on its behalf. The user selects a folder containing modules they
already own, and that folder is treated as strictly **read-only**: every module
is opened with `mode=ro`, and no file inside it is ever written, renamed or
normalised. The catalog and the search index live outside the modules folder,
in the user's cache directory.

## Problem

e-Sword is a Win32 application that requires Wine on Linux, and its UI groups
the library into fixed tabs by type, which makes hundreds of modules awkward to
navigate. esword4linux addresses both issues:

1. **Native module reading** — there is no emulation: the modules are SQLite
   databases and are opened directly.
2. **A reorganised experience** — a single modules folder, automatic
   classification, a collapsible sidebar and freely arranged central panels.

## Layers

```
src/esword4linux/ui/          PySide6. Presentation and coordination only.
  main_window · sidebar · workspace · bible_view ·
  commentary_pane · library_view · search_view ·
  entry_dialog · preferences_dialog · first_run
──────────────────────────────────────────────────────────────
src/esword4linux/core/        Pure logic, no Qt. Testable headless.
  catalog · indexer · store · search · books · text · context
──────────────────────────────────────────────────────────────
src/esword4linux/core/esword/ Format access. Only SQLite boundary.
  module · sqliteplus · twofish · rtf · font_codepages
──────────────────────────────────────────────────────────────
Modules folder (read-only)
```

`core/` does not import PySide6 anywhere. That makes it possible to run the
engine from the CLI (`tools/bootstrap.py`) and to test it without a graphical
server.

## Startup flow

```
Settings.load()                     # ~/.config/esword4linux/settings.json
   │
   ├─ no modules folder yet
   │    └─ FirstRunDialog            # before the main window is created
   │         ├─ Cancel → exit
   │         └─ folder chosen → save settings
   │
   ├─ AppContext
   │    ├─ Catalog(~/.cache/esword4linux/catalog.db)   # metadata, index state
   │    ├─ ContentStore(~/.cache/esword4linux/content.db)  # page + page_fts
   │    └─ SearchEngine
   │
   ├─ MainWindow
   │    ├─ Sidebar.refresh()         # tree from catalog.db
   │    ├─ first workspace resource  # first available Bible, else first module
   │    └─ QTimer 200 ms → _bootstrap()
   │           └─ catalog empty or metadata stale → Worker: Catalog.scan()
   │
   └─ app.exec()
```

On first run, before the main window opens, a dialog asks for the user's modules
folder. Cancelling the dialog exits the application. The window is shown
**before** any scan runs and reading works from the first instant.

The first scan reads **metadata only**: structure, title, abbreviation,
language, encryption flag and entry count. It never builds the FTS5 index and
never decrypts module content. Indexing and decryption happen only when the user
chooses an action from the **Index** menu, or when a tool such as
`tools/bootstrap.py` is run explicitly. There is no preindex list and no default
Bible: the catalog produced from the user's folder is the only inventory.

## Two independent paths

| | Reading | Search |
|---|---|---|
| Source | SQLite module | `content.db` (FTS5) |
| Cost | 1 `SELECT` (+ decryption of 1 record) | index query |
| Depends on the index | **no** | **yes** |
| Blocks the UI | no (< 30 ms) | no (< 100 ms) |

This separation is the central decision: it allows indexing on demand without
degrading the reading experience.

## Tab model

```
QTabWidget
 ├── [0] Search            (fixed)
 └── [1..] Workspace       (one per study group)
       ├── main resource (Bible | dictionary | commentary | ...)
       ├── if a Bible: parallel Bible (horizontal split)
       └── if a Bible: commentary (bottom vertical split)
```

Selecting a resource in the sidebar does **not** create a tab: it replaces the
main resource of the active tab. Creating a new group is explicit (`＋` /
`Ctrl+T`). This prevents tab proliferation and preserves reading context.

## Scanning

`Catalog.scan()` walks the folder recursively, filtering by extension, and for
each file:

1. `stat()` → if `size` and `mtime` are unchanged, skip it (incremental).
2. `_probe()` opens the module, detects its structure, reads `Details` and
   counts entries.
3. `_upsert()` stores metadata and a `fingerprint` (sha1 of size + first
   64 KiB).
4. `_mark_duplicates()` marks identical copies by fingerprint; the UI hides
   them unless requested.

The first scan covers the entire folder. Later scans are incremental and only
re-probe files whose size, timestamp or classification changed.

## Indexing

```
Index menu action (or an explicit CLI tool)
   │
index_module(row)
   ├─ kind == "bible" and encrypted → _bible_pages_parallel()
   │      SELECT all rows → ProcessPoolExecutor → decryption
   └─ everything else → _pages_sequential()
   │
   ├─ store.delete_module(id)        # idempotent
   ├─ store.add_pages(...)           # triggers → page_fts
   └─ catalog.set_status("ready")
```

The worker runs in a `QThread` with SQLite connections **created inside that
thread**. The main thread keeps reading from the module without touching those
connections.

Decryption is opt-in as well: **Index → Decrypt encrypted modules** (or
`make encrypted`) decrypts and indexes SQLitePlus modules once, so later reads
and searches do not have to wait for decryption.

## Search

```
search(query)
   ├─ parse_reference()  → intent=reference
   ├─ ^[GH]\d+$          → intent=strong   (lexicons + dictionaries)
   └─ everything else    → intent=text     (FTS5 + bm25 + snippet)
```

`build_match` quotes each term (preventing FTS syntax injection) and turns the
last one into a prefix. If `AND` returns no results, it retries with `OR`.

## Configuration and preferences

`Settings` is the single source of configuration. **Edit → Preferences**
(`Ctrl+,`) edits two blocks:

- **Appearance**: light/dark theme and three independent typographic roles
  (interface, Scripture and running text). `src/esword4linux/ui/theme.py`
  projects them into
  `ui_stylesheet(settings)` (QSS) and `document_css_for(settings)` (viewers).
- **Language**: the interface locale (`es`/`en`). On save, `MainWindow`
  rebuilds the menus and calls `retranslate()` on every view; tabs are not
  recreated and state is preserved.

The dialog preview uses the same theme functions as the window, so there is no
second palette to maintain. The **View** menu does not duplicate theme or
language settings: it only contains view options. The modules folder can be
changed later from **File → Change modules folder**.

## Persistence

| What | Where | Regenerable |
|---|---|---|
| Preferences, geometry, tabs | `~/.config/esword4linux/settings.json` | yes |
| Catalog | `~/.cache/esword4linux/catalog.db` | yes (rescan) |
| FTS5 index | `~/.cache/esword4linux/content.db` | yes (reindex) |
| e-Sword modules | user-selected modules folder | **no — immutable** |

Both directories follow the XDG base-directory conventions and can be relocated
with `XDG_CONFIG_HOME` and `XDG_CACHE_HOME`.

## Decisions (ADR summary)

| # | Decision | Reason |
|---|---|---|
| 1 | PySide6/Qt6 | `QTextDocument` renders commentary HTML well; LGPL; pip-installable. |
| 2 | Vendor `core/esword` | Keeps the app self-contained without tying its layout to an upstream repository; `make drift` reports divergence when an optional upstream is configured. |
| 3 | Index on demand | Indexing an entire library at once provides no immediate value, and reading does not require it. |
| 4 | FTS5 instead of an external engine | It ships with Python's `sqlite3` module; zero services. |
| 5 | Cache in the XDG cache directory | Heavy regenerable data belongs in `~/.cache`, and no file in the modules folder is touched. |
| 6 | Process pool only for encrypted Bibles | Pure-Python Twofish is CPU-bound; parallelising the largest encrypted workloads pays off, while the rest does not justify it. |
| 7 | i18n via JSON, not `.ts`/`lrelease` | No build step; contributors and agents can edit JSON without friction. |
| 8 | No bundled modules; first-run folder dialog | The repository must not redistribute copyrighted content, and the user owns the library. See `docs/adr/0003-no-bundled-modules.md`. |
