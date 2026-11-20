# Releasing esword4linux

This is the maintainer checklist for a public release.

## Before tagging

1. Bump the version in **every** place. They must agree or the build fails or
   the published documentation lies:

   | File | What to change |
   |---|---|
   | `src/esword4linux/__init__.py` | `__version__` — the single source of truth (`pyproject.toml` reads it) |
   | `debian/changelog` | a new `<version>-1` entry at the top |
   | `packaging/runtime-manifest.yaml` | `app_version` and the `verified` block (`date`, `deb_version`) |
   | `docs/CHANGELOG.md` | `## Unreleased` → `## <version> — <date>` |
   | `README.md`, `README.es.md` | package file name, tag download links, `cd esword4linux-<version>` |
   | `docs/INSTALL.md` | package and source-package names, tag links |
   | `.github/ISSUE_TEMPLATE/bug_report.yml` | version placeholder |

   Then confirm the previous version no longer appears in the user-facing
   documentation:

   ```bash
   git grep -n "<previous version>" -- README.md README.es.md docs/INSTALL.md
   ```

2. Confirm that no module files are tracked:

   ```bash
   git ls-files | grep -Ei '\.(bblx|bbli|cmtx|cmti|dctx|dcti|lexi|lexx|refx|refi|topx|devx|harx|mapx|twm)$'
   ```

   The command must print nothing.

3. Run the default suite without a corpus:

   ```bash
   make test
   ```

4. If a private corpus is available, run the real-module tests too:

   ```bash
   ESWORD4LINUX_TEST_CORPUS=/path/to/modules make test
   ```

5. Check the vendored core when the upstream is available:

   ```bash
   ESWORD4LINUX_VENDOR_ORIGIN=/path/to/shared/esword make drift
   ```

6. If the application logo changed, regenerate the assets and hicolor icons:

   ```bash
   .venv/bin/python tools/make_icons.py packaging/icons/hicolor
   sha256sum src/esword4linux/assets/esword4linux.png \
       src/esword4linux/assets/esword4linux-about.png
   ```

   Both hashes must match; the canonical source is
   `packaging/icons/source/esword4linux-logo.png`.

8. Build and smoke-test the application:

   ```bash
   make install
   ./run.sh
   ```

   On a clean profile, the first-run dialog must appear and cancelling must
   exit without creating a window.

## Native Debian package

The package version in `debian/changelog` is `<app version>-<Debian revision>`,
for example `0.5.2-1`. The upstream part must match `__version__` in
`src/esword4linux/__init__.py`; `packaging/build-deb.sh` enforces this.

1. Build and validate:

   ```bash
   packaging/build-deb.sh
   ```

   The script prepares the pinned wheelhouse, runs `dpkg-buildpackage` with
   debhelper 13, validates the extracted runtime, runs `lintian` and writes
   `dist/deb/esword4linux_<version>_amd64.deb`.

2. Inspect the report and package:

   ```bash
   cat .build/REPORT.txt
   dpkg-deb --info dist/deb/esword4linux_<version>_amd64.deb
   dpkg-deb --contents dist/deb/esword4linux_<version>_amd64.deb
   cat .build/lintian.txt
   ```

   Lintian must report no errors. The expected warnings are listed in
   `.build/lintian.txt`: initial upload closes no bugs, an old FSF address in
   upstream license text, and a data-only ICU library without ELF
   prerequisites. `debian/esword4linux.lintian-overrides` documents the
   intentional `/opt` layout and embedded image codecs.

   Validate the licensing evidence against the built package:

   ```bash
   packaging/audit_licensing.py --deb dist/deb/esword4linux_<version>_amd64.deb
   ```

   This checks the wheel hashes, RECORD contents, ELF inventory, license texts,
   compliance document installation and absence of wheelhouse files in the
   `.deb`. The audit's source-correspondence limitations are recorded in
   `docs/licensing/third-party-sources.md`; do not describe them as fully
   verified.

3. Confirm the runtime dependency closure:

   ```bash
   dpkg-deb -f dist/deb/esword4linux_<version>_amd64.deb Depends
   ldd .build/extract/opt/esword4linux/python/PySide6/Qt/plugins/platforms/libqxcb.so \
       | grep "not found"
   ldd .build/extract/opt/esword4linux/python/PySide6/Qt/plugins/platforms/libqwayland.so \
       | grep "not found"
   ```

   The `Depends` field must not contain a distribution Qt package such as
   `libqt6core6`.

4. Test the extracted package on an X11 session:

   ```bash
   XDG_CONFIG_HOME=/tmp/esw-test/config XDG_CACHE_HOME=/tmp/esw-test/cache \
   ESWORD4LINUX_ROOT="$PWD/.build/extract/opt/esword4linux" \
   QT_DEBUG_PLUGINS=1 .build/extract/usr/bin/esword4linux
   ```

   Verify the window opens, the first-run dialog appears on a fresh config,
   the xcb platform plugin is loaded, and no `not found` libraries appear.

5. On Wayland, if a compositor is available, run the same command with
   `QT_QPA_PLATFORM=wayland`. Record the result in the validation matrix in
   `docs/INSTALL.md`. Do not mark a distribution/session as validated unless it
   was actually exercised.

6. Test installation from the `.deb` in clean VMs:

   ```bash
   sudo apt install ./esword4linux_<version>_amd64.deb
   esword4linux
   sudo apt remove esword4linux
   test ! -e /opt/esword4linux
   test -e ~/.config/esword4linux/settings.json   # user data preserved
   ```

   The matrix in `docs/INSTALL.md` is the release gate for X11/Wayland and
   Ubuntu/Mint combinations.

## Source package and PPA

The binary `.deb` is the deliverable for direct installation. A Launchpad PPA
needs a Debian source package that contains the pinned wheelhouse, because
buildds have no PyPI access.

1. Commit every intended change. Source generation refuses a dirty tree unless
   `--allow-dirty` is passed for local validation. `--allow-dirty` includes
   modified tracked files but not untracked files.

2. Build and verify the source package:

   ```bash
   make deb-src-verify
   ```

   `make deb-src` runs the same steps without the offline binary rebuild. The
   builder validates the wheel hashes, the orig layout, the `.dsc`/`.changes`
   checksums and the absence of `debian/` from the orig.

3. Confirm the artifacts in `dist/src/`:

   ```text
   esword4linux_<version>.orig.tar.xz
   esword4linux_<version>-<rev>.debian.tar.xz
   esword4linux_<version>-<rev>.dsc
   esword4linux_<version>-<rev>_source.changes
   esword4linux_<version>-<rev>_source.buildinfo
   ```

   There must be no `NOT-PUBLICATION-READY.txt` in that directory.

4. Sign explicitly when the release is approved:

   ```bash
   packaging/build_source.py --sign-key <KEYID>
   dscverify dist/src/*.dsc
   ```

   The GPG key must be registered with Launchpad and match the maintainer
   identity. Signing is never automatic.

5. Upload manually, only after explicit authorization. The repository tooling
   never runs `dput` and never contacts Launchpad. `debian/changelog` must name
   an Ubuntu series (`noble`); `unstable` is rejected by PPAs.

**Scope.** The embedded manylinux wheels make this a PPA-only source package
for amd64. It is not directly suitable for the Debian or Ubuntu main archives
without a source-policy exception and a source-based Qt build. See
`docs/adr/0005-source-package-wheelhouse.md`.

## Publish

```bash
git add -A
git commit -m "chore: prepare public release"
git push origin main
git tag -a v<version> -m "esword4linux <version>"
git push origin v<version>
```

Then create the GitHub release from the tag and paste the top
`docs/CHANGELOG.md` section as release notes.
