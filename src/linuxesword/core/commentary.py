"""Emparejamiento biblia ↔ comentario.

e-Sword distribuye la biblia y sus notas como módulos separados. Para que al
pulsar un marcador `(B)` se abra *su* comentario, hay que emparejarlos.

Heurística: tokens normalizados del título/abreviatura/ruta + año compartido +
relación entre abreviaturas. Ante empate, gana el comentario con más entradas.
"""

from __future__ import annotations

import re
import unicodedata

_STOP = {
    "de", "del", "la", "el", "los", "las", "con", "y", "para", "en", "por",
    "una", "un", "al", "the", "of", "and", "to", "a", "biblia", "bible",
    "version", "revision", "edicion", "edition", "santa", "sagrada",
    # artefactos de ruta/extensión: no son identidad de la obra
    "es", "en", "pt", "fr", "biblias", "comentarios", "diccionarios", "libros",
    "bbli", "bblx", "cmti", "cmtx", "dcti", "dctx", "lexi", "lexx", "refi",
    "refx", "topi", "topx", "devx", "mapx", "harx", "twm", "comment", "dicc",
    "lexicon",
}
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_YEAR_RE = re.compile(r"\b(1[89]\d{2}|20\d{2})\b")


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFD", (text or "").lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def _tokens(row: dict) -> set[str]:
    blob = " ".join(str(row.get(k) or "") for k in ("title", "abbreviation", "rel_path"))
    return {t for t in _TOKEN_RE.findall(_norm(blob)) if t not in _STOP and len(t) > 1}


def _years(row: dict) -> set[str]:
    blob = " ".join(str(row.get(k) or "") for k in ("title", "abbreviation"))
    return set(_YEAR_RE.findall(_norm(blob)))


def _abbrev(row: dict) -> str:
    return "".join(_TOKEN_RE.findall(_norm(row.get("abbreviation") or "")))


def score(bible: dict, commentary: dict) -> float:
    bt, ct = _tokens(bible), _tokens(commentary)
    value = float(len(bt & ct))
    ba, ca = _abbrev(bible), _abbrev(commentary)
    if ba and ca and (ba == ca or ba in ca or ca in ba):
        value += 3.0
    if _years(bible) & _years(commentary):
        value += 2.0
    return value


def marker_verses(bible_module, limit: int = 14) -> list[tuple[int, int, int]]:
    """Versículos de la biblia que traen marcadores de nota (`\\super`/`<sup>`)."""
    if bible_module is None or bible_module.structure != "bible":
        return []
    out: list[tuple[int, int, int]] = []
    try:
        rows = bible_module.conn.execute(
            "SELECT Book, Chapter, Verse, Scripture FROM Bible "
            "WHERE Scripture LIKE '%\\super%' OR Scripture LIKE '%<sup>%' "
            "ORDER BY Book, Chapter, Verse LIMIT 600"
        )
    except Exception:
        return []
    step = max(1, 600 // max(1, limit))
    for i, row in enumerate(rows):
        if i % step:
            continue
        out.append((int(row["Book"]), int(row["Chapter"]), int(row["Verse"])))
        if len(out) >= limit:
            break
    return out


def coverage(commentary_module, verses: list[tuple[int, int, int]],
             cache: dict | None = None) -> float:
    """Fracción de los versículos muestreados que el comentario cubre."""
    if commentary_module is None or not verses:
        return 0.0
    cache = cache if cache is not None else {}
    hit = 0
    for book, chapter, verse in verses:
        key = (commentary_module.path, book, chapter)
        if key not in cache:
            try:
                cache[key] = commentary_module.chapter_comments(book, chapter)
            except Exception:
                cache[key] = {}
        if cache[key].get(verse):
            hit += 1
    return hit / len(verses)


def best_commentary(bible: dict | None, commentaries: list[dict],
                    bible_module=None, open_module=None) -> dict | None:
    """Comentario que mejor corresponde a una biblia.

    1. Puntúa por identidad (tokens del título + abreviatura + año).
    2. Si la biblia trae marcadores, verifica **cobertura real** de esos
       versículos: gana el comentario que de verdad los comenta.
    """
    if not bible or not commentaries:
        return None
    scored = sorted(
        ((score(bible, row), row.get("entries") or 0, row) for row in commentaries),
        key=lambda item: (item[0], item[1]), reverse=True,
    )
    plausible = [row for s, _, row in scored if s > 0]
    # Dos obras de años distintos no son la misma edición: se descartan.
    base_years = _years(bible)
    if base_years:
        filtered = [
            row for row in plausible
            if not _years(row) or (_years(row) & base_years)
        ]
        if filtered:
            plausible = filtered
    candidates = plausible[:5]
    if not candidates:
        return None
    if bible_module is None or open_module is None:
        return candidates[0]

    verses = marker_verses(bible_module)
    if len(verses) >= 3:
        cache: dict = {}
        best_row, best_cov = None, -1.0
        for row in candidates:
            mod = open_module(row)
            if mod is None:
                continue
            cov = coverage(mod, verses, cache)
            if cov > best_cov:
                best_cov, best_row = cov, row
        if best_row is not None and best_cov >= 0.25:
            return best_row

    # Sin cobertura suficiente: solo identidad fuerte (abreviatura o año)
    for row in candidates:
        ba, ca = _abbrev(bible), _abbrev(row)
        related = bool(ba and ca and (ba in ca or ca in ba))
        if related or (_years(bible) & _years(row)):
            return row
    return None


def match_commentary(bible: dict | None, commentaries: list[dict]) -> dict | None:
    """Emparejamiento solo por identidad (sin abrir módulos)."""
    if not bible or not commentaries:
        return None
    scored = []
    for row in commentaries:
        s = score(bible, row)
        scored.append((s, row.get("entries") or 0, row))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    best_score, _, best = scored[0]
    return best if best_score >= 2 else None


def describe_pair(bible: dict | None, commentary: dict | None) -> str:
    if not bible or not commentary:
        return ""
    return f"{bible.get('abbreviation') or ''} → {commentary.get('abbreviation') or ''}"
