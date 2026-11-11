"""Resolvedor de burbujas para referencias y números Strong.

Compartido por la Biblia, los diccionarios y el panel de comentario: cualquier
`href="ref:Juan 3:16"` produce el texto del versículo en la **biblia de
referencia** (la activa, salvo que se fije otra en los ajustes).
"""

from __future__ import annotations

from .books import book_name, parse_reference
from .text import snippet, to_plain


class RefResolver:
    def __init__(self, ctx):
        self.ctx = ctx
        self._rel = ""
        self._cache: dict[str, str] = {}

    # ── biblia de referencia ─────────────────────────────────────────────
    def set_bible(self, rel_path: str) -> None:
        if rel_path and rel_path != self._rel:
            self._rel = rel_path
            self._cache.clear()

    def bible_row(self) -> dict | None:
        settings = self.ctx.settings
        for rel in (settings.reference_bible, self._rel, settings.bible_module):
            if rel:
                row = self.ctx.catalog.by_rel_path(rel)
                if row is not None:
                    return row
        bibles = self.ctx.bibles()
        return bibles[0] if bibles else None

    # ── API ──────────────────────────────────────────────────────────────
    def tooltip(self, href: str) -> str:
        try:
            if href.startswith("ref:"):
                return self.verse_tooltip(href[4:])
            if href.startswith("strong:"):
                return self.ctx.strong.tooltip(href[7:])
        except Exception:
            return ""
        return ""

    def clear(self) -> None:
        self._cache.clear()

    def verse_tooltip(self, ref_text: str) -> str:
        if not ref_text:
            return ""
        key = ref_text.strip()
        if key in self._cache:
            return self._cache[key]
        text = self._build_verse(key)
        self._cache[key] = text
        return text

    def _build_verse(self, ref_text: str) -> str:
        ref = parse_reference(ref_text)
        row = self.bible_row()
        if ref is None or row is None:
            return ""
        mod = self.ctx.module(row)
        if mod is None or mod.structure != "bible":
            return ""
        version = row.get("abbreviation") or ""
        if ref.verse:
            page = mod.bible_verse(ref.book, ref.chapter, ref.verse)
            if page is None:
                return ""
            body = snippet(to_plain(page.raw, hint=mod.stem, codepages=mod.codepages), 330)
            return f"📖 {page.title} ({version})\n{body}"
        pages = mod.bible_chapter(ref.book, ref.chapter)
        if not pages:
            return ""
        body = " ".join(f"{p.verse} {to_plain(p.raw, hint=mod.stem, codepages=mod.codepages)}" for p in pages[:3])
        label = f"{book_name(ref.book, self.ctx.settings.locale)} {ref.chapter}"
        return f"📖 {label} ({version})\n{snippet(body, 330)}"
