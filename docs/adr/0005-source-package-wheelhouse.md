# ADR-0005 — Embed the wheelhouse in the Debian upstream source archive

- **Date**: 2026-11-17
- **Status**: accepted
- **Related**: ADR-0004 (private Qt runtime), `packaging/runtime-requirements.txt`

## Context

The native package installs a private runtime assembled by
`packaging/stage_runtime.py` from three pinned wheels:

- PySide6-Essentials 6.12.0
- shiboken6 6.12.0
- PyYAML 6.0.3

`debian/rules` reads them from `.build/wheelhouse`, which is Git-ignored. A
Launchpad buildd has no PyPI access and does not use the developer's working
tree, so a source package produced from a plain Git checkout cannot build the
runtime.

The source format is `3.0 (quilt)`. That format requires an existing
`<source>_<upstream>.orig.tar.xz`; `dpkg-source` never generates it. Any
attempt to add the wheels to an existing orig later is rejected as a binary
change in the Debian diff, and `debian/source/include-binaries` would store
them in `.debian.tar.xz`, which is the wrong archive and duplicates ~84 MiB.

## Decision

Generate the upstream archive explicitly with `packaging/build_source.py`.

The orig contains:

- every file tracked in Git at the package version;
- exactly the three validated wheel files under `.build/wheelhouse/`;
- no `debian/` directory (that belongs to `.debian.tar.xz`).

The tool, not `dpkg-source`, creates the archive. It exports tracked files from
Git metadata (preserving modes and symlinks), copies only the wheels returned
by `stage_runtime.verify_wheelhouse()`, and creates a deterministic tar:

```text
tar --sort=name --format=gnu --owner=0 --group=0 --numeric-owner \
    --mtime="@<changelog date>" --exclude=<root>/debian
  | xz -6 -T1
```

`dpkg-buildpackage -S -sa -d` then produces the `.dsc`, `.debian.tar.xz`,
`_source.changes` and `_source.buildinfo`. The package is unsigned by default;
`--sign-key` is an explicit, local option and nothing is uploaded.

`packaging/stage_runtime.py` is not modified: its SHA-256 validation remains the
single source of truth, and the source builder calls
`verify_wheelhouse()` before copying anything.

## Alternatives rejected

1. **Add wheels to Git.** Rejected: binary artifacts in history, repository
   bloat, and the project policy that `.build/` is never versioned.
2. **`debian/source/include-binaries`.** Rejected: puts wheels in the Debian
   diff, produces a huge `.debian.tar.xz`, and still needs a local wheelhouse
   at build time.
3. **`debian/source/options` with `tar-ignore`.** Rejected: `dpkg-source` does
   not create the orig in `3.0 (quilt)`, so the option has no effect on the
   upstream archive.
4. **Download wheels during the build.** Rejected: Launchpad buildds are
   offline, builds must be reproducible, and `ca-certificates`/`python3-pip`
   would become unnecessary build dependencies.
5. **Depend on distribution PySide6 packages.** Rejected in ADR-0004: Ubuntu
   noble does not provide PySide6 6.12.

## Consequences

- The source package is self-contained for the three Python dependencies.
  `dpkg-source -x` plus `unshare -rn dpkg-buildpackage -b` succeeds with no
  network access.
- The orig is about 84 MiB because the PySide6 wheel is already compressed.
  Uploads are slower and PPA quota must be monitored.
- The embedded wheels are `manylinux_2_34 x86_64` for CPython 3.10-3.14, so the
  source package is effectively amd64-specific. `Architecture: amd64` matches;
  do not upload it for other architectures.
- **Scope: Launchpad PPA only.** Prebuilt wheels in an upstream tarball are not
  acceptable for the Debian or Ubuntu main archives without a source-policy
  exception and a fully source-based Qt build. This repository does not claim
  otherwise.
- `debian/changelog` uses an Ubuntu series (`noble`), because a PPA upload
  requires one and rejects `unstable`.
- The `--allow-dirty` mode exists only to validate local work. Its output is
  marked `NOT-PUBLICATION-READY.txt` and must not be uploaded.
- The archive is byte-reproducible for a fixed changelog date and wheelhouse;
  `.dsc`/`.changes` retain host and signature metadata and are not expected to
  be byte-identical across machines.

## LGPL compliance boundary (Phase 3.5 audit)

Embedding the wheels in the orig makes the build self-contained, but it does
not by itself establish LGPL Corresponding Source correspondence. The audit
records the exact Qt/PySide6 source archives, their SHA-256 values and the
loader replacement tests in `docs/licensing/`. The current status is
`PARTIAL`: the source releases are identified and available, but no distributed
build attestation proves the wheel binaries were produced from those archives
with the exact configure flags and no unpublished patches. A full
from-source Qt/PySide6 rebuild test is still required before claiming
verified compliance. Do not describe the embedded wheelhouse as sufficient
Corresponding Source.

The full source archives are staged under `dist/source-archives/` and published
in the project-controlled GitHub Release `v0.5.0-lgpl-sources`; the assets were
downloaded back and hash-verified. See
`docs/licensing/source-release-manifest.md` for the release URLs and hashes.
