"""First-run dialog: choose the folder that contains the user's modules."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..config import asset
from ..core.catalog import EXCLUDED_DIRS
from ..core.esword.module import ESWORD_EXTS
from ..i18n import tr

# Locale/heading files are part of e-Sword but not study modules.
_NON_CONTENT_EXTS = {".lanx", ".en", ".es", ".fr", ".pt"}
_CONTENT_EXTS = ESWORD_EXTS - _NON_CONTENT_EXTS


def count_modules(root: Path) -> int:
    """Count e-Sword study modules below *root* without opening them."""
    total = 0
    try:
        for current, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
            total += sum(
                1 for name in files if Path(name).suffix.lower() in _CONTENT_EXTS
            )
    except OSError:
        return 0
    return total


class FirstRunDialog(QDialog):
    """Ask for the modules folder before the main window is created."""

    def __init__(self, parent: QWidget | None = None, initial: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("first_run.title"))
        self.setModal(True)
        self.setMinimumWidth(620)
        icon = asset("esword4linux.png")
        if icon.is_file():
            self.setWindowIcon(QIcon(str(icon)))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 16)
        layout.setSpacing(12)

        title = QLabel(tr("first_run.title"))
        title.setObjectName("appTitle")
        layout.addWidget(title)

        intro = QLabel(tr("first_run.intro"))
        intro.setWordWrap(True)
        intro.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(intro)

        if initial and not Path(initial).expanduser().is_dir():
            missing = QLabel(tr("first_run.missing"))
            missing.setWordWrap(True)
            missing.setObjectName("errorText")
            layout.addWidget(missing)

        folder_label = QLabel(tr("first_run.folder"))
        layout.addWidget(folder_label)

        row = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        self.path_edit.setPlaceholderText(tr("first_run.folder_placeholder"))
        row.addWidget(self.path_edit, 1)

        self.browse_btn = QPushButton(tr("first_run.browse"))
        self.browse_btn.clicked.connect(self._browse)
        row.addWidget(self.browse_btn)
        layout.addLayout(row)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setObjectName("appSubtitle")
        layout.addWidget(self.status)

        self.buttons = QDialogButtonBox(self)
        self.quit_btn = self.buttons.addButton(
            tr("first_run.quit"), QDialogButtonBox.ButtonRole.RejectRole
        )
        self.continue_btn = self.buttons.addButton(
            tr("first_run.continue"), QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.continue_btn.setEnabled(False)
        self.buttons.rejected.connect(self.reject)
        self.buttons.accepted.connect(self.accept)
        layout.addWidget(self.buttons)

        self._path = ""
        if initial and Path(initial).expanduser().is_dir():
            self._set_path(initial)

    # ── selection ───────────────────────────────────────────────────────
    def _browse(self) -> None:
        start = self._path or str(Path.home())
        folder = QFileDialog.getExistingDirectory(
            self, tr("first_run.folder_dialog"), start
        )
        if folder:
            self._set_path(folder)

    def _set_path(self, folder: str) -> None:
        root = Path(folder).expanduser()
        found = count_modules(root)
        if not found:
            QMessageBox.warning(
                self, tr("first_run.title"), tr("first_run.no_modules")
            )
            self._path = ""
            self.path_edit.clear()
            self.status.setText(tr("first_run.no_modules"))
            self.continue_btn.setEnabled(False)
            return
        self._path = str(root)
        self.path_edit.setText(str(root))
        self.status.setText(tr("first_run.found", n=found))
        self.continue_btn.setEnabled(True)

    def selected_path(self) -> str:
        return self._path
