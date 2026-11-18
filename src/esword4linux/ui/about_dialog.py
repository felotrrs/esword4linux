"""About dialog with the application and third-party licensing notices."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QLabel, QVBoxLayout,
)

from ..config import asset
from ..i18n import tr


class AboutDialog(QDialog):
    """Show version, GPL notice and the Qt/PySide6 LGPL notice."""

    def __init__(self, version: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("dialog.about.title"))
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(12)

        icon = QLabel(self)
        icon.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        pixmap = QPixmap(str(asset("esword4linux-about.png")))
        if not pixmap.isNull():
            icon.setPixmap(
                pixmap.scaled(
                    160, 160,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        layout.addWidget(icon)

        text = QLabel(tr("dialog.about.text", version=version), self)
        text.setTextFormat(Qt.TextFormat.RichText)
        text.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        text.setOpenExternalLinks(True)
        text.setWordWrap(True)
        text.setMinimumWidth(620)
        text.setMaximumWidth(700)
        layout.addWidget(text)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close, parent=self
        )
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.adjustSize()
