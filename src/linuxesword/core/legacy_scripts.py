"""Detección automática de codepages legacy en módulos e-Sword.

El registro vendorizado (`font_codepages.py`) solo conoce unos pocos módulos
(Vine, Certeza). Muchos otros guardan griego/hebreo como bytes de 8 bits
(`\'e8\'e5\'ef...`) que el decodificador RTF lee como cp1252 y salen como
`èåïäßäáêôïò`.

Aquí se detecta el codepage **por contenido**: se buscan **rachas** de escapes
`\'XX` (una palabra griega produce 4-10 seguidos; un acento español va suelto)
y se prueba cp1253 (griego) y cp1255 (hebreo). Si la decodificación produce
letras del alfabeto esperado, se adopta ese codepage.

El heurístico es deliberadamente conservador: sin rachas claras devuelve `{}` y
el texto se queda como está (nunca se inventa ni se "corrige" a ciegas).
"""

from __future__ import annotations

import re

_RUN = re.compile(r"(?:\\'[0-9a-fA-F]{2}){3,}")
_ESC = re.compile(r"\\'([0-9a-fA-F]{2})")

GREEK_RANGE = (0x0370, 0x03FF)
HEBREW_RANGE = (0x0590, 0x05FF)


def _decode_run(run: str, codepage: str) -> str:
    data = bytes(int(h, 16) for h in _ESC.findall(run))
    return data.decode(codepage, "replace")


def _script_ratio(text: str, bounds: tuple[int, int]) -> float:
    if not text:
        return 0.0
    lo, hi = bounds
    hits = sum(1 for ch in text if lo <= ord(ch) <= hi)
    return hits / len(text)


def detect_codepage(samples: list[str]) -> int | None:
    """1 (cp1253 griego) o 2 (cp1255 hebreo) si hay evidencia clara."""
    runs: list[str] = []
    for text in samples:
        if not text:
            continue
        runs.extend(_RUN.findall(str(text)))
        if len(runs) >= 60:
            break
    if not runs:
        return None
    joined = "".join(runs[:60])
    greek = _script_ratio(_decode_run(joined, "cp1253"), GREEK_RANGE)
    hebrew = _script_ratio(_decode_run(joined, "cp1255"), HEBREW_RANGE)
    best, ratio = None, 0.0
    if greek >= hebrew and greek >= 0.55:
        best, ratio = "cp1253", greek
    elif hebrew >= 0.55:
        best, ratio = "cp1255", hebrew
    if best is None:
        return None
    return 1 if best == "cp1253" else 2


def codepages_from_samples(samples: list[str]) -> dict[int, str]:
    """Mapa `\\fN → codepage`. e-Sword usa \\f1 para griego y \\f2 para hebreo."""
    primary = detect_codepage(samples)
    if primary is None:
        return {}
    return {1: "cp1253", 2: "cp1255"}
