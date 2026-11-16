# e-Sword module format — reverse-engineering notes

Reference document. Everything described here was verified against a private
validation corpus of e-Sword modules. That corpus is not distributed with
esword4linux; see [Validation corpus](#6-validation-corpus).

## 1. Container

**All** modules are SQLite 3 databases. Text encoding is UTF-16LE in older
modules and UTF-8 in modern ones. SQLite handles this transparently, and the
driver returns `str`.

```
$ file example.bblx
SQLite 3.x database ... UTF-16 little endian
```

## 2. Schemas by type

### Bible — `.bblx` / `.bbli`

```sql
Details (Title, Abbreviation, Information, Version,
         OldTestament, NewTestament, Apocrypha, Strongs, RightToLeft)
Bible   (Book INT, Chapter INT, Verse INT, Scripture TEXT|BLOB)
sqliteplus_license (Name)   -- only when encrypted
```

- `Book` 1–66 is canonical; 67–73 are deuterocanonical in some editions.
- `.bbli` uses the same schema, with `Scripture` always `TEXT` (plain).
- `.bblx` may store `Scripture` as an encrypted `BLOB`.

### Commentary, new schema — `.cmtx`

```sql
Details (Title, Abbreviation, Information, Version)
Books   (Book, Comments)
Chapters(Book, Chapter, Comments)
Verses  (Book, Chapter, Verse, Comments)
```

### Commentary, old schema — `.cmti` (and some `.cmtx`)

```sql
Details (Title, Abbreviation, Information, Version)
BookCommentary   (Book, Comments)
ChapterCommentary(Book, Chapter, Comments)
VerseCommentary  (Book, ChapterBegin, VerseBegin,
                  ChapterEnd, VerseEnd, Comments)
```

`VerseCommentary` covers a range: `[ChapterBegin:VerseBegin, ChapterEnd:VerseEnd]`.
In the validation corpus, some `.cmti` modules and a few `.cmtx` files use this
schema.

### Dictionary — `.dctx` / `.dcti`

```sql
Details (Title, Abbreviation, Information, Version)
Dictionary (Topic NVARCHAR(100), Definition BLOB_TEXT|TEXT)
```

### Lexicon — `.lexi` / `.lexx`

Structurally identical to a dictionary, but with a `Lexicon` table.

### Reference — `.refi` / `.refx`

```sql
Details   (Title, Abbreviation, Information, Version)
Reference (Chapter, Content)
```

Each `Chapter` is a thematic entry with rich HTML. In the validation corpus,
most modules under a `LIBROS/` folder use this shape. **A `.refx` with a
`Topics` table is a topic**, not a reference.

### Topic — `.topx`

```sql
Topics (Title NVARCHAR(100), Notes TEXT)
```

### Devotional — `.devx`

```sql
Details   (Description, Abbreviation, Comments, Version)
Devotions (Month, Day, Devotion)
```

### Harmony — `.harx`

```sql
Details  (Description, Abbreviation, Comments, Version)
Sections (ID, Title)
Parts    (Section, Part, Reference)
```

`Parts` has one row per reference, so `(Section, Part)` repeats. The navigable
unit is the section; its references are deduplicated when listed.

### Maps — `.mapx`

```sql
Details  (Description, Abbreviation, Comments, Version)
Graphics (Title, Details, Picture BLOB)
```

`Picture` is the image (PNG/JPEG). It is **not** decrypted: it is not a textual
content column. `Details` is the caption; some modules encrypt it with
SQLitePlus without compression (UTF-16LE RTF with a 5-byte header).

### TWM — `.twm`

```sql
config (name, value)
topics (id, pid, subject, rel_order, content_type)
content(topic_id, data, data2)
topics_wordindex (id, word, priority)
```

The title is stored in `config` with `name='title'`. `content.data` is RTF.

### Localisation — `.lanx`

```sql
Languages (ID, Language, Localized, RightToLeft, Skip)
<Language> (Tag, Caption)   -- one table per language: Spanish, English, ...
```

These are e-Sword interface strings, not biblical content. esword4linux
catalogs them but does not use them.

### Headings — `.en` / `.es` / `.fr` / `.pt`

```sql
Headings (Book, Chapter, Verse, Title)
```

Standalone section titles. They are not complete modules and remain
`kind=unknown`.

## 3. SQLitePlus encryption

See `skills/decryption.md` for the details. Summary:

- Marker: the `sqliteplus_license` table.
- Cipher: **Twofish-128-ECB**, key `"Heb_4:12"` (16 bytes, zero-padded).
- Blob: `[0] checksum | [1..3] u24 compressedSize | [4] 0x1F |
  [5..8] u32 expectedSize | [9..] zlib`.
- **`compressedSize` is 24-bit**, not 16. Reading it incorrectly breaks records
  larger than 64 KiB (for example, long dictionary or commentary articles).

## 4. Rich content

Three encodings coexist in the same columns:

| Encoding | Detection | Example |
|---|---|---|
| RTF | `{\rtf`, `\pard`, `{\b`, `\cfN` | most `.cmti` commentaries |
| HTML | `<p ...>`, `<span ...>`, `<ref>` | modern `.refi` and `.dctx` modules |
| Plain text | none of the above | `.bbli`; `.bblx` after decryption |

e-Sword RTF usually arrives **without a header** and with groups embedded in the
middle of the text. The default codepage is `cp1252`; Greek and Hebrew use
8-bit fonts.

`<ref>John 3:16</ref>` is a clickable cross-reference.

## 5. Book numbering

| Range | Content |
|---|---|
| 1–39 | Old Testament |
| 40–66 | New Testament |
| 67–73 | Deuterocanonical books (Tobit, Judith, Wisdom, Sirach, Baruch, 1–2 Maccabees) |

**Never** map by number across different sources: deuterocanonical numbering
changes between e-Sword, Zefania and the LXX. Map by name.

## 6. Validation corpus

The schemas, heuristics and edge cases in this document were validated against a
private validation corpus containing Bibles, commentaries, dictionaries,
lexicons, references, topics, devotionals, harmonies, maps and TWM modules,
including SQLitePlus-encrypted files and duplicate copies in nested folders.

That corpus is not part of the repository and is never redistributed. It is used
only during development to confirm structure detection, decryption and text
rendering. Tests that need real modules are skipped unless a developer points
them at their own corpus with `ESWORD4LINUX_TEST_CORPUS`.

An installed esword4linux catalog is built exclusively from the folder the user
selects. No module content is bundled with, or downloaded by, the application.

## 7. Pitfalls encountered

| Pitfall | Effect | Fix |
|---|---|---|
| Extension ≠ type | `.refx` classified as a Reference | dispatch by tables |
| `compressedSize` as u16 | articles > 64 KiB fail to decrypt | read u24 |
| RTF without a header | visible `\pard` in the text | `_is_rtf` heuristic |
| Mass `\par` in RTF | huge gaps when reading | `_tidy()` collapses `<br>` |
| `Verses` vs `VerseCommentary` | empty commentary | support both schemas |
| `topics` vs `Topics` | TWM/topic confusion | distinguish case + `config` |
| Duplicates across folders | the same module twice | sha1 fingerprint |
| NT-only modules | Psalms does not exist | `bible.not_available` |
