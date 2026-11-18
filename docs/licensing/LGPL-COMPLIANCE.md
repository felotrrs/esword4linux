# LGPL compliance information

This document describes the third-party runtime shipped with **esword4linux
0.5.0-1** and the practical mechanism for replacing the LGPL-covered libraries.
It is a technical compliance note, **not legal advice**.

## 1. Covered runtime components

The package installs a private runtime under `/opt/esword4linux`. The following
components are LGPL-covered:

| Component | Version | License used by this package |
|---|---|---|
| PySide6-Essentials (`PySide6/*.so`, `libpyside6`) | 6.12.0 | LGPL-3.0-only |
| shiboken6 (`Shiboken.abi3.so`, `libshiboken6`) | 6.12.0 | LGPL-3.0-only |
| Qt 6 shared libraries (`libQt6*.so.6`) | 6.12.0 | LGPL-3.0-only |
| Qt plugins (`platforms`, `imageformats`, `iconengines`, `platforminputcontexts`, Wayland and xcb integrations) | 6.12.0 | LGPL-3.0-only |

Additional components:

- **ICU 73** (`libicuuc.so.73`, `libicui18n.so.73`, `libicudata.so.73`) is
  distributed under the **Unicode-3.0** license.
- **PyYAML 6.0.3** is distributed under the **MIT** license and is installed as
  pure Python (`yaml/`). The compiled `_yaml` extension is not installed.
- The Qt **public suffix list** in `libQt6Network.so.6` is under **MPL-2.0**.
  That library is present in the source wheelhouse but is not installed in the
  `.deb`.
- The Qt Wayland KDE appmenu protocol in the installed
  `libQt6WaylandClient.so.6` is under **LGPL-2.1-or-later**.
- The **esword4linux application** itself is GPL-3.0-only.

PySide6 and shiboken6 are offered upstream under
`LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`. This package uses the
**LGPL-3.0-only** option. Qt is offered under LGPL-3.0-only, GPL-2.0-only,
GPL-3.0-only or a commercial license; this package uses LGPL-3.0-only.

## 2. Where the license texts and notices are

After installation:

```text
/usr/share/doc/esword4linux/copyright
/usr/share/doc/esword4linux/licenses/LGPL-3.0-only.txt.gz
/usr/share/doc/esword4linux/licenses/GPL-3.0-only.txt.gz
/usr/share/doc/esword4linux/licenses/MIT.txt
/usr/share/doc/esword4linux/licenses/Unicode-3.0.txt.gz
/usr/share/doc/esword4linux/licenses/QT-THIRD-PARTY.md.gz
/usr/share/doc/esword4linux/licenses/Qt/*.txt.gz
/opt/esword4linux/licenses/                 (runtime copy)
```

The Qt attribution file identifies the third-party components included in Qt
6.12.0 and their SPDX license expressions. The complete texts are installed
under `licenses/Qt/`.

## 3. Replacing Qt/PySide6 libraries

### 3.1 How the runtime finds libraries

The launcher sets:

```text
PYTHONPATH=/opt/esword4linux/app:/opt/esword4linux/python
QT_PLUGIN_PATH=/opt/esword4linux/python/PySide6/Qt/plugins
LD_LIBRARY_PATH=/opt/esword4linux/python/PySide6/Qt/lib:/opt/esword4linux/python/shiboken6
```

The PySide6 extension modules also carry:

```text
RPATH=$ORIGIN/:$ORIGIN/Qt/lib:$ORIGIN/../shiboken6/
```

Qt libraries carry `RUNPATH=$ORIGIN`, and plugins use relative `$ORIGIN/.../lib`
entries. There is no installed `qt.conf` and no locked `QT_QPA_PLATFORM`. The
runtime therefore loads the private libraries from `/opt/esword4linux`, and a
compatible replacement placed in the same private paths is used by the
application.

### 3.2 Replacement mechanism verified by this audit

A disposable copy of the installed runtime was used. A harmless marker was
added to a compatible copy of `libQt6Core.so.6` with `objcopy`; the modified
library was placed over the private copy, and the application was started
normally. The process map, the file hash, and the marker string all confirmed
that the replaced library was loaded. The same test was performed with the
private `libqxcb.so` platform plugin. After restoring the originals, the
application started normally again.

The exact test commands and observed loaded paths are recorded in the audit
record and in `qt-runtime-inventory.md`. The tested hashes were:

```text
original libQt6Core.so.6   7866c8700faea5237b8fa86d294ea2d76d57ed8786735c40fe32aaf8e5149220
modified libQt6Core.so.6   a6ff9301785ce9988cf00f8352563e0e835abb0502ddc7bfb64a5a6231119dc7
original libqxcb.so        36da9a40edbf2a493b913a406b731a31be64471a59beda1382e314d66cc61763
modified libqxcb.so        762b01f912af2da3c7d89e5f3e410c42ffeb6997896d8898ecb377a79310cd4b
```

The About dialog now displays the application's GPL-3.0 notice and a separate
Qt/PySide6 LGPL-3.0 notice, with a link to the GNU LGPL v3.0 text and the
installed `/usr/share/doc/esword4linux/LGPL-COMPLIANCE.md` document. The
wording still requires formal legal review.

**Limitation:** this proves that the loader uses a replaced compatible binary.
It does **not** prove a complete Qt build from source with matching ABI. That
from-source build has not been demonstrated in this audit. Replacement was
tested on X11 with `libqxcb`; Wayland-specific replacement behavior has not been
independently tested.

### 3.3 Tested rollback

```bash
sudo cp -a /opt/esword4linux /opt/esword4linux.backup
# replace one private library or plugin with a compatible build
sudo cp /path/to/libQt6Core.so.6 \
  /opt/esword4linux/python/PySide6/Qt/lib/libQt6Core.so.6
sha256sum /opt/esword4linux/python/PySide6/Qt/lib/libQt6Core.so.6
# start the application and verify the loaded path
esword4linux
grep libQt6Core.so.6 /proc/$(pgrep -n esword4linux)/maps
# rollback
sudo cp /opt/esword4linux.backup/python/PySide6/Qt/lib/libQt6Core.so.6 \
  /opt/esword4linux/python/PySide6/Qt/lib/libQt6Core.so.6
```

Root privileges are required because `/opt` is system-owned. An `apt upgrade`
or reinstall of the package replaces the private runtime and therefore
overwrites local modifications; keep a backup.

### 3.4 From-source build procedure (not yet verified)

The complete procedure is:

1. Obtain the official sources and verify their SHA-256 values:
   - Qt 6.12.0:
     `https://download.qt.io/official_releases/qt/6.12/6.12.0/single/qt-everywhere-src-6.12.0.tar.xz`
     (`98ff4f44bac6ec3e1e62ee2a4316ae0e3d15badb015d753cc0268a20db52f165`)
   - PySide6/shiboken6 6.12.0:
     `https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.12.0-src/pyside-setup-everywhere-src-6.12.0.tar.xz`
     (`099c1a597cf33c1b000e11cf68a0b82d216fb802bf81726efc720394f10c7751`)
2. Apply the intended modifications.
3. Configure and build Qt 6.12.0 with an ABI compatible with the existing
   runtime (same architecture, release build, compatible C++ runtime and
   dependencies; keep the SONAMEs such as `libQt6Core.so.6`).
4. Build PySide6/shiboken6 against that Qt, or rebuild only the component you
   changed, preserving the existing Python ABI and SONAMEs.
5. Replace the corresponding files under `/opt/esword4linux/python/`, including
   plugins if their ABI changed.
6. Verify the loaded path and hash, then test application startup and the
   affected feature.
7. Restore the backup if the replacement is not compatible.

This full from-source rebuild is **not verified** by the current audit. The
current verified result is limited to the loader/replacement mechanism.

## 4. Source availability

The exact source releases for the LGPL components are available from:

- Qt 6.12.0: URL and SHA-256 in section 3.4.
- PySide6/shiboken6 6.12.0: URL and SHA-256 in section 3.4.
- PyYAML 6.0.3 (MIT): `https://github.com/yaml/pyyaml`.

The project has staged the full Qt and PySide6 archives locally under
`dist/source-archives/` and prepared a GitHub Release manifest at
`docs/licensing/source-release-manifest.md`. Project-controlled hosting is
**READY-PENDING-PUBLICATION**; the proposed URLs are:

```text
https://github.com/felotrrs/esword4linux/releases/download/v0.5.0-lgpl-sources/qt-everywhere-src-6.12.0.tar.xz
https://github.com/felotrrs/esword4linux/releases/download/v0.5.0-lgpl-sources/pyside-setup-everywhere-src-6.12.0.tar.xz
```

Those assets are **not published yet**. Only after an authorized release and a
download/hash verification may this document treat them as available. Until
then, the upstream URLs above are the available source locations.

The Debian source package includes the wheels and this documentation, but does
**not** embed the Qt or PySide6 source archives. The distributor must keep the
corresponding source available for as long as the binaries are distributed.
`third-party-sources.md` records the correspondence status and the fact that
exact binary-to-source attestation is not available.

## 5. Installation Information

LGPLv3 section 4(e) incorporates the GPLv3 section 6 Installation Information
requirements when the covered work is conveyed in a **User Product**. The
current distribution is a downloadable Debian package for general-purpose
Ubuntu/Mint amd64 installations, not a consumer hardware product. On that
distribution model no Installation Information obligation is triggered by the
package itself.

This is a technical assessment, not a legal conclusion. A downstream party that
preinstalls esword4linux on a device, appliance or other User Product must
reassess the obligation and provide the information required by GPLv3 section 6
for that product.

## 6. Outstanding limitations

- Exact binary-to-source provenance for the official PySide6 and Qt wheels is
  not attested by the wheel or PyPI metadata; see `third-party-sources.md`
  (`PARTIAL`).
- A full Qt/PySide6 rebuild from source and ABI-compatible replacement has not
  been tested; only replacement with a compatible modified binary was tested.
- Per-object license mapping for all 288 ELF objects in the wheelhouse is
  incomplete; the installed runtime's license notices and attribution are
  present, but a file-by-file audit is still recommended.
- Replacing files under `/opt` requires administrator privileges and local
  changes are overwritten by package upgrades.
- Project-controlled source hosting is prepared but not published. The
  `v0.5.0-lgpl-sources` release and its asset URLs must not be described as
  available until an authorized upload and hash verification are complete.
- Replacement was not independently tested on a Wayland session; only X11/xcb
  was exercised.
- This document does not replace review by qualified legal counsel.
