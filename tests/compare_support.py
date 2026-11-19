"""Shared fakes for comparator integration tests (no real modules)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget

from esword4linux.core.esword.module import EswordModule

BOOK = 1
CHAPTER = 1


def make_bible(path: Path, rows: list[tuple[int, int, int, str]]) -> None:
    """Create a minimal e-Sword ``Bible`` table with harmless text."""
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "CREATE TABLE Bible (Book INT, Chapter INT, Verse INT, Scripture TEXT)"
        )
        conn.execute(
            "CREATE INDEX BookChapterVerseIndex ON Bible (Book, Chapter, Verse)"
        )
        conn.executemany(
            "INSERT INTO Bible (Book, Chapter, Verse, Scripture) VALUES (?, ?, ?, ?)",
            rows,
        )
        conn.commit()
    finally:
        conn.close()


def row(
    rel_path: str,
    path: Path,
    title: str,
    abbreviation: str,
    *,
    module_id: int,
    language: str = "es",
    entries: int = 0,
    kind: str = "bible",
) -> dict:
    return {
        "id": module_id,
        "path": str(path),
        "rel_path": rel_path,
        "filename": path.name,
        "ext": path.suffix.lstrip("."),
        "structure": "bible" if kind == "bible" else kind,
        "kind": kind,
        "title": title,
        "abbreviation": abbreviation,
        "language": language,
        "encrypted": 0,
        "entries": entries,
        "size": 0,
        "mtime": 0.0,
        "index_status": "pending",
        "duplicate_of": None,
    }


class FakeCatalog:
    def __init__(self, rows: list[dict]):
        self._rows = {r["rel_path"]: r for r in rows}

    def by_rel_path(self, rel_path: str) -> dict | None:
        return self._rows.get(rel_path)

    def modules(self, kind: str | None = None,
                include_duplicates: bool = False) -> list[dict]:
        return [
            r for r in self._rows.values()
            if kind is None or r.get("kind") == kind
        ]


class FakeRefs:
    def __init__(self):
        self.rel = ""

    def set_bible(self, rel: str) -> None:
        self.rel = rel

    def tooltip(self, href: str, rel_path: str | None = None) -> str:
        return ""

    def verse_tooltip(self, text: str, rel_path: str | None = None) -> str:
        return ""

    def clear(self) -> None:
        pass


class FakeStrong:
    def tooltip(self, code: str, max_chars: int = 2500) -> str:
        return ""

    def module(self):
        return None

    def candidates(self) -> list[dict]:
        return []

    def set_default(self, rel: str) -> None:
        pass

    def entry(self, code: str):
        return "", ""

    def label(self) -> str:
        return ""


class FakeContext:
    def __init__(self, settings, rows: list[dict],
                 modules: dict[str, EswordModule]):
        self.settings = settings
        self.catalog = FakeCatalog(rows)
        self._modules = modules
        self.refs = FakeRefs()
        self.strong = FakeStrong()

    def bibles(self) -> list[dict]:
        return self.catalog.modules("bible")

    def commentaries(self) -> list[dict]:
        return []

    def module(self, module):
        if not module:
            return None
        return self._modules.get(module["rel_path"])


class FakeLibrary(QWidget):
    """Stand-in for ``LibraryView`` in Workspace mode tests."""

    open_reference = Signal(str)
    ref_bible_changed = Signal(str)

    def __init__(self, ctx, row, initial_ref=None, ref_bible_rel="", parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.row = row
        self._ref = ref_bible_rel

    def set_reference_bible(self, rel: str) -> None:
        self._ref = rel
