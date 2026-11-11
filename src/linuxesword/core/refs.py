"""Detección de referencias bíblicas dentro de texto de módulos.

Port de `admin/src/lib/bible_refs.ts` del proyecto `bible`, adaptado a los
alias de `core/books.py` (fuente única: regla dorada #5). Se usa para las
burbujas de los `<ref>` y para enlazar citas sueltas.

Formatos que aparecen en las fuentes:

    "Ex. 32.1–6"      "Ex. 7.8ss"       "(He. 5.4; 7.11)"
    "(Ex. 4:14, 27-30)"  "Exo_28:1; Heb_5:4"   "(Ex. 32:4; Ps. 106:19)"
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .books import _ALIAS, book_name, normalize

MAX_CHARS = 400
SCAN_CHARS = 20000


@dataclass(frozen=True)
class RefSpan:
    start: int
    end: int
    text: str          # subcadena original (lo que se muestra)
    ref_text: str      # referencia normalizada (canónica, para consultar)


# Libro + capítulo + versículo opcional. El libro admite prefijo numérico y
# punto final ("He.", "1 Cor."); el capítulo puede venir tras "_" (Exo_28).
_SPAN_RE = re.compile(
    r"(?P<book>(?:[1-3]\s*)?[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{2,}\.?)\s*_?\s*"
    r"(?P<chapter>\d{1,3})"
    r"(?:\s*[.:]\s*(?P<verse>\d{1,3})"
    r"(?:\s*[-–—]\s*(?P<vend>\d{1,3}))?"
    r"(?:\s*(?:ss|ff|s|f)\b)?"
    r")?"
)


def _resolve(book_token: str) -> int | None:
    key = normalize(book_token).replace(" ", "")
    if key in _ALIAS:
        return _ALIAS[key]
    # alias con espacios (p. ej. "1 corintios")
    spaced = normalize(book_token)
    return _ALIAS.get(spaced)


def find_reference_spans(text: str, limit: int = 60) -> list[RefSpan]:
    """Devuelve las referencias detectadas, en orden y sin solapes."""
    if not text or len(text) < 4:
        return []
    text = text[:SCAN_CHARS]
    spans: list[RefSpan] = []
    for match in _SPAN_RE.finditer(text):
        if len(spans) >= limit:
            break
        book_id = _resolve(match.group("book"))
        if book_id is None:
            continue
        chapter = int(match.group("chapter"))
        if not 1 <= chapter <= 150:
            continue
        verse = int(match.group("verse")) if match.group("verse") else None
        vend = int(match.group("vend")) if match.group("vend") else None
        name = book_name(book_id, "es")
        if verse is None:
            ref_text = f"{name} {chapter}"
        elif vend and vend != verse:
            ref_text = f"{name} {chapter}:{verse}-{vend}"
        else:
            ref_text = f"{name} {chapter}:{verse}"
        spans.append(RefSpan(match.start(), match.end(), match.group(0), ref_text))
    return spans


def link_references(html_text: str, max_links: int = 40) -> str:
    """Envuelve citas sueltas de un HTML ya saneado en `<a href="ref:…">`.

    Solo actúa sobre texto plano (nunca dentro de una etiqueta ni dentro de un
    `<a>` existente).
    """
    if not html_text:
        return html_text
    out: list[str] = []
    pos = 0
    depth_a = 0
    for token in re.split(r"(<[^>]{1,400}>)", html_text):
        if token.startswith("<"):
            low = token.lower()
            if low.startswith("<a "):
                depth_a += 1
            elif low.startswith("</a"):
                depth_a = max(0, depth_a - 1)
            out.append(token)
            continue
        if depth_a:
            out.append(token)
            continue
        chunk_out: list[str] = []
        last = 0
        for i, span in enumerate(find_reference_spans(token, limit=max_links)):
            if i >= max_links:
                break
            chunk_out.append(token[last:span.start])
            chunk_out.append(
                f'<a href="ref:{_escape(span.ref_text)}">{span.text}</a>'
            )
            last = span.end
        chunk_out.append(token[last:])
        out.append("".join(chunk_out))
        pos += len(token)
    return "".join(out)


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")
