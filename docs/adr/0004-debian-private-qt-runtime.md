# ADR-0004 — Vendor the Qt runtime in the native Debian package

- **Date**: 2026-11-16
- **Status**: accepted
- **Supersedes**: the version-source assumption in the Debian packaging phase

## Context

The Debian package could either:

1. depend on distribution PySide6/Qt packages
   (`python3-pyside6.qtcore`, `.qtgui`, `.qtwidgets`) plus `python3-yaml`, or
2. install a private PySide6 6.12.0 / Qt 6.12.0 runtime under
   `/opt/esword4linux`.

The original packaging plan asked to try the simpler system-package route first
and only vendor Qt if a real version incompatibility was found.

## Evidence

Checked on Ubuntu 24.04/noble, the base of Linux Mint 22.x, on 2026-11-16:

```text
$ apt-cache search pyside6
(no python3-pyside6 packages; only PySide2 and unrelated packages)

$ apt-cache policy python3-pyside6.qtcore python3-pyside6.qtgui python3-pyside6.qtwidgets
(no candidates)

$ apt-cache policy python3-yaml
6.0.1-2build2
```

`pyproject.toml` requires `PySide6-Essentials >= 6.6`. The distribution does not
provide any PySide6 package on this target, so this is not a hypothetical
version-skew problem: the recommended system packages do not exist.

## Decision

Vendor PySide6-Essentials 6.12.0, shiboken6 6.12.0, Qt 6.12.0 and ICU 73 under
`/opt/esword4linux`, as implemented by `packaging/stage_runtime.py`. Keep
PyYAML pure-Python in the same private tree. Use the host `/usr/bin/python3`
interpreter and never install into system site-packages.

`packaging/runtime-manifest.yaml` is the shared source of truth. The
`format_specific_notes.deb.qt_source` field records this decision; Flatpak will
use the KDE runtime and AppImage will vendor its own closure.

## Consequences

**Positive**

- The package works on the target distributions without unavailable packages.
- The Qt version is known and pinned (6.12.0), so X11/Wayland plugin behavior
  and image-format support are reproducible.
- ICU 73 is isolated from the distribution's ICU major version.
- The same staging layout can seed a future AppImage.

**Negative**

- The `.deb` is about 28 MB and installs about 90 MB under `/opt`.
- Security updates to Qt/PySide6 require a new package build, not only a distro
  library update.
- The private libraries are under `/opt`, which requires a documented lintian
  override.
- `dpkg-shlibdeps` must be checked so private Qt libraries do not create
  dependencies on distribution Qt packages.

## Validation

- Recursive ELF closure for both `libqxcb.so` and `libqwayland.so`: no unresolved
  libraries.
- `Depends` contains no `libqt6*`, PySide6, shiboken6 or ICU package.
- X11 launch validated on Linux Mint 22.3; Wayland validated with Weston 13
  headless/kiosk (platform plugin and window process). A full desktop
  compositor session is still pending.
- Lintian: no errors.
