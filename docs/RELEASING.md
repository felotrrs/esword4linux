# Releasing esword4linux

This is the maintainer checklist for a public release.

## Before tagging

1. Update `__version__` in `src/esword4linux/__init__.py`. `pyproject.toml`
   reads the version from there.
2. Add the release entry at the top of `docs/CHANGELOG.md`.
3. Confirm that no module files are tracked:

   ```bash
   git ls-files | grep -Ei '\.(bblx|bbli|cmtx|cmti|dctx|dcti|lexi|lexx|refx|refi|topx|devx|harx|mapx|twm)$'
   ```

   The command must print nothing.

4. Run the default suite without a corpus:

   ```bash
   make test
   ```

5. If a private corpus is available, run the real-module tests too:

   ```bash
   ESWORD4LINUX_TEST_CORPUS=/path/to/modules make test
   ```

6. Check the vendored core when the upstream is available:

   ```bash
   ESWORD4LINUX_VENDOR_ORIGIN=/path/to/shared/esword make drift
   ```

7. If the application logo changed, regenerate the assets and hicolor icons:

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
for example `0.5.0-1`. The upstream part must match `__version__` in
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

## Publish

```bash
git add -A
git commit -m "chore: prepare public release"
git push origin main
git tag -a v0.5.0 -m "esword4linux 0.5.0"
git push origin v0.5.0
```

Then create the GitHub release from the tag and paste the top
`docs/CHANGELOG.md` section as release notes.
