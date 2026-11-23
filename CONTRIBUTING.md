# Contributing to esword4linux

Thanks for helping improve a native Linux reader for e-Sword modules.

## Ground rules

1. **Never commit e-Sword modules or other copyrighted content.** The repository
   must stay free of `.bblx`, `.cmtx`, `.dctx`, `.lexi`, `.refx`, `.mapx` and
   similar files. `.gitignore` blocks them on purpose.
2. **The modules folder is immutable.** esword4linux opens every module with
   `mode=ro`. It never repairs, normalises, rewrites or reorders a module. If a
   module contains typos, mojibake or duplicates, display it as-is.
3. **Classify by SQL structure, not by extension.** Many real modules use an
   extension that does not match their actual schema.
4. **Reading and searching are independent.** A module must be readable even
   when no search index exists.
5. **No automatic work at startup.** The first run only asks for a folder and
   scans metadata. Indexing and decryption are always explicit user actions.
6. **No hardcoded modules.** Do not add a default Bible, a preindex list or a
   path under a developer's home directory.
7. **All code comments, docstrings, docs and CLI messages are English.** The UI
   remains bilingual through `src/esword4linux/i18n/es.json` and `en.json`.

Read [AGENTS.md](AGENTS.md) and the relevant [skill](skills/) before changing an
area. The skills are the detailed conventions for modules, decryption, search,
design (widgets, wrapping and filter activation), UI layout, rendering, book
aliases, i18n, testing and performance.

## Development setup

```bash
make install
make test
./run.sh
```

`run.sh` creates `.venv`, installs the project in editable mode and starts the
app.

## Tests

The default suite must pass without any e-Sword module:

```bash
make test
```

Tests that need real modules are skipped unless `ESWORD4LINUX_TEST_CORPUS` points
at a folder containing them:

```bash
ESWORD4LINUX_TEST_CORPUS=/path/to/modules .venv/bin/python -m pytest -q
```

Do not make tests depend on a developer's cache, settings or home directory.
Use temporary catalogs (`tmp_path`) and the fixtures in `tests/conftest.py`.

## Documentation

- `README.md` is English; keep `README.es.md` in sync for user-facing changes.
- Architecture, format notes, technical debt and ADRs live in `docs/`.
- Project conventions live in `AGENTS.md` and `skills/`.
- Maintainer release steps live in `docs/RELEASING.md`.

## Commits and pull requests

- Keep changes focused and explain the user-visible behaviour.
- Mention which modules or module structures you tested with, but do not attach
  the modules themselves.
- If behaviour changes, add an entry to `docs/CHANGELOG.md`.
- If you add a new convention, document it in the owning skill.

## License

By contributing you agree that your changes are licensed under GPL-3.0, the
same license as the project. The vendored e-Sword core files keep their original
provenance headers; do not remove them.
