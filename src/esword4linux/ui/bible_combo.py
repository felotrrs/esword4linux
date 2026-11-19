"""Combo helpers shared by the Bible view and the comparison headers."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import (
    QFont, QPalette, QPainter, QPolygon, QStandardItem, QStandardItemModel,
)
from PySide6.QtWidgets import (
    QComboBox, QCompleter, QStyle, QStyleOptionComboBox,
)

from .language import language_label, language_sort_key


class BibleComboBox(QComboBox):
    """Editable combo with a clearly visible hand-drawn dropdown arrow."""

    def sizeHint(self):  # noqa: N802
        """Width for the **current caption**, not for the widest item.

        ``AdjustToContents`` would measure every installed translation (there
        can be hundreds) and the header cell would look like an empty box.
        """
        hint = super().sizeHint()
        text = self.currentText().strip()
        if not text and self.lineEdit() is not None:
            text = self.lineEdit().placeholderText().strip()
        if text:
            arrow = max(30, self.style().pixelMetric(
                QStyle.PixelMetric.PM_ScrollBarExtent))
            hint.setWidth(self.fontMetrics().horizontalAdvance(text) + arrow + 14)
        return hint

    def minimumSizeHint(self):  # noqa: N802
        """Allow the caption to shrink; ``minimumContentsLength`` would not."""
        hint = super().minimumSizeHint()
        hint.setWidth(60)
        return hint

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        arrow = self.style().subControlRect(
            QStyle.ComplexControl.CC_ComboBox,
            option,
            QStyle.SubControl.SC_ComboBoxArrow,
            self,
        )
        if not arrow.isValid():
            return
        size = max(6, min(10, arrow.width() - 7))
        cx, cy = arrow.center().x(), arrow.center().y()
        color = self.palette().color(
            QPalette.ColorRole.Text if self.isEnabled()
            else QPalette.ColorRole.Mid
        )
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(QPolygon([
            QPoint(int(cx - size / 2), int(cy - size / 4)),
            QPoint(int(cx + size / 2), int(cy - size / 4)),
            QPoint(int(cx), int(cy + size / 2)),
        ]))
        painter.end()


def fill_bible_combo(combo: QComboBox, bibles: list[dict], current_rel: str,
                     *, editable: bool = True) -> None:
    """Fill a Bible combo grouped by language (optionally editable)."""
    combo.blockSignals(True)
    model = QStandardItemModel(combo)
    grouped: dict[str, list[dict]] = {}
    for mod in bibles:
        grouped.setdefault(mod.get("language") or "und", []).append(mod)

    first_selectable = -1
    for code in sorted(grouped, key=language_sort_key):
        items = grouped[code]
        header = QStandardItem(f"— {language_label(code)} ({len(items)}) —")
        header.setEnabled(False)
        header.setSelectable(False)
        header.setData(None, Qt.UserRole)
        font = header.font()
        font.setBold(True)
        header.setFont(font)
        model.appendRow(header)
        for mod in sorted(
            items,
            key=lambda m: ((m.get("abbreviation") or "").lower(),
                           (m.get("title") or "").lower()),
        ):
            label = (
                f"{mod['abbreviation']} — {mod['title']}"
                if mod.get("abbreviation") else (mod.get("title") or "")
            )
            item = QStandardItem(label[:110])
            item.setData(mod["rel_path"], Qt.UserRole)
            # The combo's own caption is bold, and a QComboBox popup inherits
            # that font. A long list reads better in normal weight, so each
            # entry carries its own font; the language headings stay bold.
            font = item.font()
            font.setWeight(QFont.Weight.Normal)
            item.setFont(font)
            item.setToolTip(
                f"{mod.get('title') or ''}\n{language_label(code)}"
            )
            model.appendRow(item)
            if first_selectable < 0:
                first_selectable = model.rowCount() - 1

    combo.setModel(model)
    combo.setEditable(editable)
    combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
    combo.setMaxVisibleItems(20)
    combo.setSizeAdjustPolicy(
        QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
    )
    combo.setMinimumContentsLength(18)
    combo.setMaximumWidth(320)
    if editable:
        completer = QCompleter(model, combo)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        combo.setCompleter(completer)
    idx = combo.findData(current_rel)
    if idx < 0:
        idx = first_selectable
    if idx >= 0:
        combo.setCurrentIndex(idx)
    if editable and combo.lineEdit() is not None:
        # With a long title, QLineEdit leaves the cursor at the end and it
        # looks as if the translation starts with "...titles, notes...".
        combo.lineEdit().setCursorPosition(0)
    combo.blockSignals(False)

