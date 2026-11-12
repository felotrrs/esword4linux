"""Resolvedor de burbujas para referencias y números Strong.

Compartido por la Biblia, los diccionarios y el panel de comentario: cualquier
`href="ref:Juan 3:16"` produce el texto del versículo en la **biblia de
referencia** (la activa, salvo que se fije otra en los ajustes).

Los pasajes se muestran completos hasta `MAX_VERSES`; un rango mayor se corta
con aviso, nunca a mitad de un versículo.
"""

from __future__ import annotations

from ..i18n import tr
from .books import parse_reference
from .text import to_plain

MAX_VERSES = 10


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

    def bible_rows(self):
        """Biblias candidatas, en orden de preferencia y sin duplicados."""
        settings = self.ctx.settings
        seen: set[str] = set()
        for rel in (settings.reference_bible, self._rel, settings.bible_module):
            if rel and rel not in seen:
                row = self.ctx.catalog.by_rel_path(rel)
                if row is not None:
                    seen.add(rel)
                    yield row
        for row in self.ctx.bibles():
            rel = row.get("rel_path") or ""
            if rel and rel not in seen:
                seen.add(rel)
                yield row

    def bible_row(self) -> dict | None:
        return next(iter(self.bible_rows()), None)

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
        if ref is None:
            return ""
        # La biblia activa puede ser solo NT (p. ej. GNT): si no tiene el
        # libro pedido, se prueba la siguiente candidata antes de rendirse.
        for row in self.bible_rows():
            mod = self.ctx.module(row)
            if mod is None or mod.structure != "bible":
                continue
            pages, numbered = self._verse_pages(mod, ref)
            if not pages:
                continue
            version = row.get("abbreviation") or ""
            hidden = max(0, len(pages) - MAX_VERSES)
            pages = pages[:MAX_VERSES]
            texts = [
                to_plain(page.raw, hint=mod.stem, codepages=mod.codepages).strip()
                for page in pages
            ]
            if numbered:
                body = "\n".join(
                    f"{page.verse} {text}" if page.verse else text
                    for page, text in zip(pages, texts)
                )
            else:
                body = texts[0]
            if hidden:
                body += "\n" + tr("tooltip.more_verses", n=hidden)
            label = ref.label(self.ctx.settings.locale)
            return f"{tr('tooltip.verse', ref=label, version=version)}\n{body}"
        return ""

    @staticmethod
    def _verse_pages(mod, ref) -> tuple[list, bool]:
        if ref.verse is not None:
            if ref.verse_end and ref.verse_end != ref.verse:
                pages = [
                    page for page in mod.bible_chapter(ref.book, ref.chapter)
                    if page.verse and ref.verse <= page.verse <= ref.verse_end
                ]
                return pages, True
            page = mod.bible_verse(ref.book, ref.chapter, ref.verse)
            return ([page], False) if page is not None else ([], False)
        return mod.bible_chapter(ref.book, ref.chapter), True
