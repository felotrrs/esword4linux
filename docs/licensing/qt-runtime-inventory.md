# Qt/PySide6 runtime inventory

- **Audit date**: 2026-11-17
- **Audited package version**: esword4linux 0.5.0-1
- **Wheelhouse**: `.build/wheelhouse/` (Git-ignored; embedded in the Debian
  `.orig.tar.xz`)
- **Installed runtime audited**: `esword4linux_0.5.0-1_amd64.deb`, extracted to
  a disposable directory
- **Method**: exact wheel extraction, SHA-256, Python wheel `RECORD`
  verification, `readelf`, `file`, `strings`, `ldd` only on the test host, and
  live `/proc/<pid>/maps` observations. No bundled binary was executed merely
  to inspect it; the only executions were the application's own runtime in the
  replacement tests.

This document separates **verified facts** from **assumptions** and
**unresolved questions**. It is an inventory, not a legal opinion.

## 1. Exact wheels

| Wheel | Size | SHA-256 | PyPI record |
|---|---:|---|---|
| `pyside6_essentials-6.12.0-cp310-abi3-manylinux_2_34_x86_64.whl` | 84,346,433 | `16f4b5e41daf49235ae048458243da9efe5f3d8040f9cc5aa454ce69893d3bd9` | Match |
| `shiboken6-6.12.0-cp310-abi3-manylinux_2_34_x86_64.whl` | 279,268 | `3bde565bb0890044b5c7f63808adddede5abc241e9395a2bfed61919884d6240` | Match |
| `pyyaml-6.0.3-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl` | 807,870 | `ba1cc08a7ccde2d2ec775841541641e4548226580ab850948cbfda66a1befcdc` | Match |

The hashes also match `packaging/runtime-requirements.txt`.

Every `RECORD` entry with a hash verified successfully:

| Wheel | Entries with hashes | Failures |
|---|---:|---:|
| PySide6-Essentials | 2,470 | 0 |
| shiboken6 | 60 | 0 |
| PyYAML | 23 | 0 |

`METADATA` declarations:

| Wheel | Name / version | Declared license | Python requirement |
|---|---|---|---|
| PySide6-Essentials | `PySide6_Essentials` 6.12.0 | `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only` | `>=3.10,<3.16` |
| shiboken6 | `shiboken6` 6.12.0 | `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only` | `>=3.10,<3.16` |
| PyYAML | `PyYAML` 6.0.3 | `MIT` | `>=3.8` |

The PySide6 and shiboken6 wheels contain **no `LICENSE`, `COPYING` or
`NOTICE` file** for their own code. The PyYAML wheel contains
`pyyaml-6.0.3.dist-info/licenses/LICENSE`. The Debian package supplies the
missing LGPL/GPL texts and Qt attribution data under
`/usr/share/doc/esword4linux/licenses/` and `/opt/esword4linux/licenses/`.
That downstream packaging fact is verified below.

## 2. ELF inventory summary

Full machine-readable inventory: [`elf-inventory.tsv`](elf-inventory.tsv).
It has 288 rows, one per ELF object found inside the exact three wheels.

| Wheel | ELF objects | Shared objects | PIE executables | Relocatable objects |
|---|---:|---:|---:|---:|
| PySide6-Essentials | 285 | 269 | 14 | 2 |
| shiboken6 | 2 | 2 | 0 | 0 |
| PyYAML | 1 | 1 | 0 | 0 |
| **Total** | **288** | **272** | **14** | **2** |

The 14 executables are Qt/PySide developer tools (`assistant`, `designer`,
`linguist`, `lrelease`, `lupdate`, `qmlformat`, `qmllint`, `qmlls`,
`svgtoqml`, and five `Qt/libexec` tools). The two relocatable objects are QML
build artifacts under `PySide6/Qt/qml/.../objects-RelWithDebInfo/`.

These 288 objects are in the wheelhouse/source package. The **installed `.deb`
runtime contains 36 ELF objects**, because `stage_runtime.py` deliberately
selects a subset. That subset is the runtime relevant to end users:

| Installed group | Count |
|---|---:|
| PySide6 extension modules and `libpyside6` | 4 |
| shiboken6 extension and `libshiboken6` | 2 |
| Qt shared libraries and ICU | 12 |
| Qt plugins | 18 |
| PyYAML compiled extension | 0 (pure Python only) |
| **Total installed** | **36** |

The complete installed list and its source-wheel mapping are in section 4.
`validate_runtime.py` checks 36 ELF objects, matching this count.

## 3. Linking and loader facts

Verified from `readelf -d` on the exact wheel files:

- Qt libraries have `RUNPATH = $ORIGIN`.
- The PySide6 Python extension modules carry
  `RPATH = $ORIGIN/:$ORIGIN/Qt/lib:$ORIGIN/../shiboken6/`.
- Plugins use `$ORIGIN/.../lib`-relative `RUNPATH` entries.
- `libQt6Core.so.6` has SONAME `libQt6Core.so.6`; it depends on the bundled
  `libicui18n.so.73`, `libicuuc.so.73`, `libicudata.so.73`, and on system
  libraries such as `libzstd.so.1`, `libglib-2.0.so.0`, `libz.so.1`,
  `libgthread-2.0.so.0`, `libstdc++.so.6`, `libm.so.6`, `libgcc_s.so.1`,
  `libc.so.6`.
- `libQt6Gui.so.6` depends on `libEGL.so.1`, `libX11.so.6`, `libxkbcommon.so.0`,
  `libGL.so.1`, `libfreetype.so.6`, `libfontconfig.so.1`, and other system
  libraries in addition to private Qt libraries.
- The application launcher sets `LD_LIBRARY_PATH` to the private
  `PySide6/Qt/lib` and `shiboken6` directories, and `QT_PLUGIN_PATH` to the
  private plugin directory. It does **not** install a `qt.conf`.
- No `qt.conf` was found under `/opt/esword4linux` in the installed package.
- `QT_QPA_PLATFORM`, `QT_QPA_PLATFORM_PLUGIN_PATH` and `LD_PRELOAD` are not
  forced by the launcher; `QT_PLUGIN_PATH` is set but not locked.

Live observation from the baseline test:

```text
/tmp/opencode/lgpl/runtime/python/PySide6/Qt/lib/libQt6Core.so.6
/tmp/opencode/lgpl/runtime/python/PySide6/QtCore.abi3.so
/tmp/opencode/lgpl/runtime/python/PySide6/libpyside6.abi3.so.6.12
/tmp/opencode/lgpl/runtime/python/shiboken6/libshiboken6.abi3.so.6.12
/tmp/opencode/lgpl/runtime/python/PySide6/Qt/plugins/platforms/libqxcb.so
```

This confirms that the process actually loaded the private copies, not a
system Qt.

## 4. Installed runtime mapping

`stage_runtime.py` copies files from the wheels without renaming them. The
installed files are stripped by `dh_strip`, so their SHA-256 values differ from
the wheel originals by 12–120 bytes; path, SONAME and loader metadata remain
the relevant identity. The following table lists the installed runtime ELF
objects and their exact wheel source.

| Installed path under `/opt/esword4linux/python` | Wheel source | SONAME |
|---|---|---|
| `PySide6/QtCore.abi3.so` | PySide6 | — |
| `PySide6/QtGui.abi3.so` | PySide6 | — |
| `PySide6/QtWidgets.abi3.so` | PySide6 | — |
| `PySide6/libpyside6.abi3.so.6.12` | PySide6 | `libpyside6.abi3.so.6.12` |
| `PySide6/Qt/lib/libQt6Core.so.6` | PySide6 | `libQt6Core.so.6` |
| `PySide6/Qt/lib/libQt6DBus.so.6` | PySide6 | `libQt6DBus.so.6` |
| `PySide6/Qt/lib/libQt6Gui.so.6` | PySide6 | `libQt6Gui.so.6` |
| `PySide6/Qt/lib/libQt6OpenGL.so.6` | PySide6 | `libQt6OpenGL.so.6` |
| `PySide6/Qt/lib/libQt6Svg.so.6` | PySide6 | `libQt6Svg.so.6` |
| `PySide6/Qt/lib/libQt6WaylandClient.so.6` | PySide6 | `libQt6WaylandClient.so.6` |
| `PySide6/Qt/lib/libQt6Widgets.so.6` | PySide6 | `libQt6Widgets.so.6` |
| `PySide6/Qt/lib/libQt6WlShellIntegration.so.6` | PySide6 | `libQt6WlShellIntegration.so.6` |
| `PySide6/Qt/lib/libQt6XcbQpa.so.6` | PySide6 | `libQt6XcbQpa.so.6` |
| `PySide6/Qt/lib/libicuuc.so.73` | PySide6 | `libicuuc.so.73` |
| `PySide6/Qt/lib/libicui18n.so.73` | PySide6 | `libicui18n.so.73` |
| `PySide6/Qt/lib/libicudata.so.73` | PySide6 | `libicudata.so.73` |
| `shiboken6/Shiboken.abi3.so` | shiboken6 | — |
| `shiboken6/libshiboken6.abi3.so.6.12` | shiboken6 | `libshiboken6.abi3.so.6.12` |
| `PySide6/Qt/plugins/iconengines/libqsvgicon.so` | PySide6 | — |
| `PySide6/Qt/plugins/imageformats/libqgif.so` | PySide6 | — |
| `PySide6/Qt/plugins/imageformats/libqico.so` | PySide6 | — |
| `PySide6/Qt/plugins/imageformats/libqjpeg.so` | PySide6 | — |
| `PySide6/Qt/plugins/imageformats/libqsvg.so` | PySide6 | — |
| `PySide6/Qt/plugins/imageformats/libqtga.so` | PySide6 | — |
| `PySide6/Qt/plugins/imageformats/libqtiff.so` | PySide6 | — |
| `PySide6/Qt/plugins/imageformats/libqwbmp.so` | PySide6 | — |
| `PySide6/Qt/plugins/imageformats/libqwebp.so` | PySide6 | — |
| `PySide6/Qt/plugins/platforminputcontexts/libcomposeplatforminputcontextplugin.so` | PySide6 | — |
| `PySide6/Qt/plugins/platforminputcontexts/libibusplatforminputcontextplugin.so` | PySide6 | — |
| `PySide6/Qt/plugins/platforms/libqwayland.so` | PySide6 | — |
| `PySide6/Qt/plugins/platforms/libqxcb.so` | PySide6 | — |
| `PySide6/Qt/plugins/wayland-decoration-client/libbradient.so` | PySide6 | — |
| `PySide6/Qt/plugins/wayland-graphics-integration-client/libqt-plugin-wayland-egl.so` | PySide6 | — |
| `PySide6/Qt/plugins/wayland-shell-integration/libxdg-shell.so` | PySide6 | — |
| `PySide6/Qt/plugins/xcbglintegrations/libqxcb-egl-integration.so` | PySide6 | — |
| `PySide6/Qt/plugins/xcbglintegrations/libqxcb-glx-integration.so` | PySide6 | — |

There are 36 ELF entries when the 12 Qt/ICU libraries, 18 plugins, 4 PySide
extension/helper libraries and the 2 shiboken files are counted together. No
PyYAML shared object is installed: the package stages only the pure-Python
`yaml/` package.

## 5. License inventory

| Distributed component | Version | License option used | Evidence / notice |
|---|---|---|---|
| esword4linux application | 0.5.0 | GPL-3.0-only | Repository `LICENSE`; `debian/copyright` |
| PySide6-Essentials | 6.12.0 | LGPL-3.0-only (GPL-2.0-only/GPL-3.0-only alternatives exist) | Wheel `METADATA`; PySide6 source `LICENSES/LGPL-3.0-only.txt`; Debian `LGPL-3.0-only.txt` |
| shiboken6 | 6.12.0 | LGPL-3.0-only (GPL-2.0-only/GPL-3.0-only alternatives exist) | Wheel `METADATA`; same PySide6 source archive; Debian `LGPL-3.0-only.txt` |
| Qt 6.12.0 libraries/plugins | 6.12.0 | LGPL-3.0-only (commercial/GPL alternatives) | Qt source; `debian/copyright`; Qt attribution |
| ICU 73 | SONAME `libicu*.so.73` | Unicode-3.0 | Bundled `libicudata/u18n/uc`; `Unicode-3.0.txt` |
| PyYAML | 6.0.3 | MIT | Wheel `LICENSE`; `debian/copyright` |
| Qt public suffix list (in `libQt6Network.so.6`, wheelhouse only) | Qt 6.12.0 | MPL-2.0 | Confirmed by `publicsuffix` strings/symbols; `Qt/MPL-2.0.txt` |
| Wayland KDE DBus menu protocol (in installed `libQt6WaylandClient.so.6`) | Qt 6.12.0 | LGPL-2.1-or-later | Confirmed by `org_kde_kwin_appmenu` symbols; `Qt/LGPL-2.1-or-later.txt` |
| PCRE2 (in `libQt6Core.so.6`) | Qt 6.12.0 | LicenseRef-BSD-3-Clause-with-PCRE2-Binary-Like-Packages-Exception | `PCRE2_USE_OFFSET_LIMIT` string/symbols; exception text installed |
| libpng (in `libQt6Gui.so.6`) | 1.6.58 | Libpng AND libpng-2.0 | `libpng version 1.6.58` string; texts installed |
| libjpeg (in `libqjpeg.so`) | Qt 6.12.0 build | IJG AND BSD-3-Clause | `libqjpeg` plugin; IJG/BSD texts installed |
| libtiff (in `libqtiff.so`) | Qt 6.12.0 build | libtiff | `libqtiff` plugin; libtiff text installed |
| libwebp (in `libqwebp.so`) | Qt 6.12.0 build | BSD-3-Clause | `libqwebp` plugin; BSD-3 text installed |
| Qt third-party components | Qt 6.12.0 | per `QT-THIRD-PARTY.md` | `packaging/licenses/Qt/*` (39 files), installed notices |

`packaging/licenses/Qt/` contains 39 license texts, covering the SPDX
identifiers listed in `QT-THIRD-PARTY.md`, including the PCRE2 exception,
libtiff, libpng, IJG, FTL, Zlib, MPL-2.0, LGPL-2.1-or-later, ICC and
LCS-Telegraphics. The presence of these texts is verified. Whether every text
corresponds to an object actually linked into the 36 installed ELFs has **not**
been proven file-by-file; `QT-THIRD-PARTY.md` itself says the upstream list
includes components that may not be enabled in the Linux build.

The Debian package installs:

```text
/usr/share/doc/esword4linux/licenses/LGPL-3.0-only.txt.gz
/usr/share/doc/esword4linux/licenses/GPL-3.0-only.txt.gz
/usr/share/doc/esword4linux/licenses/MIT.txt
/usr/share/doc/esword4linux/licenses/QT-THIRD-PARTY.md.gz
/usr/share/doc/esword4linux/licenses/Unicode-3.0.txt.gz
/usr/share/doc/esword4linux/licenses/Qt/*.txt.gz
```

and a second copy under `/opt/esword4linux/licenses/` used by the runtime
staging. The application package also installs `debian/copyright` itself.

## 6. Verified facts, assumptions and unresolved questions

### Verified facts

- Exact wheel files, sizes, SHA-256 values and PyPI URLs.
- All wheel `RECORD` hashes verify.
- 288 ELF objects in the wheelhouse, 36 in the installed runtime.
- Qt library/plugin RPATH/RUNPATH layout.
- The runtime loads private `libQt6Core`, `libpyside6`, `libshiboken6` and the
  private `libqxcb` plugin.
- A replaced private library and a replaced private plugin are both loaded by
  the application; see `LGPL-COMPLIANCE.md` for commands and observed paths.
- The Debian package does not contain `.whl`, `wheelhouse`, `site-packages`,
  `__pycache__`, `.pyc` or `.egg-info`.
- License texts and Qt attribution are installed.

### Assumptions

- The official wheel binaries were built from the corresponding Qt/PySide
  release source rather than from an unpublished patched tree. The version
  strings, build dates and build scripts are consistent, but no build
  attestation is distributed.
- The Qt libraries in the wheel are the official Qt 6.12.0 release build, not
  a downstream rebuild. The `Qt 6.12.0 (x86_64-little_endian-lp64 shared ...
  by GCC 11.5.0 ...)` string and `manylinux_2_34` wheel tag are consistent.
- The 36 installed objects do not statically include any component omitted
  from the attribution file. This has not been proven by symbol-level analysis.

### Unresolved questions

- Exact Qt configure options and patches used for the official PySide6 wheel
  are not recorded in the wheel.
- No cryptographic attestation links the PySide6 wheel to the PySide6 source
  archive or the Qt source archive.
- The wheelhouse itself contains 288 ELFs, including developer tools and QML
  build objects that are not installed. Their licenses are covered by the same
  Qt/PySide declarations, but a per-object license audit is incomplete.
- PySide6 and shiboken6 wheels do not ship their own license files; the
  downstream Debian package supplies them, but this packaging layer is part of
  the compliance argument, not an upstream-provided notice.
- The application About dialog now displays the application GPL-3.0 notice and
  the Qt/PySide6 LGPL-3.0 notice with links to the GNU LGPL text and the
  installed compliance document. The wording still needs formal legal review.
- `debian/copyright` uses a conservative expression for the full wheelhouse.
  The MPL-2.0 public-suffix component in `libQt6Network` and the
  LGPL-2.1-or-later KDE appmenu protocol in `libQt6WaylandClient` were
  confirmed and their identifiers/texts added. A complete per-object mapping
  remains outstanding for the other Qt third-party components.
