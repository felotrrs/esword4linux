# Installation guide — Linux Mint and Ubuntu

This guide covers the native Debian package of **esword4linux v0.5.0** and,
as an alternative, a source installation on Debian/Ubuntu-based systems. Both
keep user data in the XDG directories and never modify the e-Sword modules
folder.

## Native Debian package

The package installs the application in `/usr/bin/esword4linux`, its private
Python/Qt runtime in `/opt/esword4linux`, and the desktop entry, hicolor icons,
man page and license texts in their standard locations. It does not install
anything into the system Python environment and does not depend on the
distribution Qt libraries at runtime.

### Supported platforms

- Ubuntu 24.04 LTS (noble), amd64.
- Linux Mint 22.x (Ubuntu 24.04 base), amd64.

The package bundles Qt 6.12.0 built against glibc 2.34 or newer. Other Ubuntu,
Mint or Debian releases, other architectures and non-glibc systems are **not
claimed as supported** without validation. See the validation matrix at the
end of this document.

### Build prerequisites

On Ubuntu 24.04 / Linux Mint 22.x:

```bash
sudo apt update
sudo apt install -y build-essential debhelper dpkg-dev fakeroot \
    python3 python3-pip python3-yaml ca-certificates lintian
```

`lintian` is optional. The build downloads the pinned PySide6-Essentials,
shiboken6 and PyYAML wheels with SHA-256 verification; after that, use
`--offline` to rebuild without network access.

### Build the package

From the repository root:

```bash
packaging/build-deb.sh
# or: make deb
```

The build script validates the source tree and tools, prepares
`.build/wheelhouse`, runs `dpkg-buildpackage` with debhelper 13, extracts the
package into `.build/extract`, validates the recursive ELF closure and Python
imports, runs `lintian`, and writes a report.

The resulting package is:

```text
dist/deb/esword4linux_0.5.0-1_amd64.deb
```

Useful variants:

```bash
packaging/build-deb.sh --offline       # reuse .build/wheelhouse
packaging/build-deb.sh --no-lintian    # skip lintian
packaging/build-deb.sh --wheelhouse /path/to/wheels
```

### Build the Debian source package

The source package embeds the three pinned wheels in the upstream
`.orig.tar.xz` so a Launchpad build can assemble the private runtime without
PyPI access. The wheels stay out of Git; the source builder copies them from
the validated `.build/wheelhouse`:

```bash
make deb-src           # requires a clean Git tree
make deb-src-verify    # also rebuilds the .deb offline
```

Artifacts are written to `dist/src/`:

```text
esword4linux_0.5.0.orig.tar.xz
esword4linux_0.5.0-1.debian.tar.xz
esword4linux_0.5.0-1.dsc
esword4linux_0.5.0-1_source.changes
esword4linux_0.5.0-1_source.buildinfo
```

`dpkg-source` never creates the orig for `3.0 (quilt)`; `packaging/build_source.py`
creates it deterministically (sorted tar, fixed mtime, `xz -6 -T1`), excludes
`debian/`, and verifies the archive contents, checksums and wheel hashes.
`make deb-src-verify` unpacks the resulting `.dsc` and rebuilds the binary
inside `unshare -rn`, proving that no network access is needed.

To validate uncommitted work without committing it:

```bash
packaging/build_source.py --allow-dirty
```

That result is explicitly **not publication-ready** and is marked with
`dist/src/NOT-PUBLICATION-READY.txt`. Only tracked changes are included:
untracked files must be committed before they appear in the source package.
Packages are unsigned by default; signing (`--sign-key KEYID`) and any upload
remain manual steps.

> **PPA-only.** Prebuilt wheels in the upstream tarball are acceptable for a
> Launchpad PPA, but they are not directly suitable for the Debian or Ubuntu
> main archives without a source-policy exception.

Licensing evidence for the embedded Qt/PySide6 runtime is in
`docs/licensing/`; the installed package includes
`/usr/share/doc/esword4linux/LGPL-COMPLIANCE.md`. The source correspondence is
currently `PARTIAL`: the official source archives are identified and hash-
verified, but the wheel build attestation and a full from-source rebuild test
are outstanding.

The private runtime can also be staged independently of Debian (the same
assembly is intended for a future AppImage):

```bash
python3 packaging/stage_runtime.py \
    --wheelhouse .build/wheelhouse \
    --dest /tmp/esword4linux-runtime
python3 packaging/validate_runtime.py --root /tmp/esword4linux-runtime
```

### Install

```bash
sudo apt install ./esword4linux_0.5.0-1_amd64.deb
```

Then launch **esword4linux** from the desktop menu or run:

```bash
esword4linux
```

On first run the application asks for the folder that contains your e-Sword
modules. No modules are bundled. Cancelling the folder dialog exits cleanly.

### Upgrade

Install the newer `.deb` with the same command; `dpkg`/`apt` replaces the
private runtime and keeps `~/.config/esword4linux/` and
`~/.cache/esword4linux/` intact:

```bash
sudo apt install ./esword4linux_<new-version>_amd64.deb
```

### Remove

```bash
sudo apt remove esword4linux
```

Removal deletes only package-owned files. It does **not** delete:

- `~/.config/esword4linux/` (preferences and selected modules folder),
- `~/.cache/esword4linux/` (catalog and optional FTS5 index),
- your e-Sword modules folder.

To remove the remaining user data explicitly:

```bash
rm -rf ~/.config/esword4linux ~/.cache/esword4linux
```

`apt purge` behaves like `apt remove` for these paths: they are user data, not
package conffiles.

### Runtime dependencies

`dpkg-shlibdeps` derives the versioned system library dependencies from the
staged ELF closure. They include the XCB and X11 libraries, Wayland client
libraries, EGL/GL, fontconfig/freetype, glib, dbus, zlib and the C/C++ runtime.
The package depends on `python3 (>= 3.10)` and `python3 (<< 3.16)`; the Python
interpreter itself comes from the distribution. It also depends on
`hicolor-icon-theme` so the installed icons are discoverable. It recommends
`fonts-noto-core` (the default interface and Scripture families) and
`xdg-utils` (the "open modules folder" action uses
`QDesktopServices`/`xdg-open`).

The private runtime includes PySide6-Essentials 6.12.0, shiboken6 6.12.0, Qt
6.12.0 (Core/Gui/Widgets/DBus/XcbQpa/WaylandClient/Svg/OpenGL), ICU 73 and
pure-Python PyYAML 6.0.3. See
[`packaging/runtime-manifest.yaml`](../packaging/runtime-manifest.yaml) for the
full inventory and the rationale for every retained or excluded Qt component.

### X11 and Wayland

The private Qt runtime contains both the xcb and Wayland platform plugins plus
their GL/EGL, shell, decoration and input-context integrations. The launcher
does not force `QT_QPA_PLATFORM`; Qt selects the platform from the session.

On a Wayland session that also has XWayland, force the native backend if
desired:

```bash
QT_QPA_PLATFORM=wayland esword4linux
```

Force X11/XWayland:

```bash
QT_QPA_PLATFORM=xcb esword4linux
```

### Known limitations

- The package is `amd64` only. The pinned PySide6 wheel is x86_64 and
  `manylinux_2_34`.
- Only Ubuntu 24.04 and Linux Mint 22.x were tested. Future releases are not
  claimed compatible.
- X11 launch was validated. Wayland was validated with the Weston 13 headless
  and kiosk backends (platform plugin loaded, window process alive); a full
  desktop compositor session (GNOME/KDE/wlroots) was not available in the
  build environment. See the validation matrix.
- The package intentionally installs its private runtime under `/opt`, which
  is reflected by a documented `lintian` override (`dir-or-file-in-opt`).
- A real e-Sword module corpus was not available during packaging. Runtime
  checks used synthetic Bible, commentary and map modules (including FTS5
  search and PNG/JPEG/WebP images). Real-corpus tests remain opt-in through
  `ESWORD4LINUX_TEST_CORPUS`.

## Source installation (alternative)

### Verified environment

The commands and package names below were verified against:

- **Linux Mint 22.3** (Ubuntu 24.04/noble base)
- **Python 3.12.3**
- **Cinnamon / X11**
- The actual PySide6 Qt plugin `libqxcb.so` from the project virtual environment

The project declares Python 3.10 or newer. Other Mint or Ubuntu releases were
**not verified** for v0.5.0. In particular, Wayland was not verified; the
PySide6 package does include a Wayland platform plugin.

### 1. Install system dependencies

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

### 2. Install the application

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

### 3. First launch and offline use

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

### 4. Launch the application

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

### 5. Uninstall

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

### The installed application does not start

Run it from a terminal to see the diagnostic:

```bash
esword4linux
```

The launcher reports a missing graphical session, an incomplete private
runtime, an unsupported Python version or a missing interpreter. To inspect Qt
plugin loading:

```bash
QT_DEBUG_PLUGINS=1 esword4linux
```

Check the private X11 plugin and its system libraries:

```bash
ldd /opt/esword4linux/python/PySide6/Qt/plugins/platforms/libqxcb.so | grep "not found"
ldd /opt/esword4linux/python/PySide6/Qt/plugins/platforms/libqwayland.so | grep "not found"
```

If a library is listed as `not found`, reinstall the package or report the
missing package name. The build-time validator checks the same closure for
every staged ELF object.

### Wayland: the application runs through XWayland

Qt may choose xcb when both `DISPLAY` and `WAYLAND_DISPLAY` are set. This is
normal on Wayland sessions with XWayland. To force the native backend:

```bash
QT_QPA_PLATFORM=wayland esword4linux
```

If the Wayland plugin cannot connect, the launcher/Qt prints
`Failed to create wl_display`; verify that `WAYLAND_DISPLAY` is set and that the
compositor is running.

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

## Distribution status and validation matrix

| Distribution | Session | Method | Status |
|---|---|---|---|
| Linux Mint 22.3 (Ubuntu 24.04 base) | X11 | Native `.deb`, xcb plugin | Validated |
| Linux Mint 22.3 (Ubuntu 24.04 base) | Wayland | Native `.deb`, Weston 13 headless/kiosk | Wayland plugin + window process validated; full desktop session not validated |
| Ubuntu 24.04 LTS | X11 | Native `.deb` | Not validated in a clean VM |
| Ubuntu 24.04 LTS | Wayland | Native `.deb` | Not validated in a clean VM |

A `.deb` build is not a substitute for runtime validation. The table records
what was actually exercised; do not claim a row that was not run.

## Unresolved technical uncertainty

- No full desktop Wayland compositor session (GNOME/KDE/wlroots) was available;
  validation used Weston 13 headless/kiosk.
- No clean Ubuntu 24.04 VM was available; the development host is Linux Mint
  22.3 (Ubuntu 24.04/noble base).
- No upgrade from an earlier `.deb` was possible because 0.5.0-1 is the first
  native package.
- The source installation has no `make uninstall` target; the manual commands
  above are its documented removal method.
