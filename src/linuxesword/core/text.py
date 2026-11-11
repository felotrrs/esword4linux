"""Normalización de contenido e-Sword: RTF/HTML/pseudo-tags → plano y enriquecido.

Dos representaciones con propósitos distintos:

* **plano**  → se indexa en FTS5 (sin maquetación).
* **rico**   → se renderiza en Qt (QTextDocument entiende un subconjunto HTML).

e-Sword no solo usa RTF y HTML: muchos módulos traen **pseudo-tags propios**
(`<red>`, `<blu>`, `<grk>`, `<heb>`, `<num>`, `<Pg>`…). No son HTML y si se
tratan como texto plano acaban mostrándose literalmente (`</red>`), que es
exactamente el defecto que corrige `_convert_pseudo()`.

El texto de la fuente NUNCA se altera semánticamente: solo se decodifica la
presentación que e-Sword usa para mostrar.
"""

from __future__ import annotations

import html as _html
import re

from .esword.font_codepages import font_codepages_for
from .esword.legacy_translit import apply_transliteration, transliteration_for
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

# ── pseudo-tags de e-Sword ────────────────────────────────────────────────
# Nombre → estilo CSS. `None` = se elimina el tag y se conserva el contenido.
_PSEUDO_STYLE: dict[str, str | None] = {
    "red": "color:#b03a2e;",
    "blu": "color:#2f5d8a;",
    "grk": "font-family:'DejaVu Sans','Noto Sans',serif;font-style:italic;",
    "gra": "font-family:'DejaVu Sans','Noto Sans',serif;font-style:italic;",
    "heb": "font-family:'DejaVu Sans','Noto Sans',serif;",
    "H": "font-family:'DejaVu Sans','Noto Sans',serif;",
    "h": "font-family:'DejaVu Sans','Noto Sans',serif;",
    "Hebr": "font-family:'DejaVu Sans','Noto Sans',serif;",
    "lat": "font-style:italic;",
    "trn": "font-style:italic;",
    "tvm": "font-style:italic;",
    "Pg": None,
    "T": None,
    "ST": None,
    "st": None,
    "BDB": None,
    "bdb": None,
    "TWOT": None,
    "twot": None,
}

_PSEUDO_NAMES = "|".join(sorted((k for k in _PSEUDO_STYLE), key=len, reverse=True))
_PSEUDO_RE = re.compile(rf"(?is)<\s*(/?)\s*({_PSEUDO_NAMES})\s*>")
_PSEUDO_SHE_RE = re.compile(r"(?is)</?\s*SHE\d{2,5}\s*>")
_NUM_RE = re.compile(r"(?is)<num>\s*([GHgh]\d{1,5})\s*</num>")
_STRONG_ANCHOR_RE = re.compile(
    r"""(?is)<a\b[^>]*href\s*=\s*['"]#s([GHgh]\d{1,5})['"][^>]*>.*?</a>"""
)
_STRONG_COLOR = "#8f6bc4"
_STRONG_STYLE = f"color:{_STRONG_COLOR};font-size:78%;text-decoration:none;"


def _strong_anchor(code: str) -> str:
    code = code.upper()
    return f'<a href="strong:{code}" style="{_STRONG_STYLE}">{code}</a>'


def _convert_pseudo(text: str) -> str:
    """Pseudo-tags e-Sword → HTML semántico (o se eliminan conservando texto)."""
    text = _NUM_RE.sub(lambda m: _strong_anchor(m.group(1)), text)
    # Strong como enlace interno: <a href='#sG1645'>G1645</a>
    text = _STRONG_ANCHOR_RE.sub(lambda m: _strong_anchor(m.group(1)), text)

    def _span(match: re.Match) -> str:
        closing, raw_name = match.group(1), match.group(2)
        # los nombres pueden venir en distinta caja (Hb vs hb)
        name = raw_name if raw_name in _PSEUDO_STYLE else raw_name.capitalize()
        style = _PSEUDO_STYLE.get(name, None)
        if style is None:
            return ""
        return "</span>" if closing else f'<span style="{style}">'

    text = _PSEUDO_RE.sub(_span, text)
    text = _PSEUDO_SHE_RE.sub("", text)
    return text


def is_markup(text: str) -> bool:
    """True si el contenido trae HTML real o pseudo-tags de e-Sword."""
    if not text:
        return False
    return bool(_is_html(text) or _PSEUDO_RE.search(text) or _NUM_RE.search(text))


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


def _codepages(hint: str) -> dict[int, str]:
    return font_codepages_for(hint) if hint else {}


def _legacy(text: str, hint: str) -> str:
    """Transliteración legacy por fuente (p. ej. Certeza)."""
    mapping = transliteration_for(hint) if hint else {}
    return apply_transliteration(text, mapping) if mapping else text


def to_plain(raw, hint: str = "") -> str:
    """Texto plano para indexar (sin RTF, sin HTML, sin formato).

    `hint` es el stem del módulo; activa los codepages legacy (cp1253/cp1255)
    y las transliteraciones por fuente.
    """
    s = decode_raw(raw)
    if not s.strip():
        return ""
    if _is_rtf(s):
        return _collapse(_legacy(rtf_to_text(s, codepages=_codepages(hint)), hint))
    if is_markup(s):
        return _collapse(_strip_html(_convert_pseudo(_legacy(s, hint))))
    return _collapse(_legacy(s, hint))


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


_SAFE_SCHEMES = ("ref:", "strong:", "note:", "http://", "https://")


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
        if name == "a":
            href = re.search(r'href\s*=\s*"([^"]*)"', token, re.I)
            if href:
                url = href.group(1)
                if url.startswith(_SAFE_SCHEMES):
                    attrs += f' href="{_html.escape(url, quote=True)}"'
            title = re.search(r'title\s*=\s*"([^"]*)"', token, re.I)
            if title:
                attrs += f' title="{_html.escape(title.group(1), quote=True)}"'
        out.append(f"<{name}{attrs}>")
    return "".join(out)


_BR_RUN = re.compile(r"(?:\s*<br\s*/?>\s*){3,}", re.I)
_EMPTY_P = re.compile(r"(?:<p[^>]*>\s*(?:&nbsp;|\s)*</p>\s*){2,}", re.I)


def _tidy(html: str) -> str:
    """Colapsa el relleno vertical que el RTF de e-Sword deja entre secciones."""
    html = _BR_RUN.sub("<br><br>", html)
    html = _EMPTY_P.sub("", html)
    return html.strip()


def to_rich(raw, hint: str = "") -> str:
    """HTML para renderizar en la UI (conserva negritas, itálicas, colores)."""
    s = decode_raw(raw)
    if not s.strip():
        return ""
    if _is_rtf(s):
        rich = rtf_to_rich_text(s, codepages=_codepages(hint))
        if rich:
            return _tidy(_sanitize(_convert_pseudo(rich)))
        plain = _legacy(rtf_to_text(s, codepages=_codepages(hint)), hint)
        return _html.escape(_collapse(plain)).replace("\n", "<br>")
    if is_markup(s):
        return _tidy(_sanitize(_convert_pseudo(_legacy(s, hint))))
    return _html.escape(_legacy(s, hint)).replace("\n", "<br>")


def snippet(plain: str, max_chars: int = 260) -> str:
    """Recorte para listas de resultados."""
    text = re.sub(r"\s+", " ", plain or "").strip()
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    if " " in cut[80:]:
        cut = cut[: cut.rfind(" ")]
    return cut + "…"
