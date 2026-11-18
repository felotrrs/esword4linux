# Third-party source correspondence

- **Audit date**: 2026-11-17
- **Scope**: the exact wheels embedded in the esword4linux 0.5.0-1 Debian
  source package, and the Qt/PySide6 binaries installed in the `.deb`
- **Status vocabulary**: `VERIFIED`, `PARTIAL`, `UNVERIFIED`, `MISSING`,
  `NOT APPLICABLE`

This document records what can and cannot be established about the source
corresponding to the distributed binaries. A matching version number is **not**
treated as proof of binary/source correspondence.

## 1. Exact wheel provenance

The wheels are byte-identical to the files published on PyPI by the Qt project
and PyYAML maintainers. The SHA-256 values below are also pinned in
`packaging/runtime-requirements.txt`.

| Wheel | PyPI URL | SHA-256 | Status |
|---|---|---|---|
| PySide6-Essentials 6.12.0 | `https://files.pythonhosted.org/packages/7b/3c/7597d8dcb36aa8315427635ec6ec9d850ffbad4ce78b9118ac854889f2d3/pyside6_essentials-6.12.0-cp310-abi3-manylinux_2_34_x86_64.whl` | `16f4b5e41daf49235ae048458243da9efe5f3d8040f9cc5aa454ce69893d3bd9` | `VERIFIED` |
| shiboken6 6.12.0 | `https://files.pythonhosted.org/packages/49/c2/a04fa003b4360e99d8e3fc2829abacf37396ace63ea1cd616402209ec7c6/shiboken6-6.12.0-cp310-abi3-manylinux_2_34_x86_64.whl` | `3bde565bb0890044b5c7f63808adddede5abc241e9395a2bfed61919884d6240` | `VERIFIED` |
| PyYAML 6.0.3 | `https://files.pythonhosted.org/packages/8b/9d/b3589d3877982d4f2329302ef98a8026e7f4443c765c46cfecc8858c6b4b/pyyaml-6.0.3-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl` | `ba1cc08a7ccde2d2ec775841541641e4548226580ab850948cbfda66a1befcdc` | `VERIFIED` |

Evidence: `https://pypi.org/pypi/PySide6-Essentials/6.12.0/json`,
`https://pypi.org/pypi/shiboken6/6.12.0/json`,
`https://pypi.org/pypi/PyYAML/6.0.3/json`, plus local `sha256sum` and full
`RECORD` verification.

## 2. Official source archives

Both archives were downloaded during this audit; their SHA-256 values were
computed locally and matched the official checksum files.

| Source archive | Official URL | SHA-256 | Local hash match |
|---|---|---|---|
| Qt 6.12.0 | `https://download.qt.io/official_releases/qt/6.12/6.12.0/single/qt-everywhere-src-6.12.0.tar.xz` | `98ff4f44bac6ec3e1e62ee2a4316ae0e3d15badb015d753cc0268a20db52f165` | `VERIFIED` |
| PySide6/shiboken6 6.12.0 | `https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.12.0-src/pyside-setup-everywhere-src-6.12.0.tar.xz` | `099c1a597cf33c1b000e11cf68a0b82d216fb802bf81726efc720394f10c7751` | `VERIFIED` |

The PySide6 archive also carries the official `.sha256` sidecar. The Qt archive
has an official `.sha256` sidecar at the same directory; its value is the one
above.

## 3. Component-to-source table

| Binary component | Version | Source archive | Exact correspondence | Hash verified | Status |
|---|---|---|---|---|---|
| `PySide6/QtCore.abi3.so`, `QtGui`, `QtWidgets`, `libpyside6` | 6.12.0 | `pyside-setup-everywhere-src-6.12.0.tar.xz` | Version 6.12.0; source contains the PySide6 CMake/build scripts and `LICENSES/`; no build attestation links this wheel to the archive | Archive hash yes; wheel-to-source no | `PARTIAL` |
| `shiboken6/Shiboken.abi3.so`, `libshiboken6` | 6.12.0 | `pyside-setup-everywhere-src-6.12.0.tar.xz` | Same archive contains `sources/shiboken6`; same limitation | Archive hash yes; wheel-to-source no | `PARTIAL` |
| `libQt6Core`, `QtDBus`, `QtGui`, `QtWidgets`, `QtOpenGL`, `QtSvg`, `QtWaylandClient`, `QtWlShellIntegration`, `QtXcbQpa` | 6.12.0 | `qt-everywhere-src-6.12.0.tar.xz` | Version string 6.12.0 and `coin/product_dependencies.yaml` point to Qt 6.12.0; exact configure/patches not recorded in the wheel | Archive hash yes; binary-to-source no | `PARTIAL` |
| Qt plugins (`platforms`, `imageformats`, `iconengines`, `platforminputcontexts`, Wayland/xcb integrations) | 6.12.0 | `qt-everywhere-src-6.12.0.tar.xz` | Built from the Qt source tree; exact plugin build configuration not recorded in the wheel | Archive hash yes; binary-to-source no | `PARTIAL` |
| ICU 73 (`libicuuc`, `libicui18n`, `libicudata`) | SONAME 73 | Not part of the Qt source archive | ICU is bundled by the Qt for Python build; Unicode-3.0 is a permissive license and does not impose a Corresponding Source obligation | N/A | `NOT APPLICABLE` for LGPL source; license text verified |
| PyYAML pure-Python `yaml/` | 6.0.3 | `https://github.com/yaml/pyyaml` at 6.0.3 | MIT; wheel contains `LICENSE`; source is public | Wheel `RECORD` yes | `VERIFIED` for license; source not required by MIT |
| PyYAML `_yaml` compiled extension | 6.0.3 | PyYAML 6.0.3 source | Present in the wheel, **not installed** by esword4linux | Wheel `RECORD` yes | `NOT APPLICABLE` to installed runtime; still distributed in the source package |
| Qt public suffix list in `libQt6Network` | Qt 6.12.0 | Qt source `src/network/kernel/qpublicsuffix*` | Confirmed by built-in `publicsuffix` strings in the wheel binary; not installed in the `.deb` | Archive hash yes | `VERIFIED` presence; `MPL-2.0` |
| Wayland KDE appmenu protocol in `libQt6WaylandClient` | Qt 6.12.0 | Qt source `qtwayland` protocols | Confirmed by `org_kde_kwin_appmenu` symbols in the installed binary | Archive hash yes | `VERIFIED` presence; `LGPL-2.1-or-later` |
| Qt third-party statically linked components | Qt 6.12.0 | Qt source `src/3rdparty/**` | Listed in `packaging/licenses/QT-THIRD-PARTY.md`; not every listed component is enabled in the Linux build | Source archive yes; per-object no | `PARTIAL` |
| Application | 0.5.0 | This repository | Tracked in Git | N/A | `VERIFIED` |

### What “PARTIAL” means here

A `PARTIAL` status means:

- the exact official source **release** is available and hash-verified;
- the source contains the build system and license files for the component;
- but no distributed attestation, reproducible-build record, or signed
  provenance statement proves that the wheel's binary objects were produced
  from that exact archive with the exact configure flags and without
  unpublished patches.

This is deliberately not upgraded to `VERIFIED` merely because the version
number matches.

## 4. Corresponding Source availability

The current Debian source package:

- embeds the three wheels in `esword4linux_0.5.0.orig.tar.xz`;
- includes this document and `debian/copyright`;
- **does not embed** the Qt or PySide6 source archives.

The source package therefore relies on network availability of the official
Qt/PySide source archives. The archives have been prepared locally under
`dist/source-archives/` and a release manifest exists at
`docs/licensing/source-release-manifest.md`. Their project-controlled GitHub
Release publication is **READY-PENDING-PUBLICATION**: no tag, release asset or
external upload exists yet. Until an authorized publication and download
verification is completed, treat only the upstream URLs as available.

Proposed asset names and locations (not yet published):

```text
https://github.com/felotrrs/esword4linux/releases/download/v0.5.0-lgpl-sources/qt-everywhere-src-6.12.0.tar.xz
https://github.com/felotrrs/esword4linux/releases/download/v0.5.0-lgpl-sources/pyside-setup-everywhere-src-6.12.0.tar.xz
```

The Qt archive is 443,394,020 bytes (≈423 MiB), below GitHub's 2 GiB per-file
limit; the PySide6 archive is 18,211,772 bytes. Both full upstream archives are
used; no module-pruned variant is required.

## 5. Build-script evidence

The PySide6 source archive contains:

```text
build_scripts/
  main.py
  options.py
  platforms/linux.py
  wheel_files.py
  wheel_utils.py
sources/pyside6/
sources/shiboken6/
LICENSES/LGPL-3.0-only.txt
coin/product_dependencies.yaml   # Qt dependency ref: 6.12.0
```

`build_scripts/platforms/linux.py` shows that the wheel build copies
`libQt6*.so.?` and `libicu*.so.??` into `PySide6/Qt/lib`, adjusts RPATH, copies
plugins/qml/translations, and patches bundled executables. This is consistent
with the observed wheel layout, but it is build-script evidence, not a
bit-for-bit proof of the distributed binaries.

## 6. Missing or unverified source items

- Exact Qt `configure` command line for the official PySide6 wheel: `MISSING`.
- Exact compiler/toolchain provenance beyond `.comment` (GCC 11.5.0, Red Hat):
  `PARTIAL`.
- Cryptographic wheel-to-source attestation (for example Sigstore/PEP 740):
  `MISSING` in the audited wheel and PyPI metadata.
- Per-object license mapping for all 288 wheel ELF objects: `PARTIAL`.
- ICU 73 exact upstream source release and build flags: `UNVERIFIED`; no LGPL
  Corresponding Source obligation is assumed for ICU's permissive license.
