"""Strong index: locates the lexicon and resolves a `G2316` number."""

from __future__ import annotations

import re

from ..i18n import tr
from .text import to_plain

_CODE_RE = re.compile(r"^[GH]\d{1,5}$")
_COMPACT_RE = re.compile(r"\s+")


class StrongIndex:
    """Auto-detects the Strong lexicon and caches queried entries."""

    def __init__(self, ctx: AppContext):
        self.ctx = ctx
        self._row: dict | None = None
        self._resolved = False
        self._cache: dict[str, str] = {}
        self._probed: list[dict] | None = None

    # ── detection ────────────────────────────────────────────────────────
    def _probe(self, row: dict) -> bool:
        mod = self.ctx.module(row)
        if mod is None or mod.structure not in ("lexicon", "dictionary"):
            return False
        table = "Lexicon" if mod.structure == "lexicon" else "Dictionary"
        try:
            rows = mod.conn.execute(
                f'SELECT Topic FROM "{table}" LIMIT 30'
            ).fetchall()
        except Exception:
            return False
        topics = [str(r[0] or "") for r in rows]
        if not topics:
            return False
        hits = sum(1 for t in topics if _CODE_RE.match(t.strip()))
        return hits >= max(3, int(len(topics) * 0.6))

    def _candidates(self) -> list[dict]:
        lexicon = [m for m in self.ctx.catalog.modules(kind="lexicon")]
        dictionaries = [m for m in self.ctx.catalog.modules(kind="dictionary")]

        def score(m: dict) -> tuple:
            blob = f"{m['rel_path']} {m['title']} {m['abbreviation']}".lower()
            strong = 0 if "strong" in blob else 1
            kind = 0 if m["kind"] == "lexicon" else 1
            return (strong, kind, -(m["entries"] or 0))

        return sorted(lexicon + dictionaries, key=score)

    def candidates(self) -> list[dict]:
        """Lexicons that actually index by Strong number (cached)."""
        if self._probed is None:
            self._probed = [row for row in self._candidates()[:24] if self._probe(row)]
        return list(self._probed)

    def set_default(self, rel_path: str) -> None:
        """Sets the lexicon used for bubbles and discards the cache."""
        self.ctx.settings.strong_rel = rel_path
        self.ctx.settings.save()
        self._row = None
        self._resolved = False
        self._cache.clear()

    def module(self) -> dict | None:
        if self._resolved:
            return self._row
        self._resolved = True
        preferred = self.ctx.settings.strong_rel
        if preferred:
            row = self.ctx.catalog.by_rel_path(preferred)
            if row is not None and self._probe(row):
                self._row = row
                return self._row
        for row in self._candidates()[:24]:
            if self._probe(row):
                self._row = row
                self.ctx.settings.strong_rel = row["rel_path"]
                return self._row
        return None

    # ── lookup ───────────────────────────────────────────────────────────
    def available(self) -> bool:
        return self.module() is not None

    def label(self) -> str:
        row = self.module()
        if row is None:
            return ""
        return f"{row['abbreviation']} · {row['title']}"

    def _resolve_page(self, code: str):
        """(row, module, page) of the first lexicon that has the entry.

        If the chosen lexicon does not cover that language (e.g. a Hebrew-only
        one and `G2316` is requested), the rest of the candidates are tried in
        order.
        """
        primary = self.module()
        order = ([primary] if primary else []) + [
            c for c in self.candidates()
            if primary is None or c["id"] != primary["id"]
        ]
        for row in order:
            mod = self.ctx.module(row)
            if mod is None:
                continue
            page = mod.page_by_ref(code)
            if page is not None and (page.raw or "").strip():
                return row, mod, page
        return None, None, None

    def lookup(self, code: str) -> str:
        """Plain text of the Strong entry ('' if it exists in no lexicon)."""
        code = _COMPACT_RE.sub("", code or "").upper()
        if not _CODE_RE.match(code):
            return ""
        if code in self._cache:
            return self._cache[code]
        _row, mod, page = self._resolve_page(code)
        text = ""
        if page is not None and mod is not None:
            text = to_plain(page.raw, hint=mod.stem, codepages=mod.codepages)
        self._cache[code] = text
        return text

    def tooltip(self, code: str, max_chars: int = 2500) -> str:
        """Bubble text: abbreviated source and full entry (with a cap).

        The long work name does not go in the header: only the lexicon
        abbreviation is shown there. That way vertical space is devoted to the
        text.
        """
        code = _COMPACT_RE.sub("", code or "").upper()
        body = self.lookup(code)
        if not body:
            return f"{code}\n(entry not found in any lexicon)"
        row, _mod, _page = self._resolve_page(code)
        if row:
            label = (row.get("abbreviation") or row.get("title") or "").strip()
        else:
            label = ""
        if not label:
            label = self.label().split(" · ", 1)[-1]
        if len(label) > 36:
            label = label[:36].rsplit(" ", 1)[0] + "…"
        # One line per module paragraph is preserved (Hebrew word,
        # transliteration, definition...). Flattening them into a single
        # paragraph made Hebrew (first strong RTL character) drag the rest
        # along.
        lines = [
            re.sub(r"[ \t]+", " ", line).strip()
            for line in body.splitlines()
        ]
        body = "\n".join(line for line in lines if line)
        if len(body) > max_chars:
            cut = body[:max_chars]
            if "\n" in cut:
                cut = cut.rsplit("\n", 1)[0]
            else:
                cut = cut.rsplit(" ", 1)[0]
            body = cut.rstrip() + "…\n" + tr("tooltip.strong_more")
        return f"{code} · {label}\n{body}"

    def entry(self, code: str) -> tuple[str, str]:
        """(entry title, full text) with fallback across lexicons."""
        code = _COMPACT_RE.sub("", code or "").upper()
        _row, mod, page = self._resolve_page(code)
        if page is None or mod is None:
            return code, ""
        return page.title or code, to_plain(page.raw, hint=mod.stem, codepages=mod.codepages)
