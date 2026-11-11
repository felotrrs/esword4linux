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

## Pseudo-tags de e-Sword (no son HTML)

`to_rich()` / `to_plain()` convierten 20 tags propios antes de sanear. Si se
tratan como texto plano, se muestran literalmente (`</red>`).

| Tag | Conversión |
|---|---|
| `<red>` | `<span style="color:#b03a2e">` |
| `<blu>` | azul |
| `<grk>`, `<gra>` | fuente con griego + itálica |
| `<heb>`, `<H>`, `<h>`, `<Hebr>` | fuente con hebreo |
| `<lat>`, `<trn>`, `<tvm>` | itálica |
| `<num>H1</num>` | `<a href="strong:H1">` |
| `<a href='#sG1645'>` | `<a href="strong:G1645">` |
| `<Pg>`, `<T>`, `<ST>`, `<st>`, `<BDB>`, `<bdb>`, `<TWOT>`, `<twot>`, `<SHE####>` | se eliminan, se conserva el texto |

`is_markup()` decide si un contenido es HTML real o pseudo-tag: sin ella,
`<red>…</red>` cae en la rama de texto plano y se escapa.

## Codepages y transliteraciones legacy

`to_plain(raw, hint)` / `to_rich(raw, hint)` reciben el **stem del módulo**.
Con él:

- `font_codepages_for(hint)` → `\f1`/`\f2` como cp1253/cp1255 (Vine NT/AT).
  Sin esto el griego sale `ἀðüèåóéò` en vez de `ἀπόθεσις`.
- `transliteration_for(hint)` + `apply_transliteration()` → glifos Latin-1 de
  Certeza.

Los ficheros vendorizados **no se modifican** (los vigila `make drift`); el
hint solo los activa.

## Burbujas

- Notas y referencias resuelven su texto **al pintar** y usan el atributo
  `title` de `<a>` (tooltip nativo de Qt).
- Los números Strong se resuelven **al pasar el ratón** (`RichBrowser`, 180 ms,
  caché) porque cada uno es un `SELECT` al léxico.
