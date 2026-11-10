"""Workers de Qt para no bloquear la UI (escaneo e indexación)."""

from __future__ import annotations

import traceback

from PySide6.QtCore import QThread, Signal


class Worker(QThread):
    """Ejecuta una función en segundo plano y reenvía su progreso."""

    progress = Signal(int, int, str)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:  # noqa: D401
        try:
            result = self._fn(self._emit)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self.failed.emit(str(exc))
            return
        self.done.emit(result)

    def _emit(self, done: int, total: int, label: str = "") -> None:
        self.progress.emit(int(done), int(total), str(label))
