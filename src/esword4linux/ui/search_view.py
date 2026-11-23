"""Search view: a single box that understands references, Strong and free text.

The text box keeps its three intents (reference, Strong, free text). Below it a
filter row narrows the search by material type, by specific work and — only
when the type is Bible — by biblical book and chapter.

Every list comes from existing metadata: the catalog (types, works, index
state) and the modules themselves (their books and their actual chapter
numbers). Nothing is invented, and the lists are recomputed only when the
catalog, the index or the selection changes — never by polling.
"""

from __future__ import annotations

import html as _html

from PySide6.QtCore import QEvent, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSizePolicy, QTextBrowser, QToolButton, QVBoxLayout, QWidget,
)

from ..core.books import BOOK_GROUPS, TESTAMENTS, book_name
from ..core.catalog import KIND_ORDER
from ..core.context import AppContext
from ..core.search import SearchFilters, SearchHit
from ..core.store import (
    MODE_ALL, MODE_ANY, MODE_PHRASE, MODE_REGEX, SEARCH_MODES,
)
from ..core.text import to_plain
from ..i18n import tr
from .flow_layout import FlowLayout
from .rich_browser import RichBrowser
from .tasks import Worker
from .theme import document_css_for

# Filter-row geometry. Every control has a fixed width, so the group is packed
# to the left with a constant distance between a label and its control: growing
# the window only adds empty space at the right end, never between controls.
TYPE_WIDTH = 140
WORK_WIDTH = 300
BOOK_WIDTH = 170
CHAPTER_WIDTH = 90
MODE_WIDTH = 190
TESTAMENT_WIDTH = 160
GROUP_WIDTH = 180
RANGE_BOOK_WIDTH = 170
RANGE_CHAPTER_WIDTH = 90
FILTER_SPACING = 6
#: Extra space inserted between two filter groups (combo → next label). Fixed,
#: so the groups stay readable at any window width.
GROUP_SPACING = 8

#: The search modes, in the order the combo shows them.
MODE_KEYS = {
    MODE_ALL: "search.mode_all",
    MODE_ANY: "search.mode_any",
    MODE_PHRASE: "search.mode_phrase",
    MODE_REGEX: "search.mode_regex",
}


class SearchView(QWidget):
    open_hit = Signal(int, str, str)      # module_id, ref, kind
    go_reference = Signal(str)

    def __init__(self, ctx: AppContext, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.settings = ctx.settings
        # The search runs only on an explicit action (Enter, the Search button
        # or a programmatic request). Typing updates the box but never queries
        # the index: a typo must not cost a whole-library search.
        self._approved_query = ""
        # ── background book/chapter lists ─────────────────────────────────
        # One worker at a time. Each request carries a generation id: a result
        # is applied only if it is still the newest request of its kind, so a
        # slow answer can never overwrite a newer selection.
        self._books_worker: Worker | None = None
        self._gen_books = 0
        self._gen_chapters = 0
        self._pending_books: tuple[int, list[tuple[int, str]]] | None = None
        self._pending_chapters: tuple[int, list[tuple[int, str]], int] | None = None
        self._wanted_book: int | None = None
        self._books: list[int] = []
        self._chapters: list[int] = []
        self._closed = False
        self._build_ui()
        self.refresh_filters()

    # ── UI ───────────────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        bar = QWidget()
        rows = QVBoxLayout(bar)
        rows.setContentsMargins(12, 10, 12, 8)
        rows.setSpacing(6)

        top = QHBoxLayout()
        top.setSpacing(8)
        self.query = QLineEdit()
        self.query.setPlaceholderText(tr("search.placeholder"))
        self.query.setToolTip(tr("search.query_help"))
        self.query.setClearButtonEnabled(True)
        # No textChanged → search: the query is committed with Enter or the
        # Search button. On clear, drop the committed query so the welcome
        # screen comes back without searching anything.
        self.query.textChanged.connect(self._on_query_edited)
        self.query.returnPressed.connect(lambda: self.run_search(explicit=True))
        top.addWidget(self.query, 1)

        self.mode_filter = QComboBox()
        self.mode_filter.setObjectName("filterCombo")
        self.mode_filter.setToolTip(tr("search.mode_help"))
        self.mode_filter.setFixedWidth(MODE_WIDTH)
        for mode in SEARCH_MODES:
            self.mode_filter.addItem(tr(MODE_KEYS[mode]), mode)
        self.mode_filter.currentIndexChanged.connect(self._on_mode_changed)
        top.addWidget(self.mode_filter)

        self.btn = QPushButton(tr("search.tab"))
        self.btn.setToolTip(tr("search.query_help"))
        self.btn.setObjectName("primary")
        self.btn.clicked.connect(lambda: self.run_search(explicit=True))
        top.addWidget(self.btn)
        rows.addLayout(top)

        # ── filters ──────────────────────────────────────────────────────
        # A flow of fixed-width groups (label + control). The controls keep
        # their size and position; when the window is too narrow for one row
        # the area grows vertically and the groups continue on the next line,
        # so nothing is ever clipped or hidden behind a scroller.
        filter_bar = QWidget()
        self._filter_flow = FlowLayout(
            filter_bar, hspacing=GROUP_SPACING, vspacing=6
        )

        self.type_label = QLabel(tr("search.filter_type"))
        self.type_label.setObjectName("appSubtitle")
        self.type_filter = QComboBox()
        self.type_filter.setObjectName("filterCombo")
        self.type_filter.setToolTip(tr("search.filter_help"))
        self.type_filter.setFixedWidth(TYPE_WIDTH)
        self.type_filter.currentIndexChanged.connect(self._on_type_changed)

        self.work_label = QLabel(tr("search.filter_work"))
        self.work_label.setObjectName("appSubtitle")
        self.work_filter = QComboBox()
        self.work_filter.setObjectName("filterCombo")
        self.work_filter.setToolTip(tr("search.filter_help"))
        self.work_filter.setFixedWidth(WORK_WIDTH)
        self.work_filter.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.work_filter.setMinimumContentsLength(14)
        self.work_filter.currentIndexChanged.connect(self._on_work_changed)

        self.book_label = QLabel(tr("search.filter_book"))
        self.book_label.setObjectName("appSubtitle")
        self.book_filter = QComboBox()
        self.book_filter.setObjectName("filterCombo")
        self.book_filter.setToolTip(tr("search.filter_help"))
        self.book_filter.setFixedWidth(BOOK_WIDTH)
        self.book_filter.currentIndexChanged.connect(self._on_book_changed)

        self.chapter_label = QLabel(tr("search.filter_chapter"))
        self.chapter_label.setObjectName("appSubtitle")
        self.chapter_filter = QComboBox()
        self.chapter_filter.setObjectName("filterCombo")
        self.chapter_filter.setToolTip(tr("search.filter_help"))
        self.chapter_filter.setFixedWidth(CHAPTER_WIDTH)
        self.chapter_filter.currentIndexChanged.connect(self._on_chapter_changed)

        # The labels keep their natural width; the slack belongs to Work only,
        # so no label can absorb it and shift the controls around.
        for label in (self.type_label, self.work_label,
                      self.book_label, self.chapter_label):
            label.setSizePolicy(
                QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred
            )

        self.btn_reset = QToolButton()
        self.btn_reset.setObjectName("filterReset")
        self.btn_reset.setText(tr("search.filter_reset"))
        self.btn_reset.setToolTip(tr("search.filter_help"))
        self.btn_reset.setEnabled(False)
        self.btn_reset.clicked.connect(self.reset_filters)

        self.advanced = QCheckBox(tr("search.advanced"))
        self.advanced.setToolTip(tr("search.advanced_help"))
        self.advanced.toggled.connect(self._on_advanced_toggled)

        # ── advanced Bible ranges (revealed by the checkbox) ─────────────
        self._advanced_bar = QWidget()
        self._advanced_flow = FlowLayout(
            self._advanced_bar, hspacing=GROUP_SPACING, vspacing=4
        )

        self.testament_label = QLabel(tr("search.range_testament"))
        self.testament_label.setObjectName("appSubtitle")
        self.testament_filter = QComboBox()
        self.testament_filter.setObjectName("filterCombo")
        self.testament_filter.setToolTip(tr("search.range_help"))
        self.testament_filter.setFixedWidth(TESTAMENT_WIDTH)
        self.testament_filter.currentIndexChanged.connect(self._on_range_changed)

        self.group_label = QLabel(tr("search.range_group"))
        self.group_label.setObjectName("appSubtitle")
        self.group_filter = QComboBox()
        self.group_filter.setObjectName("filterCombo")
        self.group_filter.setToolTip(tr("search.range_help"))
        self.group_filter.setFixedWidth(GROUP_WIDTH)
        self.group_filter.currentIndexChanged.connect(self._on_range_changed)

        self.books_label = QLabel(tr("search.range_books"))
        self.books_label.setObjectName("appSubtitle")
        self.book_from = QComboBox()
        self.book_from.setObjectName("filterCombo")
        self.book_from.setToolTip(tr("search.range_help"))
        self.book_from.setFixedWidth(RANGE_BOOK_WIDTH)
        self.book_from.currentIndexChanged.connect(self._on_range_changed)
        self.book_range_dash = QLabel("–")
        self.book_range_dash.setObjectName("appSubtitle")
        self.book_to = QComboBox()
        self.book_to.setObjectName("filterCombo")
        self.book_to.setToolTip(tr("search.range_help"))
        self.book_to.setFixedWidth(RANGE_BOOK_WIDTH)
        self.book_to.currentIndexChanged.connect(self._on_range_changed)

        self.chapters_label = QLabel(tr("search.range_chapters"))
        self.chapters_label.setObjectName("appSubtitle")
        self.chapter_from = QComboBox()
        self.chapter_from.setObjectName("filterCombo")
        self.chapter_from.setToolTip(tr("search.range_help"))
        self.chapter_from.setFixedWidth(RANGE_CHAPTER_WIDTH)
        self.chapter_from.currentIndexChanged.connect(self._on_range_changed)
        self.chapter_range_dash = QLabel("–")
        self.chapter_range_dash.setObjectName("appSubtitle")
        self.chapter_to = QComboBox()
        self.chapter_to.setObjectName("filterCombo")
        self.chapter_to.setToolTip(tr("search.range_help"))
        self.chapter_to.setFixedWidth(RANGE_CHAPTER_WIDTH)
        self.chapter_to.currentIndexChanged.connect(self._on_range_changed)

        for label in (self.testament_label, self.group_label, self.books_label,
                      self.chapters_label):
            label.setSizePolicy(
                QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred
            )

        # Main filter groups, in reading order; then the checkbox and Reset.
        self._filter_flow.addWidget(
            self._group(self.type_label, self.type_filter)
        )
        self._filter_flow.addWidget(
            self._group(self.work_label, self.work_filter)
        )
        self._filter_flow.addWidget(
            self._group(self.book_label, self.book_filter)
        )
        self._filter_flow.addWidget(
            self._group(self.chapter_label, self.chapter_filter)
        )
        self._filter_flow.addWidget(self.advanced)
        self._filter_flow.addWidget(self.btn_reset)

        # Advanced range groups wrap independently, under the main row.
        self._advanced_flow.addWidget(
            self._group(self.testament_label, self.testament_filter)
        )
        self._advanced_flow.addWidget(
            self._group(self.group_label, self.group_filter)
        )
        self._advanced_flow.addWidget(
            self._group(self.books_label, self.book_from,
                        self.book_range_dash, self.book_to)
        )
        self._advanced_flow.addWidget(
            self._group(self.chapters_label, self.chapter_from,
                        self.chapter_range_dash, self.chapter_to)
        )
        self._advanced_bar.setVisible(False)

        filter_box = QWidget()
        filter_box_rows = QVBoxLayout(filter_box)
        filter_box_rows.setContentsMargins(0, 0, 0, 0)
        filter_box_rows.setSpacing(4)
        filter_box_rows.addWidget(filter_bar)
        filter_box_rows.addWidget(self._advanced_bar)
        rows.addWidget(filter_box)

        # Contextual hint: library/index state, or an uncommitted query.
        self.hint = QLabel("")
        self.hint.setObjectName("appSubtitle")
        self.hint.setWordWrap(True)
        self.hint.setVisible(False)
        rows.addWidget(self.hint)
        layout.addWidget(bar)

        self.info = QLabel("")
        self.info.setObjectName("appSubtitle")
        self.info.setContentsMargins(14, 0, 14, 6)
        layout.addWidget(self.info)

        # RichBrowser: hover shows the passage behind a result in a bubble.
        self.results = RichBrowser(resolver=self._resolve_hit)
        self.results.setOpenLinks(False)
        self.results.setOpenExternalLinks(False)
        self.results.anchorClicked.connect(self._on_anchor)
        self.results.document().setDefaultStyleSheet(
            document_css_for(self.settings)
        )
        layout.addWidget(self.results, 1)

        self._reset_combo(self.book_filter, "search.filter_all")
        self._reset_combo(self.chapter_filter, "search.filter_all")
        self._reset_combo(self.testament_filter, "search.filter_all")
        self._reset_combo(self.group_filter, "search.filter_all")
        self._reset_combo(self.book_from, "search.filter_all")
        self._reset_combo(self.book_to, "search.filter_all")
        self._reset_combo(self.chapter_from, "search.filter_all")
        self._reset_combo(self.chapter_to, "search.filter_all")
        self._sync_enabled()

    @staticmethod
    def _group(*widgets) -> QWidget:
        """A label and its control(s) as one unit: the flow never splits it."""
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(FILTER_SPACING)
        for widget in widgets:
            row.addWidget(widget)
        box.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        return box

    def retranslate(self) -> None:
        self.query.setPlaceholderText(tr("search.placeholder"))
        self.query.setToolTip(tr("search.query_help"))
        self.type_label.setText(tr("search.filter_type"))
        self.work_label.setText(tr("search.filter_work"))
        self.book_label.setText(tr("search.filter_book"))
        self.chapter_label.setText(tr("search.filter_chapter"))
        self.testament_label.setText(tr("search.range_testament"))
        self.group_label.setText(tr("search.range_group"))
        self.books_label.setText(tr("search.range_books"))
        self.chapters_label.setText(tr("search.range_chapters"))
        self.advanced.setText(tr("search.advanced"))
        self.advanced.setToolTip(tr("search.advanced_help"))
        self.btn_reset.setText(tr("search.filter_reset"))
        self.btn_reset.setToolTip(tr("search.filter_help"))
        self.type_filter.setToolTip(tr("search.filter_help"))
        self.work_filter.setToolTip(tr("search.filter_help"))
        self.mode_filter.setToolTip(tr("search.mode_help"))
        self.btn.setText(tr("search.tab"))
        self._refresh_modes()
        # Book names and category labels are translated: re-render both lists
        # without losing the current selection and without recomputing them.
        self.refresh_filters()
        if self._type() == "bible":
            self._fill_books(self._books, self._book())
            self._fill_chapters(self._chapters, self._chapter())
            self._fill_ranges()
        self.run_search()

    def _refresh_modes(self) -> None:
        current = self._mode()
        self.mode_filter.blockSignals(True)
        self.mode_filter.clear()
        for mode in SEARCH_MODES:
            self.mode_filter.addItem(tr(MODE_KEYS[mode]), mode)
        idx = self.mode_filter.findData(current)
        self.mode_filter.setCurrentIndex(idx if idx >= 0 else 0)
        self.mode_filter.blockSignals(False)

    # ── module lists (catalog) ───────────────────────────────────────────
    def refresh_filters(self) -> None:
        """Rebuild the type and work lists from the catalog.

        Called at startup, after every metadata scan and after indexing, and
        by ``retranslate()`` (the ``kind.*`` labels are translated). The
        current selections are preserved while they are still valid.
        """
        current_kind = self._type()
        current_work = self._work()
        counts = self.ctx.catalog.counts_by_kind()
        self.type_filter.blockSignals(True)
        self.type_filter.clear()
        self.type_filter.addItem(tr("search.filter_all"), "")
        for kind in KIND_ORDER:
            # "unknown" is never indexed, so it can never return results.
            if kind == "unknown" or not counts.get(kind):
                continue
            self.type_filter.addItem(tr(f"kind.{kind}"), kind)
        idx = self.type_filter.findData(current_kind)
        self.type_filter.setCurrentIndex(idx if idx >= 0 else 0)
        self.type_filter.blockSignals(False)
        self._refresh_works(preselect=current_work)
        self._sync_enabled()
        if self._type() == "bible":
            self._request_books()
        self._update_reset()
        self._refresh_hint()

    def _refresh_works(self, preselect=None) -> None:
        """List the indexed modules of the selected type."""
        kind = self._type()
        ids = self.ctx.search.indexed_module_ids([kind] if kind else None)
        rows = [row for i in ids if (row := self.ctx.catalog.module(i))]
        rows.sort(key=lambda r: ((r.get("title") or "").lower(),
                                 (r.get("abbreviation") or "").lower()))
        self.work_filter.blockSignals(True)
        self.work_filter.clear()
        self.work_filter.addItem(tr("search.filter_all"), None)
        for row in rows:
            label = (
                f"{row['abbreviation']} — {row['title']}"
                if row.get("abbreviation") else (row.get("title") or "")
            )
            self.work_filter.addItem(label[:100], row["id"])
            tooltip = row.get("title") or ""
            if row.get("language"):
                tooltip = f"{tooltip}\n{row['language']}"
            self.work_filter.setItemData(
                self.work_filter.count() - 1, tooltip, Qt.ToolTipRole
            )
        idx = self.work_filter.findData(preselect) if preselect is not None else 0
        self.work_filter.setCurrentIndex(idx if idx >= 0 else 0)
        self.work_filter.blockSignals(False)

    # ── filters: state, visibility and cascade ───────────────────────────
    def _type(self) -> str:
        return self.type_filter.currentData() or ""

    def _work(self) -> int | None:
        data = self.work_filter.currentData()
        return data if isinstance(data, int) else None

    def _book(self) -> int | None:
        data = self.book_filter.currentData()
        return data if isinstance(data, int) else None

    def _chapter(self) -> int | None:
        data = self.chapter_filter.currentData()
        return data if isinstance(data, int) else None

    def _mode(self) -> str:
        return self.mode_filter.currentData() or MODE_ALL

    def _range_value(self, combo: QComboBox) -> int | None:
        data = combo.currentData()
        return data if isinstance(data, int) else None

    def _book_range(self) -> tuple[int, int] | None:
        """Intersection of testament, group and from/to book selections."""
        if not self.advanced.isChecked() or self._type() != "bible":
            return None
        constraints: list[tuple[int, int]] = []
        testament = self.testament_filter.currentData()
        if isinstance(testament, tuple):
            constraints.append(testament)
        group = self.group_filter.currentData()
        if isinstance(group, tuple):
            constraints.append(group)
        low = self._range_value(self.book_from)
        high = self._range_value(self.book_to)
        if low is not None:
            constraints.append((low, 999))
        if high is not None:
            constraints.append((0, high))
        if not constraints:
            return None
        lo = max(c[0] for c in constraints)
        hi = min(c[1] for c in constraints)
        return (lo, hi)

    def _chapter_range(self) -> tuple[int, int] | None:
        if (not self.advanced.isChecked() or self._type() != "bible"
                or self._book() is None):
            return None
        low = self._range_value(self.chapter_from)
        high = self._range_value(self.chapter_to)
        if low is None and high is None:
            return None
        return (low if low is not None else 1,
                high if high is not None else 200)

    def filters(self) -> SearchFilters:
        """The filters handed to the engine, derived from the active state.

        A disabled control is cleared and contributes ``None``: a book or
        chapter can never reach the engine while the selected type is not
        Bible, even if a stale value survived somewhere in the combo.
        """
        kind = self._type()
        is_bible = kind == "bible"
        book = (
            self._book()
            if is_bible and self.book_filter.isEnabled() else None
        )
        chapter = (
            self._chapter()
            if book is not None and self.chapter_filter.isEnabled() else None
        )
        return SearchFilters(
            kinds=(kind,) if kind else (),
            module_id=self._work(),
            book=book,
            chapter=chapter,
            book_range=self._book_range(),
            chapter_range=self._chapter_range(),
        )

    def _sync_enabled(self) -> None:
        """Activate the filters that can still add something.

        The Bible scope is a chain — Testament → Group → Books range → Book →
        Chapters range → Chapter — so an exact value and a range of the same
        dimension are **mutually exclusive**: the newest choice wins and the
        other one is cleared and disabled. With nothing selected («All») every
        control is available.
        """
        is_bible = self._type() == "bible"
        book_range = self._book_range_selected()
        exact_book = self._book() is not None
        chapter_range = self._chapter_range_selected()
        exact_chapter = self._chapter() is not None
        has_exact_book = is_bible and exact_book

        # Book dimension: exact Book ↔ book ranges.
        book_enabled = is_bible and not book_range
        ranges_enabled = is_bible and not exact_book
        # Chapter dimension: needs an exact book (a book range has no single
        # chapter numbering), exact Chapter ↔ chapters range.
        chapter_enabled = has_exact_book and not chapter_range
        chapter_ranges_enabled = has_exact_book and not exact_chapter

        for widget in (self.book_label, self.book_filter):
            widget.setEnabled(book_enabled)
        for widget in (self.chapter_label, self.chapter_filter):
            widget.setEnabled(chapter_enabled)
        for widget in (self.testament_label, self.testament_filter,
                       self.group_label, self.group_filter,
                       self.books_label, self.book_from, self.book_range_dash,
                       self.book_to):
            widget.setEnabled(ranges_enabled)
        for widget in (self.chapters_label, self.chapter_from,
                       self.chapter_range_dash, self.chapter_to):
            widget.setEnabled(chapter_ranges_enabled)

        self.advanced.setEnabled(is_bible)
        self._advanced_bar.setVisible(is_bible and self.advanced.isChecked())

        # A control that cannot add anything must not keep filtering, but its
        # list is kept: clearing the *selection* is enough and the user gets it
        # back the moment the conflicting filter is removed.
        if not book_enabled:
            self._select_all(self.book_filter)
        if not ranges_enabled:
            self._clear_book_ranges()
        if not chapter_enabled:
            self._select_all(self.chapter_filter)
        if not chapter_ranges_enabled:
            self._clear_chapter_ranges()
        if not is_bible:
            self.advanced.setChecked(False)
            self._clear_ranges()

    def _book_range_selected(self) -> bool:
        return any(
            isinstance(combo.currentData(), tuple)
            for combo in (self.testament_filter, self.group_filter)
        ) or self._range_value(self.book_from) is not None \
            or self._range_value(self.book_to) is not None

    def _chapter_range_selected(self) -> bool:
        return (self._range_value(self.chapter_from) is not None
                or self._range_value(self.chapter_to) is not None)

    def _select_all(self, combo: QComboBox) -> None:
        """Back to the «All» entry without dropping the list."""
        if combo.count() == 0:
            return
        combo.blockSignals(True)
        combo.setCurrentIndex(0)
        combo.blockSignals(False)

    def _clear_book_ranges(self) -> None:
        for combo in (self.testament_filter, self.group_filter,
                      self.book_from, self.book_to):
            self._select_all(combo)
        self._fill_ranges()

    def _clear_chapter_ranges(self) -> None:
        for combo in (self.chapter_from, self.chapter_to):
            self._select_all(combo)
        self._fill_ranges()

    def _clear_ranges(self) -> None:
        self._clear_book_ranges()
        self._clear_chapter_ranges()

    def _update_reset(self) -> None:
        self.btn_reset.setEnabled(self.filters().is_active())

    def _reset_combo(self, combo: QComboBox, label_key: str) -> None:
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(tr(label_key), None)
        combo.setCurrentIndex(0)
        combo.blockSignals(False)

    def _invalidate_scope(self) -> None:
        """A type/work change invalidates the pending lists and the values."""
        self._wanted_book = self._book()
        self._gen_books += 1
        self._gen_chapters += 1
        self._pending_books = None
        self._pending_chapters = None
        self._reset_combo(self.book_filter, "search.filter_all")
        self._reset_combo(self.chapter_filter, "search.filter_all")
        self._clear_ranges()

    def _invalidate_chapters(self) -> None:
        self._gen_chapters += 1
        self._pending_chapters = None
        self._reset_combo(self.chapter_filter, "search.filter_all")
        self._clear_chapter_ranges()

    def _on_type_changed(self, _index: int) -> None:
        self._invalidate_scope()
        self._refresh_works()
        self._sync_enabled()
        if self._type() == "bible":
            self._request_books()
        self._update_reset()
        self._refresh_hint()
        self.run_search()

    def _on_work_changed(self, _index: int) -> None:
        self._invalidate_scope()
        self._sync_enabled()
        if self._type() == "bible":
            self._request_books()
        self._update_reset()
        self._refresh_hint()
        self.run_search()

    def _on_book_changed(self, _index: int) -> None:
        self._invalidate_chapters()
        self._sync_enabled()
        if self._type() == "bible" and self._book() is not None:
            self._request_chapters()
        self._update_reset()
        self.run_search()

    def _on_chapter_changed(self, _index: int) -> None:
        self._sync_enabled()
        self._update_reset()
        self.run_search()

    def _on_mode_changed(self, _index: int) -> None:
        """The mode is a search setting: re-run the committed query."""
        self._refresh_hint()
        self.run_search()

    def _on_advanced_toggled(self, checked: bool) -> None:
        is_bible = self._type() == "bible"
        self._advanced_bar.setVisible(checked and is_bible)
        if not checked:
            self._clear_ranges()
        self._update_reset()
        self.run_search()

    def _on_range_changed(self, _index: int) -> None:
        # Refill first: the *to* selectors follow the *from* one and the groups
        # follow the testament, so a stale value is dropped before searching.
        self._fill_ranges()
        self._sync_enabled()
        self._update_reset()
        self.run_search()

    def reset_filters(self) -> None:
        """Clear every filter and search again."""
        self.type_filter.blockSignals(True)
        self.type_filter.setCurrentIndex(0)
        self.type_filter.blockSignals(False)
        self.advanced.blockSignals(True)
        self.advanced.setChecked(False)
        self.advanced.blockSignals(False)
        self._wanted_book = None
        self._invalidate_scope()
        self._clear_ranges()
        self._refresh_works()
        self._sync_enabled()
        self._update_reset()
        self._refresh_hint()
        self.run_search()

    # ── book / chapter lists (background worker) ─────────────────────────
    def _bible_scope(self) -> list[tuple[int, str]]:
        """(module_id, path) of the Bibles participating in the search."""
        work = self._work()
        ready = set(self.ctx.search.indexed_module_ids(["bible"]))
        out: list[tuple[int, str]] = []
        for row in self.ctx.catalog.modules(kind="bible"):
            if row["id"] not in ready:
                continue
            if work is not None and row["id"] != work:
                continue
            out.append((row["id"], row["path"]))
        return out

    def _request_books(self) -> None:
        self._gen_books += 1
        self._pending_books = (self._gen_books, self._bible_scope())
        self._pump()

    def _request_chapters(self) -> None:
        book = self._book()
        if book is None:
            return
        self._gen_chapters += 1
        self._pending_chapters = (self._gen_chapters, self._bible_scope(), book)
        self._pump()

    def _pump(self) -> None:
        """Start the next queued request when no worker is running."""
        if self._closed or self._books_worker is not None:
            return
        if self._pending_books is not None:
            gen, modules = self._pending_books
            self._pending_books = None
            kind, book = "books", None
        elif self._pending_chapters is not None:
            gen, modules, book = self._pending_chapters
            self._pending_chapters = None
            kind = "chapters"
        else:
            return
        worker = Worker(
            lambda _progress, g=gen, k=kind, m=modules, b=book:
                SearchView._compute_lists(g, k, m, b),
            self,
        )
        worker.done.connect(self._on_worker_done)
        worker.failed.connect(self._on_worker_failed)
        worker.finished.connect(self._on_worker_finished)
        self._books_worker = worker
        worker.start()

    @staticmethod
    def _compute_lists(gen: int, kind: str,
                       modules: list[tuple[int, str]],
                       book: int | None):
        """Union of books (or of a book's chapters) over the scope.

        Runs in the worker thread: it only opens the module files read-only and
        never touches a widget. A module that disappeared during a catalog
        refresh, or that cannot be read, is skipped instead of failing the run.
        """
        from ..core.esword.module import EswordModule

        thread = QThread.currentThread()
        values: set[int] = set()
        for _module_id, path in modules:
            if thread.isInterruptionRequested():
                break
            try:
                mod = EswordModule(path)
            except Exception:   # noqa: BLE001 — deleted, moved or unreadable
                continue
            try:
                if kind == "books":
                    values.update(mod.books())
                elif book is not None:
                    values.update(mod.chapters(int(book)))
            except Exception:   # noqa: BLE001 — one bad module must not fail all
                continue
            finally:
                mod.close()
        return kind, gen, sorted(values)

    def _on_worker_done(self, payload) -> None:
        if self._closed:
            return
        sender = self.sender()
        # A worker that was superseded must never touch the UI. ``sender()`` is
        # None only when the slot is invoked directly (tests), never from Qt.
        if sender is not None and sender is not self._books_worker:
            return
        try:
            kind, gen, values = payload
        except (TypeError, ValueError):
            return
        if kind == "books":
            if gen != self._gen_books:
                return
            self._apply_books(values)
        else:
            if gen != self._gen_chapters:
                return
            self._apply_chapters(values)

    def _on_worker_failed(self, _message: str) -> None:
        # The UI keeps its current lists; the request simply yields nothing.
        return

    def _on_worker_finished(self) -> None:
        worker = self._books_worker
        self._books_worker = None
        if worker is not None:
            worker.deleteLater()
        if not self._closed:
            self._pump()

    def _apply_books(self, books: list[int]) -> None:
        if self._type() != "bible":
            return
        previous = self._book()
        self._books = list(books)
        self._fill_books(books, self._wanted_book)
        self._wanted_book = None
        current = self._book()
        # A refresh that keeps the same book must not drop the chapter; a new
        # book (selected here or in the combo) invalidates it.
        if current is not None and current != previous:
            self._invalidate_chapters()
            self._request_chapters()

    def _fill_books(self, books: list[int], wanted=None) -> None:
        target = wanted if wanted is not None else self._book()
        self.book_filter.blockSignals(True)
        self.book_filter.clear()
        self.book_filter.addItem(tr("search.filter_all"), None)
        for book_id in books:
            self.book_filter.addItem(
                book_name(book_id, self.settings.locale), book_id
            )
        idx = self.book_filter.findData(target) if target is not None else 0
        self.book_filter.setCurrentIndex(idx if idx >= 0 else 0)
        self.book_filter.blockSignals(False)
        self._fill_ranges()
        self._sync_enabled()
        self._update_reset()

    def _apply_chapters(self, chapters: list[int]) -> None:
        if self._type() != "bible":
            return
        self._chapters = list(chapters)
        self._fill_chapters(chapters, self._chapter())

    def _fill_chapters(self, chapters: list[int], wanted=None) -> None:
        target = wanted if wanted is not None else self._chapter()
        self.chapter_filter.blockSignals(True)
        self.chapter_filter.clear()
        self.chapter_filter.addItem(tr("search.filter_all"), None)
        for chapter in chapters:
            self.chapter_filter.addItem(str(chapter), chapter)
        idx = self.chapter_filter.findData(target) if target is not None else 0
        self.chapter_filter.setCurrentIndex(idx if idx >= 0 else 0)
        self.chapter_filter.blockSignals(False)
        self._fill_ranges()
        self._sync_enabled()
        self._update_reset()

    # ── advanced ranges ──────────────────────────────────────────────────
    def _fill_ranges(self) -> None:
        """Populate the advanced combos with what the Bibles actually contain.

        The chain narrows itself: the groups come from the selected testament,
        the books from testament ∩ group, and the *to* selectors only offer
        values at or after the matching *from* (the publication/chapter order).
        Only what the indexed Bibles carry is offered, so the Apocrypha appears
        only when a Bible includes it.
        """
        locale = self.settings.locale
        base = set(self._books)

        # 1. Testaments present in the available Bibles.
        self._fill_range_combo(
            self.testament_filter,
            [(t.key, t.label(locale), (t.start, t.end))
             for t in TESTAMENTS if base & set(t.books())],
        )
        scope = self._range_ids(base, self.testament_filter.currentData())

        # 2. Groups inside the selected testament (and the available books).
        self._fill_range_combo(
            self.group_filter,
            [(g.key, g.label(locale), (g.start, g.end))
             for g in BOOK_GROUPS if scope & set(g.books())],
        )
        scope = self._range_ids(scope, self.group_filter.currentData())

        # 3. Books: the *to* selector starts where the *from* one does.
        books = sorted(scope)
        self._fill_range_combo(
            self.book_from,
            [(str(b), book_name(b, locale), b) for b in books],
        )
        start = self._range_value(self.book_from)
        self._fill_range_combo(
            self.book_to,
            [(str(b), book_name(b, locale), b)
             for b in books if start is None or b >= start],
        )

        # 4. Chapters of the selected book: same forward-only rule.
        chapters = list(self._chapters)
        self._fill_range_combo(
            self.chapter_from, [(str(c), str(c), c) for c in chapters]
        )
        start = self._range_value(self.chapter_from)
        self._fill_range_combo(
            self.chapter_to,
            [(str(c), str(c), c) for c in chapters
             if start is None or c >= start],
        )

    @staticmethod
    def _range_ids(books: set[int], span) -> set[int]:
        """Intersect *books* with a (lo, hi) span (or leave it untouched)."""
        if isinstance(span, tuple):
            return books & set(range(span[0], span[1] + 1))
        return set(books)

    def _fill_range_combo(self, combo: QComboBox, items) -> None:
        current = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(tr("search.filter_all"), None)
        for _key, label, data in items:
            combo.addItem(label[:60], data)
        combo.setCurrentIndex(self._index_of(combo, current) if current is not None else 0)
        combo.blockSignals(False)

    @staticmethod
    def _index_of(combo: QComboBox, data) -> int:
        """Index of *data* by value (Qt's findData cannot compare tuples)."""
        for index in range(combo.count()):
            if combo.itemData(index) == data:
                return index
        return -1

    def shutdown(self) -> None:
        """Stop the background worker before the widgets are destroyed."""
        self._closed = True
        worker = self._books_worker
        self._books_worker = None
        self._pending_books = None
        self._pending_chapters = None
        if worker is not None:
            if worker.isRunning():
                worker.requestInterruption()
                worker.wait(3000)
            worker.deleteLater()

    # ── search ───────────────────────────────────────────────────────────
    def set_query(self, text: str) -> None:
        """Fill the box from another view and search it straight away."""
        self.query.setText(text)
        self.query.setFocus()
        self.run_search(explicit=True)

    def _on_query_edited(self, _text: str) -> None:
        """Typing only updates the box — it never queries the index.

        Clearing the box does drop the committed query, so the welcome screen
        comes back without waiting for Enter.
        """
        if self.query.text().strip():
            self._refresh_hint()
            return
        self._approved_query = ""
        self.run_search()

    def _refresh_hint(self) -> None:
        """Contextual hint under the filters: library state, then the query.

        The library/index warnings come first: an empty combo must never look
        like a broken feature. When everything is fine, a pending (not yet
        committed) query is announced.
        """
        message = self._library_hint()
        if not message and self.query.text().strip() != self._approved_query:
            message = tr("search.press_enter")
        self.hint.setText(message)
        self.hint.setVisible(bool(message))

    def _library_hint(self) -> str:
        """Explain why the selectors may be empty."""
        counts = self.ctx.catalog.counts_by_kind()
        if not counts:
            return tr("search.no_library")
        kind = self._type()
        indexed = self.ctx.search.indexed_module_ids([kind] if kind else None)
        if indexed:
            return ""
        return tr("search.category_not_indexed" if kind else "search.no_index")

    def run_search(self, explicit: bool = False) -> None:
        """Run the **committed** query, or commit the current text.

        ``explicit`` is the human approval (Enter, the Search button, another
        view asking for a query). Without it only the last approved query is
        re-run, so filter changes refresh the results without ever searching a
        half-typed text.
        """
        if explicit:
            self._approved_query = self.query.text().strip()
        query = self._approved_query
        self.results.document().setDefaultStyleSheet(
            document_css_for(self.settings)
        )
        pending = self.query.text().strip() != self._approved_query
        self._refresh_hint()
        if not query:
            self.info.setText("")
            self.results.setHtml(self._welcome())
            return

        filters = self.filters()
        active = filters.is_active()
        result = self.ctx.search.search(
            query, filters=filters if active else None, mode=self._mode()
        )

        if result.note == "regex_error":
            self.info.setText(tr("search.intent_text"))
            self.results.setHtml(
                f'<p class="muted">'
                f'{_html.escape(tr("search.regex_invalid", error=result.note_detail))}'
                f'</p>'
            )
            return
        if result.note == "regex_empty":
            self.info.setText(tr("search.intent_text"))
            self.results.setHtml(
                f'<p class="muted">{tr("search.regex_no_word")}</p>'
            )
            return

        if result.intent == "reference" and result.reference:
            ref = result.reference
            self.info.setText(
                f'{tr("search.intent_reference")} · '
                f'{ref.label(self.settings.locale)}'
            )
            self.results.setHtml(self._render_reference(ref))
            if explicit:
                # Enter/explicit action: go directly, without requiring a click on the link.
                self.go_reference.emit(ref.label(self.settings.locale))
            return

        if result.note == "sin_indice":
            self.info.setText(tr("search.intent_text"))
            self.results.setHtml(f'<p class="muted">{tr("search.no_index")}</p>')
            return

        label = {
            "strong": tr("search.intent_strong"),
            "text": tr("search.intent_text"),
        }.get(result.intent, tr("search.intent_text"))
        extra = ""
        if active:
            extra = f' · {tr("search.filters_applied", filters=self._filter_summary(filters))}'
        self.info.setText(
            f'{label} · {tr("search.results_n", n=len(result.hits), ms=f"{result.elapsed_ms:.0f}")}'
            f' · {tr("search.scope_n", n=result.searched_modules)}{extra}'
        )
        self.results.setHtml(self._render_hits(result.hits, query, active))

    def _filter_summary(self, filters: SearchFilters) -> str:
        parts: list[str] = []
        if filters.kinds:
            parts.append(", ".join(tr(f"kind.{k}") for k in filters.kinds))
        if filters.module_id is not None:
            row = self.ctx.catalog.module(filters.module_id)
            if row:
                parts.append(row.get("abbreviation") or row.get("title") or "")
        if filters.book is not None:
            name = book_name(filters.book, self.settings.locale)
            if filters.chapter is not None:
                name = f"{name} {filters.chapter}"
            parts.append(name)
        if filters.book_range is not None:
            lo, hi = filters.book_range
            if (lo, hi) != (1, 999):
                parts.append(
                    f"{book_name(lo, self.settings.locale)}–"
                    f"{book_name(hi, self.settings.locale)}"
                )
        if filters.chapter_range is not None:
            lo, hi = filters.chapter_range
            parts.append(f"{lo}–{hi}")
        return " · ".join(p for p in parts if p)

    # ── rendering ────────────────────────────────────────────────────────
    def _resolve_hit(self, href: str, _rel: str | None = None) -> str:
        """Passage or entry behind a result link, for the hover bubble.

        This is the second read of a hit: the search only stored module id and
        reference, so the text is read from that module when the pointer rests
        on the link (the bubble caches it).
        """
        if not href.startswith("hit:"):
            return ""
        parts = href.split(":", 2)
        if len(parts) != 3:
            return ""
        try:
            module_id = int(parts[1])
        except ValueError:
            return ""
        ref = parts[2]
        row = self.ctx.catalog.module(module_id)
        mod = self.ctx.module(row) if row else None
        if mod is None:
            return ""
        page = mod.page_by_ref(ref)
        if page is None:
            return ""
        text = to_plain(page.raw, hint=mod.stem, codepages=mod.codepages)
        if not text.strip():
            return ""
        head = page.title or ref
        if row.get("abbreviation"):
            title = row.get("title") or ""
            head = f"{row['abbreviation']} — {title} · {head}"
        return f"{head}\n{text}"

    def _welcome(self) -> str:
        indexed = len(self.ctx.search.indexed_module_ids())
        if not indexed:
            return f'<p class="muted">{tr("search.no_index")}</p>'
        return (
            f'<p class="muted">{tr("search.scope_n", n=indexed)}</p>'
            f'<p class="muted">{tr("search.placeholder")}</p>'
        )

    def _render_reference(self, ref) -> str:
        label = ref.label(self.settings.locale)
        return (
            f'<p class="hit"><a href="goref:{_html.escape(label, quote=True)}">'
            f'→ {tr("search.go_to", ref=label)}</a></p>'
        )

    def _render_hits(self, hits: list[SearchHit], query: str,
                     filtered: bool = False) -> str:
        if not hits:
            key = "search.no_results_filtered" if filtered else "search.no_results"
            return f'<p class="muted">{tr(key, q=_html.escape(query))}</p>'
        grouped = self.ctx.search.group_by_kind(hits)
        out = []
        for kind in KIND_ORDER:
            group = grouped.get(kind)
            if not group:
                continue
            out.append(
                f'<div class="group">{tr(f"kind.{kind}")} '
                f'<span class="muted">({len(group)})</span></div>'
            )
            for hit in group[:80]:
                out.append(
                    f'<div class="hit">'
                    f'<a href="hit:{hit.module_id}:{_html.escape(hit.ref, quote=True)}">'
                    f'<b>{_html.escape(hit.title)}</b></a>'
                    f' <span class="meta">· {_html.escape(hit.module_abbrev)}</span>'
                    f'<div>{hit.snippet}</div>'
                    f"</div>"
                )
        return "".join(out)

    def _on_anchor(self, url) -> None:
        scheme = url.scheme()
        text = url.toString()
        if scheme == "hit":
            rest = text[len("hit:"):]
            mod_id, _, ref = rest.partition(":")
            if mod_id.isdigit():
                self.open_hit.emit(int(mod_id), ref, "")
        elif scheme == "goref":
            self.go_reference.emit(url.path() or text[6:])
