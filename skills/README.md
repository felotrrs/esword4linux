# Skills — esword4linux conventions

Each file describes a **mandatory** convention. Read the skill for an area
before creating or modifying code there.

## Index

| Skill | Read it when… |
|---|---|
| [`esword-modules.md`](esword-modules.md) | You read a module, add a new type or table, or touch `src/esword4linux/core/esword/module.py`. |
| [`decryption.md`](decryption.md) | You touch Twofish, SQLitePlus, keys or per-column decryption. |
| [`search-index.md`](search-index.md) | You touch FTS5, `build_match`, the indexer, search scope, filters, modes or index states. |
| [`design.md`](design.md) | You add or move a tool area, a filter, a toolbar or a panel; you touch widget sizing, wrapping, the activation hierarchy or the disabled state. |
| [`ui-layout.md`](ui-layout.md) | You touch the window, tabs, sidebar, panes, views or layout persistence. |
| [`rendering.md`](rendering.md) | You touch RTF/HTML, `to_rich`, typography, themes or the document CSS. |
| [`book-aliases.md`](book-aliases.md) | You touch books, testaments/groups, aliases, reference detection or passage/Strong pop-ups. |
| [`i18n.md`](i18n.md) | You add UI strings, add a language or touch `tr()`. |
| [`testing.md`](testing.md) | You add or adapt a test, a fixture or a synthetic module. |
| [`performance.md`](performance.md) | You measure performance, change the pool or adjust cache size. |

## Cross-cutting rule

Before adding a list (categories, books, testaments, groups, colors, strings),
check whether it already exists in its single source (`AGENTS.md`, rule 6).
Duplicating it is a defect.
