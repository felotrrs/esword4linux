# Third-party notices

esword4linux is distributed under **GPL-3.0-only**. It includes or depends on
the following third-party components.

## Vendored e-Sword core

These files live under `src/esword4linux/core/esword/` and keep their original
provenance headers:

| File | Origin | License |
|---|---|---|
| `twofish.py` | Port of KingJamesPureBibleSearch, © Donna Whisnant | GPL-3.0 |
| `sqliteplus.py` | SQLitePlus reader derived from the same project | GPL-3.0 |
| `rtf.py` | RTF-to-text/HTML converter from the shared e-Sword core | GPL-3.0 |
| `font_codepages.py` | Legacy font codepage mapping | GPL-3.0 |
| `legacy_translit.py` | Legacy transliteration mapping | GPL-3.0 |

Upstream: <https://github.com/dewhisna/KingJamesPureBibleSearch>

These vendored files keep their upstream headers and comments; they are not
translated or reformatted in order to preserve provenance and drift checks.

The GPL-3.0 license text is in [LICENSE](LICENSE).

## Runtime dependencies

| Component | License | Use |
|---|---|---|
| [PySide6 / Qt 6](https://www.qt.io/) | LGPL-3.0 / GPL-3.0 | GUI toolkit |
| [PyYAML](https://pyyaml.org/) | MIT | Loads `core/books.yaml` |

PySide6 and PyYAML are installed from PyPI; their own license files apply.

## e-Sword modules

e-Sword modules are **not** part of this project. They are copyrighted by their
respective publishers and are supplied by the user. esword4linux reads them
in place, read-only, and never redistributes their content.
