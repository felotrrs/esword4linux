# esword4linux

**A native Linux reader for e-Sword modules — no Wine, no bundled content.**

[Español](README.es.md) · [Documentation](docs/README.md) · [Changelog](docs/CHANGELOG.md)

<p align="center">
  <img src="packaging/icons/hicolor/256x256/apps/esword4linux.png" alt="esword4linux icon" width="128">
</p>

esword4linux opens the SQLite modules you already own from **one folder of your
choice**. It classifies each file by its database structure rather than its
extension, and never modifies a single byte of your library.

> **No Bibles, commentaries, dictionaries or other e-Sword modules are included
> in this repository.** You choose the folder that contains your own modules on
> first run. e-Sword modules are copyrighted by their respective publishers.

## Features

- **One modules folder.** Read any supported e-Sword module in place, read-only.
- **Structure-based detection.** `.refx` files that are really topics and
  `.cmtx` files using the old commentary schema are classified correctly.
- **Workspace tabs.** Each tab holds its own main resource, parallel Bible and
  commentary panel. Selecting a module reuses the active tab; `Ctrl+T` creates
  another workspace.
- **Organisable sidebar.** Group by type, language and work, combine up to three
  levels, and filter by several types or languages at once (`Ctrl+B` toggles it).
- **Bible reading.** Parallel translation, chapter navigation, multi-reference
  citation chains, verse pop-ups and Strong's number pop-ups.
- **Commentary and lexicon panels.** Commentary is matched to the active Bible
  and shown in a bottom panel; Strong's entries open in the same area.
- **Unified search.** One box understands Bible references, Strong's numbers and
  free text. The FTS5 index is optional and built only when you ask for it.
- **Encrypted modules.** SQLitePlus/Twofish-128 modules can be read and indexed.
- **Bilingual UI.** Spanish and English, switchable at runtime.
- **Readable typography.** Independent fonts for the interface, Scripture and
  running text; light and dark themes.

## Requirements

- Linux
- Python 3.10 or newer
- PySide6 (Qt 6) and PyYAML, installed automatically by `run.sh` or `pip`

The application starts without network access and without Wine.

## Quick start

```bash
git clone https://github.com/felotrrs/esword4linux.git
cd esword4linux
./run.sh
```

The first run creates a local virtual environment, installs dependencies and
opens the app. Alternatively:

```bash
make install
make run
```

On first launch, esword4linux asks for the folder containing your e-Sword
modules (`.bblx`, `.bbli`, `.cmtx`, `.cmti`, `.dctx`, `.lexi`, `.refx`,
`.topx`, `.devx`, `.harx`, `.mapx`, `.twm`, …). If you cancel, the app exits.
You can change the folder later from **File → Change modules folder**.

## Reading vs. indexing

Reading is direct and does not need an index. The first scan only collects
metadata so the sidebar can show your library.

Build search indexes only when you want them:

- **Index → Index this category** for one kind of module
- **Index → Index everything** for the whole library
- **Index → Decrypt encrypted modules** for SQLitePlus modules
- or from the command line:

```bash
make scan          # metadata only
make encrypted     # decrypt and index encrypted modules (explicit)
python tools/bootstrap.py --kind bible
python tools/bootstrap.py --all
```

No module is indexed or decrypted automatically at startup.

## Data locations

| What | Where |
|---|---|
| Modules | Your own folder, read-only |
| Settings | `~/.config/esword4linux/settings.json` |
| Catalog | `~/.cache/esword4linux/catalog.db` |
| Search index | `~/.cache/esword4linux/content.db` |

The catalog and the search index are regenerable. Deleting the cache is safe;
your modules are never touched.

## Supported module families

| Family | Typical extensions | Detection |
|---|---|---|
| Bibles | `.bblx`, `.bbli` | `Bible` table |
| Commentaries | `.cmtx`, `.cmti` | `Verses`, `VerseCommentary`, `BookCommentary` or `ChapterCommentary` |
| Dictionaries | `.dctx`, `.dcti`, `.twm` | `Dictionary`, or `topics` + `config` |
| Lexicons | `.lexi`, `.lexx` | `Lexicon` |
| Books / references | `.refx`, `.refi`, `.topx` | `Reference` or `Topics`, refined by content |
| Devotionals | `.devx` | `Devotions` or `Devotional` |
| Harmonies | `.harx` | `Sections` + `Parts` |
| Maps | `.mapx` | `Graphics` |

The extension is only used to discover files. The type always comes from the
SQL structure.

## Development

```bash
make install
make test
```

The test suite runs without any e-Sword modules. Tests that need real modules
are skipped unless you point them at a corpus:

```bash
ESWORD4LINUX_TEST_CORPUS=/path/to/modules .venv/bin/python -m pytest -q
```

Never commit modules to the repository. `.gitignore` blocks the common e-Sword
extensions on purpose.

See [AGENTS.md](AGENTS.md) for the project rules, [CONTRIBUTING.md](CONTRIBUTING.md)
for the development workflow, and [docs/](docs/) for architecture, format notes,
technical debt and ADRs.

## License

**GPL-3.0**. The Twofish decryptor is a port of
[KingJamesPureBibleSearch](https://github.com/dewhisna/KingJamesPureBibleSearch)
(© Donna Whisnant, GPL-3.0). See [LICENSE](LICENSE) and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

e-Sword modules are the property of their respective rights holders.
esword4linux is only a reader: it neither distributes nor modifies their
content.
