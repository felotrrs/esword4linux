# RTF → texto legible (módulos e-Sword)
#
# Regla: el procesamiento RTF es solamente una decodificación de presentación
# necesaria para recuperar el texto que e-Sword presenta al usuario. No es
# traducción, edición, resumen, reordenamiento ni interpretación.
#
# Responsabilidad EXCLUSIVA: RTF → texto. NO conoce SQLite ni BDL.
#
# Contrato:
#   * \par, \line → salto de línea.
#   * \'XX → carácter cp1252 (objetivo ES).
#   * \uN → Unicode con gestión del fallback (sin duplicación).
#   * grupos {} anidados (incluye destino \* y fonttbl/colortbl/etc, que se
#     ignoran por completo).
#   * \b \i \ul \cf \f \fs \lang ... → sintaxis eliminada, texto conservado.
#   * tablas (\trowd \cell \row) → texto con separadores claros.
#   * control desconocido → sintaxis eliminada, contenido textual conservado;
#     si puede afectar fidelidad → warning (nunca pérdida silenciosa).
#   * entrada no-RTF → passthrough sin tocar.

from __future__ import annotations

import re
from typing import List, Tuple

_WARNING_ITEM = None

# Destinos RTF cuyo contenido íntegro debe ignorarse (tablas de fuentes,
# colores, imágenes, campos, metadatos...).
_SKIP_DESTINATIONS = {
    "fonttbl", "colortbl", "stylesheet", "info", "pict", "nonshppict",
    "header", "footer", "footnote", "field", "object", "fldinst", "fldrslt",
    "data", "bin", "revtbl", "listtable", "listoverridetable", "themedata",
    "colorschememapping", "pn", "bkmkstart", "bkmkend", "xe", "tc",
}

# Controles de símbolo simples (una sola letra tras `\`).
_SYMBOL_ESCAPES = {
    "~": "\u00A0",  # espacio no separable
    "-": "-",       # guión opcional
    "_": "\u00A0",  # guión no separable
    " ": " ",       # espacio literal
}

# Controles que producen salto de línea.
_BREAK_CONTROLS = {"par", "line", "sect", "page"}

# Símbolos básicos (representación textual; es decodificación, no edición).
_SYMBOL_WORDS = {
    "tab": "\t",
    "emdash": "\u2014",
    "endash": "\u2013",
    "bullet": "\u2022",
    "lquote": "\u2018",
    "rquote": "\u2019",
    "ldblquote": "\u201C",
    "rdblquote": "\u201D",
}


def _is_rtf(text: str) -> bool:
    """Heurística: si el contenido parece RTF.

    e-Sword almacena a veces fragmentos RTF SIN cabecera `{\rtf1` (p. ej.
    comienzan con `\\par` o `{\\b`), y en `.bblx` fragmentos RTF EMBEBIDOS en
    texto que empieza plano (`... {\\cf15\\I was} ...`). Detectamos la
    presencia de controles RTF inequívocos en todo el texto, no solo al inicio.
    """
    if not text or not text.strip():
        return False
    head = text.lstrip()[:40]
    if head.startswith("{\\rtf") or head.startswith("{\\urtf") \
            or head.startswith("\\rtf"):
        return True
    # fragmentos RTF embebidos: grupo `{\...` en cualquier posición
    if re.search(r"\{(?:\\\*)?\\[A-Za-z]", text):
        return True
    # `\par` puede aparecer después de los primeros 200 chars (Certeza y
    # otros módulos guardan fragmentos RTF sin cabecera).
    if re.search(r"\\par\b", text):
        return True
    # controles RTF que no aparecen en texto plano normal (primeros 200 chars
    # + barridos en todo el texto para \cf / \fs / \par embebidos)
    if re.search(
        r"\\(?:par|pard|rtf|u\d|\'\w{2}|b(?:\s|\d|\\|\{)|i(?:\s|\d|\\|\{))",
        text[:200],
    ):
        return True
    return bool(re.search(r"\\(?:cf\d+|fs\d+|lang\d+)(?:\s|\d|\\|\{)", text))


def _is_html(text: str) -> bool:
    """Heurística: si el contenido parece HTML.

    Algunos módulos e-Sword (.dctx) almacenan definiciones como HTML en
    lugar de RTF. Se detecta la presencia de tags HTML comunes en TODO el
    texto (no solo el inicio): hay definiciones que comienzan con texto
    plano y las etiquetas aparecen más adelante.
    """
    if not text or not text.strip():
        return False
    return bool(re.search(
        r"</?(?:p|div|span|br|table|tr|td|b|i|u|em|strong|sup|sub|a|ref|font)\b",
        text, re.I))


def _strip_html(text: str) -> str:
    """Elimina tags HTML y decodifica entidades, conservando solo texto plano.

    NO modifica el contenido textual — solo elimina la maquetación HTML.
    Tags de bloque (p, div, br) se convierten a saltos de línea.
    Tags inline (span, ref, b, i, u, font) se eliminan directamente.
    """
    if not text:
        return ""
    from html import unescape
    # tags de bloque → salto de línea antes de eliminarlos
    clean = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    clean = re.sub(r"</(?:p|div|h[1-6])>", "\n", clean, flags=re.I)
    # eliminar todos los tags restantes (incluyendo <ref>)
    clean = re.sub(r"<[^>]+>", "", clean)
    # decodificar entidades HTML (&nbsp; &amp; &lt; etc.)
    clean = unescape(clean)
    # normalizar &nbsp; (\xa0) a espacio normal
    clean = clean.replace("\xa0", " ")
    # colapsar espacios múltiples (preservando saltos de línea)
    clean = re.sub(r"[^\S\n]+", " ", clean)
    # colapsar líneas vacías
    clean = re.sub(r"\n\s*\n", "\n", clean)
    return clean.strip()


def rtf_to_text(rtf: str, warnings: list | None = None,
                codepages: dict[int, str] | None = None) -> str:
    """Convierte RTF o HTML a texto plano.

    Detecta el formato y aplica la conversión apropiada:
    - RTF → decodificación completa (parser dedicado).
    - HTML → strip de tags + decodificación de entidades.
    - Texto plano → passthrough sin modificar.

    `codepages` mapea `\\fN → codepage` para fuentes legacy (p. ej. Vine:
    `{1: "cp1253", 2: "cp1255"}`). Sin mapa, `\\'XX` se decodifica cp1252.

    Los warnings (estructuras no soportadas que afectan fidelidad) se agregan
    a la lista `warnings` si se pasa (lista de dicts `{level, code, message}`).
    """
    if not rtf or not rtf.strip():
        return rtf

    if _is_rtf(rtf):
        wlist = warnings if warnings is not None else []
        parser = _RtfParser(rtf, wlist, codepages=codepages)
        return parser.parse()

    if _is_html(rtf):
        return _strip_html(rtf)

    return rtf


class _RtfParser:
    def __init__(self, text: str, warnings: list,
                 codepages: dict[int, str] | None = None):
        self.s = text
        self.i = 0
        self.n = len(text)
        self.out: List[str] = []
        self.warnings = warnings
        # pila de grupos: True si el grupo debe ignorarse por completo
        self.group_stack: List[bool] = []
        # Fuente actual (`\fN`) y codepage legacy por fuente. El estado \fN es
        # parte del formato de carácter y se guarda/restaura por grupo.
        self.codepages = dict(codepages or {})
        self.font = 0
        self.rtl = False
        self._font_stack: List[tuple[int, bool]] = []

    def parse(self) -> str:
        while self.i < self.n:
            c = self.s[self.i]
            if c == "{":
                self._open_group()
            elif c == "}":
                self._close_group()
            elif c == "\\":
                self._control()
            elif c in "\r\n\t":
                self.i += 1  # whitespace crudo del fichero (no contenido)
            else:
                if not self._in_skip():
                    self.out.append(c)
                self.i += 1
        return "".join(self.out).strip()

    # ── grupos ────────────────────────────────────────────────────────────

    def _in_skip(self) -> bool:
        return any(self.group_stack)

    def _open_group(self):
        self.i += 1  # consume {
        self._font_stack.append((self.font, self.rtl))
        skip = False
        # \* → destino a saltar
        if self.s.startswith("\\*", self.i):
            skip = True
        else:
            m = re.match(r"\\([A-Za-z]+)", self.s[self.i:])
            if m and m.group(1).lower() in _SKIP_DESTINATIONS:
                skip = True
        self.group_stack.append(skip)
        # si el grupo es destino de salto, consumir el control y dejar que el
        # bucle principal ignore el resto del grupo.

    def _close_group(self):
        self.i += 1  # consume }
        if self.group_stack:
            self.group_stack.pop()
        if self._font_stack:
            self.font, self.rtl = self._font_stack.pop()

    # ── controles ─────────────────────────────────────────────────────────

    def _control(self):
        self.i += 1  # consume backslash
        if self.i >= self.n:
            return
        c = self.s[self.i]

        # caracteres escapados literales
        if c in "\\{}":
            if not self._in_skip():
                self.out.append(c)
            self.i += 1
            return

        # símbolos de una letra
        if c in _SYMBOL_ESCAPES:
            if not self._in_skip():
                self.out.append(_SYMBOL_ESCAPES[c])
            self.i += 1
            return

        # \'XX hex: cp1252 por defecto; cp1253/cp1255 si `\fN` lo declara
        if c == "'":
            hexs = self.s[self.i + 1:self.i + 3]
            self.i += 3
            if not self._in_skip() and len(hexs) == 2:
                enc = self.codepages.get(self.font)
                if not enc and self.rtl:
                    enc = "cp1255"
                enc = enc or "cp1252"
                try:
                    raw = bytes.fromhex(hexs)
                    self.out.append(raw.decode(enc))
                except (ValueError, LookupError, UnicodeDecodeError):
                    try:
                        self.out.append(bytes.fromhex(hexs).decode("cp1252"))
                    except (ValueError, UnicodeDecodeError):
                        self._warn("rtf_hex_invalid", f"hex inválido \\'{hexs}")
            return

        # \* dentro de grupo (ya gestionado en _open_group)
        if c == "*":
            self.i += 1
            return

        # Un `\` seguido de un carácter no-ASCII no es un control RTF válido
        # (p. ej. RTF mal codificado en la fuente: `\é`, `\‡`). Se descarta
        # solo la barra y el carácter se conserva como contenido textual.
        if not c.isascii():
            return

        # control con palabra (solo letras ASCII)
        if c.isalpha():
            self._control_word()
            return

        # cualquier otro control de un carácter (p. ej. `\ `) → ignorar
        self.i += 1

    def _control_word(self):
        m = re.match(r"([A-Za-z]+)", self.s[self.i:])
        if not m:
            self.i += 1
            return
        word = m.group(1)
        self.i += len(word)

        neg = False
        if self.i < self.n and self.s[self.i] == "-":
            neg = True
            self.i += 1
        num = ""
        while self.i < self.n and self.s[self.i].isdigit():
            num += self.s[self.i]
            self.i += 1

        # separador espacio tras el control (se consume, no es contenido)
        if self.i < self.n and self.s[self.i] == " ":
            self.i += 1

        wl = word.lower()
        if self._in_skip():
            return

        if wl in _BREAK_CONTROLS:
            self.out.append("\n")
        elif wl == "f":
            # `\fN` selecciona la fuente; las legacy (cp1253/cp1255) se
            # resuelven al decodificar `\'XX`.
            try:
                self.font = int(num or 0)
            except ValueError:
                self.font = 0
        elif wl == "rtlch":
            self.rtl = True
        elif wl == "ltrch":
            self.rtl = False
        elif wl == "cell":
            self.out.append(" | ")
        elif wl == "row":
            self.out.append("\n")
        elif wl == "tab":
            self.out.append("\t")
        elif wl in _SYMBOL_WORDS:
            self.out.append(_SYMBOL_WORDS[wl])
        elif wl == "u":
            self._unicode_escape(neg, num)
        elif wl == "uc":
            pass  # número de chars de fallback tras \u — irrelevante aquí
        elif wl == "pict":
            self._warn("rtf_pict", "imagen \\pict omitida del texto")
        else:
            # control de formato desconocido → sintaxis eliminada, el texto
            # asociado se conserva (el bucle principal sigue leyéndolo).
            pass

    def _unicode_escape(self, neg: bool, num: str):
        r"""\uN → code point; descarta el fallback de un carácter (sin duplicar).

        El separador espacio tras el número ya fue consumido por
        `_control_word`. El fallback (si existe) es `?`, o una secuencia
        `\'XX`, o el carácter real en la fuente del cliente. Para no comer
        texto legítimo se descarta SOLO el fallback inequívoco: `?` o `\'XX`.
        Un carácter de letra/dígito que sigue se conserva (es contenido real).
        """
        try:
            val = int(num) if num else 0
        except ValueError:
            return
        if neg:
            val = -val
        cp = val & 0xFFFF
        try:
            self.out.append(chr(cp))
        except (ValueError, OverflowError):
            return
        if self.i >= self.n:
            return
        # fallback `?` (placeholder estándar RTF)
        if self.s[self.i] == "?":
            self.i += 1
            return
        # fallback `\'XX` (carácter cp1252 que representa el mismo Unicode)
        if self.s.startswith("\\'", self.i) and self.i + 3 <= self.n:
            self.i += 3
            return

    def _warn(self, code: str, message: str):
        self.warnings.append({"level": "warning", "code": code, "message": message})


def extract_refs(text: str) -> list[str]:
    """Extrae referencias de tags <ref> del texto, preservando el orden.

    Retorna lista de strings con las referencias encontradas (sin duplicados,
    manteniendo orden de aparición). Ejemplo:
        '<ref>Mat 16:24</ref>; <ref>Mar 8:34</ref>' → ['Mat 16:24', 'Mar 8:34']
    """
    if not text:
        return []
    refs = []
    for m in re.finditer(r"<ref>([^<]+)</ref>", text):
        ref = m.group(1).strip()
        if ref and ref not in refs:
            refs.append(ref)
    return refs


def html_to_bdl_safe(html: str) -> str | None:
    """Sanitiza y preserva el HTML enriquecido semántico para el campo rich_text en BDL.

    Preserva etiquetas semánticas: <ref>, <b>, <strong>, <i>, <em>, <u>, <sup>, <sub>, <a>, <p>, <br>.
    Transforma enlaces Strong's a formato canónico <a href="strongs:G26">G26</a> o <span class="strongs-code" data-strongs="G26"><sup>G26</sup></span>.
    Si no existen etiquetas semánticas de valor, retorna None (sin contaminar BDL).
    """
    if not html or not html.strip() or not _is_html(html):
        return None
    return _sanitize_html(html)


def _sanitize_html(html: str) -> str | None:
    """Limpia/estructura un HTML ya identificado como tal. Retorna None si el
    resultado es texto plano trivial (sin semántica de valor)."""
    # Convertir tabs a 4 espacios (HTML colapsa tabs a espacios por defecto)
    clean = html.replace('\t', '    ')

    # Normalizar Strong's URLs si existen (ej. sword://StrongsGreek/0026 -> strongs:G26)
    clean = re.sub(
        r'href=["\'](?:sword://)?Strongs(?:Greek|Hebrew)/0*([A-Za-z0-9]+)["\']',
        r'href="strongs:\1"',
        clean,
        flags=re.I,
    )

    # Eliminar tags peligrosos o irrelevantes (script, style, font, div no semánticos)
    clean = re.sub(r"<(?:script|style|font)\b[^>]*>.*?</(?:script|style|font)>", "", clean, flags=re.I | re.S)

    # Spans Strong's → anclas canónicas <a href="strongs:XX">…</a>; el resto de
    # spans (no semánticos) se eliminan por completo (se conserva el contenido).
    clean = re.sub(
        r"<span\b[^>]*\bdata-strongs=[\"\']([A-Za-z0-9]+)[\"\'][^>]*>(.*?)</span>",
        r'<a href="strongs:\1">\2</a>',
        clean, flags=re.I | re.S,
    )
    clean = re.sub(r"</?span\b[^>]*>", "", clean, flags=re.I)
    
    # Remover atributos inseguros (style, class except strongs-code, onclick, etc)
    def _clean_attrs(match):
        tag_content = match.group(1)
        is_close = match.group(0).startswith("</")
        tag_name = tag_content.lstrip("/").split()[0].lower()
        if is_close:
            if tag_name in ("ref", "b", "strong", "i", "em", "u", "sup", "sub", "p", "a", "br"):
                return f"</{tag_name}>"
            return ""
        if tag_name == "ref":
            return f"<{tag_content}>"
        if tag_name == "a":
            href_m = re.search(r'href=["\']([^"\']+)["\']', tag_content)
            if href_m:
                return f'<a href="{href_m.group(1)}">'
            return "<a>"
        if tag_name in ("b", "strong", "i", "em", "u", "sup", "sub", "p", "br"):
            return f"<{tag_name}>"
        return ""  # tag no permitido → se elimina (el contenido se conserva)

    # Filtrar solo tags permitidos
    allowed_tags = {"ref", "b", "strong", "i", "em", "u", "sup", "sub", "a", "p", "br"}
    clean = re.sub(r"</?([A-Za-z][^>]*)>", lambda m: _clean_attrs(m), clean)
    
    # Verificar si contiene al menos una etiqueta semántica de valor
    # (br/p por sí solos NO cuentan: son solo estructura de párrafo).
    semantic_tags = {"ref", "b", "strong", "i", "em", "u", "sup", "sub", "a"}
    has_semantic = bool(re.search(
        r"</?(?:" + "|".join(semantic_tags) + r")\b", clean, re.I))
    if not has_semantic:
        return None

    return clean.strip()


def rtf_to_rich_text(rtf: str, warnings: list | None = None,
                      codepages: dict[int, str] | None = None) -> str | None:
    r"""Convierte RTF a HTML enriquecido semántico para el campo rich_text en BDL.

    Conserva negritas (\b), itálicas (\i), subrayado (\ul), super/subíndice
    (\super / \sub) y cualquier tag HTML embebido (p. ej. <ref>). Si el input
    no es RTF (HTML o texto plano) se delega en html_to_bdl_safe. Retorna None
    cuando el resultado es texto plano trivial (sin semántica de valor).
    """
    if not rtf or not rtf.strip():
        return None
    if not _is_rtf(rtf):
        return html_to_bdl_safe(rtf)
    wlist = warnings if warnings is not None else []
    parser = _RtfHtmlParser(rtf, wlist, codepages=codepages)
    html = parser.parse()
    return _sanitize_html(html)


class _RtfHtmlParser(_RtfParser):
    r"""Parser RTF que preserva formato semántico como HTML (no solo texto).

    Emite <b>, <i>, <u>, <sup>, <sub> según los controles RTF de formato y
    mantiene la anidación bien formada (los tags se cierran en orden inverso
    cuando un formato activo termina). El resto del contrato RTF es idéntico
    al parser de texto plano (saltos, cp1252, \uN, tablas...).

    RTF group semantics: los grupos {} guardan/restauran el estado de formato.
    Un \ul encendido dentro de un grupo se apaga automáticamente al cerrar }.
    """

    # control RTF → (clave de formato, tag HTML). \u es escape unicode (lo
    # maneja la base); el subrayado es \ul.
    _HTML_TAG = {"b": ("b", "b"), "i": ("i", "i"), "ul": ("u", "u")}

    def __init__(self, text: str, warnings: list,
                 codepages: dict[int, str] | None = None):
        super().__init__(text, warnings, codepages=codepages)
        self._fmt_on: dict[str, bool] = {"b": False, "i": False, "u": False,
                                         "sup": False, "sub": False}
        self._tag_stack: list[str] = []
        # Stack para snapshots de estado por grupo (RTF group semantics)
        self._group_fmt_stack: list[tuple[dict[str, bool], list[str]]] = []

    def _open_group(self):
        # Snapshot当前 estado de formato ANTES de entrar al grupo
        fmt_snapshot = dict(self._fmt_on)
        tag_snapshot = list(self._tag_stack)
        self._group_fmt_stack.append((fmt_snapshot, tag_snapshot))
        super()._open_group()

    def _close_group(self):
        super()._close_group()
        # Restaurar estado de formato del snapshot
        if self._group_fmt_stack:
            saved_fmt, saved_tags = self._group_fmt_stack.pop()
            # Cerrar tags que se abrieron dentro del grupo
            while self._tag_stack and (not saved_tags or self._tag_stack[-1] != saved_tags[-1]):
                tag = self._tag_stack.pop()
                self._fmt_on[tag] = False
                self.out.append(f"</{tag}>")
            # Restaurar estado exacto
            self._fmt_on.update(saved_fmt)
            if saved_tags:
                self._tag_stack[:] = saved_tags

    def _control_word(self):
        m = re.match(r"([A-Za-z]+)", self.s[self.i:])
        if not m:
            self.i += 1
            return
        word = m.group(1)
        wl = word.lower()

        idx = self.i + len(word)
        if idx < self.n and self.s[idx] == "-":
            idx += 1
        num = ""
        while idx < self.n and self.s[idx].isdigit():
            num += self.s[idx]
            idx += 1
        if idx < self.n and self.s[idx] == " ":
            idx += 1  # separador tras el control (no contenido)

        if self._in_skip():
            self.i = idx
            return

        if wl in self._HTML_TAG:
            self.i = idx
            key, tag = self._HTML_TAG[wl]
            self._set_fmt(key, tag, num != "0")
            return
        if wl in ("super", "sub", "nosupersub"):
            self.i = idx
            if wl == "super":
                self._set_fmt("sup", "sup", True)
            elif wl == "sub":
                self._set_fmt("sub", "sub", True)
            else:
                self._set_fmt("sup", "sup", False)
                self._set_fmt("sub", "sub", False)
            return
        if wl in _BREAK_CONTROLS:
            self.i = idx
            self.out.append("<br>")
            return
        if wl in ("cell", "row"):
            self.i = idx
            self.out.append(" | " if wl == "cell" else "<br>")
            return
        if wl in _SYMBOL_WORDS:
            self.i = idx
            self.out.append(_SYMBOL_WORDS[wl])
            return
        if wl == "tab":
            self.i = idx
            self.out.append("\t")
            return
        if wl == "pict":
            self.i = idx
            self._warn("rtf_pict", "imagen \\pict omitida del texto")
            return

        # resto (uN, controles de formato desconocido, etc.) → comportamiento base
        super()._control_word()

    def _set_fmt(self, key: str, tag: str, on: bool):
        # sup/sub son mutuamente excluyentes
        if key == "sup" and on:
            self._set_fmt("sub", "sub", False)
        elif key == "sub" and on:
            self._set_fmt("sup", "sup", False)
        if on:
            if self._fmt_on[key]:
                return
            self._fmt_on[key] = True
            self._tag_stack.append(tag)
            self.out.append(f"<{tag}>")
        else:
            if not self._fmt_on[key]:
                return
            self._fmt_on[key] = False
            self._close_tag(tag)

    def _close_tag(self, tag: str):
        if tag not in self._tag_stack:
            return
        while self._tag_stack:
            t = self._tag_stack.pop()
            self._fmt_on[t] = False
            self.out.append(f"</{t}>")
            if t == tag:
                break

    def parse(self) -> str:
        super().parse()  # procesa todo; self.out conserva el contenido
        # cerrar formato abierto al final (nunca dejar HTML sin cerrar)
        while self._tag_stack:
            self.out.append(f"</{self._tag_stack.pop()}>")
        return "".join(self.out).strip()



def self_test() -> bool:
    """Criterios del contrato RTF/HTML (DoD)."""
    def check(label, rtf, expected, expect_warning=False):
        warnings: list = []
        got = rtf_to_text(rtf, warnings)
        assert got == expected, f"[{label}] got={got!r} esperado={expected!r}"
        if expect_warning:
            assert warnings, f"[{label}] debería emitir warning"
        return got

    # \par → salto
    check("par", r"{\rtf1\ansi Hola\par Mundo}", "Hola\nMundo")
    # \line → salto
    check("line", r"{\rtf1\ansi A\line B}", "A\nB")
    # \'XX cp1252 español
    check("cp1252", r"{\rtf1\ansi \'e9\'ed\'f1\'f1}", "éíññ")
    # \uN con fallback ? → sin duplicación
    check("uN", r"{\rtf1\ansi caf\u233?}", "café")
    # \uN negativo (codepoint > 32767 se codifica como N-65536)
    check("uNneg", r"{\rtf1\ansi \u-241?", chr(0xFF0F))
    # acentos por ambos métodos
    check("espanol", r"{\rtf1\ansi \u225? \'e1 \u237? \'ed}", "á á í í")
    # controles de formato eliminados (el espacio tras el control es delimitador)
    check("formato", r"{\rtf1\ansi \b negrita\b0 \i italica\i0 \cf2\fs20 x}", "negritaitalicax")
    # grupos anidados de formato
    check("grupos", r"{\rtf1\ansi a {\b {\i b}} c}", "a b c")
    # fonttbl/colortbl ignorados íntegramente
    check("fonttbl", r"{\rtf1\ansi{\fonttbl{\f0\fnil Arial;}}{\colortbl;\red0\green0\blue0;}text}", "text")
    # \* destino ignorado
    check("asterisco", r"{\rtf1\ansi hola{\*\bkmkstart x} mundo}", "hola mundo")
    # tablas básicas
    check("tabla", r"{\rtf1\ansi\trowd\cell c1\cell c2\row fin}", "| c1 | c2\nfin")
    # control desconocido no contamina
    check("unknown", r"{\rtf1\ansi \fancyword123 texto}", "texto")
    # \pict (imagen) en grupo → se salta íntegro, texto alrededor conservado
    check("pict", r"{\rtf1\ansi antes{\*\pict\pngblip 89504e47}despues}", "antesdespues")
    # passthrough no-RTF
    check("plain", "Texto plano sin RTF, 100% literal.", "Texto plano sin RTF, 100% literal.")

    # \uN sin fallback (RTF que omite placeholder) no consume texto siguiente
    got = rtf_to_text(r"{\rtf1\ansi \u233 xyz}")
    assert got == "éxyz", f"[uNsinfallback] got={got!r}"

    # ── HTML tests ───────────────────────────────────────────────────────
    # HTML básico → texto plano
    check("html_basic", "<p>Hola mundo</p>", "Hola mundo")
    # HTML con estilos → solo texto
    check("html_style",
          '<p lang="es-ES" style="font-weight:bold;">Texto</p>',
          "Texto")
    # HTML con &nbsp; → espacio normal
    check("html_nbsp", "<p>Hola&nbsp;mundo</p>", "Hola mundo")
    # HTML con <ref> → tags eliminados (refs se extraen por separado)
    check("html_ref",
          "<p>Texto <ref>Mat 16:24</ref> y <ref>Mar 8:34</ref>.</p>",
          "Texto Mat 16:24 y Mar 8:34.")
    # HTML multi-párrafo
    check("html_multi",
          "<p>Primero</p><p>Segundo</p>",
          "Primero\nSegundo")
    # No-HTML no se toca
    check("html_passthrough", "Texto plano sin HTML.", "Texto plano sin HTML.")

    # ── extract_refs tests ───────────────────────────────────────────────
    refs = extract_refs("<ref>Mat 16:24</ref>; <ref>Mar 8:34</ref>")
    assert refs == ["Mat 16:24", "Mar 8:34"], f"[extract_refs] got={refs!r}"

    refs2 = extract_refs("Sin tags aqui")
    assert refs2 == [], f"[extract_refs_empty] got={refs2!r}"

    refs3 = extract_refs("")
    assert refs3 == [], f"[extract_refs_empty_str] got={refs3!r}"

    # deduplicados
    refs4 = extract_refs("<ref>Mat 16:24</ref> <ref>Mat 16:24</ref>")
    assert refs4 == ["Mat 16:24"], f"[extract_refs_dedup] got={refs4!r}"

    return True


if __name__ == "__main__":
    if self_test():
        print("RTF/HTML self-test OK")
