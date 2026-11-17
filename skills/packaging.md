# Packaging: native Debian package and private runtime

This skill owns the native `.deb`, the private runtime staged under
`/opt/esword4linux`, and the reuse path for a future AppImage. Application
behavior is out of scope: packaging must not require code changes.

## Golden rules

1. **Never install into system Python.** The interpreter is `/usr/bin/python3`;
   PySide6-Essentials, shiboken6, Qt and PyYAML live under
   `/opt/esword4linux/python`.
2. **Never modify the developer `.venv`.** Staging runs in `.build/` and reads
   only pinned wheels from `.build/wheelhouse`. `debian/rules` overrides
   `dh_clean` with `-X.venv -X.build -Xdist -X.cache` because debhelper's
   `__pycache__` sweep otherwise enters the virtual environment.
3. **The runtime manifest is the inventory.** Every retained or excluded Qt
   library/plugin, system library, license and rationale belongs in
   `packaging/runtime-manifest.yaml`. The manifest doubles as the AppImage input.
4. **Pin and hash every wheel.** `packaging/runtime-requirements.txt` contains
   versions and SHA-256 hashes. A build without network access uses
   `--offline`; runtime never downloads anything.
5. **No modules.** The package must never contain `.bblx`, `.cmtx`, `.dctx`,
   `.lexi`, `.twm`, `.mapx` or any other e-Sword module. The build script
   checks this.
6. **User data is untouchable.** Settings live in `~/.config/esword4linux/`,
   cache in `~/.cache/esword4linux/`. Maintainer scripts must not remove them.
7. **X11 and Wayland are both client requirements.** Keep the xcb and Wayland
   platform plugins, their GL/EGL integrations, shell/decoration plugins and
   image-format plugins. Do not remove an image plugin without testing a module
   that uses it.
8. **Do not force a platform.** The launcher leaves `QT_QPA_PLATFORM` unset so
   Qt selects the session backend; users may override it explicitly.
9. **Validate, don't assume.** A built package is not a tested package. Record
   X11/Wayland and distribution results in the matrix in `docs/INSTALL.md`.
10. **Licensing is a release gate.** Update `debian/copyright`,
    `packaging/licenses/` and `packaging/licenses/QT-THIRD-PARTY.md` when a
    bundled component or version changes.

## Why there is no qt.conf

The PySide6 wrappers carry RPATH entries relative to their own directory
(`$ORIGIN/Qt/lib`, `$ORIGIN/../shiboken6`) and the launcher sets
`QT_PLUGIN_PATH` to the private plugin tree. Qt resolves the private prefix
correctly with that setup. Do not add a `qt.conf` unless a reproducible plugin
path failure proves it necessary; document the failure and the change.

## Layout

```text
/usr/bin/esword4linux                     shell launcher (scoped environment)
/opt/esword4linux/app/esword4linux/       application package + data
/opt/esword4linux/python/PySide6/         PySide6 and private Qt tree
/opt/esword4linux/python/shiboken6/       Shiboken runtime
/opt/esword4linux/python/yaml/            pure-Python PyYAML
/opt/esword4linux/licenses/               license and attribution texts
/usr/share/applications/esword4linux.desktop
/usr/share/icons/hicolor/<size>/apps/esword4linux.png
/usr/share/doc/esword4linux/
```

The canonical icon source is `packaging/icons/source/esword4linux-logo.png`.
`tools/make_icons.py` regenerates `src/esword4linux/assets/esword4linux.png`,
`esword4linux-about.png`, the installer copies under `packaging/icons/apps/`
and the hicolor 16–512 px set. Keep the app and About assets byte-identical.

## Commands

```bash
packaging/build-deb.sh                 # full build + package QA + lintian
packaging/build-deb.sh --offline       # reuse .build/wheelhouse
packaging/qa-deb.sh dist/deb/*.deb     # X11/Wayland runtime observations
python3 packaging/stage_runtime.py --wheelhouse DIR --dest DIR
python3 packaging/validate_runtime.py --root DIR
make deb
```

Build output: `dist/deb/esword4linux_<version>_amd64.deb`.
Logs and report: `.build/REPORT.txt`, `.build/lintian.txt`,
`.build/dpkg-deb-contents.txt`.

## Adding or removing a Qt component

1. Change `packaging/runtime-manifest.yaml` (`staging.qt_libraries` or the
   exact lists under `qt_plugins_required`) and add the exclusion/rationale to
   `qt_plugins_required.excluded_explicitly`.
2. Rebuild and run `packaging/validate_runtime.py`: it resolves every ELF
   object recursively and fails on `not found` or on a private Qt/ICU library
   resolving outside the runtime.
3. Check `dpkg-shlibdeps` output for new system dependencies and update
   `system_libraries_expected` in the YAML if the closure changed.
4. Update `debian/copyright` and `packaging/licenses/` if a new component adds
   a license.
5. Test representative modules: Bible, commentary, map/illustration with
   PNG/JPEG/WebP, and a search query.

## Future AppImage

Do not extract the `.deb` and call it portable. Reuse `stage_runtime.py` with a
different `--dest`, plus the manifest and system-library inventory. The
launcher already supports `ESWORD4LINUX_ROOT`; an AppImage should build its own
wrapper and still avoid a virtualenv or runtime installation.
