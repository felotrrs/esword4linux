# AGENTS.md — esword4linux

Native Linux reader for e-Sword modules (PySide6/Qt6). This file contains the
golden rules, the system map and the commands. The details live in `skills/`
(read on demand).

## Golden rules

1. **The modules folder is IMMUTABLE.** esword4linux opens every module with
   `mode=ro`. It never writes, fixes, "cleans" or reorders a `.bblx`, `.cmtx`,
   `.dctx`, `.lexi`, `.twm`, etc. If a module contains typos, mojibake or
   duplicate entries, they are **documented and shown as-is**. Never invent or
   backfill content from another source.

2. **No e-Sword module ships with the repository.** Nothing is bundled,
   preloaded or hardcoded: there is no default Bible and no default last
   reference. On first run the user selects **one** modules folder; cancelling
   that dialog exits the app. The repository never distributes copyrighted
   modules, so **never commit** `.bblx`, `.bbli`, `.cmtx`, `.cmti`, `.dctx`,
   `.dcti`, `.lexi`, `.lexx`, `.twm`, `.refx`, `.refi`, `.topx`, `.devx`,
   `.harx`, `.mapx` or any other e-Sword module. Tests that need real modules
   use `ESWORD4LINUX_TEST_CORPUS` and skip when it is unset; they must never
   depend on the developer's corpus or cache.

3. **The type is decided by STRUCTURE, never by extension.** `kind` comes from
   the tables present (`Bible`, `VerseCommentary`, `Dictionary`, `Topics`,
   `Sections`+`Parts`, `Graphics`, `Reference`, `topics`+`config`...). In
   real-world collections there are `.refx` files that are topics and `.cmtx`
   files with the old commentary schema. The extension is only used to discover
   files.

4. **Reading ≠ searching.** The viewer reads from the module directly and
   decrypts only what it displays. The FTS5 index exists **only** for search.
   Reading is never blocked because a module has no index.

5. **Indexing and decryption are always explicit.** The first scan reads
   **metadata only** (structure, title, language, entry count). There is no
   preindex list and no automatic indexing at startup. Each module has the
   state `pending → indexing → ready | failed` in `catalog.db`. Index from the
   *Index* menu, the sidebar context menu, or the CLI tools: `make scan` only
   scans; `make encrypted` decrypts and indexes encrypted modules on request.

6. **One source per concept.** Categories → `src/esword4linux/core/catalog.py`
   `KIND_ORDER` / `KIND_LABELS`. Books, names and aliases →
   `src/esword4linux/core/books.yaml` (loaded by
   `src/esword4linux/core/books.py`; `BOOKS` is derived from it). UI strings →
   `src/esword4linux/i18n/es.json` +
   `src/esword4linux/i18n/en.json` (same keys in both). Colors and typography
   → `src/esword4linux/ui/theme.py`, fed by `Settings`. Theme, language and
   user fonts are edited **only** in *Edit → Preferences*; the View menu does
   not duplicate them. Do not duplicate lists in other files.

7. **No scattered `os.environ.get()`.** Configuration flows through
   `src/esword4linux/config.py:Settings`; environment defaults live only
   in `_xdg()`. The only other environment variables are test/tooling hooks:
   `ESWORD4LINUX_TEST_CORPUS` (real-module tests) and
   `ESWORD4LINUX_VENDOR_ORIGIN` (optional drift check).

8. **No heavy work on the UI thread.** Scanning and indexing run in
   `src/esword4linux/ui/tasks.py:Worker` (QThread) with SQLite connections
   **owned by the worker thread** (new `Catalog`/`ContentStore` inside the
   worker). Objects from the main thread are never shared with the worker.

9. **All module text goes through `src/esword4linux/core/text.py`.**
   `to_plain(raw, hint)` for indexing, `to_rich(raw, hint)` for display.
   Besides sanitizing (`<script>`, allowlist, RTF padding), it **converts the
   e-Sword pseudo-tags** (`<red>`, `<blu>`, `<grk>`, `<heb>`, `<num>`, `<Pg>`…);
   without this they show up literally as `</red>`. The `hint` (module stem)
   activates the legacy codepages (cp1253/cp1255) and transliterations. Raw
   module HTML is never injected into a `QTextBrowser`.

10. **The crypto/RTF core is vendored and GPL-3.0.** `twofish.py`,
    `sqliteplus.py`, `rtf.py`, `font_codepages.py` and `legacy_translit.py`
    live in `src/esword4linux/core/esword/` and come from an upstream shared
    library. Any local change must be checked with `make drift` and documented;
    the provenance header is never removed. The upstream origin is optional and
    private: set `ESWORD4LINUX_VENDOR_ORIGIN` (or pass `--origin DIR`) to
    compare; otherwise `make drift` skips cleanly. The project builds, tests
    and runs without that upstream.

11. **The app must start without network access and without Wine.** Any new
    dependency is justified in `docs/adr/`.

12. **Performance is measured, not assumed.** Pure-Python Twofish runs at
    roughly 284 records/s/core. Encrypted Bibles use the process pool in
    `src/esword4linux/core/indexer.py:_parallel_decrypt`. Do not introduce
    sequential decryption on paths with more than ~2,000 records without
    measuring it.

13. **The UI never goes blank.** If a module fails, the viewer shows the error
    (`index_error`/`ModuleError`) and the app stays alive. A single module
    failure must never take down the catalog.

## Startup and state

1. No Bible or module is bundled, preloaded or hardcoded. `Settings.load()`
   reads `~/.config/esword4linux/settings.json` (honoring `XDG_CONFIG_HOME`).
   On first run (`resources_dir` empty) `FirstRunDialog` asks for the modules
   folder. If the user cancels or quits, the process exits with status 0 and no
   main window is created.
2. The window appears before any scan. If the catalog is empty or metadata is
   stale, a **metadata-only** scan runs in a `Worker`. Indexing and decryption
   never start automatically.
3. There is no preindex list, no default Bible and no default last reference.
   When a workspace has no resource yet, the app may fall back to the first
   available Bible/module **from the user's own catalog** so the UI is not
   blank; this is derived from the selected folder, never hardcoded.
4. Heavy state lives in `~/.cache/esword4linux` (honoring `XDG_CACHE_HOME`):
   `catalog.db` for metadata and index state, `content.db` for pages and FTS5.
   Both are regenerable; the modules folder is never used for writes.
5. Reading works without any index. The search view explains that modules must
   be indexed before text search returns results.

## System map

Conceptual map (package paths are abbreviated to `core/` and `ui/` for
readability):

```
Modules folder (user-selected, ro)        Cache (~/.cache/esword4linux)
  ├── BIBLES/      .bblx .bbli             ├── catalog.db  metadata + index state
  ├── COMMENTARIES/ .cmti .cmtx            └── content.db  page + page_fts (FTS5)
  ├── DICTIONARIES/ .dctx .dcti
  ├── BOOKS/       .refi .topx .devx ...          ▲
  └── root         .lexi .harx .mapx .twm         │
             │                                    │
             ▼                                    │
   core/esword/module.py ── decrypts ── core/indexer.py
        │  (Twofish/SQLitePlus)                   │
        │                                         ▼
        │                               core/store.py (FTS5)
        │                                         │
        ▼                                         ▼
   ui/bible_view.py  ◄── direct reading ──  core/search.py
   ui/library_view.py                        (reference | strong | text)
        ▲                                         ▲
        └──────────── ui/main_window.py ──────────┘
                          ▲
                    ui/sidebar.py (catalog by category)
```

The module table uses paths relative to the repository root.

| Module | Role |
|---|---|
| `src/esword4linux/core/esword/module.py` | Opens the SQLite file, detects structure, extracts metadata, iterates pages and decrypts per column. The only entry point to a module. |
| `src/esword4linux/core/esword/sqliteplus.py` | SQLitePlus header + zlib. Decrypts one blob. |
| `src/esword4linux/core/esword/twofish.py` | Twofish-128-ECB (vendored, GPL-3.0). |
| `src/esword4linux/core/esword/rtf.py` | RTF → plain text / rich HTML (vendored). |
| `src/esword4linux/core/text.py` | `to_plain` / `to_rich` / `snippet`. e-Sword pseudo-tags + legacy codepages. |
| `src/esword4linux/core/refs.py` | Biblical citation detection (`find_reference_spans`, `link_references`). |
| `src/esword4linux/core/refresolver.py` | `RefResolver`: verse pop-up using the reference Bible. |
| `src/esword4linux/core/legacy_scripts.py` | Automatic detection of legacy codepages (cp1253/cp1255). |
| `src/esword4linux/core/strong.py` | `StrongIndex`: auto-detects the Strong lexicon and resolves `G2316`. |
| `src/esword4linux/core/commentary.py` | Bible↔commentary pairing by identity + actual coverage. |
| `src/esword4linux/core/refchain.py` | Multi-citation chains (`Gen 23:1-6, 2:5-7; John 3:16`) → references. |
| `src/esword4linux/core/catalog.py` | Incremental scan, classification, language, fingerprint, duplicates and index state. |
| `src/esword4linux/core/store.py` | `page` + `page_fts` FTS5 schema, triggers, `build_match`. |
| `src/esword4linux/core/indexer.py` | Module → pages → FTS5. Process pool for encrypted Bibles. |
| `src/esword4linux/core/search.py` | Intent detection and store queries. |
| `src/esword4linux/core/books.py` | Loads `src/esword4linux/core/books.yaml` (IDs 1–73, es/en/fr/pt names, aliases) and exposes `parse_reference`. |
| `src/esword4linux/core/context.py` | `AppContext`: catalog, store, engine and an LRU cache of open modules. |
| `src/esword4linux/ui/bible_view.py` | `BiblePane`: navigation, parallel Bible, citation box (replaces the main view) and bottom panel (Commentary\|Lexicon). |
| `src/esword4linux/ui/commentary_pane.py` | `CommentaryPane`: chapter commentaries, jump to note. |
| `src/esword4linux/ui/strong_pane.py` | `StrongPane`: Strong lexicon entry. |
| `src/esword4linux/ui/rich_browser.py` | `RichBrowser`: lazy pop-ups on hover. |
| `src/esword4linux/ui/checkstyle.py` | `CheckMarkStyle`: checkbox checkmark indicator, theme-aware. |
| `src/esword4linux/ui/language.py` | Labels (`lang.*`) and language order for the UI. |
| `src/esword4linux/ui/tab_bar.py` | `ColoredTabBar`: solid-color tabs, bold text and a ＋ button. |
| `src/esword4linux/ui/tooltip.py` | `TipBubble`: custom bubble painted from a `QTextDocument` (max width 600 px, one line per block). |
| `src/esword4linux/ui/workspace.py` | `Workspace`: a view-tab (main resource + Bible/parallel/commentary). |
| `src/esword4linux/ui/entry_dialog.py` | `EntryDialog`: read a full entry without creating a tab. |
| `src/esword4linux/ui/library_view.py` | Generic viewer; term list with a hide/show handle. |
| `src/esword4linux/ui/search_view.py` | Single search box with intent and grouped results. |
| `src/esword4linux/ui/sidebar.py` | Tree with combinable groupings (kind/language/work) and multiple filters. |
| `src/esword4linux/ui/citation_pane.py` | Verse collection for a citation chain. |
| `src/esword4linux/ui/first_run.py` | First-run dialog: asks for the user's modules folder before the main window opens. |
| `src/esword4linux/ui/main_window.py` | View-tabs, names/colors, menus, workers, persistence. |
| `src/esword4linux/ui/preferences_dialog.py` | Preferences: appearance (theme + typography), language and preview. |
| `src/esword4linux/ui/theme.py` | Light/dark palettes, QSS and document CSS from `Settings`. |
| `src/esword4linux/i18n/` | `tr(key, **kwargs)` over JSON catalogs `es`/`en`. |
| `packaging/` | Private runtime staging (`stage_runtime.py`), pinned wheels, runtime manifest, launcher, QA and the `.deb` build script. |
| `debian/` | Debian packaging (debhelper 13, control, rules, copyright, install, man page). |

## Commands

```bash
make install     # venv + dependencies
make run         # start the app
make scan        # scan the modules folder (metadata only, CLI)
make encrypted   # decrypt and index encrypted modules (explicitly)
make dedup       # duplicate report (--apply moves copies to _duplicados/)
make test        # pytest
make deb         # build the native Debian package (packaging/build-deb.sh)
make drift       # optional: check vendored core against ESWORD4LINUX_VENDOR_ORIGIN
make desktop     # install app + hicolor icons (16–512 px)
make clean       # remove venv and cache
```

Quick diagnostics:

```bash
# Which type is detected and how many entries does a module have?
.venv/bin/python -c "
from esword4linux.core.esword.module import EswordModule
m = EswordModule('<MODULES_DIR>/bible.bblx')
print(m.structure, m.kind, m.encrypted, m.count_entries())"

# What is indexed?
.venv/bin/python -c "
from esword4linux.config import Settings
from esword4linux.core.catalog import Catalog
c = Catalog(Settings.load().catalog_db)
print(c.counts_by_kind(), c.status_counts())"
```

## Definition of "done"

- `make test` is green. Tests that need real modules use
  `ESWORD4LINUX_TEST_CORPUS` and skip when it is unset; they never read the
  developer's cache.
- `make drift` reports no unexpected drift when `ESWORD4LINUX_VENDOR_ORIGIN` is
  set; without it the check skips cleanly.
- The app starts with `./run.sh`: on first run it asks for the modules folder,
  and cancelling exits cleanly.
- Reading a Bible works without an index.
- Behavior change → one line in `docs/CHANGELOG.md`.
- Open work → `docs/TECH_DEBT.md`.
- New convention → the `skills/*.md` file that owns it.
- New UI string → added to both `src/esword4linux/i18n/es.json` and `en.json`.

## Documentation language

Documentation, code comments, identifiers and commit messages are
**English-first**. The application UI remains bilingual Spanish/English through
the i18n JSON catalogs; Spanish is a supported UI locale, not the documentation
language.

## If you touch X, read Y

| When… | Skill |
|---|---|
| You read a module, add a type or a table | `skills/esword-modules.md` |
| You touch Twofish, SQLitePlus or decryption | `skills/decryption.md` |
| You touch FTS5, the indexer or search | `skills/search-index.md` |
| You touch the window, tabs, sidebar or views | `skills/ui-layout.md` |
| You touch RTF/HTML, typography or themes | `skills/rendering.md` |
| You touch Preferences (theme, language or fonts) | `skills/ui-layout.md` + `skills/rendering.md` |
| You touch books, aliases, references or passage pop-ups | `skills/book-aliases.md` |
| You add UI strings or a language | `skills/i18n.md` |
| You measure performance or change the pool | `skills/performance.md` |
| You touch packaging, the private runtime or the `.deb` | `skills/packaging.md` |

## Git Workflow and Repository Management

The project uses a local Git repository synchronized with GitHub through the
`origin` remote.

### General rules

1. Preserve the existing Git history, branches, tags, and remote configuration.
2. Never execute destructive Git commands such as `reset --hard`, `clean -fd`,
   forced pushes, or history rewriting unless explicitly authorized.
3. Never modify or delete existing commits or tags without explicit
   authorization.
4. Do not commit generated files, credentials, secrets, local environment files,
   or temporary artifacts.

### Session initialization

At the beginning of each development session:

1. Run `git status`.
2. Identify the current branch.
3. Check whether the working tree contains uncommitted changes.
4. Check whether the current branch is synchronized with its upstream branch.
5. If remote updates exist, report them before integrating changes.
6. Never discard or overwrite existing local changes.

### During development

- Work normally within the current branch.
- Do not create commits automatically.
- Do not push changes automatically.
- Preserve unrelated user modifications.

### Task completion

When a development task is completed:

1. Run `git status`.
2. Review changes using `git diff`.
3. Summarize modified, added, and deleted files.
4. Report relevant tests and validation results.
5. Suggest an appropriate commit message.

### Commit policy

Only create commits after explicit user authorization.

Before committing, verify that the staged changes contain only the intended
files.

### GitHub synchronization

Only execute `git push` after explicit user authorization.

Before pushing:

1. Verify the current branch and upstream.
2. Check for remote changes.
3. Ensure the working tree and commit state are understood.
4. Never use force push unless explicitly authorized.

After pushing, verify the remote references and report the result.

### Release and version tags

- Never create, move, overwrite, or delete release tags automatically.
- Create annotated version tags only after explicit authorization.
- Verify that the tag points to the intended commit.
- Push release tags only after explicit authorization.
