# Changelog

## 0.5.0 — 2026-11-16

- Use the classic e-Sword/penguin/book logo as the single application, window
  and About icon; the hicolor 16–512 px set is generated from the same source.
- Removed the superseded runtime icon assets (`esword4linux2.webp` and
  `esword4linux3.jpeg`); the archived JPEG remains only under
  `packaging/icons/source/`.
- Native Debian package (`0.5.0-1`) for Ubuntu 24.04 and Linux Mint 22.x: private
  PySide6/Qt runtime under `/opt/esword4linux`, X11 and Wayland client plugins,
  desktop entry, hicolor icons, man page and license texts. The system Python
  environment is not modified and user data remains in the XDG directories.
- Adopted `packaging/runtime-manifest.yaml` as the shared runtime inventory for
  the `.deb`, the planned Flatpak and the future AppImage.
- Removed the unused `libadwaita` Wayland decoration plugin after Weston
  validation; `libbradient` remains as the generic client-side fallback.
- Verified that the private ICU 73 under `/opt` is used even when the system
  has ICU 74 installed.
- Renamed the project and Python package to esword4linux.
- No modules or Bibles are bundled or hardcoded; first run asks for the user's modules folder before opening the window.
- First scan builds metadata only. Indexing and decryption are always explicit.
- Settings and cache moved to XDG paths (`~/.config/esword4linux`, `~/.cache/esword4linux`).
- Documentation, skills, AGENTS.md and code comments are English-first; the UI remains Spanish/English. Documentation now lives under `docs/`.
- Tests no longer depend on a developer machine: optional corpus via `ESWORD4LINUX_TEST_CORPUS`.
- Public repository hygiene: module extensions are gitignored and generated duplicate reports stay outside version control.

## 0.4.7 — 2026-11-15

### Added

- **Edit → Preferences**: typography suite with font family and size for the
  interface, the biblical text and body text (commentaries, dictionaries,
  lexicon and search). Includes live preview and "Reset".
- Preferences are stored in `Settings` (`ui_font_*`, `font_*`,
  `content_font_*`) and applied to the QSS and `document_css` without a
  restart.
- **Tabbed Preferences**: "Appearance" gathers the theme and the three
  typographic roles; "Language" switches the interface live on save. The
  **View** menu keeps only view options (panel, unclassified and lexicon).
- Font selectors are non-editable combos listing every installed family;
  before, `QFontComboBox` showed an editable text box.

### Fixed

- **Official icon**: `esword4linux3.jpeg` becomes the app's actual icon.
  `tools/make_icons.py` crops the rounded card from the JPEG (removing the
  painted checkerboard) and generates a transparent `esword4linux.png`, used by
  the window, "About" and the hicolor sizes 16–512 px.
- **Sidebar filters**: "type" and "language" sit together and left-aligned;
  the intermediate `stretch` is removed.
- **"Paired with…"**: the badge no longer opens a pop-up; it switches the
  commentary in the bottom panel and scrolls to the current verse.

## 0.4.6 — 2026-11-15

### Fixed

- **Map legend encrypted without zlib**: a map module stores
  `Graphics.Details` with SQLitePlus encryption but uncompressed UTF-16LE RTF.
  The 5-byte header is recognized (magic `0x1F`) and the text decoded, instead
  of showing random bytes as garbage characters.
- **Map and illustration images**: UTF-16LE BLOB titles are decoded so that the
  list, `page_by_ref` and `map_picture` find every entry, and the `lt\0\0` +
  size wrapper that some `.mapx` files prepend to the BMP is stripped.
- **Visible map controls**: the toolbar with `+`, `-`, `1:1`, "Fit" and
  "Legend" is shown again when a map entry is selected. The legend respects its
  button, and if the image is missing the notice is shown in the panel.
- **"Paired with…" badge**: clickable again, opening the paired commentary; it
  now keeps the module path when painting the badge.
- **Book-only commentaries**: some commentaries ship an empty
  `VerseCommentary` table and keep all their text in `BookCommentary`.
  `count_entries()` sums the real tables (it used to return 0, so the catalog
  hid them) and `page_by_ref()` accepts book references (`"43"`), so their
  entries now display text.
- **Commentaries with a dictionary schema**: commentary modules distributed as
  `.dcti` and `.dctx` move from the Dictionaries category to Commentaries
  without altering the module.
- **Harmonies**: the navigable unit is the section. Each entry groups all the
  references in `Parts` (no duplicate records), cleans the RTF from
  `Section.Title` and uses a single section `ref`. The FTS5 index no longer
  keeps only the last reference of each `(section, part)`.
- **Reindexing on metadata changes**: if a scan changes a module's type,
  structure or entry count, its content index is left `pending` so it can be
  rebuilt with the new indexable unit.

## 0.4.5 — 2026-11-12

### Added

- **Interactive map and illustration viewer (`ImageViewer`)**: smooth
  mouse-wheel zoom, hand drag (pan), floating buttons for zoom in/out/100%/fit
  to window, and full-screen display in a dialog.
- **Book category and detection (`book`)**: a heuristic that distinguishes
  `Reference` tables containing cross-references (`reference`) from literary
  works and treatises with sequential chapters (`book`).
- **Heuristic classification of TWM modules**: `.twm` modules are reclassified
  according to their real content as dictionaries, books or topics, ending
  their status as an outcast category.
- **Magnifier icon on the Search tab**: crisp vector rendering in
  `ColoredTabBar` that adapts to the theme palette.
- **Hiding of system/empty modules**: modules without entries or UI modules
  (`headings`, `localize`) are not shown in the sidebar by default, with an
  option under *View → Show files without content / unclassified*.

### Changed

- **Visual consistency in filters**: the Type and Language buttons now sit
  together in the layout with the same style, typography, padding and borders
  as the Group selectors.
- **Semantic theme tokens**: `Palette` gains `success`, `error` and `strong` to
  unify state colors in the resource tree and biblical text while respecting
  the light and dark themes.
- **Compact close buttons**: the Commentary and Lexicon panels use discreet
  circular ✕ buttons (`#closeButton`).

## 0.4.4 — 2026-11-12

### Fixed

- **Tooltips**: the inner `QTextBrowser` is replaced by a widget that paints a
  `QTextDocument` directly. The global QSS padding no longer clips the
  viewport, height is measured against the real width, and a safety bottom
  margin keeps the last line (including descenders) from being cut off or
  half-visible.
- **Hebrew in lexicon tooltips**: `StrongIndex.tooltip()` preserves the
  module's line breaks (Hebrew word, transliteration and definition). Each line
  is an independent block and the Hebrew word is shown at heading size, without
  RTL dragging the rest of the text.
- **Citations**: enabling the collection no longer hides the book/chapter
  combos or the navigation arrows. The Bible can always be restored with them
  or with ↩.
- **Parallel view**: the checkbox shows a checkmark drawn by `CheckMarkStyle`,
  in addition to the accent color when checked.
- **Default icon**: the icon from the "About" dialog
  (`esword4linux-about.png`) is used, and `esword4linux.png` plus the hicolor
  16–512 sizes are regenerated.

### Changed

- The **Strong** button and panel are renamed to **Lexicon**.
- **Resources**: "Filter" is now a full-width section title, like "Group", with
  vertical spacing separating both control blocks.
- **Default resources folder**: updated to follow the renamed corpus folder.
  This affects the initial `Settings` value and the corpus-dependent tests.

### Tests

- 175 tests collected: 169 passing and 6 skipped because the current corpus
  does not include those modules. Widget coverage is added in `offscreen` mode
  for tooltips (height, Hebrew, lines), checkmark, the Resources organizer and
  citation mode, without depending on `pytest-qt`.

## 0.4.3 — 2026-11-11

### Fixed

- **Standardized tooltips**: body without empty lines or HTML remnants, one
  line per verse, height measured from the real layout and last line not cut
  off. Residual native tooltips were removed.
- **Orphan tags**: stray `</p>` tags in some Bible modules no longer split a
  verse into two blocks (they caused the vertical gap).
- **Recoverable panels**: the dictionary term list uses a vertical `‹/›` handle
  like Resources, with a minimum width and persisted state.
- **Strong/commentaries** apply the material change instantly, without pressing
  "Open".
- **Search**: Enter on a reference navigates directly to the Bible.
- **Bible**: no vertical chapter arrows; the parallel combo is hidden when the
  parallel view is unchecked; the checkbox has contrast in dark mode. The
  "Citations" button and the panel-hide arrow were removed; search uses the
  selection or, failing that, the current reference.
- **Translation combo**: non-editable drop-down; opening it shows all versions
  grouped by language.
- **"Tab A"**: automatic names are recalculated when the language changes and
  menus are retranslated live.
- **Icon**: the checkerboard/card background is removed from the WebP and a PNG
  with real transparency is generated; hicolor is regenerated from the clean
  icon.

### Added

- **Resources organizer**: up to three grouping levels (type/language/work) and
  multiple filters by type and language, persisted.
- **Multiple-citation box** in the Bible toolbar itself: pressing Enter makes
  the collection replace the chapter view (also in the parallel view), and the
  Bible can be restored with ↩.
- Help tooltips on the main controls.

## 0.4.2 — 2026-11-11

### Fixed

- **Tooltip height**: calculated from the document's real layout plus the
  frame's margins/borders; the last line is no longer cut off.
- **Unrecoverable side panels**: the resources panel has a 240 px minimum plus
  a handle, and its splitter is not collapsible. The dictionary/lexicon term
  list has a 220 px minimum and an always-visible `☰` button to hide/restore it
  (state and width persisted).
- **Stale Strong/commentary tooltips**: switching lexicon or commentary
  invalidates the `RichBrowser` and `_comments_cache` caches, regenerates the
  chapter notes and applies the change without pressing "Open".
- **Language detection**: title/abbreviation, file marker, content sample and
  native alphabets are prioritized; author names that confused Spanish with
  English were removed. `METADATA_VERSION` forces a metadata rescan to update
  the existing catalog.
- **Dark theme contrast**: stronger background steps, more visible borders and
  alternating rows in trees/lists.

### Added

- **Third "By language" view** in Resources, with i18n labels and groups by
  `module.language`.
- **Translation combo grouped by language and sorted**; opening it shows every
  version. The parallel view uses the same grouping.
- **New default icon** `esword4linux2.webp`; `make desktop` generates the
  hicolor PNGs from that WebP. The "About" dialog keeps its logo.
- Tests for tooltip height, contrast, languages, translation filtering and
  recoverable panels.

## 0.4.1 — 2026-11-11

### Fixed

- **Bibliography tooltips**: width now adapts to the text (up to 600 px) and
  the header shows only the reference or lexicon abbreviation, not the work's
  long title. Passages show the full text (no `snippet`) and chapters/ranges
  are capped at **10 verses** with a notice about the rest. Strong entries are
  capped at 2500 characters, with a notice to open the full entry in the Strong
  panel.
- **The Bible uses the full horizontal width**: the side `stretch` spacers that
  left ~17% of the panel as margin were removed.
- **Book and passage normalization**: the book and alias table moves to
  `core/books.yaml` (Spanish/English/French/Portuguese names). It recognizes
  `I/II/III`, `Primera/Segunda/Tercera`, `1ª/1a/1ra` prefixes, abbreviations
  such as `Luk`, `Jhn`, `Deu`, `Pro`, `Amo`, `Rth`, `Ezk`, `Mrk`, separators
  like `Jn 3,16` and lists like `Ex. 4:14, 27-30` / `He. 5.4; 7.11`. `<ref>`
  elements with lists are split into per-sub-reference links. Books missing
  from the 1–73 numbering (`1 Esdras`, `3 Macc`) are not linked to another
  book.

### Added

- `PyYAML>=6` and ADR-0002; `skills/book-aliases.md` documents the schema.
- Tests for formats, continuations, multi-word names, the verse cap and tooltip
  width.

## 0.4.0 — 2026-11-10

### Added

- **Sidebar with two views** (`By type` / `By work`), persisted: the
  by-type view helps find a lexicon without knowing which work it belongs to;
  the by-work view groups modules that belong to the same work (text + notes +
  lexicon). The year separates editions, so a 1960 edition is not merged with a
  1995 revision.
- **Custom tooltip** (`TipBubble`): dark card independent of the theme, accent
  border, **maximum width 380 px** and a gold header. It replaces the native
  tooltip, which inherited the panel colors and did not limit width.
- **Tooltips across the whole bibliography**: dictionaries, lexicons and
  commentaries link their citations — both `<ref>` and **plain text**
  (`Neh. 8:15`, `2Co 4:6`) — and show the verse on hover.
- **Selectable default Strong lexicon**: the Strong panel combo lists the
  available Strong lexicons (★ = active) and fixes the one used for tooltips;
  also under **View → Default Strong lexicon**. If the chosen lexicon does not
  cover the requested language (for example a Hebrew-only lexicon when
  `G2316` is requested), it resolves through **automatic fallback** to the
  first candidate containing the entry, and the tooltip indicates which
  lexicon it came from.
- **Automatic legacy codepage detection** (`core/legacy_scripts.py`):
  recognizes cp1253/cp1255 from runs of RTF escapes and fixes Greek in modules
  outside the vendored registry (for example a Greek dictionary module goes
  from `èåïäßäáêôïò` to `θεοδίδακτος`).
- **`tools/deduplicate.py`** plus a duplicates report: a complete report of
  exact duplicates (sha256) and of "same work, different files", with a
  retention policy and reversible quarantine.
- **`make dedup`**.

### Fixed

- **The sidebar would not grow**: it had `setMaximumWidth(460)`; the tree now
  takes all the width it is given.
- **Tabs would not grow when the panel was hidden**: the dock kept its 290 px.
  It is now capped at 16 px and the content recovers the space.
- **Panel handle at half height**: now a fixed size (15×26) aligned to the top.
- **The Bible would not grow horizontally**: the 980 px cap was removed; it now
  fills the width like the commentary area.

### Library

- **Duplicate copies moved to quarantine** with a manifest in
  `_duplicados/manifest-*.json`. The move is reversible.
- The scan **excludes `_duplicados/`**, VCS and hidden folders, and **purges
  from the catalog** modules that no longer exist on disk
  (`ScanResult.removed`).
- Modules whose text had literal pseudo-tags or mojibake in the FTS5 index were
  reindexed.

## 0.3.0 — 2026-11-10

### Added

- **e-Sword pseudo-tags** (`<red>`, `<blu>`, `<grk>`, `<heb>`, `<num>`, `<Pg>`,
  `<T>`, `<trn>`, `<Hebr>`, `<SHE…>`…) converted to semantic HTML. They used to
  appear literally as `</red>` because HTML detection did not recognize them.
- **Legacy Greek/Hebrew**: `font_codepages.py` (cp1253/cp1255) and
  `legacy_translit.py` are wired to the module stem. A Greek dictionary module
  goes from `ἀðüèåóéò` to `ἀπόθεσις`. The vendored files are not touched.
- **Tooltips**: notes and references resolve their text when painted (native
  `title` attribute tooltip); Strong numbers are resolved on hover with a cache
  (`RichBrowser`, 180 ms).
- **Clicking a note marker** opens the commentary if it was closed, jumps to
  the module paired with that Bible, scrolls to the note and keeps focus on the
  verse.
- **Clicking a Strong number** switches the bottom panel to **Strong** with the
  full entry (lexeme, transliteration, morphology).
- **Stacked bottom panel**: `Commentary ⇄ Strong` with a selector in the bar.
- **Automatic, visible Bible↔commentary pairing**: identity
  (tokens/year/abbreviation) plus the **real coverage** of the text's markers.
  When there is no match it does not invent one.
- **Full-color tabs**: `ColoredTabBar` paints the background, bold text when
  selected, a pale tint when not, a padded close button and a browser-style
  **＋** button behind the last tab.
- **Collapsible sidebar** with a handle on its own border (`‹`/`›`).

### Fixed

- False references: `_abbrev()` returned spaces and the substring bonus matched
  any commentary.
- Render cost: notes and references are resolved from the chapter data already
  loaded (zero extra queries per verse).

## 0.2.0 — 2026-11-10

### Changed (UI model)

- **Workspace tabs (`Workspace`)** instead of one tab per module. Each tab
  groups a main resource and, if it is a Bible, its own parallel Bible and its
  own commentary. Automatic names "Tab A/B/C…", assignable color and renaming
  from the context menu. Full persistence of the group (translation, parallel,
  commentary, heights).
- **Commentary in its own panel**, at the bottom with a vertical split (~28%),
  instead of embedded between verses.
- **Selecting a resource no longer opens a tab**: it loads as the main resource
  of the active tab. Creating a tab is explicit (`＋`, `Ctrl+T`).
- **Parallel and commentary only with Bibles.** A dictionary no longer shows
  Bible controls (the "dictionary parallel view" is gone).
- **"Read in full" opens a dialog**, not a tab.

### Added

- **A single click loads the resource** in the sidebar; clicking a category
  collapses/expands it.
- **Hideable resources panel**: `Ctrl+B`, *View → Resources panel* menu and a
  `☰` button next to the tabs; the state is persisted.
- **Application icons**: flat icon (window, launcher, hicolor 16–512 px) and
  illustrated icon (*About* dialog). Installation with `make desktop`.
- **`make encrypted` / Index menu**: decrypts and indexes all encrypted modules
  at once so they are ready to use.
- **Commentaries with the modern schema**: support for `.cmtx` with
  `Verses(ChapterBegin, ChapterEnd, VerseBegin, VerseEnd)` in addition to the
  old `VerseCommentary`. It used to fail with "no such column: Chapter".
- Regression tests for both commentary schemas (50 in total).

### Fixed

- The commentary panel did not refresh because `isVisible()` is false before
  the window is shown; it now depends on the toggle.
- The fixed "Search" tab no longer shows an inert close button.

## 0.1.0 — 2026-11-10

First working version.

### Added

- **Native e-Sword module reader** (`core/esword/module.py`): SQLite
  `mode=ro`, structure detection by tables (11 types), normalized metadata,
  pages by type and direct queries (`bible_chapter`, `page_by_ref`,
  `chapter_comments`).
- **SQLitePlus decryption** with Twofish-128-ECB (vendored core, GPL-3.0).
  Verified against an encrypted Bible module.
- **Catalog** (`core/catalog.py`): incremental scan of the resources folder,
  classification by structure, sha1 fingerprint and duplicate detection,
  persistent indexing state.
- **FTS5 index** (`core/store.py`, `core/indexer.py`): `page` table with
  external content, `remove_diacritics 2`, synchronization triggers, prefix
  search and AND→OR fallback. Indexing on demand by category.
- **Parallel decryption** with `ProcessPoolExecutor` for encrypted Bibles:
  109 s → ~13 s for a large encrypted Bible.
- **Unified search** (`core/search.py`): reference (`John 3:16`), Strong
  (`G2316`) and free text, with intent detection.
- **PySide6 UI**: collapsible category sidebar, closable and reorderable tabs,
  Bible with book/chapter navigation, parallel view of two translations,
  commentaries inline under each verse, generic viewer for 10 module types,
  search with grouped results and highlighting.
- **Light/dark themes** and serif typography for Scripture.
- **es/en i18n** through JSON catalogs, Spanish by default.
- **Persistence** of geometry, open tabs, translation and theme.
- **Base pre-index** on first start: a reference Bible, a second translation
  and its commentary in about 20 s.
- **Packaging**: `run.sh`, `Makefile`, `.desktop`, `pyproject.toml`.
- **48 tests** (`make test`).
- **Documentation**: `AGENTS.md`, 7 skills, architecture, e-Sword format.

### Notes

- A resources folder can mix encrypted modules with plain SQLite ones; the app
  opens both.
- `content.db` is regenerable; `catalog.db` can be rebuilt with a rescan.
