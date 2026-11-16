# Installation guide — Linux Mint and Ubuntu

This guide covers a source installation of **esword4linux v0.5.0** on
Debian/Ubuntu-based systems. It does not install a system package: the
application runs from a checkout and keeps user data in XDG directories.

## Verified environment

The commands and package names below were verified against:

- **Linux Mint 22.3** (Ubuntu 24.04/noble base)
- **Python 3.12.3**
- **Cinnamon / X11**
- The actual PySide6 Qt plugin `libqxcb.so` from the project virtual environment

The project declares Python 3.10 or newer. Other Mint or Ubuntu releases were
**not verified** for v0.5.0. In particular, Wayland was not verified; the
PySide6 package does include a Wayland platform plugin.

## 1. Install system dependencies

Update the package index and install Python and the Qt runtime libraries:

```bash
sudo apt update
sudo apt install -y python3 python3-venv
sudo apt install -y libegl1 libgl1 libxkbcommon-x11-0 libxcb-cursor0 \
    libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 \
    libxcb-render-util0 libxcb-shape0 libxcb-xkb1
```

If you will install from Git or use the `make` commands, also install:

```bash
sudo apt install -y git make
```

If you use the command-line archive examples, also install `curl` and `unzip`:

```bash
sudo apt install -y curl unzip
```

Notes:

- `python3-pip` is not required. `run.sh` creates a virtual environment and
  uses the `pip` inside it.
- `git` is only needed for the Git installation method.
- `make` is only needed for `make install`, `make run`, `make desktop`,
  `make test`, `make scan`, `make encrypted`, `make dedup`, `make drift` and
  `make clean`.
- Do not run the application or `make desktop` with `sudo`. Everything is
  installed under your user account.

## 2. Install the application

### Option A — from Git

```bash
git clone https://github.com/felotrrs/esword4linux.git
cd esword4linux
./run.sh
```

The first `./run.sh` creates `.venv`, installs PySide6-Essentials and PyYAML
from PyPI, and opens the application.

For a development setup that also installs `pytest`:

```bash
make install
make run
```

### Option B — from a source ZIP/TAR archive

Download the v0.5.0 source archive:

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

For the ZIP archive:

```bash
curl -L -o esword4linux-v0.5.0.zip \
  https://github.com/felotrrs/esword4linux/archive/refs/tags/v0.5.0.zip
unzip esword4linux-v0.5.0.zip
cd esword4linux-0.5.0
./run.sh
```

The command-line examples use `curl`, `tar` and `unzip`; a graphical file
manager and archive tool work as well. The extracted folder is named
`esword4linux-0.5.0`.

## 3. First launch and offline use

The first installation needs Internet access because `run.sh` downloads
PySide6-Essentials and PyYAML from PyPI. Once `.venv` exists and imports work,
normal launches do not need network access.

On first launch, the application asks for the folder containing your e-Sword
modules. Select the folder that contains your `.bblx`, `.bbli`, `.cmtx`,
`.cmti`, `.dctx`, `.lexi`, `.refx`, `.topx`, `.devx`, `.harx`, `.mapx`,
`.twm`, etc. files. If you cancel, the application exits. You can change the
folder later from **File → Change modules folder**.

The modules folder is opened read-only. The catalog, settings and search index
live outside it.

## 4. Launch the application

From the checkout:

```bash
./run.sh
```

Or, after `make install`:

```bash
make run
```

### Desktop launcher

After `./run.sh` or `make install` has created `.venv`, run:

```bash
make desktop
```

This creates:

- `~/.local/share/applications/esword4linux.desktop`
- `~/.local/share/icons/hicolor/<size>/apps/esword4linux.png` (16–512 px)

The desktop entry runs `run.sh` from the **current checkout path**. If you move
or delete the checkout, the launcher stops working. Run `make desktop` again
from the new location to repair it.

The menu entry may take a moment to appear. If it does not, log out and back in,
or run:

```bash
gtk-update-icon-cache -f -t ~/.local/share/icons/hicolor 2>/dev/null || true
update-desktop-database ~/.local/share/applications 2>/dev/null || true
```

## 5. Uninstall

v0.5.0 has no system-wide installer and no `make uninstall` target. The
application runs from the checkout, so removal is manual.

1. Delete the checkout directory (for example `esword4linux` or
   `esword4linux-0.5.0`).
2. If you ran `make desktop`, remove the desktop entry and icons:

   ```bash
   rm -f ~/.local/share/applications/esword4linux.desktop
   rm -f ~/.local/share/icons/hicolor/*/apps/esword4linux.png
   gtk-update-icon-cache -f -t ~/.local/share/icons/hicolor 2>/dev/null || true
   update-desktop-database ~/.local/share/applications 2>/dev/null || true
   ```

The following user data is **preserved** by default:

| Path | Contents |
|---|---|
| `~/.config/esword4linux/` | Preferences (`settings.json`) |
| `~/.cache/esword4linux/` | Catalog (`catalog.db`) and search index (`content.db`) |

Remove them only if you want a completely clean uninstall:

```bash
rm -rf ~/.config/esword4linux ~/.cache/esword4linux
```

Your e-Sword modules folder is never modified by esword4linux. Delete it only
if you want to remove your own modules.

`make clean` removes only `.venv`, `.pytest_cache` and the repository `.cache`.
It does **not** remove the XDG configuration/cache, the desktop entry or the
icons.

## Troubleshooting

### `python3 -m venv` fails

Symptom:

```text
No module named venv
```

or:

```text
ensurepip is not available
```

Install the virtual-environment package, remove any partial environment and
retry:

```bash
sudo apt install -y python3-venv
rm -rf .venv
./run.sh
```

### Qt cannot load the `xcb` platform plugin

Typical symptom:

```text
qt.qpa.plugin: Could not load the Qt platform plugin "xcb" in "" even though it was found.
```

Install the Qt runtime libraries from step 1, then check for unresolved
libraries:

```bash
ldd .venv/lib/python*/site-packages/PySide6/Qt/plugins/platforms/libqxcb.so \
  | grep "not found"
```

If the command prints nothing, all linked libraries are resolved. If it prints
a library name, install the matching `libxcb-*` or related package from step 1.

### `make: command not found`

Install `make`:

```bash
sudo apt install -y make
```

### The first run fails while downloading dependencies

The first installation needs PyPI access. Check the network, proxy settings or
package mirror, then retry:

```bash
rm -rf .venv
./run.sh
```

### The desktop entry does not appear

Run `make desktop` again from the checkout, then log out and back in. Verify
that the file exists:

```bash
ls -l ~/.local/share/applications/esword4linux.desktop
```

### The launcher stopped working after moving the project

The desktop entry contains the checkout path. Run `make desktop` from the new
location.

## Distribution status

**v0.5.0 is source-only.** No DEB, AppImage, Flatpak or Snap package is provided.
Install from Git or from the GitHub tag source archives.

## Unresolved technical uncertainty

- Wayland was not tested. The reference session was Cinnamon/X11.
- Only Linux Mint 22.3 (Ubuntu 24.04/noble base) and Python 3.12.3 were verified.
- No `make uninstall` target exists in v0.5.0; the manual commands above are the
  documented removal method.
