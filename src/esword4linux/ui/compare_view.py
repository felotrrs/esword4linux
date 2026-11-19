"""Multi-version comparison table for the Bible workspace.

The pure alignment lives in :mod:`esword4linux.core.compare`; the data access
lives in :mod:`esword4linux.core.compare_reader`.

The header is not a decorative strip: it is the **column model** of the table.
:func:`column_metrics` is the single source of truth for the pixel width of
every column, and both sides consume it, so a native header cell always sits
exactly over its HTML column — with one version or with twenty, with or without
a scrollbar. The header lives in a clipping host and follows the table's
horizontal scroll, because keeping the two decoupled is what made the old
header drift out of place.

Headers are native widgets so changing a translation, typing and removing a
column do not depend on nested popups; the body stays a sanitized HTML table
inside :class:`RichBrowser`, which keeps the Strong/reference bubbles and the
``cmp-verse:`` anchors working.
"""

from __future__ import annotations

import html as _html
import re
from dataclasses import dataclass

from PySide6.QtCore import QEvent, QRect, QTimer, Qt, Signal
from PySide6.QtGui import QGuiApplication, QTextLength, QTextTable
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QSizePolicy, QToolButton,
    QVBoxLayout, QWidget,
)

from ..core.books import book_name
from ..core.compare import CellStatus, ColumnStatus, CompareCell
from ..core.compare_reader import CompareBuild, CompareSource
from ..core.text import to_rich
from ..i18n import tr
from .bible_combo import BibleComboBox, fill_bible_combo
from .language import language_label
from .rich_browser import RichBrowser
from .theme import document_css_for, palette

__all__ = [
    "BibleColumnHeader",
    "ColumnMetrics",
    "CompareView",
    "column_metrics",
]

#: Pixel width of the verse-number column, shared by the header and the body.
VERSE_COL_WIDTH = 46
#: Readability floor for one translation column. Below it the table scrolls.
MIN_VERSION_WIDTH = 200
#: Left inset of a header cell. The body cell starts its text at
#: ``border + 5 px`` of padding, so the caption needs ``3 + border + 3`` to
#: land on the same pixel column.
CELL_PAD = 3

#: Qt's "no maximum" sentinel, spelled out so the intent is obvious.
QWIDGETSIZE_MAX = 16777215

#: A collapsed table border is drawn half outside each outer edge, so the
#: document is two pixels wider than the sum of the column widths. Reserving
#: them keeps a spurious horizontal scrollbar from appearing.
BORDER_SLACK = 2

_HEADING_START = re.compile(
    r"^(?:\s*<br\s*/?>\s*){2,}<b>(.*?)</b>(?:\s*<br\s*/?>\s*)*",
    re.I | re.S,
)
_HEADING_END = re.compile(
    r"(?:\s*<br\s*/?>\s*){2,}<b>(.*?)</b>(?:\s*<br\s*/?>\s*)*$",
    re.I | re.S,
)


@dataclass(frozen=True)
class ColumnMetrics:
    """Pixel geometry shared by the native header and the HTML table."""

    widths: tuple[int, ...]
    total: int


def column_metrics(usable: int, versions: int) -> ColumnMetrics:
    """Column widths in pixels for ``versions`` translation columns.

    The verse column is fixed and the translation columns share the remaining
    space; the last one absorbs the rounding remainder so the total is exact
    and no scrollbar appears for a one-pixel rounding error. When the result
    does not fit, ``total`` is wider than ``usable`` and the table scrolls
    horizontally instead of squeezing the text below readability.
    """
    versions = max(1, int(versions))
    usable = max(1, int(usable))
    minimum = VERSE_COL_WIDTH + versions * MIN_VERSION_WIDTH
    total = max(usable, minimum)
    remaining = total - VERSE_COL_WIDTH
    base = remaining // versions
    widths = [VERSE_COL_WIDTH] + [base] * versions
    widths[-1] += remaining - base * versions
    return ColumnMetrics(tuple(widths), total)


def _format_headings(html: str) -> str:
    """Separate centered RTF headings embedded in a verse row."""
    prefix = suffix = ""
    match = _HEADING_START.match(html)
    if match:
        prefix = f'<div class="cmp-heading">{match.group(1)}</div>'
        html = html[match.end():]
    match = _HEADING_END.search(html)
    if match:
        suffix = f'<div class="cmp-heading">{match.group(1)}</div>'
        html = html[:match.start()]
    return prefix + html + suffix


def _short_label(row: dict) -> str:
    """Compact header caption: the abbreviation is what a header needs."""
    return (row.get("abbreviation") or row.get("title") or "")[:110]


def _full_label(row: dict) -> str:
    """Label used inside the dropdown, matching ``fill_bible_combo``."""
    title = row.get("title") or ""
    abbreviation = row.get("abbreviation") or ""
    return (f"{abbreviation} — {title}" if abbreviation else title)[:110]


def _combo_rel(combo: QComboBox, bibles: list[dict]) -> str:
    """Return a rel_path only for an exact installed item or typed name."""
    by_rel = {mod["rel_path"]: mod for mod in bibles}

    rel = combo.currentData()
    text = combo.currentText().strip()
    if rel in by_rel:
        row = by_rel[rel]
        if text in {_short_label(row), _full_label(row)}:
            return rel

    if not text:
        return ""
    needle = text.casefold()
    for rel_path, row in by_rel.items():
        names = {
            _short_label(row).casefold(),
            _full_label(row).casefold(),
            (row.get("title") or "").casefold(),
            (row.get("abbreviation") or "").casefold(),
        }
        if needle in names:
            return rel_path
    return ""


class BibleColumnHeader(QWidget):
    """Editable translation cell of the comparison header.

    Visually it is a table-header caption (flat, bold, left aligned); it turns
    into a field only on hover or focus. The closed caption shows the short
    abbreviation, while the dropdown keeps the full ``ABBR — Title`` so the
    list stays informative.
    """

    changed = Signal(int, str)
    remove_requested = Signal(int)

    def __init__(self, index: int, bibles: list[dict], current_rel: str,
                 *, status: ColumnStatus | None = None,
                 theme: str = "light", parent=None):
        super().__init__(parent)
        self.index = index
        self._bibles = list(bibles)
        self._current_rel = current_rel
        self._theme_name = theme

        self.setObjectName("cmpColumnHead")
        self.setMinimumWidth(0)
        self.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )

        row = QHBoxLayout(self)
        row.setContentsMargins(CELL_PAD, 3, 4, 3)
        row.setSpacing(2)

        self.combo = BibleComboBox()
        self.combo.setObjectName("cmpCombo")
        self.combo.setEditable(True)
        self.combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        fill_bible_combo(self.combo, self._bibles, current_rel, editable=True)
        # `fill_bible_combo` caps the combo for toolbar use; a header cell owns
        # its whole column so the caption and the caret belong to it.
        self.combo.setMaximumWidth(QWIDGETSIZE_MAX)
        self.combo.setMinimumWidth(60)
        self.combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        # A combo's popup is as wide as the combo, so a 200 px column would
        # truncate every translation name. `setMinimumWidth` on the view is
        # independent of the combo and survives the model reset of every
        # render.
        self.combo.view().setMinimumWidth(self._popup_width())
        self.combo.setToolTip(tr("compare.choose_version_help"))
        self.combo.activated.connect(self._on_activated)
        if self.combo.lineEdit() is not None:
            self.combo.lineEdit().installEventFilter(self)
            self.combo.lineEdit().returnPressed.connect(self._on_text)
        if current_rel:
            self._show_caption()
        else:
            self.combo.setCurrentIndex(-1)
            self.combo.setEditText("")
            if self.combo.lineEdit() is not None:
                self.combo.lineEdit().setPlaceholderText(
                    tr("compare.choose_version")
                )
        row.addWidget(self.combo, 1)

        self.status = QLabel()
        self.status.setObjectName("cmpStatus")
        self.status.setFixedSize(8, 8)
        if status is not None and status is not ColumnStatus.PRESENT:
            self._set_status(status)
        else:
            self.status.hide()
        row.addWidget(self.status)

        self.close_button = QToolButton()
        self.close_button.setText("✕")
        self.close_button.setObjectName("cmpClose")
        self.close_button.setFixedWidth(18)
        self.close_button.setToolTip(tr("compare.remove_column"))
        self.close_button.clicked.connect(
            lambda: self.remove_requested.emit(self.index)
        )
        row.addWidget(self.close_button)

    # ── caption ──────────────────────────────────────────────────────────
    @staticmethod
    def _popup_width() -> int:
        """Readable width for the dropdown, independent of the column."""
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return 380
        available = screen.availableGeometry().width()
        return max(280, min(420, int(available * 0.45)))

    def _row_for(self, rel: str) -> dict | None:
        for mod in self._bibles:
            if mod["rel_path"] == rel:
                return mod
        return None

    def _show_caption(self) -> None:
        """Caption of the closed cell: the full label, elided if needed."""
        row = self._row_for(self._current_rel)
        if row is None:
            return
        self.combo.setEditText(_full_label(row))
        if self.combo.lineEdit() is not None:
            # Long titles leave the cursor at the end and it looks as if the
            # caption started with "...".
            self.combo.lineEdit().setCursorPosition(0)
        self.combo.updateGeometry()
        code = row.get("language") or ""
        tip = row.get("title") or row.get("rel_path") or ""
        if code:
            tip = f"{tip}\n{language_label(code)}"
        self.combo.setToolTip(tip)

    @staticmethod
    def _status_text(status: ColumnStatus) -> str:
        if status is ColumnStatus.MISSING_BOOK:
            return tr("compare.missing_book")
        if status is ColumnStatus.MISSING_CHAPTER:
            return tr("compare.missing_chapter")
        if status is ColumnStatus.EMPTY:
            return tr("compare.empty_column")
        return ""

    def _set_status(self, status: ColumnStatus) -> None:
        pal = palette(self._theme_name)
        color = (
            pal.muted if status is ColumnStatus.EMPTY else pal.error
        )
        self.status.setStyleSheet(
            f"background: {color}; border-radius: 4px;"
        )
        self.status.setToolTip(self._status_text(status))
        self.status.show()

    def selected_rel(self) -> str:
        return _combo_rel(self.combo, self._bibles)

    def _on_activated(self, index: int) -> None:
        rel = self.combo.itemData(index)
        if rel:
            self._current_rel = rel
            self._show_caption()
            self.changed.emit(self.index, rel)

    def _on_text(self) -> None:
        rel = self.selected_rel()
        if not rel:
            self._restore_current()
            return
        self._current_rel = rel
        self._show_caption()
        self.changed.emit(self.index, rel)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if (
            obj is self.combo.lineEdit()
            and event.type() == QEvent.Type.FocusOut
        ):
            rel = self.selected_rel()
            if rel:
                self._current_rel = rel
            # Whatever the user typed but did not confirm is discarded: the
            # caption always reflects the selected translation.
            self._show_caption()
        return super().eventFilter(obj, event)

    def _restore_current(self) -> None:
        if not self._current_rel:
            return
        idx = self.combo.findData(self._current_rel)
        if idx >= 0:
            self.combo.setCurrentIndex(idx)
        self._show_caption()

    def focus_combo(self) -> None:
        self.combo.setFocus()
        if self.combo.lineEdit() is not None:
            self.combo.lineEdit().selectAll()
        self.combo.showPopup()


class CompareView(QWidget):
    """Verse-aligned table with a header coupled to its columns."""

    remove_requested = Signal(int)
    verse_clicked = Signal(int)
    column_changed = Signal(int, str)
    add_requested = Signal()

    def __init__(self, settings, resolver=None, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._build: CompareBuild | None = None
        self._bibles: list[dict] = []
        self._draft = False
        self._draft_header: BibleColumnHeader | None = None
        self._metrics: ColumnMetrics | None = None
        self._header_height = 30
        self.header_widgets: list[QWidget] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── top strip: chapter name and the "add version" action ─────────
        # The two header bands are **free children**, not layout items: a
        # layout item with a fixed width turns that width into the minimum of
        # the whole view, and the viewport width depends on the view width, so
        # the view could never get narrower than itself (the window grew on
        # every sidebar toggle). `_place_bands()` positions them.
        self.top = QWidget(self)
        self.top.setObjectName("cmpTop")
        top = QHBoxLayout(self.top)
        top.setContentsMargins(12, 6, 12, 5)
        top.setSpacing(8)
        self.chapter_label = QLabel("")
        self.chapter_label.setObjectName("cmpChapter")
        top.addWidget(self.chapter_label)
        top.addStretch(1)
        self.add_button = QToolButton()
        self.add_button.setObjectName("cmpAdd")
        self.add_button.setText(self._add_label())
        self.add_button.setToolTip(tr("compare.add_version_help"))
        self.add_button.clicked.connect(self.add_requested)
        top.addWidget(self.add_button)

        # ── header strip: a clipping host for the scrolling column track ──
        self.header_host = QWidget(self)
        self.header_host.setObjectName("cmpHeader")
        self.header_track = QWidget(self.header_host)
        self.header_track.setObjectName("cmpHeaderTrack")
        self.header_row = QHBoxLayout(self.header_track)
        self.header_row.setContentsMargins(0, 0, 0, 0)
        self.header_row.setSpacing(0)

        # ── body ──────────────────────────────────────────────────────────
        self.browser = RichBrowser(resolver=resolver)
        self.browser.setObjectName("cmpBrowser")
        # No frame, no padding and no document margin: the table's left border
        # must land on the same pixel as the header's left border.
        self.browser.setFrameShape(QFrame.Shape.NoFrame)
        self.browser.setOpenLinks(False)
        self.browser.setOpenExternalLinks(False)
        self.browser.anchorClicked.connect(self._on_anchor)
        self.browser.document().setDocumentMargin(0)
        self.browser.document().setDefaultStyleSheet(
            document_css_for(self.settings)
        )
        self.browser.viewport().installEventFilter(self)
        self.browser.horizontalScrollBar().valueChanged.connect(
            self._sync_header_offset
        )
        layout.addWidget(self.browser, 1)
        self._place_bands()

    # ── API ──────────────────────────────────────────────────────────────
    def _add_label(self) -> str:
        return f"＋  {tr('compare.add_version')}"

    def begin_add(self) -> None:
        """Create a local draft header and focus its native combo."""
        self._draft = True
        self._render()
        # A new column always grows to the right: bring it into view *before*
        # focusing, otherwise the combo and its popup open off-screen.
        self._scroll_to_end()
        QTimer.singleShot(0, self._focus_draft)

    def _scroll_to_end(self) -> None:
        """Scroll to the right edge, where new columns appear."""
        bar = self.browser.horizontalScrollBar()
        bar.setValue(bar.maximum())

    def _focus_draft(self) -> None:
        self._scroll_to_end()
        if self._draft_header is not None:
            self._draft_header.focus_combo()

    def cancel_draft(self) -> None:
        if self._draft:
            self._draft = False
            self._render()

    def has_draft(self) -> bool:
        return self._draft

    def draft_index(self) -> int:
        table = self._build.table if self._build is not None else None
        return len(table.columns) if table is not None else 0

    def set_build(self, build: CompareBuild | None,
                  bibles: list[dict] | None = None) -> None:
        self._build = build
        if bibles is not None:
            self._bibles = list(bibles)
        self._render()

    def current_build(self) -> CompareBuild | None:
        return self._build

    def scroll_to_verse(self, verse: int) -> None:
        if verse:
            self.browser.scrollToAnchor(f"cv{verse}")

    def reload_theme(self) -> None:
        self._render()

    def retranslate(self) -> None:
        self.add_button.setText(self._add_label())
        self.add_button.setToolTip(tr("compare.add_version_help"))
        self._render()

    # ── events ───────────────────────────────────────────────────────────
    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._place_bands()
        self._sync_widths()

    def _place_bands(self) -> None:
        """Position the two header bands above the browser.

        They are free children so their width can follow the view without
        becoming the view's minimum width.
        """
        top_h = self.top.sizeHint().height()
        head_h = self._header_height if self.header_host.isVisible() else 0
        width = max(1, self.browser.viewport().width())
        self.top.setGeometry(0, 0, self.width(), top_h)
        self.header_host.setGeometry(0, top_h, width, head_h)
        margins = self.layout().contentsMargins()
        if margins.top() != top_h + head_h:
            self.layout().setContentsMargins(0, top_h + head_h, 0, 0)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        # The viewport also resizes when the vertical scrollbar appears, which
        # changes the usable width without resizing `CompareView`.
        if (
            obj is self.browser.viewport()
            and event.type() == QEvent.Type.Resize
        ):
            QTimer.singleShot(0, self._sync_widths)
        return super().eventFilter(obj, event)

    # ── rendering ────────────────────────────────────────────────────────
    def _render(self) -> None:
        self.browser.document().setDefaultStyleSheet(
            document_css_for(self.settings)
        )
        self.browser.setHtml(self._html())
        self._rebuild_header()
        self._sync_widths()
        self.browser.clear_cache()

    def _document_table(self) -> QTextTable | None:
        frames = self.browser.document().rootFrame().childFrames()
        return next(
            (frame for frame in frames if isinstance(frame, QTextTable)),
            None,
        )

    def _table_columns(self) -> int:
        table = self._build.table if self._build is not None else None
        return len(table.columns) if table is not None else 0

    def _sync_widths(self) -> None:
        """Apply the shared pixel geometry to the header and to the table."""
        columns = self._table_columns()
        if columns == 0 and not self._draft:
            self.header_host.setVisible(False)
            self._metrics = None
            self._place_bands()
            return

        versions = max(1, columns) + (1 if self._draft else 0)
        usable = max(1, self.browser.viewport().width() - BORDER_SLACK)
        metrics = column_metrics(usable, versions)
        self._metrics = metrics

        for widget, width in zip(self.header_widgets, metrics.widths):
            widget.setFixedWidth(width)

        heights = [w.sizeHint().height() for w in self.header_widgets]
        self._header_height = max([30] + heights)
        self.header_host.setVisible(True)
        self._place_bands()
        self._sync_header_offset()

        table = self._document_table()
        if table is None or table.columns() != len(metrics.widths):
            return
        fmt = table.format()
        current = [
            length.rawValue()
            for length in fmt.columnWidthConstraints()
        ]
        if (
            len(current) == len(metrics.widths)
            and all(abs(a - b) < 0.5
                    for a, b in zip(current, metrics.widths))
        ):
            return
        fmt.setColumnWidthConstraints([
            QTextLength(QTextLength.Type.FixedLength, float(width))
            for width in metrics.widths
        ])
        table.setFormat(fmt)

    def _sync_header_offset(self) -> None:
        """Follow the table's horizontal scroll, if any."""
        if self._metrics is None:
            return
        offset = self.browser.horizontalScrollBar().value()
        target = QRect(
            -offset, 0, self._metrics.total, self.header_host.height()
        )
        if self.header_track.geometry() != target:
            self.header_track.setGeometry(target)

    def _clear_header(self) -> None:
        while self.header_row.count():
            item = self.header_row.takeAt(0)
            widget = item.widget()
            if widget is not None:
                # `deleteLater` alone leaves the widget visible until the event
                # loop runs, so it would paint over the rebuilt header.
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        self.header_widgets = []
        self._draft_header = None

    def _rebuild_header(self) -> None:
        self._clear_header()
        table = self._build.table if self._build is not None else None
        columns = table.columns if table is not None else ()
        self.chapter_label.setText(
            f"{book_name(table.book, self.settings.locale)} {table.chapter}"
            if table is not None else ""
        )
        pal = palette(self.settings.theme)
        self.chapter_label.setStyleSheet(
            f'font-family: "{self.settings.font_family}", "Noto Serif", '
            f'Georgia, serif; font-size: {self.settings.font_size + 8}px; '
            f'font-weight: 700; color: {pal.accent};'
        )
        self.add_button.setEnabled(not self._draft)

        self.verse_header = QLabel(tr("compare.verse_short"))
        self.verse_header.setObjectName("cmpVerseHead")
        self.verse_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.header_row.addWidget(self.verse_header)
        self.header_widgets.append(self.verse_header)

        used = [state.column.key for state in columns]
        for index, state in enumerate(columns):
            if index == 0:
                label = QLabel(state.column.label)
                label.setObjectName("cmpMainHead")
                label.setMinimumWidth(0)
                label.setSizePolicy(
                    QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
                )
                label.setAlignment(
                    Qt.AlignmentFlag.AlignLeft
                    | Qt.AlignmentFlag.AlignVCenter
                )
                label.setToolTip(
                    f"{state.column.title or state.column.key}\n"
                    f"{tr('compare.main_column_hint')}"
                )
                self.header_row.addWidget(label)
                self.header_widgets.append(label)
                continue

            candidates = [
                mod for mod in self._bibles
                if mod["rel_path"] not in used
                or mod["rel_path"] == state.column.key
            ]
            header = BibleColumnHeader(
                index, candidates, state.column.key, status=state.status,
                theme=self.settings.theme,
            )
            header.changed.connect(self.column_changed)
            header.remove_requested.connect(self.remove_requested)
            self.header_row.addWidget(header)
            self.header_widgets.append(header)

        if self._draft:
            candidates = [
                mod for mod in self._bibles
                if mod["rel_path"] not in used
            ]
            # An empty `current_rel` is the draft: the combo shows its
            # placeholder until the user picks a translation.
            header = BibleColumnHeader(
                len(columns), candidates, "",
                theme=self.settings.theme,
            )
            header.changed.connect(self.column_changed)
            header.remove_requested.connect(self.remove_requested)
            self.header_row.addWidget(header)
            self.header_widgets.append(header)
            self._draft_header = header

        visible = bool(columns) or self._draft
        self.header_host.setVisible(visible)

    def _html(self) -> str:
        build = self._build
        table = build.table if build is not None else None
        if table is None or not table.columns:
            out = [f"<style>{document_css_for(self.settings)}</style>"]
            if build is not None and build.warnings:
                out.append(
                    f'<p class="muted cmp-warning">'
                    f'{tr("compare.some_columns_failed")}</p>'
                )
            if not self._draft:
                out.append(
                    f'<p class="muted">{tr("compare.no_columns")}</p>'
                )
            return "".join(out)

        out = [f"<style>{document_css_for(self.settings)}</style>"]
        if build.warnings:
            out.append(
                f'<p class="muted cmp-warning">'
                f'{tr("compare.some_columns_failed")}</p>'
            )
        # Column widths come from `column_metrics` through the table format,
        # never from the HTML itself.
        out.append(
            '<table class="cmp-table" cellspacing="0" cellpadding="3">'
        )

        sources = build.sources
        for row_index, row in enumerate(table.rows):
            alt = " cmp-row-alt" if row_index % 2 else ""
            out.append("<tr>")
            out.append(
                f'<td class="cmp-verse{alt}" align="center" valign="middle">'
                f'<a name="cv{row.verse}"></a>'
                f'<a href="cmp-verse:{row.verse}">{row.verse}</a></td>'
            )
            for cell in row.cells:
                source = sources.get(cell.column.key)
                out.append(
                    f'<td class="cmp-cell cmp-{cell.status.value}{alt}">'
                    f"{self._cell_html(cell, source)}</td>"
                )
            if self._draft:
                out.append(
                    f'<td class="cmp-cell cmp-draft{alt}">&nbsp;</td>'
                )
            out.append("</tr>")

        out.append("</table>")
        return "".join(out)

    def _cell_html(self, cell: CompareCell, source: CompareSource | None) -> str:
        if cell.status is CellStatus.PRESENT:
            parts: list[str] = []
            for page in cell.pages:
                body = to_rich(
                    page.raw,
                    hint=source.hint if source else "",
                    codepages=source.codepages if source else None,
                )
                body = _format_headings(body)
                if not body:
                    body = "&nbsp;"
                parts.append(f'<div class="cmp-src">{body}</div>')
            if not parts:
                return "&nbsp;"
            count = (
                f'<span class="cmp-count">×{len(cell.pages)}</span>'
                if len(cell.pages) > 1 else ""
            )
            return count + "".join(parts)

        if cell.status is CellStatus.EMPTY:
            return '<span class="cmp-empty" title="' + _html.escape(
                tr("compare.empty_cell"), quote=True
            ) + '">&nbsp;</span>'

        if cell.status is CellStatus.MISSING_BOOK:
            text = tr("compare.missing_book")
        elif cell.status is CellStatus.MISSING_CHAPTER:
            text = tr("compare.missing_chapter")
        else:
            text = tr("compare.missing_verse")
        return (
            '<span class="cmp-missing" title="'
            + _html.escape(text, quote=True)
            + '">&nbsp;</span>'
        )

    # ── anchors ──────────────────────────────────────────────────────────
    def _on_anchor(self, url) -> None:
        text = url.toString()
        if text.startswith("cmp-verse:"):
            try:
                self.verse_clicked.emit(int(text.split(":", 1)[1]))
            except ValueError:
                pass
