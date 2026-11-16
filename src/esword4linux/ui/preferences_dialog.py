"""Appearance and language preferences.

Single source of truth: the `Settings` fields. On accept, the main window
applies the theme, language and typography live.
"""

from __future__ import annotations

import html as _html

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QSpinBox, QTabWidget, QTextBrowser, QVBoxLayout,
    QWidget,
)

from .. import i18n
from ..config import Settings
from ..core.context import AppContext
from ..i18n import tr
from .theme import document_css, palette

LANGUAGE_NAMES = {"es": "Español", "en": "English"}


class PreferencesDialog(QDialog):
    """Appearance (theme and typography) and UI language suite."""

    def __init__(self, ctx: AppContext, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.settings = ctx.settings
        self.setWindowTitle(tr("prefs.title"))
        self.resize(760, 720)
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

        self.tabs = QTabWidget()
        self.tabs.addTab(self._appearance_tab(), tr("prefs.tab.appearance"))
        self.tabs.addTab(self._language_tab(), tr("prefs.tab.language"))
        layout.addWidget(self.tabs, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.RestoreDefaults
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Ok
        )
        restore = buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults)
        restore.setText(tr("prefs.restore"))
        restore.clicked.connect(self._restore_defaults)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(
            tr("common.cancel")
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            tr("prefs.save")
        )
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self._accept)
        layout.addWidget(buttons)

    def _appearance_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(6, 10, 6, 6)
        layout.setSpacing(10)

        theme_box = QGroupBox(tr("prefs.theme"))
        theme_box.setToolTip(tr("prefs.theme_help"))
        theme_row = QHBoxLayout(theme_box)
        theme_row.setContentsMargins(12, 8, 12, 10)
        self.theme = QComboBox()
        self.theme.setToolTip(tr("prefs.theme_help"))
        self.theme.addItem(tr("prefs.theme_light"), "light")
        self.theme.addItem(tr("prefs.theme_dark"), "dark")
        self.theme.currentIndexChanged.connect(lambda _i: self._update_preview())
        theme_row.addWidget(self.theme, 1)
        layout.addWidget(theme_box)

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
        return page

    def _language_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(6, 10, 6, 6)
        layout.setSpacing(10)

        box = QGroupBox(tr("prefs.language"))
        box.setToolTip(tr("prefs.language_help"))
        grid = QGridLayout(box)
        grid.setContentsMargins(12, 8, 12, 10)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)

        self.language = QComboBox()
        self.language.setToolTip(tr("prefs.language_help"))
        for code in i18n.available():
            self.language.addItem(LANGUAGE_NAMES.get(code, code), code)
        grid.addWidget(self.language, 0, 0)
        grid.setColumnStretch(0, 1)
        layout.addWidget(box)

        note = QLabel(tr("prefs.language_note"))
        note.setWordWrap(True)
        note.setObjectName("appSubtitle")
        layout.addWidget(note)
        layout.addStretch(1)
        return page

    def _font_group(self, layout: QVBoxLayout, title: str, help_key: str,
                    minimum: int, maximum: int) -> tuple[QComboBox, QSpinBox]:
        box = QGroupBox(tr(title))
        box.setToolTip(tr(help_key))
        grid = QGridLayout(box)
        grid.setContentsMargins(12, 8, 12, 10)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)

        family = QComboBox()
        family.setEditable(False)
        family.setMaxVisibleItems(20)
        family.setMinimumContentsLength(24)
        family.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        family.setToolTip(tr(help_key))
        family.addItems(sorted(QFontDatabase.families(), key=str.casefold))
        family.currentIndexChanged.connect(lambda _i: self._update_preview())
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

    # ── values ───────────────────────────────────────────────────────────
    @staticmethod
    def _family(combo: QComboBox) -> str:
        return combo.currentText().strip() or "Noto Sans"

    @staticmethod
    def _select_text(combo: QComboBox, text: str) -> None:
        idx = combo.findText(text)
        if idx < 0:
            for i in range(combo.count()):
                if combo.itemText(i).casefold() == text.casefold():
                    idx = i
                    break
        if idx < 0:
            combo.addItem(text)
            idx = combo.count() - 1
        combo.setCurrentIndex(idx)

    @staticmethod
    def _select_data(combo: QComboBox, data: str) -> None:
        idx = combo.findData(data)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _load(self, values) -> None:
        self._select_data(self.theme, values.theme)
        self._select_data(self.language, values.locale)
        for combo, name in (
            (self.ui_family, values.ui_font_family),
            (self.reading_family, values.font_family),
            (self.content_family, values.content_font_family),
        ):
            self._select_text(combo, name)
        self.ui_size.setValue(int(values.ui_font_size))
        self.reading_size.setValue(int(values.font_size))
        self.content_size.setValue(int(values.content_font_size))

    def _accept(self) -> None:
        self.settings.theme = self.theme.currentData() or "light"
        self.settings.locale = self.language.currentData() or "es"
        self.settings.ui_font_family = self._family(self.ui_family)
        self.settings.ui_font_size = self.ui_size.value()
        self.settings.font_family = self._family(self.reading_family)
        self.settings.font_size = self.reading_size.value()
        self.settings.content_font_family = self._family(self.content_family)
        self.settings.content_font_size = self.content_size.value()
        self.settings.save()
        self.accept()

    def _restore_defaults(self) -> None:
        self._load(Settings())
        self._update_preview()

    # ── preview ──────────────────────────────────────────────────────────
    def _update_preview(self) -> None:
        if not hasattr(self, "preview"):
            return
        family = self._family(self.ui_family)
        self.ui_sample.setStyleSheet(
            f'font-family: "{family}"; font-size: {self.ui_size.value()}px;'
        )
        theme = self.theme.currentData() or self.settings.theme
        css = document_css(
            theme,
            self.reading_size.value(),
            self._family(self.reading_family),
            content_family=self._family(self.content_family),
            content_size=self.content_size.value(),
        )
        self.preview.document().setDefaultStyleSheet(css)
        pal = palette(theme)
        # The preview must simulate the real background of the chosen theme,
        # not the one the window currently has.
        self.preview.setStyleSheet(
            f"QTextBrowser {{ background: {pal.bg}; color: {pal.text};"
            f" border: 1px solid {pal.border}; padding: 8px 12px; }}"
        )
        self.preview.setHtml(
            f"<style>{css}</style>"
            f'<div class="chapter-title">{_html.escape(tr("prefs.sample.title"))}</div>'
            f'<p class="verse scripture">'
            f'<a class="vnum" href="v:1" style="text-decoration:none;">'
            f'<font color="{pal.verse_num}"><b>1</b></font></a>&nbsp;'
            f'{_html.escape(tr("prefs.sample.verse"))}</p>'
            f'<p class="verse scripture">'
            f'<a class="vnum" href="v:2" style="text-decoration:none;">'
            f'<font color="{pal.verse_num}"><b>2</b></font></a>&nbsp;'
            f'{_html.escape(tr("prefs.sample.verse2"))}</p>'
            f'<div class="comment"><span class="ctag">'
            f'{_html.escape(tr("prefs.sample.tag"))}</span><br>'
            f'{_html.escape(tr("prefs.sample.comment"))}</div>'
            f'<div class="entry-title">{_html.escape(tr("prefs.sample.entry"))}</div>'
            f'<div>{_html.escape(tr("prefs.sample.body"))}</div>'
        )
