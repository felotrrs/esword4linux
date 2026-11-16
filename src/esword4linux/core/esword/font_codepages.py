"""Codepages de fuentes legacy en módulos e-Sword.

Algunos `.dctx`/`.cmtx` guardan griego/hebreo con fuentes de 8 bits: los bytes
`\\'XX` son cp1253 (griego) o cp1255 (hebreo), no cp1252. El parser RTF decodifica
por defecto cp1252; sin este registro el texto sale como `ἀãÜðç` (mojibake).

El registro es por **código de fuente** (y por stem del archivo, para el
Importer Lab antes de resolver el código). `font_number` es el `\\fN` del RTF:

    {1: "cp1253", 2: "cp1255"}

No se aplica globalmente: `\\f1`/`\\f2` pueden ser fuentes normales en otros
módulos. Para una fuente nueva, agregar una entrada aquí (o dejar que el
Importer Lab la detecte y la proponga).
"""

from __future__ import annotations

from typing import Optional

# code / stem → {font_number: codepage}
KNOWN_CODEPAGES: dict[str, dict[int, str]] = {
    "vine_es_nt": {1: "cp1253", 2: "cp1255"},
    "vine_es_at": {1: "cp1253", 2: "cp1255"},
    # stems del Importer Lab / nombres de archivo originales
    "dicc_vine_es_nt_es": {1: "cp1253", 2: "cp1255"},
    "dicc_vine_es_at_es": {1: "cp1253", 2: "cp1255"},
}

# Heurística por nombre: cualquier módulo Vine AT/NT usa el mismo esquema.
_HINTS = (
    ("vine", "nt", {1: "cp1253", 2: "cp1255"}),
    ("vine", "at", {1: "cp1253", 2: "cp1255"}),
)


def font_codepages_for(hint: Optional[str]) -> dict[int, str]:
    """Devuelve el mapa `\\fN → codepage` para una fuente, o `{}`.

    `hint` puede ser el código BDL (`vine_es_nt`), el stem del archivo
    (`dicc_vine_es_nt_es`) o el nombre original. Se compara en minúsculas.
    """
    if not hint:
        return {}
    key = str(hint).strip().lower()
    for known, mapping in KNOWN_CODEPAGES.items():
        if key == known or key.startswith(known + "_") or key.endswith(known):
            return dict(mapping)
    for first, second, mapping in _HINTS:
        if first in key and second in key:
            return dict(mapping)
    return {}


__all__ = ["KNOWN_CODEPAGES", "font_codepages_for"]
