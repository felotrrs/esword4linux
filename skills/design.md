# Design — tool areas, widgets and activation

These are the arrangement rules the interface follows. They are **mandatory**:
a new tool, filter or panel that breaks them is a defect, even if it works.

The goal is a calm, predictable surface: controls never move under the user's
hand, never disappear, and every one stays reachable on a narrow window.

## 1. A tool area grows vertically; it never hides controls

When a row of controls does not fit the available width:

1. **Wrap to the next line.** The area grows vertically.
2. **Never clip, never hide, never scroll horizontally** to reach a control.

Use `src/esword4linux/ui/flow_layout.py:FlowLayout` for every horizontal row of
controls (toolbars, filter rows, headers with several controls):

```python
bar = QWidget()
flow = FlowLayout(bar, hspacing=GROUP_SPACING, vspacing=4)
flow.addWidget(self._group(label, combo))
```

The flow reports `hasHeightForWidth()`, so the parent layout gives it the height
of its lines. Its **minimum width is the widest single item**, not the sum of
the row: this is also what keeps the window's minimum width low.

The classic `QHBoxLayout` + `QScrollArea` pattern is **retired** for tool areas
(the Bible toolbar and the search filters were converted). Do not reintroduce
it: a horizontal scroller makes controls "vanish" and forces the user to
discover a scrollbar.

## 2. Labels stick to their control; groups are separated

- A label sits **immediately before** its control, at `FILTER_SPACING` (6 px).
- Two different groups are separated by `GROUP_SPACING` (8 px extra) so the
  eye can tell where one filter ends and the next begins.
- Inside a flow, the separation is the layout's `hspacing`; inside an explicit
  row, add a fixed spacer. **Never use a stretch to separate groups**: a
  stretch turns into a growing gap when the window grows, and the label ends
  up far from its control.
- A **label + control is one atomic unit**: wrap it in a small container
  (`SearchView._group(label, combo…)`) so the flow never splits the pair.

## 3. Fixed sizes, packed left, no growing gaps

- Controls have **fixed or bounded widths**. Choose the width for the content
  (a work title needs more room than a chapter number; both are still fixed).
- The row **packs to the left**; the free space goes to the **end** of the row.
- The result is deterministic: growing the window does not move or resize any
  control, and no gap opens between a label and its combo.
- Widths live in named constants at the top of the view, never scattered magic
  numbers.

Measured invariant (search view at 1200 and 1600 px): the four filters keep
`x = 33, 218, 562, 792` and `w = 140, 300, 170, 90`; the label→combo distance is
6 px in every state. Growing the window only adds space after the last group.

## 4. Disabled is visible, not hidden

- A control that is not applicable stays **visible but disabled** (`setEnabled`),
  so the interface never re-flows when a selection changes.
- The disabled state is a **visual signal**, not only a semantic one:
  - `QLabel#appSubtitle:disabled` → the label dims to the border tone;
  - `QComboBox#filterCombo:disabled` → the frame fades into the panel;
  - `QToolButton#filterReset:disabled` → text and frame fade.
- Disabling a control **clears its value** with signals blocked, so a disabled
  control can never keep filtering. Hidden controls are a last resort, only for
  a whole row that does not apply (the range row for a non-Bible type).

## 5. Activation follows the hierarchy

Filters that describe the same dimension are ordered from broad to narrow:

```
Testament → Group → Books range → Book → Chapters range → Chapter
```

- **Exact and range are mutually exclusive**: choosing one clears and disables
  the other. The newest choice wins.
- A control is enabled only if it can still add something: a book range has no
  single chapter numbering, so it disables the whole chapter dimension.
- **Ranges are forward-only**: the *to* selector offers only values at or after
  the *from* one (publication order for books, natural order for chapters).
- **The lists narrow themselves**: the groups come from the selected testament,
  the books from testament ∩ group. Only what the indexed modules actually
  contain is offered (the Apocrypha appears only when a Bible carries it).
- With nothing selected (“All”), everything available is enabled.
- Every disabled control contributes `None` to `SearchFilters`; the search
  must never receive a stale value from an inactive control.

## 6. Search is committed by a human action

- Typing **never** queries the index. The query runs on **Enter**, the
  **Search** button, or a programmatic request (`set_query`).
- Filter changes re-run the **committed** query, never the half-typed text.
- While the box holds an uncommitted query, the hint line says
  `search.press_enter`.
- The four modes live in one combo (`search.mode_*`): all → any → phrase →
  regex. “All of the words” is strict; there is no silent OR fallback.

## 7. Window minimum and typography

- The window minimum must stay below **~800 px** with the sidebar shown or
  hidden, or the window manager disables *maximise*.
- Typography and colours come **only** from `ui/theme.py` tokens
  (`palette(theme)`, `document_css_for`, `ui_stylesheet`). Never hardcode a
  colour in a view.
- Every user-visible string goes through `tr()` and exists in **both**
  `i18n/es.json` and `i18n/en.json` (see `skills/i18n.md`).

## 8. Checklist for a new tool area or filter

1. Build it from `FlowLayout` + atomic label/control groups, with fixed widths.
2. Give every control a disabled state that is visible and clears its value.
3. Decide its place in the activation hierarchy (§5) and clear the controls it
   makes redundant.
4. Keep the window minimum low: the flow's widest item is the floor.
5. Add the strings to both catalogs; add the QSS rule only if the generic
   `appSubtitle` / `filterCombo` rules do not already cover it.
6. Write the regression test in `tests/` (see `skills/testing.md`): the
   controls stay visible on a narrow window, keep their line/x across states,
   and the disabled ones send `None`.
7. Record the convention here if it is new; a one-line entry in
   `docs/CHANGELOG.md` describes the behaviour change.

## Related

- `skills/ui-layout.md` — window, tabs, panes and the view model.
- `skills/search-index.md` — the search engine and its filters.
- `skills/rendering.md` — RTF/HTML, typography and the document CSS.
- `skills/i18n.md` — strings and locales.
