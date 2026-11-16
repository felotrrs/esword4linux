# Rendering — RTF/HTML, typography and themes

## Two representations

| Function | Output | Use |
|---|---|---|
| `text.to_plain(raw)` | plain text | index into FTS5 |
| `text.to_rich(raw)` | HTML safe for Qt | display on screen |

**Never** index `to_rich()` (it would put tags into the index) and **never**
show `to_plain()` in the Bible (it would lose bold, italics and red letters).

## `to_rich` pipeline

```
raw (str | bytes)
  ├─ _is_rtf  → rtf_to_rich_text() → _sanitize() → _tidy()
  ├─ _is_html → _sanitize() → _tidy()
  └─ plain    → html.escape() + <br>
```

- `_sanitize` removes `<script>`/`<style>`, drops tags outside `_ALLOWED`
  (keeping their text), filters `style` to harmless properties and converts
  `<ref>X</ref>` into `<a href="ref:X">X</a>`.
- `_tidy` collapses `(<br>){3,}` to two and removes empty `<p>` elements:
  e-Sword RTF leaves dozens of line breaks between sections, and without this
  the reading pane is full of gaps.
- `_sanitize` balances tags: an orphan block closing tag (`</p>` without `<p>`)
  becomes `<br>`; orphan inline closings are dropped. Without this, some real
  modules split a verse into two blocks with a vertical gap.

## e-Sword RTF

- Frequently **without a header** `{\rtf1`: it starts at `\pard` or contains
  `{\b ...}` groups embedded in plain text. `_is_rtf` detects this.
- Default codepage is `cp1252`; Greek/Hebrew with 8-bit fonts require
  `font_codepages.py` / `legacy_translit.py` (vendored). They are connected
  through `EswordModule.codepages` and the module-stem hint; unknown modules
  use automatic content detection.

## Typography

Three independent roles, editable in **Edit → Preferences** (*Appearance* tab,
next to the theme):

- **Interface**: `Settings.ui_font_family` / `ui_font_size` (13 px by default).
  Feeds `app.setFont()` and `ui_stylesheet(settings)`.
- **Scripture**: `Settings.font_family` / `font_size` (Noto Serif, 15 px).
  Applied with `.scripture` and headings in `document_css`.
- **Running text**: `Settings.content_font_family` / `content_font_size`
  (Noto Sans, 13 px) for commentaries, dictionaries, lexicons and search. This
  is the `p, div, li, td, th` rule in `document_css`.

`document_css_for(settings)` is the shortcut used by every view; do not pass
loose constants. Qt ignores `body { ... }`, which is why the running-text size
is declared on the elements.

In Preferences, font selectors are non-editable `QComboBox` widgets populated
with `QFontDatabase.families()`; `QFontComboBox` looks like a text box and is
confusing. The combo keeps a saved family even if it is no longer installed, so
the preference is not lost.

## Themes

`src/esword4linux/ui/theme.py` is the **only** source of color:

- `LIGHT` / `DARK`: a `Palette` with `bg, panel, panel_alt, border, text,
  muted, accent, accent_text, link, highlight, comment_bg, verse_num`, plus the
  semantic tokens `success`, `error` and `strong`.
- In `DARK`, the `bg → panel → panel_alt` steps and the border have enough
  contrast to distinguish panels, entries and alternating rows.
- `ui_stylesheet(settings)` → application QSS (uses the UI typography).
- `document_css_for(settings)` → CSS embedded in every `QTextBrowser`.

Adding a color means adding it to **both** palettes and using it through
`palette()`. Do not write raw hex values in views. The theme is chosen in
**Edit → Preferences** (not the View menu), and the dialog preview uses the
same `palette()`.

## Rules

1. A new `QTextBrowser` **must** call
   `document().setDefaultStyleSheet(document_css(...))` and refresh it in
   `reload_theme()`.
2. No module HTML without `to_rich()`. It is the only sanitization boundary.
3. The commentary block uses a `<table>` with `border-left`: it is the reliable
   way to draw the accent bar in `QTextDocument` (`div` borders do not render
   correctly).
4. Internal links use their own schemes (`v:`, `c:`, `ref:`, `hit:`, `goref:`)
   with `setOpenLinks(False)` + `anchorClicked`. Never use `http` for internal
   navigation.

## e-Sword pseudo-tags (not HTML)

`to_rich()` / `to_plain()` convert 20 proprietary tags before sanitizing. If
treated as plain text, they are shown literally (`</red>`).

| Tag | Conversion |
|---|---|
| `<red>` | `<span style="color:#b03a2e">` |
| `<blu>` | blue |
| `<grk>`, `<gra>` | Greek font + italic |
| `<heb>`, `<H>`, `<h>`, `<Hebr>` | Hebrew font |
| `<lat>`, `<trn>`, `<tvm>` | italic |
| `<num>H1</num>` | `<a href="strong:H1">` |
| `<a href='#sG1645'>` | `<a href="strong:G1645">` |
| `<Pg>`, `<T>`, `<ST>`, `<st>`, `<BDB>`, `<bdb>`, `<TWOT>`, `<twot>`, `<SHE####>` | removed; text kept |

`is_markup()` decides whether content is real HTML or pseudo-tags: without it,
`<red>…</red>` falls into the plain-text branch and is escaped.

## Legacy codepages and transliterations

`to_plain(raw, hint)` / `to_rich(raw, hint)` receive the **module stem**. With
it:

- `font_codepages_for(hint)` → `\f1`/`\f2` as cp1253/cp1255 for known 8-bit
  Greek/Hebrew sources. Without it, Greek comes out as mojibake instead of
  proper Unicode.
- `transliteration_for(hint)` + `apply_transliteration()` → Latin-1 glyphs
  used by known legacy transliteration sources.

The vendored files **are not modified** (the optional `make drift` check
watches them); the hint only activates them.

## Pop-ups

- All use `src/esword4linux/ui/tooltip.py:TipBubble` (adaptive width up to
  600 px), not Qt's native tooltip. The document is **painted directly** (no
  `QTextBrowser` or viewport) and the height is
  `documentLayout().documentSize()` with `ceil` + padding + `BOTTOM_EXTRA`
  (5 px of safety). This keeps the last line and its descendants from being
  clipped, and QSS padding does not affect the measurement.
- Notes and references resolve their text **at paint time**; references go
  through `src/esword4linux/core/refresolver.py:RefResolver` (full verse, full
  range, or chapter capped at 10 verses).
- Strong numbers resolve **on hover** (`RichBrowser`, 180 ms, cache) because
  each one is a `SELECT` against the lexicon; the header uses the lexicon
  abbreviation, not the long title.

## Codepages: registry + detection

`font_codepages_for(stem)` covers known modules. For everything else,
`EswordModule.codepages` **detects** the codepage from content:
`src/esword4linux/core/legacy_scripts.py` looks for runs of `\'XX` escapes (a
Greek word produces 4–10 consecutive escapes; a Spanish accent usually appears
alone) and tries cp1253/cp1255. If decoding yields Greek/Hebrew letters in at
least 55 % of the sample, the map is adopted.

It is deliberately conservative: without evidence it returns `{}` and leaves
the text untouched. `to_plain`/`to_rich` accept an explicit `codepages=`;
callers pass `mod.codepages`.
