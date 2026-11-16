# ADR-0002 — Books and aliases in YAML (PyYAML)

- **Date**: 2026-11-11
- **Status**: accepted

## Context

The book table lived in `core/books.py` as Python tuples with Spanish/English
aliases. As names and abbreviations from other traditions were added, two
problems appeared:

1. **There was no readable source** for reviewing or extending aliases: every
   new format (`Luk`, `Jhn`, `Rth`, `Ezk`, `I/II` prefixes, `Primera de…`,
   French or Portuguese names) required editing code.
2. **Real-world aliases were missing** (the Bible project's registry contains
   hundreds of them), and numbered books duplicated variants with a prefix.

The application must still start **offline**; the YAML is read once at import
time.

## Decision

Move books, names and aliases to `src/esword4linux/core/books.yaml`, loaded by
`src/esword4linux/core/books.py`. The YAML separates:

- `families`: numbered series with `default` and `books` (for example,
  Corinthians 1→46, 2→47) plus base aliases without a number;
- `books`: the 73 e-Sword IDs with `es/en/fr/pt` names, abbreviations and
  explicit aliases.

Add **PyYAML>=6** as a runtime dependency.

## Alternatives considered

| Option | Why not |
|---|---|
| **Keep Python tuples** | That is the current situation: hard to read when extending aliases and prone to duplicating variants. |
| **JSON** | The user and the Bible project use YAML; JSON does not support comments or readable multi-line lists. |
| **TOML** | `tomllib` requires Python ≥3.11 and the project declares ≥3.10; the nested per-language schema also becomes more verbose. |
| **A custom YAML parser** | An unnecessary error surface for a data file that is read once. |
| **Read the Bible project's YAML at runtime** | It couples esword4linux to another installation and breaks startup when that repository is absent. |

## Consequences

**Positive**

- A single source for the 73 books and all their aliases; adding a language
  means adding a block to the YAML.
- Tests verify IDs, names and formats without touching loader code.
- The YAML is shipped as package data for the `esword4linux.core` package via
  `[tool.setuptools.package-data]` (`"esword4linux.core" = ["*.yaml"]` in
  `pyproject.toml`).

**Negative**

- A new, small dependency (~700 KB) and one more installation step.
- Malformed YAML prevents startup; the loader raises an explicit error including
  the file path.
