"""Vista de búsqueda: una caja que entiende referencias, Strong y texto libre."""

from __future__ import annotations

import html as _html

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextBrowser,
    QVBoxLayout, QWidget,
)

from ..core.catalog import KIND_LABELS, KIND_ORDER
from ..core.context import AppContext
from ..core.search import SearchHit
from ..i18n import tr
from .theme import document_css


class SearchView(QWidget):
    open_hit = Signal(int, str, str)      # module_id, ref, kind
    go_reference = Signal(str)

    def __init__(self, ctx: AppContext, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.settings = ctx.settings
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(220)
        self._timer.timeout.connect(self.run_search)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        bar = QWidget()
        row = QHBoxLayout(bar)
        row.setContentsMargins(12, 10, 12, 10)
        row.setSpacing(8)

        self.query = QLineEdit()
        self.query.setPlaceholderText(tr("search.placeholder"))
        self.query.setToolTip(tr("search.query_help"))
        self.query.setClearButtonEnabled(True)
        self.query.textChanged.connect(lambda _=0: self._timer.start())
        self.query.returnPressed.connect(lambda: self.run_search(explicit=True))
        row.addWidget(self.query, 1)

        self.scope = QComboBox()
        self.scope.addItem(tr("search.scope_all"), "")
        for kind in KIND_ORDER:
            if kind == "unknown":
                continue
            self.scope.addItem(tr(f"kind.{kind}"), kind)
        self.scope.currentIndexChanged.connect(lambda _=0: self.run_search())
        self.scope.setMinimumWidth(170)
        self.scope.setToolTip(tr("search.scope_help"))
        row.addWidget(self.scope)

        self.btn = QPushButton(tr("search.tab"))
        self.btn.setToolTip(tr("search.query_help"))
        self.btn.setObjectName("primary")
        self.btn.clicked.connect(lambda: self.run_search(explicit=True))
        row.addWidget(self.btn)

        layout.addWidget(bar)

        self.info = QLabel("")
        self.info.setObjectName("appSubtitle")
        self.info.setContentsMargins(14, 0, 14, 6)
        layout.addWidget(self.info)

        self.results = QTextBrowser()
        self.results.setOpenLinks(False)
        self.results.setOpenExternalLinks(False)
        self.results.anchorClicked.connect(self._on_anchor)
        self.results.document().setDefaultStyleSheet(
            document_css(self.settings.theme, self.settings.font_size, self.settings.font_family)
        )
        layout.addWidget(self.results, 1)

    def retranslate(self) -> None:
        self.query.setPlaceholderText(tr("search.placeholder"))
        self.query.setToolTip(tr("search.query_help"))
        current = self.scope.currentData()
        self.scope.blockSignals(True)
        self.scope.clear()
        self.scope.addItem(tr("search.scope_all"), "")
        for kind in KIND_ORDER:
            if kind != "unknown":
                self.scope.addItem(tr(f"kind.{kind}"), kind)
        idx = self.scope.findData(current)
        if idx >= 0:
            self.scope.setCurrentIndex(idx)
        self.scope.blockSignals(False)
        self.btn.setText(tr("search.tab"))
        self.run_search()

    # ── búsqueda ─────────────────────────────────────────────────────────
    def set_query(self, text: str) -> None:
        self.query.setText(text)
        self.query.setFocus()
        self.run_search()

    def run_search(self, explicit: bool = False) -> None:
        query = self.query.text().strip()
        self.results.document().setDefaultStyleSheet(
            document_css(self.settings.theme, self.settings.font_size, self.settings.font_family)
        )
        if not query:
            self.info.setText("")
            self.results.setHtml(self._welcome())
            return

        kind = self.scope.currentData() or None
        scope = self.ctx.search.indexed_module_ids([kind] if kind else None)
        result = self.ctx.search.search(query, scope=scope or None)

        if result.intent == "reference" and result.reference:
            ref = result.reference
            self.info.setText(f'{tr("search.intent_reference")} · {ref.label(self.settings.locale)}')
            self.results.setHtml(self._render_reference(ref))
            if explicit:
                # Enter/acción explícita: ir directo, sin exigir clic en el enlace.
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
        self.info.setText(
            f'{label} · {tr("search.results_n", n=len(result.hits), ms=f"{result.elapsed_ms:.0f}")}'
            f' · {tr("search.scope_n", n=result.searched_modules)}'
        )
        self.results.setHtml(self._render_hits(result.hits, query))

    # ── render ───────────────────────────────────────────────────────────
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

    def _render_hits(self, hits: list[SearchHit], query: str) -> str:
        if not hits:
            return f'<p class="muted">{tr("search.no_results", q=_html.escape(query))}</p>'
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
