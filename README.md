# esword4linux

**A native Linux reader for e-Sword modules — no Wine, no bundled content.**

[Español](README.es.md) · [Installation guide](docs/INSTALL.md) · [Documentation](docs/README.md) · [Changelog](docs/CHANGELOG.md)

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

The reference environment for v0.5.0 is:

- **Linux Mint 22.3** (Ubuntu 24.04/noble base), Cinnamon/X11
- **Python 3.12.3**
- A graphical desktop session. This guide was verified on X11; the PySide6
  package includes a Wayland plugin, but Wayland was not verified.
- **Internet access the first time** you run `./run.sh` or `make install`, so
  Python dependencies can be downloaded from PyPI. After the virtual
  environment is ready, normal launches work offline.

The project declares Python 3.10 or newer. Other Debian/Ubuntu-based releases
were not verified for v0.5.0.

### System dependencies on Linux Mint / Ubuntu

```bash
sudo apt update
sudo apt install -y python3 python3-venv
sudo apt install -y libegl1 libgl1 libxkbcommon-x11-0 libxcb-cursor0 \
    libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 \
    libxcb-render-util0 libxcb-shape0 libxcb-xkb1
```

If you install from Git or use the `make` commands, also install:

```bash
sudo apt install -y git make
```

If you use the command-line archive examples, also install `curl` and `unzip`:

```bash
sudo apt install -y curl unzip
```

`python3-pip` is not required by these instructions: the virtual environment
provides its own `pip`. The Qt package names above were verified on Linux Mint
22.3 against the actual PySide6 `libqxcb.so` plugin.

## Installation

Detailed prerequisites, troubleshooting, the validation matrix and uninstall
notes are in [`docs/INSTALL.md`](docs/INSTALL.md).

### Native Debian package (Ubuntu 24.04 / Linux Mint 22.x)

```bash
sudo apt install ./esword4linux_0.5.0-1_amd64.deb
esword4linux
```

The package bundles PySide6-Essentials, shiboken6, Qt 6 and PyYAML in a private
runtime under `/opt/esword4linux` and installs the desktop entry, icons, man
page and license texts. It uses the distribution `/usr/bin/python3` without
modifying system Python. Build it from a checkout with:

```bash
packaging/build-deb.sh
```

The result is `dist/deb/esword4linux_0.5.0-1_amd64.deb`. X11 was validated on
Linux Mint 22.3; Wayland was validated with Weston 13 headless/kiosk, but a
full desktop compositor session was not available during packaging.

### From Git

```bash
git clone https://github.com/felotrrs/esword4linux.git
cd esword4linux
./run.sh
```

The first `./run.sh` creates `.venv`, installs PySide6-Essentials and PyYAML
from PyPI, and opens the application. This first step needs Internet access.
Later launches use the existing environment and work offline.

For development, `make install` creates the same virtual environment and also
installs the `dev` extra (`pytest`):

```bash
make install
make run
```

### From a source ZIP/TAR archive

Download the v0.5.0 source archive from GitHub:

- [esword4linux v0.5.0 tar.gz](https://github.com/felotrrs/esword4linux/archive/refs/tags/v0.5.0.tar.gz)
- [esword4linux v0.5.0 zip](https://github.com/felotrrs/esword4linux/archive/refs/tags/v0.5.0.zip)

Extract it with your file manager, or from a terminal:

```bash
curl -L -o esword4linux-v0.5.0.tar.gz \
  https://github.com/felotrrs/esword4linux/archive/refs/tags/v0.5.0.tar.gz
tar -xzf esword4linux-v0.5.0.tar.gz
cd esword4linux-0.5.0
./run.sh
```

For the ZIP archive, replace the download and extraction commands with
`curl -L -o esword4linux-v0.5.0.zip ...` and `unzip esword4linux-v0.5.0.zip`.
The command-line examples use `curl`, `tar` and `unzip`; a file manager works
too.

### First launch

On first launch, esword4linux asks for the folder containing your e-Sword
modules (`.bblx`, `.bbli`, `.cmtx`, `.cmti`, `.dctx`, `.lexi`, `.refx`,
`.topx`, `.devx`, `.harx`, `.mapx`, `.twm`, …). If you cancel, the app exits.
You can change the folder later from **File → Change modules folder**.

## Launch

From the checkout:

```bash
./run.sh
```

Or, after `make install`:

```bash
make run
```

### Desktop launcher

After `./run.sh` or `make install` has created the virtual environment, run:

```bash
make desktop
```

This installs `~/.local/share/applications/esword4linux.desktop` and the
application icons under `~/.local/share/icons/hicolor/`. The launcher uses the
`run.sh` script in the **current checkout location**; if you move or delete the
checkout, the menu entry stops working. Run `make desktop` again from the new
location to repair it.

The menu entry may take a moment to appear, or may require logging out and back
in.

## Uninstall

v0.5.0 has no system-wide installer and no `make uninstall` target. The
application runs from the checkout and stores user data separately.

1. Delete the checkout folder (for example `esword4linux` or
   `esword4linux-0.5.0`).
2. If you ran `make desktop`, remove the launcher and icons:

   ```bash
   rm -f ~/.local/share/applications/esword4linux.desktop
   rm -f ~/.local/share/icons/hicolor/*/apps/esword4linux.png
   gtk-update-icon-cache -f -t ~/.local/share/icons/hicolor 2>/dev/null || true
   update-desktop-database ~/.local/share/applications 2>/dev/null || true
   ```

Your settings and search cache are **preserved** by default:

- `~/.config/esword4linux/` (preferences)
- `~/.cache/esword4linux/` (catalog and search index)

Remove them manually only if you want a completely clean uninstall:

```bash
rm -rf ~/.config/esword4linux ~/.cache/esword4linux
```

Your e-Sword modules folder is never modified by esword4linux. Delete it only
if you want to remove your own modules.

`make clean` removes only `.venv`, `.pytest_cache` and the repository `.cache`;
it does **not** remove the XDG configuration/cache or the desktop launcher and
icons.

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

## Distribution status

v0.5.0 is distributed as Git source, as the GitHub tag archives and as a native
Debian package for Ubuntu 24.04 / Linux Mint 22.x (amd64). No AppImage, Flatpak
or Snap package is provided yet. See
[`docs/INSTALL.md`](docs/INSTALL.md#distribution-status-and-validation-matrix)
for what was actually validated.

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
