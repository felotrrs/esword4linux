"""Bubble resolver for references and Strong numbers.

Shared by the Bible, the dictionaries and the commentary panel: any
`href="ref:Juan 3:16"` produces the verse text from the **reference Bible**
(the active one, unless another one is fixed in the settings).

Passages are shown in full up to `MAX_VERSES`; a larger range is cut
with a notice, never in the middle of a verse.
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

    # ── reference Bible ──────────────────────────────────────────────────
    def set_bible(self, rel_path: str) -> None:
        if rel_path and rel_path != self._rel:
            self._rel = rel_path
            self._cache.clear()

    def bible_rows(self):
        """Candidate Bibles, in order of preference and without duplicates."""
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
    def tooltip(self, href: str, rel_path: str | None = None) -> str:
        try:
            if href.startswith("ref:"):
                return self.verse_tooltip(href[4:], rel_path)
            if href.startswith("strong:"):
                return self.ctx.strong.tooltip(href[7:])
        except Exception:
            return ""
        return ""

    def clear(self) -> None:
        self._cache.clear()

    def verse_tooltip(self, ref_text: str, rel_path: str | None = None) -> str:
        if not ref_text:
            return ""
        key = ref_text.strip()
        if rel_path:
            key = f"{rel_path}::{key}"
        if key in self._cache:
            return self._cache[key]
        text = self._build_verse(ref_text, rel_path)
        self._cache[key] = text
        return text

    def bible_rows_for(self, rel_path: str | None = None):
        """Candidate Bibles, giving priority to rel_path when provided.

        Always includes the default Bible as fallback (settings.bible_module)
        and, lastly, every indexed Bible, so that it never runs out of
        candidates even if rel_path is not a valid Bible or does not contain the
        requested passage.
        """
        settings = self.ctx.settings
        seen: set[str] = set()
        order: list[str] = []
        if rel_path:
            order.append(rel_path)
        for r in (settings.reference_bible, self._rel, settings.bible_module):
            if r and r not in order:
                order.append(r)
        # Every indexed Bible as a last resort.
        for row in self.ctx.bibles():
            r = row.get("rel_path") or ""
            if r and r not in order:
                order.append(r)
        for rel in order:
            if rel and rel not in seen:
                row = self.ctx.catalog.by_rel_path(rel)
                if row is not None:
                    seen.add(rel)
                    yield row

    def _build_verse(self, ref_text: str, rel_path: str | None = None) -> str:
        ref = parse_reference(ref_text)
        if ref is None:
            return ""
        # The active Bible may be NT-only (e.g. GNT): if it does not have the
        # requested book, the next candidate is tried before giving up.
        for row in self.bible_rows_for(rel_path):
            try:
                mod = self.ctx.module(row)
            except Exception:
                continue
            if mod is None or mod.structure != "bible":
                continue
            try:
                pages, numbered = self._verse_pages(mod, ref)
            except Exception:
                continue
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
