"""Transliteración legacy de fuentes e-Sword (texto plano).

Algunos módulos (p. ej. Certeza) guardan transliteraciones griegas/hebreas con
un juego de glifos Latin-1 (`µ`, `ƒ`, `Æ`, `û`, `Œ`, `\\`, `÷`, `<`, `>`...)
en lugar de Unicode. No es un codepage: son caracteres literales que hay que
mapear a transliteración académica.

El mapeo es **por fuente** y se aplica en la conversión (BDL derivado); la
fuente original no se modifica.
"""

from __future__ import annotations

import re
from typing import Optional

# Certeza: transliteración académica (Unicode) de los glifos legacy.
_CERTEZA: dict[str, str] = {
    # vocales largas: el glifo es un marcador de macron tras la vocal
    "aµ": "ā", "eµ": "ē", "iµ": "ī", "oµ": "ō", "uµ": "ū",
    "Aµ": "Ā", "Eµ": "Ē", "Iµ": "Ī", "Oµ": "Ō", "Uµ": "Ū",
    "aÆ": "ā", "eÆ": "ē", "iÆ": "ī", "oÆ": "ō", "uÆ": "ū",
    "AÆ": "Ā", "EÆ": "Ē", "IÆ": "Ī", "OÆ": "Ō", "UÆ": "Ū",
    # alef/ayin + breve
    ">‡": "ʿă", "<‡": "ʾă",
    # shin / sin: el módulo usa el digrafo s + marcador
    "sû": "š", "sŒ": "ś", "Sû": "Š", "SŒ": "Ś",
    # consonantes con punto inferior / diacríticos (secuencias primero)
    "h\\": "ḥ", "t\\": "ṭ", "s\\": "ṣ", "d\\": "ḍ", "r\\": "ṛ",
    "z\\": "ẓ", "q\\": "q̇", "g\\": "ġ", "k\\": "ḳ", "p\\": "ṗ",
    "b\\": "ḅ", "m\\": "ṃ", "n\\": "ṇ", "w\\": "ẉ", "y\\": "ỵ",
    "g÷": "ḡ", "d÷": "ḏ", "r÷": "ṟ", "t÷": "ṯ", "s÷": "ṡ",
    # vocales / semivocales (fallback si el marcador va solo)
    "µ": "ē", "Æ": "ā", "ƒ": "ə", "‡": "ă",
    "¬": "u",
    # alef / ayin
    "<": "ʾ", ">": "ʿ",
    # shin / sin
    "Œ": "ś", "û": "š",
    # marcadores sin equivalente claro: se eliminan (no se inventa texto)
    "_": "", "\\": "", "÷": "",
}

_SOURCE_MAPS: dict[str, dict[str, str]] = {
    "certeza": _CERTEZA,
    "dicc_certeza_es": _CERTEZA,
}

_HINTS = (("certeza", _CERTEZA),)


def transliteration_for(hint: Optional[str]) -> dict[str, str]:
    """Mapa `glifo → Unicode` para una fuente, o `{}` si no aplica."""
    if not hint:
        return {}
    key = str(hint).strip().lower()
    for known, mapping in _SOURCE_MAPS.items():
        if key == known or key.startswith(known + "_") or key.endswith(known):
            return dict(mapping)
    for token, mapping in _HINTS:
        if token in key:
            return dict(mapping)
    return {}


def apply_transliteration(text: str, mapping: dict[str, str] | None) -> str:
    """Aplica el mapa respetando el orden (secuencias más largas primero)."""
    if not text or not mapping:
        return text
    keys = sorted(mapping, key=len, reverse=True)
    pattern = re.compile("|".join(re.escape(k) for k in keys))
    return pattern.sub(lambda m: mapping[m.group(0)], text)


__all__ = ["transliteration_for", "apply_transliteration"]
