"""Preferencias de tipografía: interfaz, Escritura y texto corriente.

Una sola fuente de verdad: los campos de `Settings`. Al aceptar, la ventana
principal reconstruye la hoja de estilo Qt y el CSS de los visores.
"""

from __future__ import annotations

import html as _html

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFontComboBox, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QSpinBox, QTextBrowser, QVBoxLayout, QWidget,
)

from ..config import Settings
from ..core.context import AppContext
from ..i18n import tr
from .theme import document_css, palette


class PreferencesDialog(QDialog):
    """Suite de fuentes y tamaños para cada rol de texto."""

    def __init__(self, ctx: AppContext, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.settings = ctx.settings
        self.setWindowTitle(tr("prefs.title"))
        self.resize(720, 700)
        self._build_ui()
        self._load(self.settings)
        self._update_preview()

    # ── UI ───────────────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(10)

        intro = QLabel(tr("prefs.intro"))
        intro.setWordWrap(True)
        intro.setObjectName("appSubtitle")
        layout.addWidget(intro)

        self.ui_family, self.ui_size = self._font_group(
            layout, "prefs.ui", "prefs.ui_help", 8, 24
        )
        self.reading_family, self.reading_size = self._font_group(
            layout, "prefs.reading", "prefs.reading_help", 10, 40
        )
        self.content_family, self.content_size = self._font_group(
            layout, "prefs.content", "prefs.content_help", 9, 36
        )

        preview_box = QGroupBox(tr("prefs.preview"))
        preview_layout = QVBoxLayout(preview_box)
        preview_layout.setContentsMargins(12, 8, 12, 10)
        preview_layout.setSpacing(6)

        self.ui_sample = QLabel(tr("prefs.preview.ui"))
        preview_layout.addWidget(self.ui_sample)

        self.preview = QTextBrowser()
        self.preview.setOpenLinks(False)
        self.preview.setMinimumHeight(190)
        preview_layout.addWidget(self.preview, 1)
        layout.addWidget(preview_box, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.RestoreDefaults
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Ok
        )
        buttons.button(
            QDialogButtonBox.StandardButton.RestoreDefaults
        ).setText(tr("prefs.restore"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(
            tr("common.cancel")
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            tr("prefs.save")
        )
        buttons.button(
            QDialogButtonBox.StandardButton.RestoreDefaults
        ).clicked.connect(self._restore_defaults)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self._accept)
        layout.addWidget(buttons)

    def _font_group(self, layout: QVBoxLayout, title: str, help_key: str,
                    minimum: int, maximum: int) -> tuple[QFontComboBox, QSpinBox]:
        box = QGroupBox(tr(title))
        box.setToolTip(tr(help_key))
        grid = QGridLayout(box)
        grid.setContentsMargins(12, 8, 12, 10)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)

        family = QFontComboBox()
        family.setToolTip(tr(help_key))
        family.currentFontChanged.connect(lambda _f: self._update_preview())
        grid.addWidget(QLabel(tr("prefs.family")), 0, 0)
        grid.addWidget(family, 0, 1)

        size = QSpinBox()
        size.setRange(minimum, maximum)
        size.setSuffix(" px")
        size.setToolTip(tr(help_key))
        size.valueChanged.connect(lambda _v: self._update_preview())
        grid.addWidget(QLabel(tr("prefs.size")), 1, 0)
        h = QWidget()
        row = QHBoxLayout(h)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(size)
        row.addStretch(1)
        grid.addWidget(h, 1, 1)
        grid.setColumnStretch(1, 1)

        layout.addWidget(box)
        return family, size

    # ── valores ──────────────────────────────────────────────────────────
    @staticmethod
    def _family(combo: QFontComboBox) -> str:
        family = combo.currentFont().family().strip()
        if not family:
            family = combo.currentText().strip()
        return family or "Noto Sans"

    def _load(self, values) -> None:
        for combo, name in (
            (self.ui_family, values.ui_font_family),
            (self.reading_family, values.font_family),
            (self.content_family, values.content_font_family),
        ):
            combo.setCurrentFont(QFont(name))
        self.ui_size.setValue(int(values.ui_font_size))
        self.reading_size.setValue(int(values.font_size))
        self.content_size.setValue(int(values.content_font_size))

    def _accept(self) -> None:
        self.settings.ui_font_family = self._family(self.ui_family)
        self.settings.ui_font_size = self.ui_size.value()
        self.settings.font_family = self._family(self.reading_family)
        self.settings.font_size = self.reading_size.value()
        self.settings.content_font_family = self._family(self.content_family)
        self.settings.content_font_size = self.content_size.value()
        self.settings.save()
        self.accept()

    def _restore_defaults(self) -> None:
        values = Settings()
        self._load(values)
        self._update_preview()

    # ── vista previa ─────────────────────────────────────────────────────
    def _update_preview(self) -> None:
        if not hasattr(self, "preview"):
            return
        family = self._family(self.ui_family)
        self.ui_sample.setStyleSheet(
            f'font-family: "{family}"; font-size: {self.ui_size.value()}px;'
        )
        css = document_css(
            self.settings.theme,
            self.reading_size.value(),
            self._family(self.reading_family),
            content_family=self._family(self.content_family),
            content_size=self.content_size.value(),
        )
        self.preview.document().setDefaultStyleSheet(css)
        pal = palette(self.settings.theme)
        self.preview.setHtml(
            f"<style>{css}</style>"
            f'<div class="chapter-title">{_html.escape(tr("prefs.sample.title"))}</div>'
            f'<p class="verse scripture">'
            f'<a class="vnum" href="v:1" style="color:{pal.verse_num};'
            f'text-decoration:none;"><b>1</b></a>&nbsp;'
            f'{_html.escape(tr("prefs.sample.verse"))}</p>'
            f'<p class="verse scripture">'
            f'<a class="vnum" href="v:2" style="color:{pal.verse_num};'
            f'text-decoration:none;"><b>2</b></a>&nbsp;'
            f'{_html.escape(tr("prefs.sample.verse2"))}</p>'
            f'<div class="comment"><span class="ctag">'
            f'{_html.escape(tr("prefs.sample.tag"))}</span><br>'
            f'{_html.escape(tr("prefs.sample.comment"))}</div>'
            f'<div class="entry-title">{_html.escape(tr("prefs.sample.entry"))}</div>'
            f'<div>{_html.escape(tr("prefs.sample.body"))}</div>'
        )
