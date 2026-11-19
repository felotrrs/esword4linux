# Technical debt

Open, known and non-blocking work. Roughly ordered by impact.

## Open packaging work

- Licensing audit: exact binary-to-source provenance for the official Qt and
  PySide6 wheels is `PARTIAL`. The source archives are identified and their
  SHA-256 values are verified, but no wheel build attestation links them to the
  binaries. A full Qt/PySide6 rebuild and ABI-compatible replacement test is
  still outstanding; only the loader/replacement mechanism was demonstrated.
  See `docs/technical-debt/td-lgpl-source-rebuild.md`.
- Per-object license mapping for all 288 ELF objects in the wheelhouse is
  incomplete. The installed runtime has its license texts and Qt attribution;
  the confirmed MPL-2.0 public-suffix component and LGPL-2.1-or-later KDE
  appmenu protocol are now declared, but a file-by-file review of the remaining
  Qt third-party components is still recommended.
- The full Qt/PySide6 source archives are published in the project-controlled
  GitHub Release `v0.5.0-lgpl-sources` and were round-trip verified on
  2026-11-17. See `docs/licensing/source-release-manifest.md`.
- The About dialog now shows the GPL-3.0 and Qt/PySide6 LGPL-3.0 notices with the
  GNU LGPL link and the installed compliance-document link. The remaining
  notice question is only the formal legal review of the wording.

- The wheelhouse-embedded Debian source package (ADR-0005) is **PPA-only**. The
  Debian/Ubuntu main archives need a source-policy exception and a Qt build
  from source; do not propose it for those archives as-is.
- Validate the generated `.dsc` on a real Launchpad PPA buildd for noble/amd64.
  Local validation uses `unshare -rn` and cannot reproduce the buildd image
  exactly. Signing and `dput` remain manual, explicitly authorized steps.
- The source orig is about 84 MiB because PySide6 is already compressed. Watch
  PPA quota and upload time when publishing a new version.
- `packaging/build-deb.sh --wheelhouse DIR` does not work: the script exports
  `ESWORD4LINUX_WHEELHOUSE`, while `debian/rules` reads the make variable
  `WHEELHOUSE`. Use the default wheelhouse, or fix the script separately.
- `--verify-build` reflects the working tree as-is: an unrelated uncommitted
  icon change can fail `validate_runtime.py` even though the source package is
  structurally valid. Validate the release from a clean tree.

- Validate the native `.deb` in clean Ubuntu 24.04 LTS and Linux Mint 22.x VMs
  under both X11 and Wayland. The current build host validated X11 and Weston
  13 headless/kiosk Wayland.
- Test a full desktop Wayland compositor session (GNOME/KDE/wlroots) with the
  bundled xdg-shell, bradient decoration and EGL client integrations.
- Test an upgrade from an earlier package version; `0.5.0-1` is the initial
  native package.
- Build and validate a Flatpak from the `org.kde.Platform` runtime using the
  same `packaging/runtime-manifest.yaml`; do not vendor Qt separately there.
- Build and validate an AppImage independently, reusing
  `packaging/runtime-manifest.yaml` and `packaging/stage_runtime.py`; do not
  extract the `.deb` and call it portable.
- Consider whether the AppImage needs additional font, icon-theme or
  xdg-desktop-portal integration that the Debian package intentionally leaves
  to the distribution.

## Resolved in 0.4.4

- Pop-ups with their last line cut off or half-hidden by `QTextBrowser` padding;
  the document is now painted directly.
- Hebrew words invisible in Strong's entries because line breaks were flattened
  into a single RTL paragraph.
- Citations that hid the book/chapter with no way to restore them.
- Parallel-view checkbox without a checkmark.
- "Strong" button renamed to "Lexicon"; About icon replaced with the default
  application icon.

## Resolved in 0.4.3

- Pop-ups with vertical gaps caused by orphan closing tags (`</p>`).
- Inconsistent height and clipping in pop-ups; there is now a single format and
  measurement path.
- Library term-list button inconsistent with the Resources panel.
- Resources limited to a single grouping criterion; filters and groupings can
  now be combined.
- Enter in Search required clicking "Go to …" for references.
- Bible with vertical chapter arrows and a permanently visible parallel combo.
- Missing a multi-citation box in the style of the Bible project.
- "Tab A" was not retranslated when the language changed.
- Parallel-view checkbox barely visible in the dark theme.
- Icon with a painted checkerboard/background card.

## Resolved in 0.4.2

- Pop-ups with the last line cut off (height now calculated from the real
  layout).
- Resource panel and library term list disappearing when dragging the splitter;
  they now have minimum sizes, non-collapsible splitters and a recovery button.
- Strong's entries and commentaries not refreshing pop-ups until "Open" was
  pressed.
- Language detection producing false positives from English authors and words.
- Missing "By language" view and missing filter in the translation combo.
- Low contrast between dark-theme backgrounds.
- Outdated default icon; `esword4linux2.webp` now also generates the hicolor
  set.

## Resolved in 0.4.1

- Narrow or clipped pop-ups and a header using the long work title.
- Bible with side margins caused by `stretch` (it now uses the full width).
- Hardcoded book aliases and unrecognised passage formats (I/II prefixes,
  `1ª`, `Jn 3,16`, lists such as `, 27-30` / `; 7.11`, multi-word names and
  abbreviations such as `Luk`/`Jhn`/`Rth`/`Ezk`…).

## Resolved in 0.4.0

- Sidebar with no maximum width and with its handle at the top.
- Tabs not growing when the panel was collapsed.
- Bible not growing horizontally.
- Native tooltip that was wide and used the panel colour → custom bubble.
- No pop-ups in dictionaries, lexicons or commentaries.
- Strong's lexicon could not be selected.
- Legacy Greek in modules outside the vendored registry.
- Duplicates had no listing or tool.

## Resolved in 0.3.0

- e-Sword pseudo-tags (`</red>`, `</grk>`…) displayed literally.
- Undecoded cp1253/cp1255 Greek in older commentaries.
- Cross-references and notes without a pop-up or navigation.
- Strong's numbers without access to the lexicon.
- Single-colour tabs (dot) and a close button stuck to the edge.

## Resolved in 0.2.0

- Commentaries in their own bottom panel (previously embedded in the text).
- One tab per module → workspace tabs with a Bible group + parallel + commentary.
- Parallel view and commentary hidden when the resource is not a Bible.
- Collapsible resources panel (`Ctrl+B`).
- One click loads a resource (previously a double click).
- Modern commentary schema `.cmtx` (`Verses` with ranges).
- Bulk decryption of encrypted modules (`make encrypted`).
- Application icons installed with `make desktop`.

## Data / format

| # | Topic | Detail | Impact |
|---|---|---|---|
| 1 | **Legacy codepages** | ✅ Resolved: registry + automatic detection from content (0.4.0). | — |
| 2 | **Strong's in the text** | ✅ Resolved in 0.3.0: anchor + pop-up + bottom Strong's panel. | — |
| 3 | **Deuterocanonical books** | They are displayed (books 67–73), but their names depend on `src/esword4linux/core/books.yaml`; it still needs edition-by-edition verification that the numbering matches the content. | Low |
| 4 | **`.lanx` / `headings.*`** | Cataloged as `unknown` and shown under "Unclassified". They could be hidden or labelled "e-Sword resources". | Low |
| 5 | **Duplicates** | ✅ Resolved in 0.4.0: `tools/deduplicate.py` (sha256) + quarantine with a manifest. | — |
| 6 | **Map images** | Shown at a fixed width of 760 px; zoom and fit-to-window are missing. | Low |

## Index / search

| # | Topic | Detail | Impact |
|---|---|---|---|
| 7 | **Full indexing** | Indexing an entire library is a long, memory-heavy job; it still needs measurement and chunking with cancellable progress. | Medium |
| 8 | **Cancellable indexing** | The worker honours `requestInterruption()`, but `Indexer` does not check the flag between modules. | Medium |
| 9 | **Proximity search** | FTS5 `NEAR` is not used; "love god" searches for both terms in any order or position. | Low |
| 10 | **Highlighting in the viewer** | Jumping from a result does not highlight the term in the module text. | Low |
| 11 | **Search in maps** | Only the title and caption are indexed, not the image content (obviously). | — |

## UI

| # | Topic | Detail | Impact |
|---|---|---|---|
| 12 | **Split a tab into two groups** | Tabs can be reordered and each has its vertical split (Bible/commentary) and horizontal split (parallel), but two independent groups cannot coexist inside the same tab. | Medium |
| 13 | **Pop-ups and typography** | The pop-ups in `src/esword4linux/ui/tooltip.py` use fixed CSS and do not follow the font preferences. | Low |
| 14 | **Accessibility** | No configurable shortcuts and no keyboard navigation beyond Ctrl+F/Ctrl+R/Ctrl+Q. | Low |
| 15 | **Icons** | The UI uses text glyphs (`●○✕🔒`) instead of an icon set. | Low |
| 21 | **Stacked comparison bands** | When more versions do not fit in one row, the parallel table scrolls horizontally. Splitting it into stacked bands (five versions each) that scroll together vertically is designed but not implemented. | Medium |

## Engineering

| # | Topic | Detail | Impact |
|---|---|---|---|
| 16 | **Twofish in C** | Pure-Python Twofish is CPU-bound; a C extension would reduce decryption time by orders of magnitude. Today it is compensated for with a process pool. | Low |
| 17 | **Schema migrations** | `content.db` has no versioning; a schema change requires deleting it. | Low |
| 18 | **Packaging** | There is no AppImage or Flatpak; the app runs from the checkout with `run.sh`. | Low |
| 19 | **UI tests** | The widget tests (`test_ui_layout`, `test_theme`, `test_tooltip`) use `QApplication` in `offscreen` mode without `pytest-qt`. More end-to-end window flows need coverage. | Low |
| 20 | **Core drift** | `make drift` exists but does not run in a hook; it depends on someone running it. | Low |
