"""Workspace: a view tab with its own main resource.

A tab groups one main resource. If it is a Bible, it includes its own parallel
Bible and commentary panel. If it is not a Bible, it shows the module viewer
and offers a reference Bible selector for bubbles and for opening citations
from that work.
"""

from __future__ import annotations

import re

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget

from ..core.context import AppContext
from ..i18n import tr
from .bible_view import BiblePane, fill_bible_combo
from .library_view import LibraryView


class Workspace(QWidget):
    reference_changed = Signal(str)
    open_module = Signal(int, str)
    search_requested = Signal(str)
    reference_requested = Signal(str)

    def __init__(self, ctx: AppContext, name: str, color: str, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.settings = ctx.settings
        self.name = name
        self.color = color
        self.name_auto = False
        self.auto_letter = ""
        self.main_rel = ""
        self.main_kind = ""
        self._library: LibraryView | None = None
        # Independent reference Bible for non-Bible workspaces
        self._ref_bible_rel: str = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.stack = QStackedWidget()
        self.bible = BiblePane(ctx)
        self.bible.reference_changed.connect(self.reference_changed)
        self.bible.open_module.connect(self.open_module)
        self.bible.search_requested.connect(self.search_requested)
        self.stack.addWidget(self.bible)

        self.placeholder = QWidget()
        self.stack.addWidget(self.placeholder)
        layout.addWidget(self.stack)

    # ── reference Bible for non-Bible workspaces ─────────────────────────
    def ref_bible_rel(self) -> str:
        """Relative path of this workspace reference Bible."""
        return self._ref_bible_rel

    def set_ref_bible_rel(self, rel: str) -> None:
        """Set this workspace reference Bible (independent)."""
        rel = rel or ""
        self._ref_bible_rel = rel
        if self._library is not None:
            self._library.set_reference_bible(self._ref_bible_rel)
        # Notify the bubble resolver so citations in this work resolve with
        # the translation chosen in this workspace.
        # Each LibraryView passes its own bible_rel when resolving; we do not
        # use the global RefResolver state to avoid affecting other workspaces.

    # ── main resource ────────────────────────────────────────────────────
    def set_main(self, row: dict | None, ref: str | None = None) -> None:
        if row is None:
            self.stack.setCurrentWidget(self.placeholder)
            return
        if (row["rel_path"] == self.main_rel and self.main_kind == row["kind"]
                and (row["kind"] == "bible" or self._library is not None)
                and not ref):
            return
        self.main_rel = row["rel_path"]
        self.main_kind = row["kind"]
        if row["kind"] == "bible":
            self.stack.setCurrentWidget(self.bible)
            self.bible.load_module(row)
            return
        old = self._library
        self._library = LibraryView(self.ctx, row, initial_ref=ref,
                                    ref_bible_rel=self._ref_bible_rel or "")
        self._library.open_reference.connect(self.reference_requested)
        self._library.ref_bible_changed.connect(self.set_ref_bible_rel)
        self.stack.addWidget(self._library)
        self.stack.setCurrentWidget(self._library)
        # Propagate the reference Bible to the bubble resolver from workspace
        # startup (state restoration or initial load).
        self.set_ref_bible_rel(self._ref_bible_rel)
        if old is not None:
            self.stack.removeWidget(old)
            old.deleteLater()

    def is_bible(self) -> bool:
        return self.main_kind == "bible"

    # ── state ────────────────────────────────────────────────────────────
    def state(self) -> dict:
        data = {
            "name": self.name,
            "color": self.color,
            "name_auto": self.name_auto,
            "auto_letter": self.auto_letter,
            "main_rel": self.main_rel,
        }
        if self.is_bible():
            data.update({
                "parallel": self.bible.is_parallel(),
                "parallel_rel": self.bible.parallel_rel(),
                "commentary": self.bible.is_commentary(),
                "commentary_rel": self.bible.commentary_rel(),
                "split": list(self.bible.split_sizes()),
            })
        else:
            data["ref_bible_rel"] = self._ref_bible_rel
        return data

    def apply_state(self, data: dict) -> None:
        if not data:
            return
        self.name = data.get("name") or self.name
        self.color = data.get("color") or self.color
        auto = data.get("name_auto")
        letter = data.get("auto_letter") or ""
        if auto is None:
            match = re.match(r"^(?:Pestaña|Espacio|Tab|Workspace)\s+([A-Z])$", self.name)
            auto = bool(match)
            letter = match.group(1) if match else letter
        self.name_auto = bool(auto)
        self.auto_letter = letter
        if self.name_auto and self.auto_letter:
            self.name = tr("workspace.default_name", letter=self.auto_letter)
        # Restore the reference Bible before loading the module
        self._ref_bible_rel = data.get("ref_bible_rel") or ""
        rel = data.get("main_rel") or ""
        row = self.ctx.catalog.by_rel_path(rel) if rel else None
        if row is None:
            row = self.ctx.catalog.by_rel_path(self.settings.bible_module)
        if row is None:
            bibles = self.ctx.bibles()
            row = bibles[0] if bibles else None
        self.set_main(row)
        if self.is_bible():
            if data.get("commentary_rel"):
                self.bible.set_commentary_rel(data["commentary_rel"])
            if data.get("parallel_rel"):
                self.bible.set_parallel_rel(data["parallel_rel"])
            self.bible.set_commentary(bool(data.get("commentary", True)))
            self.bible.set_parallel(bool(data.get("parallel", False)))
            split = data.get("split")
            if isinstance(split, (list, tuple)) and len(split) == 2:
                self.bible.set_split_sizes((int(split[0]), int(split[1])))

    # ── theme ────────────────────────────────────────────────────────────
    def reload_theme(self) -> None:
        self.bible.reload_theme()
        if self._library is not None:
            self._library.reload_theme()

    def retranslate(self) -> None:
        if self.name_auto and self.auto_letter:
            self.name = tr("workspace.default_name", letter=self.auto_letter)
        self.bible.retranslate()
        if self._library is not None:
            self._library.retranslate()

    def label(self) -> str:
        return self.name

