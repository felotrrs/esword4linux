"""Normalización de contenido e-Sword: RTF/HTML/texto → plano y enriquecido.

Dos representaciones con propósitos distintos:

* **plano**  → se indexa en FTS5 (sin maquetación).
* **rico**   → se renderiza en Qt (QTextDocument entiende un subconjunto HTML).

El texto de la fuente NUNCA se altera semánticamente: solo se decodifica la
presentación (RTF/HTML) que e-Sword usa para mostrar.
"""

from __future__ import annotations

import html as _html
import re

from .esword.rtf import _is_html, _is_rtf, _strip_html, rtf_to_rich_text, rtf_to_text

# Tags que QTextDocument renderiza bien. El resto se descarta conservando
# el contenido (nunca se pierde texto).
_ALLOWED = {
    "p", "div", "span", "br", "b", "strong", "i", "em", "u", "s", "sup", "sub",
    "a", "font", "table", "thead", "tbody", "tr", "td", "th", "ul", "ol", "li",
    "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "hr", "center",
}
_SELF_CLOSING = {"br", "hr"}

_TAG_SPLIT = re.compile(r"(<[^>]{1,400}>)")


def decode_raw(raw) -> str:
    """bytes (UTF-8, fallback latin-1) o str → str."""
    if raw is None:
        return ""
    if isinstance(raw, (bytes, bytearray)):
        try:
            return bytes(raw).decode("utf-8")
        except UnicodeDecodeError:
            return bytes(raw).decode("latin-1", "replace")
    return str(raw)


def _collapse(text: str) -> str:
    text = text.replace("\xa0", " ").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[^\S\n]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def to_plain(raw) -> str:
    """Texto plano para indexar (sin RTF, sin HTML, sin formato)."""
    s = decode_raw(raw)
    if not s.strip():
        return ""
    if _is_rtf(s):
        return _collapse(rtf_to_text(s))
    if _is_html(s):
        return _collapse(_strip_html(s))
    return _collapse(s)


def _filter_style(style: str) -> str:
    keep = []
    for decl in style.split(";"):
        if ":" not in decl:
            continue
        prop, _, val = decl.partition(":")
        prop = prop.strip().lower()
        val = val.strip()
        if prop in {
            "color", "background-color", "font-weight", "font-style",
            "text-decoration", "text-align", "font-family", "font-size",
            "text-indent", "margin-left", "margin-top", "margin-bottom",
        } and not re.search(r"url\(|expression|javascript", val, re.I):
            keep.append(f"{prop}:{val}")
    return ";".join(keep)


def _sanitize(html: str) -> str:
    """HTML de módulo → HTML seguro para QTextDocument."""
    html = re.sub(r"(?is)<(script|style)\b.*?</\1>", "", html)
    # <ref>Jn 3:16</ref> → enlace interno clicable
    html = re.sub(
        r"(?is)<ref>(.*?)</ref>",
        lambda m: f'<a href="ref:{_html.escape(m.group(1).strip(), quote=True)}">'
                  f"{m.group(1)}</a>",
        html,
    )
    out = []
    for token in _TAG_SPLIT.split(html):
        if not token.startswith("<"):
            out.append(token)
            continue
        m = re.match(r"</?\s*([a-zA-Z][a-zA-Z0-9]*)", token)
        if not m:
            out.append(_html.escape(token))
            continue
        name = m.group(1).lower()
        closing = token.startswith("</")
        if name not in _ALLOWED:
            continue  # se descarta el tag, se conserva el contenido
        if closing:
            out.append(f"</{name}>")
            continue
        attrs = ""
        style = re.search(r'style\s*=\s*"([^"]*)"', token, re.I)
        if style:
            kept = _filter_style(style.group(1))
            if kept:
                attrs += f' style="{kept}"'
        href = re.search(r'href\s*=\s*"([^"]*)"', token, re.I)
        if href and name == "a":
            url = href.group(1)
            if url.startswith(("ref:", "http://", "https://")):
                attrs += f' href="{_html.escape(url, quote=True)}"'
        if name in _SELF_CLOSING:
            out.append(f"<{name}{attrs}>")
        else:
            out.append(f"<{name}{attrs}>")
    return "".join(out)


_BR_RUN = re.compile(r"(?:\s*<br\s*/?>\s*){3,}", re.I)
_EMPTY_P = re.compile(r"(?:<p[^>]*>\s*(?:&nbsp;|\s)*</p>\s*){2,}", re.I)


def _tidy(html: str) -> str:
    """Colapsa el relleno vertical que el RTF de e-Sword deja entre secciones."""
    html = _BR_RUN.sub("<br><br>", html)
    html = _EMPTY_P.sub("", html)
    return html.strip()


def to_rich(raw) -> str:
    """HTML para renderizar en la UI (conserva negritas, itálicas, colores)."""
    s = decode_raw(raw)
    if not s.strip():
        return ""
    if _is_rtf(s):
        rich = rtf_to_rich_text(s)
        if rich:
            return _tidy(_sanitize(rich))
        return _html.escape(_collapse(rtf_to_text(s))).replace("\n", "<br>")
    if _is_html(s):
        return _tidy(_sanitize(s))
    return _html.escape(s).replace("\n", "<br>")


def snippet(plain: str, max_chars: int = 260) -> str:
    """Recorte para listas de resultados."""
    text = re.sub(r"\s+", " ", plain or "").strip()
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    if " " in cut[80:]:
        cut = cut[: cut.rfind(" ")]
    return cut + "…"
