# UI — view-tabs, panels and views

## Startup

1. On first run, `FirstRunDialog` asks for the modules folder **before** the
   main window exists. Cancelling or choosing *Quit* ends the process cleanly;
   no empty window is shown.
2. Once a folder is configured, the window appears before any scan. If the
   catalog is empty or its metadata is stale, a metadata-only scan runs in a
   `Worker`. No indexing or decryption starts automatically.

## Model

```
QMainWindow
└── QSplitter (horizontal)
    ├── Sidebar                (collapsible: Ctrl+B or the ☰ button)
    └── QTabWidget
        ├── [0] SearchView     — fixed, no close button
        └── [1..] Workspace    — "Workspace A", "Workspace B", … with a color
```

A **Workspace** is a view-tab: it groups one main resource and, if that
resource is a Bible, its own comparison table and its own commentary.

```
Workspace
└── QStackedWidget
    ├── BiblePane                    (if the main resource is a Bible)
    │   ├── toolbar  (translation · book · chapter · parallel · add · commentary)
    │   └── QSplitter(Vertical)
    │       ├── QStackedWidget         reading | citations | comparison
    │       └── CommentaryPane         (bottom, ~28 %)
    └── LibraryView                  (any other type)
```

## Rules

1. **Selecting a resource does NOT create a tab.** Clicking in the sidebar
   loads the resource as the **main resource of the active tab**
   (`MainWindow.open_resource`). Creating a tab is an explicit action
   (`＋`, `Ctrl+T`).
2. **One tab = one group.** Changing the resource inside a tab replaces its
   main resource; it does not accumulate materials.
3. **Comparison table and commentary only exist in Bible mode.** If the main
   resource is not a Bible, `Workspace` shows `LibraryView` and the Bible
   toolbar disappears. There is no "comparison dictionary view". The
   **Vista paralela** checkbox opens the verse-aligned table of installed
   translations; it does not open a second chapter pane.
4. **`FIXED_TABS = 1`.** The *Search* tab cannot be closed (its button is
   removed with `setTabButton(0, RightSide, None)`). Do not reorder that
   assumption: if the number changes, review `_close_tab()`.
5. **Never close the last view-tab.** `_close_tab()` shows
   `workspace.last` and aborts.
6. **Commentary lives in its own bottom panel**, not inside the biblical text.
   `CommentaryPane` makes **one** query per chapter (`chapter_comments`),
   never one per verse.
7. **"Read full" opens a dialog, not a tab** (`EntryDialog`). This avoids tab
   proliferation. The "matched with…" badge does not use the dialog: it
   switches the module in `CommentaryPane` and shows it in the bottom panel
   (`open_inline` → `BiblePane._show_commentary_inline`).
8. **All long work goes through
   `src/esword4linux/ui/tasks.py:Worker`** with SQLite connections created
   inside the thread. The sidebar is disabled while it runs.

## Workspace names and colors

- Default name: `tr("workspace.default_name", letter="A")` → "Workspace A".
  `_next_name()` uses the first free letter; renaming frees the letter.
- Color: `TAB_COLORS` (8 shades). A 12 px dot is painted as the tab icon
  (`color_dot`).
- Workspace tab context menu: **Rename**, **Color**, **Close**.
- State (`name`, `color`, `main_rel`, `parallel`, `parallel_rel`,
  `compare_columns`, `commentary`, `commentary_rel`, `split`) is persisted in
  `Settings.workspaces` and restored by `_restore_state()`.

## Menus and preferences

- **File** → scan, choose folder, quit. **Edit** → Preferences (`Ctrl+,`).
  **View** → sidebar, unclassified files and Strong lexicon. **Index** and
  **Help** complete the bar.
- The Index menu and the sidebar context menu are the in-app ways to build the
  search index: all categories, pending modules, encrypted modules, one
  category or one module.
- Theme, language and typography live **only** in Preferences, with
  *Appearance* and *Language* tabs. Do not duplicate those options in the View
  menu.
- On accept: `MainWindow._open_preferences()` applies the theme
  (`_set_theme`), language (`_set_locale` → `_retranslate_ui`) and typography
  (`_apply_typography` → QSS + `reload_theme()` on every view).

## Sidebar

- **A single click** loads the module (`itemClicked` → `_on_click`). Clicking a
  category expands or collapses it.
- `itemActivated` (Enter) also loads, for keyboard use.
- Hidden with **View → Resource panel** (Ctrl+B) or the ☰ button in the tab
  corner; the state is stored in `Settings.sidebar_visible`.
- With the panel **visible**, the `QSplitter` is not collapsible and the dock
  has a minimum of `SIDEBAR_MIN_WIDTH + SIDEBAR_HANDLE_WIDTH` (200 + 15 px).
  Dragging the divider never makes it disappear; when hidden, only the 15 px
  handle remains.
- **`_apply_sidebar_sizes(visible)` is the only place that sizes the band.**
  It applies the dock constraints *and* the splitter sizes together, because
  the `QSplitter` keeps its own copy: clamping the dock with a maximum width
  alone leaves the splitter reserving the old width and an empty band appears
  where the panel used to be (it happened after reopening the app with the
  panel collapsed).
- The toolbar of a Bible workspace lives inside a `QScrollArea` (horizontal
  scroll only). Its controls demand ~975 px; without the wrapper that became
  the **window's** minimum width, and a window manager disables *maximise*
  when the minimum exceeds the usable screen width. The window minimum must
  stay below ~800 px with the panel shown or hidden.
- The "type" and "language" filter buttons are adjacent and left-aligned: do
  not insert a `stretch` between them.

## BiblePane

- `self._loading` blocks signals while synchronizing combos (prevents
  cascades).
- `_current` stores the reference; `reload()` renders and notifies
  `CommentaryPane` if the toggle is active.
- Anchors `<a name="v16">` + `scrollToAnchor`.
- Links: `v:N` (verse menu), `ref:<text>` (navigate), `c:<id>:<ref>` (full
  entry in a dialog).
- **No side gutters**: the `QTextBrowser` uses the full panel width; reading
  margins come from the QSS padding (`8px 18px`). The old side `stretch`
  widgets were removed because they left ~17 % of the width unused.
- **Translation combo** (`fill_bible_combo`): drop-down grouped by language and
  sorted by abbreviation/title. It preserves the selection by `rel_path`.
- **Comparison table** (`CompareView`): the *Vista paralela* checkbox shows a
  verse-aligned table of installed translations. The chapter name and
  **Agregar versión +** live in their own top strip (`#cmpTop`, page
  background) above the tinted header strip, so the table header reads as such.
  The first column is the locked main translation: the accent-coloured caption
  over a tinted cell marks it, and it only follows the *Traducción* combo.
  Additional columns use a flat inline `BibleComboBox` that fills the column
  and shows the full `ABBR — Título` caption (elided if the column is narrow,
  full title and language in the tooltip). It only becomes a bounded field on
  hover or focus, plus a muted `✕` that turns red on hover. The dropdown is
  independent of the column width (`view().setMinimumWidth`), so names are
  readable; its rows are normal weight and its language headings stay bold.
  **Agregar versión** creates a local draft header until a version is chosen
  and scrolls the table to the new right-most column first, so the column and
  its menu are never off-screen.
  The header is the **column model**: `column_metrics()` returns the pixel
  width of every column and both the native header cells and the `QTextTable`
  consume it, so a caption always sits exactly over its column — with one
  version or with twenty. The body starts at the browser's left edge
  (`QTextBrowser#cmpBrowser` has no padding, no frame and no document margin)
  and the strip is clipped to the viewport width, so the vertical scrollbar
  cannot desync it. **The two header bands are free children of `CompareView`,
  positioned by `_place_bands()`, not layout items**: a layout item with a
  fixed width turns that width into the minimum of the whole view, and the
  viewport width depends on the view width, so the view could never get
  narrower than itself (the window grew on every sidebar toggle).
  Below `MIN_VERSION_WIDTH` (200 px) per version the table scrolls horizontally
  and the header track follows the scrollbar.
  The table uses `core.compare_reader.build_compare_table()` and never runs
  SQLite queries from the widget. `compare_columns` is persisted per
  workspace.
- **Citation box** (`src/esword4linux/core/refchain.py` +
  `src/esword4linux/ui/citation_pane.py`): accepts
  `Gen 23:1-6, 2:5-7; Mark 2:1; John 3:16`, inherits book/chapter and
  **replaces the main view** with the collection grouped by chapter. The ↩
  button returns to the chapter. Book, chapter and ◀ ▶ arrows always remain
  visible in citation mode: hiding them left the bar with no way back to normal
  navigation. Leaving citation mode returns to the comparison table if the
  parallel view is still checked.
- The bar uses no vertical chapter arrows: the chapter is editable without
  buttons and navigated with ◀ ▶.

## CommentaryPane

- Header: title · pairing badge · module combo · **Open** · **✕** (hides the
  panel and unchecks the toggle).
- The "matched with…" badge emits `open_inline`; `BiblePane` shows that same
  panel and scrolls to the current verse. It does not open `EntryDialog`.
- Renders verse by verse with a "John 3:16" heading and the full text.
- If the text exceeds `MAX_CHARS` (9,000), it is truncated and a "Read full"
  action is offered.

## Known Qt traps

- `isVisible()` is **false** while the window has not been shown yet: do not
  use it to decide whether to render. Use the toggle state instead.
- A `QSplitter` keeps its **own copy** of the sizes. Resizing one of its
  children (e.g. `setMaximumWidth`) does not update that copy: call
  `setSizes()` again or the splitter will keep reserving the old space and an
  empty band will be painted.
- A wide child (a toolbar with many controls) raises the **window's** minimum
  width, and window managers hide the *maximise* button when that minimum
  exceeds the usable screen. Wrap such a bar in a horizontal `QScrollArea`.
- A layout item with a **fixed width** turns that width into the layout's
  minimum. If the width is derived from the viewport, the dependency is
  circular and the view can never shrink (the window grows on every toggle).
  Size such an item by hand as a free child, never through the layout.
- Giving a widget **its own layout** while it is already a layout item takes
  it out of the parent layout: it becomes a free child with its default size.
- `QTextDocument` ignores inline `color` on `<a>`: use `<font color>` inside.
- A `QLabel` with `wordWrap` inside a `QSplitter` does not calculate its height
  correctly.
- `processEvents()` does not fire a 180 ms `QTimer`: in tests, wait explicitly.
- `QTabWidget.setMovable(True)` lets the fixed tab be moved; it is harmless
  (closing is still blocked by index).
- `QFontComboBox` is **editable** by default and looks like a text box. To pick
  a font in Preferences, use a non-editable `QComboBox` populated with
  `QFontDatabase.families()`.

## Custom tab bar (`src/esword4linux/ui/tab_bar.py`)

QSS cannot color individual tabs (`QTabBar` has no `:nth-child`), so
`ColoredTabBar` paints them by hand:

- **selected**: solid color + **bold** text with contrast computed from
  luminance; **unselected**: pale tint (18 %) + muted text.
- close button with a right `CLOSE_MARGIN` (not glued to the edge).
- **＋** button drawn behind the last tab, with its own hit-testing
  (`new_tab_requested`).
- the color travels with the tab because it is stored in `setTabData()`.

`QTabWidget.setTabsClosable(False)`: the tab bar paints the close affordance.
The `tabBar().tabCloseRequested → _close_tab` connection is explicit.

## Collapsible sidebar

`SidebarDock` = `[Sidebar][15 px vertical handle]`. The handle
(`#sidebarHandle`) is always visible on the edge: `‹` when open, `›` when
collapsed. `toggle_sidebar()` stores the previous width in `_sidebar_width`
and restores it when reopened.

## Stacked bottom panel

`QStackedWidget{ CommentaryPane, StrongPane }` + two checkable `QToolButton`s
in an exclusive `QButtonGroup` (**Commentary**, **Lexicon**). State goes to
`Settings.bottom_page` and `show_commentary_inline`; pressing the active button
again hides the panel.

## Sidebar: filter and grouping organizer

`Sidebar` combines up to **three grouping levels** (`kind`, `language`, `work`)
in order, plus **multiple filters** by type and language and the text filter.
State is persisted in `Settings.sidebar_grouping`, `sidebar_kind_filters` and
`sidebar_language_filters`. The "Group" and "Filter" headings each take a full
line, with vertical space between the two blocks.

- **kind** — categories (`KIND_ORDER`).
- **work** — `Catalog.works()` groups by normalized title; the year separates
  editions when several coexist under the same base title.
- **language** — `module.language` (`es`, `en`, `fr`, `pt`, `de`, `it`, `la`,
  `grc`, `hbo`, `und`) with `lang.*` labels. `detect_language()` combines
  title/abbreviation, filename marker, a short content sample and original
  alphabets; `METADATA_VERSION` forces a metadata rescan when the heuristic
  changes.

The tree is built recursively and the text filter is recursive: if it matches
a group, all its descendants are shown.

## LibraryView term panel

`LibraryView` (dictionaries, lexicons, references…) has its own `QSplitter`
between the term list and the detail pane:

- list with a minimum of `LIST_MIN_WIDTH` (220 px) and detail with
  `DETAIL_MIN_WIDTH` (240 px); `setChildrenCollapsible(False)`;
- a `☰` button **always visible in the header** to hide/show the list;
- state in `Settings.library_list_visible` and width in
  `Settings.library_list_width`;
- stretch `0` for the list and `1` for the detail: widening the window grows
  the text, not the list.

## Pop-ups (`src/esword4linux/ui/tooltip.py`)

`TipBubble` replaces the native tooltip with a card painted directly from a
`QTextDocument` (no `QTextBrowser`, viewport or scrollbars): background
`#23262e`, accent left border, **adaptive width up to 600 px** and a gold
header. The header is compact (reference or lexicon abbreviation, never the
long work title). Each body line is an independent block, so Hebrew words keep
their RTL direction. The height is `documentLayout().documentSize()` + padding
+ a 5 px bottom margin: the last line and its descendants are never clipped.
Passages show up to 10 complete verses (`RefResolver.MAX_VERSES`); lexicon
entries are capped at 2,500 characters (with a hint to open the full entry in
the Lexicon panel).
`RichBrowser` extracts `title=` attributes from the HTML into its internal map
(so Qt does not show its own tooltip) and resolves Strong numbers on the fly.
Changing the lexicon or commentary invalidates the caches with
`RichBrowser.clear_all_caches()`.

## Default Strong lexicon

The Lexicon panel combo lists the lexicons that index by `G####`/`H####`
(★ = active). Changing it calls `StrongIndex.set_default()`, which persists
`settings.strong_rel`, invalidates the cache and refreshes the pop-ups
immediately (just as the commentary combo updates the chapter notes). It is
also available under **View → Default Strong lexicon**.
