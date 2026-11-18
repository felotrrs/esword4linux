# Source archive release manifest — READY-PENDING-PUBLICATION

- **Prepared**: 2026-11-17
- **Status**: `READY-PENDING-PUBLICATION`
- **Published**: **NO** (no GitHub release, tag, upload or PPA operation has been performed)
- **Purpose**: durable, project-controlled availability of the LGPL
  Corresponding Source for the Qt/PySide6 binaries shipped by esword4linux
  0.5.0-1.

## 1. Archives

| Component | Version | Original filename | SHA-256 | Size | Local path | License |
|---|---|---|---|---:|---|---|
| Qt | 6.12.0 | `qt-everywhere-src-6.12.0.tar.xz` | `98ff4f44bac6ec3e1e62ee2a4316ae0e3d15badb015d753cc0268a20db52f165` | 443,394,020 | `dist/source-archives/qt-everywhere-src-6.12.0.tar.xz` | LGPL-3.0-only / GPL-2.0-only / GPL-3.0-only / commercial |
| PySide6 + shiboken6 | 6.12.0 | `pyside-setup-everywhere-src-6.12.0.tar.xz` | `099c1a597cf33c1b000e11cf68a0b82d216fb802bf81726efc720394f10c7751` | 18,211,772 | `dist/source-archives/pyside-setup-everywhere-src-6.12.0.tar.xz` | LGPL-3.0-only / GPL-2.0-only / GPL-3.0-only / commercial |

Original upstream locations:

```text
https://download.qt.io/official_releases/qt/6.12/6.12.0/single/qt-everywhere-src-6.12.0.tar.xz
https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.12.0-src/pyside-setup-everywhere-src-6.12.0.tar.xz
```

The official sidecar files were checked:

```text
https://download.qt.io/official_releases/qt/6.12/6.12.0/single/qt-everywhere-src-6.12.0.tar.xz.sha256
https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.12.0-src/pyside-setup-everywhere-src-6.12.0.tar.xz.sha256
```

## 2. Verification

```bash
cd dist/source-archives
sha256sum -c ../../docs/licensing/source-archives.sha256
```

Expected output:

```text
pyside-setup-everywhere-src-6.12.0.tar.xz: OK
qt-everywhere-src-6.12.0.tar.xz: OK
```

GitHub Releases permits 2 GiB per asset. The largest archive is 443,394,020
bytes (≈423 MiB), so **both full archives fit**; no module-pruned replacement
is required.

## 3. Proposed project-controlled location

- **Hosting**: GitHub Releases in `felotrrs/esword4linux`.
- **Proposed tag**: `v0.5.0-lgpl-sources`
- **Proposed asset URLs**:

```text
https://github.com/felotrrs/esword4linux/releases/download/v0.5.0-lgpl-sources/qt-everywhere-src-6.12.0.tar.xz
https://github.com/felotrrs/esword4linux/releases/download/v0.5.0-lgpl-sources/pyside-setup-everywhere-src-6.12.0.tar.xz
```

These URLs are **proposed**. They do not exist until an authorized release is
created and the assets are uploaded and verified.

## 4. Publication procedure (not executed)

Requires separate authorization. Do not run these commands as part of the
audit.

```bash
cd /mnt/StorageC/esword4linux
sha256sum -c docs/licensing/source-archives.sha256 --ignore-missing
gh release create v0.5.0-lgpl-sources \
  --title "LGPL corresponding source — Qt/PySide6 6.12.0" \
  --notes-file docs/licensing/source-release-notes.md \
  dist/source-archives/qt-everywhere-src-6.12.0.tar.xz \
  dist/source-archives/pyside-setup-everywhere-src-6.12.0.tar.xz
```

After publication, an authorized reviewer must verify:

```bash
curl -fsSL -o /tmp/qt-source.tar.xz \
  https://github.com/felotrrs/esword4linux/releases/download/v0.5.0-lgpl-sources/qt-everywhere-src-6.12.0.tar.xz
sha256sum /tmp/qt-source.tar.xz
curl -fsSL -o /tmp/pyside-source.tar.xz \
  https://github.com/felotrrs/esword4linux/releases/download/v0.5.0-lgpl-sources/pyside-setup-everywhere-src-6.12.0.tar.xz
sha256sum /tmp/pyside-source.tar.xz
```

Only after those downloads and hashes match may the installed documentation
reference the release URLs as available. Until then, the project-controlled
availability status remains `PENDING-PUBLICATION`.

## 5. Scope of the source correspondence

These are the official Qt and PySide6 source releases corresponding to the
component versions. Their archive integrity is verified.

They do **not** prove that the official PyPI wheels were produced from these
archives with an exact, attested configure and patch set. That limitation is
documented in `third-party-sources.md` and
`../technical-debt/td-lgpl-source-rebuild.md`.

The archives are not added to Git and are not embedded in `.orig.tar.xz`; they
are staged under the Git-ignored `dist/source-archives/` directory.
