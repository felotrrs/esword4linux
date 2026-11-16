"""Automatic detection of legacy codepages in e-Sword modules.

The vendored registry (`font_codepages.py`) only knows a few modules
(Vine, Certeza). Many others store Greek/Hebrew as 8-bit bytes
(`\'e8\'e5\'ef...`) that the RTF decoder reads as cp1252 and they come out as
`èåïäßäáêôïò`.

Here the codepage is detected **by content**: **runs** of `\'XX` escapes are
searched (a Greek word produces 4-10 in a row; a Spanish accent appears on its
own) and cp1253 (Greek) and cp1255 (Hebrew) are tried. If decoding produces
letters of the expected alphabet, that codepage is adopted.

The heuristic is deliberately conservative: without clear runs it returns `{}`
and the text stays as it is (nothing is ever invented or "fixed" blindly).
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
    """1 (cp1253 Greek) or 2 (cp1255 Hebrew) if there is clear evidence."""
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
    """Map `\\fN → codepage`. e-Sword uses \\f1 for Greek and \\f2 for Hebrew."""
    primary = detect_codepage(samples)
    if primary is None:
        return {}
    return {1: "cp1253", 2: "cp1255"}
