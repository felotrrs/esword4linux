# ADR-0001 — Native PySide6/Qt6 client, no Wine

- **Date**: 2026-11-10
- **Status**: accepted

## Context

e-Sword exists only for Windows. On Linux it ran under Wine, with two problems:

1. **Fragility**: it depended on an installation symlink, registered OCX
   controls (`ComboList.ocx`, `RichEdit.ocx`), `wmp11`, and a 64-bit prefix with
   classes under `Wow6432Node`. A single broken link produced a silent failure
   (`c0000135` on stderr, exit code 0).
2. **Inadequate UI**: the library is grouped into fixed tabs by type; with
   hundreds of modules, navigation becomes unmanageable.

The project needed a client that opens **any** module from a single folder,
classifies it automatically, and provides freely arranged panels with real
search.

## Decision

Build a **native** application in **PySide6 (Qt 6)** that reads the SQLite
modules directly, with no compatibility layer.

## Alternatives considered

| Option | Why not |
|---|---|
| **Keep Wine** | It solves neither the UI problem nor the fragility. The app would still depend on OCX controls and the Wine prefix. |
| **GTK4 + PyGObject** | Already installed, but its rich HTML rendering for commentaries is poor; matching `QTextDocument` would require WebKit2GTK. |
| **PyQt5** | Qt5 is end-of-life and lacks the Qt6 APIs. |
| **Electron / Tauri** | Excellent web rendering, but 150–300 MB of RAM for a reading app and a stack different from the rest of the environment. |

## Consequences

**Positive**

- Startup well under two seconds; chapter reads in tens of milliseconds; no
  emulation.
- `QTextDocument` renders RTF→HTML and module HTML with sufficient quality.
- `QTreeView`/`QTabWidget` cover the collapsible sidebar and the requested
  closable/reorderable tabs.
- A single dependency (`PySide6-Essentials`, LGPLv3), installable with pip.

**Negative**

- Around 120 MB of wheels in the virtual environment.
- Everything e-Sword already did (navigation, comparison, search) has to be
  implemented by hand. That is precisely the point of the project.
- The UI is tied to Qt; the logic is not (see `docs/ARCHITECTURE.md`: `core/`
  does not import PySide6).

## Licensing note

The Twofish decryptor is a GPL-3.0 port of KingJamesPureBibleSearch
(© Donna Whisnant). esword4linux is therefore distributed as **GPL-3.0**.
PySide6 is LGPLv3 and is compatible.
