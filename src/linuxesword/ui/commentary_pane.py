"""Panel de comentario: vista propia en la parte inferior del área de Biblia."""

from __future__ import annotations

import html as _html

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from ..core.context import AppContext
from ..core.refs import link_references
from ..core.text import snippet, to_plain, to_rich
from ..i18n import tr
from .rich_browser import RichBrowser
from .theme import document_css, palette

MAX_CHARS = 9000


class CommentaryPane(QWidget):
    """Comentarios del capítulo actual, agrupados por versículo."""

    open_module = Signal(int, str)
    module_changed = Signal(str)

    def __init__(self, ctx: AppContext, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.settings = ctx.settings
        self._book = 0
        self._chapter = 0
        self._label = ""
        self.setMinimumHeight(120)
        self._build_ui()
        self.reload_modules()

    # ── UI ───────────────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        head = QWidget()
        row = QHBoxLayout(head)
        row.setContentsMargins(12, 5, 10, 5)
        row.setSpacing(8)

        self.title_label = QLabel(tr("commentary.title"))
        self.title_label.setObjectName("sectionTitle")
        row.addWidget(self.title_label)

        self.match_label = QLabel("")
        self.match_label.setObjectName("matchBadge")
        self.match_label.hide()
        row.addWidget(self.match_label)

        self.combo = QComboBox()
        self.combo.setMinimumWidth(260)
        self.combo.setToolTip(tr("commentary.pick_help"))
        self.combo.currentIndexChanged.connect(self._on_module_changed)
        row.addWidget(self.combo, 1)

        self.btn_open = QPushButton(tr("common.open"))
        self.btn_open.setToolTip(tr("commentary.title"))
        self.btn_open.clicked.connect(self._open_full)
        row.addWidget(self.btn_open)

        self.btn_hide = QPushButton("✕")
        self.btn_hide.setObjectName("closeButton")
        self.btn_hide.setFixedSize(24, 24)
        self.btn_hide.setCursor(Qt.PointingHandCursor)
        self.btn_hide.setToolTip(tr("bible.comments_off"))
        self.btn_hide.clicked.connect(lambda: self.setVisible(False))
        self.btn_hide.clicked.connect(self._notify_hidden)
        row.addWidget(self.btn_hide)

        layout.addWidget(head)

        self.browser = RichBrowser(resolver=self.ctx.refs.tooltip)
        self.browser.setOpenLinks(False)
        self.browser.setOpenExternalLinks(False)
        self.browser.anchorClicked.connect(self._on_anchor)
        self.browser.document().setDefaultStyleSheet(
            document_css(self.settings.theme, self.settings.font_size, self.settings.font_family)
        )
        layout.addWidget(self.browser, 1)

    def _notify_hidden(self) -> None:
        parent = self.parent()
        while parent is not None and not hasattr(parent, "_on_commentary_closed"):
            parent = parent.parent()
        if parent is not None:
            parent._on_commentary_closed()

    # ── módulos ──────────────────────────────────────────────────────────
    def reload_modules(self) -> None:
        current = self.combo.currentData() if self.combo.count() else ""
        self.combo.blockSignals(True)
        self.combo.clear()
        for mod in self.ctx.commentaries():
            label = f"{mod['abbreviation']} — {mod['title']}" if mod["abbreviation"] else mod["title"]
            self.combo.addItem(label[:86], mod["rel_path"])
        wanted = current or self._default_rel()
        idx = self.combo.findData(wanted)
        if idx >= 0:
            self.combo.setCurrentIndex(idx)
        self.combo.blockSignals(False)
        self.refresh()

    def _default_rel(self) -> str:
        pre = set(self.settings.preindex)
        for mod in self.ctx.commentaries():
            if mod["rel_path"] in pre:
                return mod["rel_path"]
        mods = self.ctx.commentaries()
        return max(mods, key=lambda m: m["entries"] or 0)["rel_path"] if mods else ""

    def commentary_rel(self) -> str:
        return self.combo.currentData() or ""

    def set_commentary_rel(self, rel: str) -> None:
        idx = self.combo.findData(rel)
        if idx >= 0 and idx != self.combo.currentIndex():
            self.combo.setCurrentIndex(idx)

    def _module_row(self) -> dict | None:
        rel = self.commentary_rel()
        return self.ctx.catalog.by_rel_path(rel) if rel else None

    def _on_module_changed(self, _index: int) -> None:
        self.refresh()
        self.module_changed.emit(self.commentary_rel())

    # ── contenido ────────────────────────────────────────────────────────
    def set_chapter(self, book: int, chapter: int, label: str = "") -> None:
        self._book, self._chapter, self._label = book, chapter, label
        self.refresh()

    def scroll_to_verse(self, verse: int) -> None:
        """Lleva el panel a la nota del versículo indicado."""
        if not verse:
            return
        self.browser.scrollToAnchor(f"cv{verse}")

    def set_match_badge(self, text: str) -> None:
        self.match_label.setText(text)
        self.match_label.setVisible(bool(text))

    def refresh(self) -> None:
        self.browser.document().setDefaultStyleSheet(
            document_css(self.settings.theme, self.settings.font_size, self.settings.font_family)
        )
        if not self._book or not self._chapter:
            self.browser.setHtml(f'<p class="muted">{tr("commentary.hint")}</p>')
            return
        row = self._module_row()
        mod = self.ctx.module(row) if row else None
        if mod is None:
            self.browser.setHtml(f'<p class="muted">{tr("commentary.hint")}</p>')
            return
        comments = mod.chapter_comments(self._book, self._chapter)
        if not comments:
            self.browser.setHtml(f'<p class="muted">{tr("commentary.none")}</p>')
            return

        pal = palette(self.settings.theme)
        out = [
            f"<style>{document_css(self.settings.theme, self.settings.font_size, self.settings.font_family)}</style>",
            f'<div class="entry-title">{_html.escape(self._label)}</div>',
        ]
        for verse in sorted(comments):
            for page in comments[verse]:
                anchor = f"cv{verse}"
                caption = f"{self._label}:{verse}" if verse else self._label
                out.append(f'<a name="{anchor}"></a>')
                out.append(
                    f'<div style="color:{pal.accent}; font-weight:700; '
                    f'font-size:{max(10, self.settings.font_size - 3)}px; '
                    f'margin:14px 0 4px 0;">{_html.escape(caption)}</div>'
                )
                raw = link_references(to_rich(page.raw, hint=mod.stem, codepages=mod.codepages))
                plain = to_plain(page.raw, hint=mod.stem, codepages=mod.codepages)
                if len(plain) > MAX_CHARS:
                    out.append(
                        f'<div>{to_rich(snippet(plain, MAX_CHARS))} '
                        f'<a href="full:{page.ref}">{tr("bible.read_more")}</a></div>'
                    )
                else:
                    out.append(f"<div>{raw}</div>")
        self.browser.setHtml("".join(out))
        self.browser.verticalScrollBar().setValue(0)

    def reload_theme(self) -> None:
        self.refresh()

    def retranslate(self) -> None:
        self.title_label.setText(tr("commentary.title"))
        self.btn_open.setText(tr("common.open"))
        self.btn_open.setToolTip(tr("commentary.title"))
        self.btn_hide.setToolTip(tr("bible.comments_off"))
        self.refresh()

    # ── eventos ──────────────────────────────────────────────────────────
    def _open_full(self) -> None:
        row = self._module_row()
        if row is None:
            return
        ref = ""
        if self._book and self._chapter:
            ref = f"{self._book}:{self._chapter}:1"
        self.open_module.emit(row["id"], ref)

    def _on_anchor(self, url) -> None:
        if url.scheme() == "full":
            row = self._module_row()
            if row is not None:
                self.open_module.emit(row["id"], url.path() or url.toString()[5:])
