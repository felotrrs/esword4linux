# Books, aliases and references

## Single source

`src/esword4linux/core/books.yaml` is the **only** definition of:

- the 73 e-Sword books (`id` 1–73);
- their names in `es`, `en`, `fr` and `pt`;
- abbreviations and aliases from different publishing traditions.

`src/esword4linux/core/books.py` loads the YAML, normalizes it and exposes
`BOOKS`, `book_name()`, `book_abbrev()`, `resolve_book()` and
`parse_reference()`. **Do not create book or alias lists in other modules,
tests, documentation or the UI.**

Provenance: the base aliases were imported from an earlier internal project.
They now live in `src/esword4linux/core/books.yaml` so esword4linux starts
without depending on any external repository.

## YAML schema

```yaml
books:
  genesis:
    id: 1
    names: {es: Génesis, en: Genesis, fr: Genèse, pt: Gênesis}
    abbreviations: {es: [gn, gen], en: [gen, ge]}
    aliases:
      es: [genesis, gen, gn, ge]
      en: [genesis, gen, gn, ge]
      fr: [genèse, genese, gen, gn]
      pt: [gênesis, genesis, gen, gn]
```

You do not need to enumerate accent, case or punctuation variants: the loader
applies NFD, lowercases, removes diacritics and punctuation, and collapses
whitespace. You do need to add **genuinely different spellings** (`gen` and
`gn`, `jhn` and `john`).

## Numbered books

Series (Samuel, Kings, Chronicles, Corinthians, Thessalonians, Timothy, Peter,
the letters of John, Maccabees) are declared once in `families`:

```yaml
families:
  corinthians:
    default: 46        # numberless form → 1 Corinthians
    books: {1: 46, 2: 47}
    aliases: [corintios, cor, co, corinthians, corinthiens]
```

`resolve_book()` understands `1`, `2`, `3`, `I`, `II`, `III`,
`Primera/Segunda/Tercera`, `1ª`, `1a`, `1ra`, `first/second/third`, etc.
Do not duplicate prefixed aliases in the YAML.

`john_letters` has `default: null` on purpose: "Juan"/"John" without a number
is the Gospel (43), not 1 John (62).

## Detection in text (`src/esword4linux/core/refs.py`)

`find_reference_spans()` links citations in bibliography text and returns one
span per sub-reference. Covered formats:

```
Ex. 32.1–6      Ex. 7.8ss        (Heb. 5.4; 7.11)
(Ex. 4:14, 27-30)   Exo_28:1; Heb_5:4   John 3,16
I Samuel 1:1    First Corinthians 13:4   Genesis 1-3
The Wisdom of Solomon 2:23   Song of Songs 1:1
```

- Comma as chapter–verse separator (`John 3,16`) and as continuation
  (`Ex. 4:14, 27-30`).
- Chapter–verse with `.`, `:`, `,` or a space.
- Multi-word names: extensions to the left up to 6 words are attempted
  (`_extend_book`), without building a giant alternation.
- Books that do not exist in the 1–73 numbering (`1 Esdras`, `3 Macc`) are
  **not linked to another book**: they are discarded.
- `SCAN_CHARS = 200_000` so citations near the end of long entries are still
  linked.

## Pop-ups

`src/esword4linux/core/refresolver.py:RefResolver` is the only passage-pop-up
implementation (used by the Bible, the library and the commentary):

- single verse → full text, no `snippet`;
- range → every verse in the range;
- chapter or open-ended range → at most `MAX_VERSES = 10`;
- if there are more, `tooltip.more_verses` is appended with the remaining
  count.

The reference Bible is the active one unless the user has configured another;
if none is configured, `RefResolver` falls back to the first available Bible in
the user's catalog. Nothing is hardcoded.

`src/esword4linux/core/strong.py:StrongIndex.tooltip()` uses only the lexicon
**abbreviation** in the header (not the long title), caps the entry at 2,500
characters and, when truncated, points to the Lexicon panel for the full entry.

## Adding a language or an alias

1. Edit only `src/esword4linux/core/books.yaml` (names and aliases).
2. Add a case to `tests/test_books.py` / `tests/test_matching.py`.
3. `make test` is green and `./run.sh` still starts.
