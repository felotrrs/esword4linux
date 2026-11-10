# Renderizado — RTF/HTML, tipografía y temas

## Dos representaciones

| Función | Salida | Uso |
|---|---|---|
| `text.to_plain(raw)` | texto sin formato | indexar en FTS5 |
| `text.to_rich(raw)` | HTML seguro para Qt | mostrar en pantalla |

**Nunca** se indexa `to_rich()` (metería tags en el índice) y **nunca** se
muestra `to_plain()` en la Biblia (perdería negritas, itálicas y letras rojas).

## Cadena de `to_rich`

```
raw (str | bytes)
  ├─ _is_rtf  → rtf_to_rich_text() → _sanitize() → _tidy()
  ├─ _is_html → _sanitize() → _tidy()
  └─ plano    → html.escape() + <br>
```

- `_sanitize` elimina `<script>`/`<style>`, descarta tags fuera de `_ALLOWED`
  (conservando el texto), filtra `style` a propiedades inocuas y convierte
  `<ref>X</ref>` en `<a href="ref:X">X</a>`.
- `_tidy` colapsa `(<br>){3,}` a dos y elimina `<p>` vacíos: el RTF de e-Sword
  deja decenas de saltos entre secciones y sin esto la lectura queda llena de
  huecos.

## RTF de e-Sword

- Frecuentemente **sin cabecera** `{\rtf1`: empieza en `\pard` o contiene
  grupos `{\b ...}` embebidos en texto plano. `_is_rtf` lo detecta.
- Codepage por defecto `cp1252`; griego/hebreo con fuentes de 8 bits requieren
  `font_codepages.py` / `legacy_translit.py` (vendorizados, aún no conectados a
  la UI: ver `documentacion/TECH_DEBT.md`).

## Tipografía

- Escritura: serif (`Noto Serif`, fallback `DejaVu Serif`). Se aplica con
  `.scripture { font-family: ... }` en `document_css`.
- UI: sans (`Noto Sans`, `DejaVu Sans`).
- Tamaño base en `Settings.font_size` (15 por defecto). Todo el CSS deriva de él.

## Temas

`ui/theme.py` es la **única fuente** de color:

- `LIGHT` / `DARK`: `Palette` con `bg, panel, text, muted, accent, link,
  highlight, comment_bg, verse_num`.
- `stylesheet(theme, font_size)` → QSS de la app.
- `document_css(theme, font_size, serif)` → CSS embebido en cada `QTextBrowser`.

Añadir un color = añadirlo a **ambas** paletas y usarlo desde `palette()`.
No escribir hex sueltos en las vistas.

## Reglas

1. Un `QTextBrowser` nuevo **debe** llamar a
   `document().setDefaultStyleSheet(document_css(...))` y refrescarlo en
   `reload_theme()`.
2. Nada de HTML del módulo sin `to_rich()`. Es la única frontera de saneado.
3. El bloque de comentario usa una `<table>` con `border-left`: es la forma
   fiable de dibujar la barra de acento en `QTextDocument` (los `div` con
   borde no se renderizan bien).
4. Los enlaces internos usan esquemas propios (`v:`, `c:`, `ref:`, `hit:`,
   `goref:`) y `setOpenLinks(False)` + `anchorClicked`. Nunca `http` para
   navegación interna.
