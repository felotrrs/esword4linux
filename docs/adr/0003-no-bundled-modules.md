# ADR-0003 — No bundled modules and a mandatory first-run folder dialog

- **Date**: 2026-11-16
- **Status**: accepted

## Context

esword4linux is a reader for e-Sword modules. Those modules are copyrighted by
their publishers and are not redistributable with the application. Earlier
development builds used a developer-specific folder, a default Bible and a
small preindex list so the app looked complete on the maintainer's machine.

That is unacceptable for a public release:

- users would see paths and modules that do not exist on their computers;
- the application could appear to ship content it has no right to distribute;
- search indexes would be built without the user asking for them;
- tests and documentation would depend on a private corpus.

## Decision

1. The repository contains **no e-Sword modules**, no default Bible and no
   default last reference.
2. On first run, before the main window is created, `FirstRunDialog` asks the
   user for a single modules folder. If the user cancels, the process exits.
3. The folder is opened read-only. Invalid folders (no recognised modules) are
   rejected.
4. The first scan collects metadata only. Indexing and decryption are explicit
   actions from the **Index** menu or the CLI tools.
5. Settings and the cache use XDG paths (`~/.config/esword4linux` and
   `~/.cache/esword4linux`), never a developer path.
6. Tests that need real modules read `ESWORD4LINUX_TEST_CORPUS` and skip when it
   is unset. They use temporary catalogs, never the user's cache.

## Alternatives considered

| Option | Why not |
|---|---|
| **Ship a public-domain Bible** | Still creates a default module, adds legal review and makes the app look incomplete without it. The user's library is the point. |
| **Ask for the folder from a preference page after startup** | Leaves a blank window and lets users believe the app is broken. |
| **Auto-index the first module** | Surprises users with heavy CPU/disk work and contradicts the on-demand index design. |
| **Keep a preindex list** | Any list is machine-specific or privileges certain publishers. |

## Consequences

**Positive**

- The public repository is safe to distribute and has no copyrighted content.
- First-run behaviour is predictable and identical on every machine.
- Users keep control of indexing cost and timing.
- Tests are reproducible in CI without private data.

**Negative**

- The app is unusable until the user selects a folder; this is intentional.
- The first-run dialog adds a small amount of UI code and translation work.
- Development and manual testing need an external corpus supplied through
  `ESWORD4LINUX_TEST_CORPUS`.
