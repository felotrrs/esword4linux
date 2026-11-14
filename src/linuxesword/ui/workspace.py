"""Workspace: una pestaña-vista con su propio recurso principal.

Una pestaña agrupa un recurso principal. Si es una biblia, incluye su propia
biblia paralela y su propio panel de comentario. Si no es biblia, muestra el
visor del módulo y ofrece un selector de biblia de referencia para burbujas y
apertura de citas desde esa obra.
"""

from __future__ import annotations

import re

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget

from ..core.context import AppContext
from ..i18n import tr
from .bible_view import BiblePane, fill_bible_combo
from .library_view import LibraryView
from .rich_browser import RichBrowser


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
        # Biblia de referencia independiente para workspaces no-biblia
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

    # ── biblia de referencia para workspaces no-biblia ───────────────────
    def ref_bible_rel(self) -> str:
        """Ruta relativa de la biblia de referencia de este workspace."""
        return self._ref_bible_rel

    def set_ref_bible_rel(self, rel: str) -> None:
        """Establece la biblia de referencia de este workspace (independiente)."""
        rel = rel or ""
        self._ref_bible_rel = rel
        if self._library is not None:
            self._library.set_reference_bible(self._ref_bible_rel)
        # Notificar al resolvedor de burbujas para que las citas de esta obra
        # se resuelvan con la traducción elegida en este workspace.
        if rel:
            self.ctx.refs.set_bible(rel)
            RichBrowser.clear_all_caches()

    # ── recurso principal ────────────────────────────────────────────────
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
                                    ref_bible_rel=self._ref_bible_rel
                                    or self.settings.reference_bible or "")
        self._library.open_reference.connect(self.reference_requested)
        self._library.ref_bible_changed.connect(self.set_ref_bible_rel)
        self.stack.addWidget(self._library)
        self.stack.setCurrentWidget(self._library)
        # Propagar la biblia de referencia al resolvedor de burbujas desde el
        # arranque del workspace (restauración de estado o carga inicial).
        self.set_ref_bible_rel(self._ref_bible_rel)
        if old is not None:
            self.stack.removeWidget(old)
            old.deleteLater()

    def is_bible(self) -> bool:
        return self.main_kind == "bible"

    # ── estado ───────────────────────────────────────────────────────────
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
        # Restaurar biblia de referencia antes de cargar el módulo
        self._ref_bible_rel = data.get("ref_bible_rel") or ""
        rel = data.get("main_rel") or ""
        row = self.ctx.catalog.by_rel_path(rel) if rel else None
        if row is None:
            row = self.ctx.catalog.by_rel_path(self.settings.bible_module)
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

    # ── tema ─────────────────────────────────────────────────────────────
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

