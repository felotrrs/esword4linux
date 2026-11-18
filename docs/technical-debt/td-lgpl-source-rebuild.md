# TD-LGPL-01 — Qt/PySide6 source rebuild and provenance

- **Status**: deferred, accepted risk for the personal Ubuntu Noble PPA
- **Date opened**: 2026-11-17
- **Applies to**: esword4linux 0.5.0-1 and the private `/opt/esword4linux`
  runtime
- **Not a legal opinion**

## Problem

The installed runtime contains Qt/PySide6 6.12.0 binaries from the official
PyPI wheels. The exact build configuration and patch set used by the upstream
wheel builders are not independently attested. The project has demonstrated
that a compatible modified shared library and plugin are loaded after
replacement, but it has **not** built Qt/PySide6 from source and replaced the
runtime with that independent build.

This is distinct from source availability: the official source archives are
identified, hash-verified and staged for project-controlled publication.

## Current evidence

- Exact PyPI wheels and SHA-256 values are recorded in
  `docs/licensing/third-party-sources.md`.
- The wheel `RECORD` hashes verify completely.
- Qt 6.12.0 and PySide6/shiboken6 6.12.0 source archives were downloaded and
  hash-verified.
- A disposable runtime accepted a modified `libQt6Core.so.6` and a modified
  `libqxcb.so`; the application started and `/proc/<pid>/maps` showed the
  replaced files. The originals were restored successfully.
- No full Qt/PySide6 build was performed.

## Missing evidence

- No signed build attestation or reproducible-build record links the wheels to
  the source archives.
- Exact Qt `configure` options and any patches are not recorded in the wheel.
- No independently rebuilt Qt/PySide6 library has been ABI-tested against the
  application.
- The replacement test used a binary-patched compatible copy, not a rebuilt
  library.

## Proposed future investigation

1. Reproduce the official wheel build in a controlled environment using the
   documented Qt/PySide6 releases.
2. Record the exact configure flags, compiler/glibc toolchain and patches.
3. Produce a modified compatible Qt/PySide6 build and replace the private
   runtime libraries/plugins with it.
4. Verify startup, representative Bible/commentary/dictionary operations, X11
   and Wayland, and rollback.
5. Compare build metadata/attestations with the official wheel and document
   any remaining difference.

## Suggested acceptance criteria

- A reproducible build log or attestation ties the source archives to the
  distributed binaries.
- A modified rebuilt library with the same SONAME/ABI is loaded by the
  application and passes runtime validation.
- The procedure is documented and independently repeatable.
- Any residual binary/source differences are explicitly documented.

## Why deferred for the personal PPA

The intended distribution is a personal Ubuntu Noble PPA, not an official
Ubuntu archive or a corporate product. The wheels are the official Qt project
wheels, source archives and license texts are available, the replacement
mechanism works, and the remaining provenance gap is documented rather than
hidden. A full Qt rebuild is disproportionate for this distribution channel.

## Reopening triggers

Reopen this issue if any of the following occurs:

- submission to an official Ubuntu/Debian archive;
- adoption by a corporate distributor or a User Product;
- a requirement for independently reproducible Qt/PySide6 builds;
- discovery of a source-correspondence discrepancy or a wheel hash change;
- a licensing review that requires stronger provenance evidence;
- a change to the bundled Qt/PySide6 version or wheel source.
