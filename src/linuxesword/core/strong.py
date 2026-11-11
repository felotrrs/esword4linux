"""Índice Strong: localiza el léxico y resuelve un número `G2316`."""

from __future__ import annotations

import re

from .text import to_plain

_CODE_RE = re.compile(r"^[GH]\d{1,5}$")
_COMPACT_RE = re.compile(r"\s+")


class StrongIndex:
    """Auto-detecta el léxico Strong y cachea las entradas consultadas."""

    def __init__(self, ctx: AppContext):
        self.ctx = ctx
        self._row: dict | None = None
        self._resolved = False
        self._cache: dict[str, str] = {}
        self._probed: list[dict] | None = None

    # ── detección ────────────────────────────────────────────────────────
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
        """Léxicos que de verdad indexan por número Strong (cacheado)."""
        if self._probed is None:
            self._probed = [row for row in self._candidates()[:24] if self._probe(row)]
        return list(self._probed)

    def set_default(self, rel_path: str) -> None:
        """Fija el léxico de las burbujas y descarta la caché."""
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

    # ── consulta ─────────────────────────────────────────────────────────
    def available(self) -> bool:
        return self.module() is not None

    def label(self) -> str:
        row = self.module()
        if row is None:
            return ""
        return f"{row['abbreviation']} · {row['title']}"

    def lookup(self, code: str) -> str:
        """Texto plano de la entrada Strong ('' si no existe)."""
        code = _COMPACT_RE.sub("", code or "").upper()
        if not _CODE_RE.match(code):
            return ""
        if code in self._cache:
            return self._cache[code]
        row = self.module()
        if row is None:
            return ""
        mod = self.ctx.module(row)
        if mod is None:
            return ""
        page = mod.page_by_ref(code)
        text = to_plain(page.raw, hint=mod.stem, codepages=mod.codepages) if page is not None else ""
        self._cache[code] = text
        return text

    def tooltip(self, code: str, max_chars: int = 320) -> str:
        """Texto corto para la burbuja."""
        code = code.upper()
        body = self.lookup(code)
        if not body:
            return f"{code}\n(entrada no encontrada en el léxico)"
        body = _COMPACT_RE.sub(" ", body).strip()
        if len(body) > max_chars:
            body = body[:max_chars].rsplit(" ", 1)[0] + "…"
        return f"{code} · {self.label()}\n{body}"

    def entry(self, code: str) -> tuple[str, str]:
        """(título de la entrada, texto completo)."""
        code = code.upper()
        row = self.module()
        mod = self.ctx.module(row) if row else None
        page = mod.page_by_ref(code) if mod else None
        if page is None:
            return code, ""
        return page.title or code, to_plain(page.raw, hint=mod.stem, codepages=mod.codepages)
