# Testing — conventions for the suite

The suite must be **hermetic**: no real modules, no real user configuration, no
network, no writes outside `tmp_path`. It runs with `make test` on a machine
that has never opened an e-Sword module.

## Structure

| Area | File |
|---|---|
| Books, references, pairing, Strong | `tests/test_books.py`, `test_matching.py`, `test_refchain.py` |
| Modules, decryption, text | `test_module.py`, `test_decrypt.py`, `test_text.py`, `test_rich_text.py` |
| Search engine and index | `test_pipeline.py`, `test_search_filters.py` |
| UI (offscreen Qt) | `test_ui_layout.py`, `test_main_window.py`, `test_commentary_selector.py`, `test_compare_ui.py` |
| Packaging, licensing, icons | `test_licensing.py`, `test_about_license.py`, `test_icons.py` |

## Hermetic rules

1. **Never touch the user's configuration.** `tests/conftest.py` redirects
   `SETTINGS_FILE`/`CONFIG_DIR` to a temporary directory for every test. A test
   that builds a `MainWindow` calls `Settings.save()`; without that redirect it
   would overwrite `~/.config/esword4linux/settings.json` (including
   `cache_dir`). Keep the fixture `isolated_user_config` autouse.
2. **Synthetic modules only.** Build them in `tmp_path` with `sqlite3` (see
   `_make_bible()` in `test_search_filters.py` and `test_compare_sqlite.py`).
   They are never committed and never written to the user's modules folder.
   `.gitignore` blocks the real extensions on purpose.
3. **Real corpora are opt-in.** Tests that need a real library use the
   `corpus_context` / `corpus_catalog` fixtures and `requires_corpus`, which
   **skip** when `ESWORD4LINUX_TEST_CORPUS` is unset. Never read the
   developer's cache from a test.
4. **A synthetic catalog row is enough** for metadata tests: insert into the
   `module` table (see `populated_settings` in `conftest.py`); use
   `ContentStore.add_pages()` to fill the FTS5 index with controlled bodies.

## Qt tests

```python
pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication

@pytest.fixture()
def app():
    return QApplication.instance() or QApplication([])
```

- Show the widget (`resize` + `show`) before asserting visibility or geometry;
  `isVisible()` is false while the parent chain is hidden.
- `app.processEvents()` does not fire `QTimer`s: wait explicitly.
- **Workers:** a `QThread` result arrives asynchronously. Use the explicit
  `_wait_lists(view, app)` loop (bounded, `processEvents` + a short sleep) or a
  `QSignalSpy`; never a fixed `sleep` as the only synchronisation.
- **Count what matters:** to prove that typing does not search, monkeypatch the
  engine and assert the call list (`counted_search` fixture) instead of
  inspecting the UI text only.
- **Prefer widget state over pixels.** Assert `isEnabled()`, `currentData()`,
  object names and layout membership. Geometric checks are fine when they are
  *relative* (same line, same order, same width) and not absolute coordinates.

## What every change needs

- A **regression test** for the behaviour, not for the implementation.
- A **bug** gets a test that fails before the fix (reproduce, then fix).
- **New filters/modes:** engine tests with a synthetic index, plus UI tests for
  the enablement, the mutual exclusion and the `SearchFilters` payload.
- **New UI areas:** the narrow-window behaviour (everything visible, wrapped in
  reading order) and the disabled state.
- The **full suite** stays green: `make test` (332 passed, ~35 skipped without
  a corpus at the time of writing).

## Naming

- One sentence docstring per test file, one line per test when the name is not
  enough.
- `test_<behaviour>_<condition>`: `test_typing_does_not_search`,
  `test_book_range_restricts_the_search`, `test_first_launch_populates_the_commentary_selector`.
- Fixtures that build data are named after what they build (`env`, `view`,
  `make_window`, `corpus_context`).

## Related

- `skills/design.md` — what the UI tests must assert.
- `skills/search-index.md` — the engine and filter semantics.
- `skills/performance.md` — measuring instead of assuming.
