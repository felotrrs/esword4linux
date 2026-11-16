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
- `_sanitize` equilibra tags: un cierre huérfano de bloque (`</p>` sin `<p>`)
  se convierte en `<br>`; los cierres inline huérfanos se descartan. Sin esto,
  datos como RVR1960x partían un versículo en dos bloques con hueco vertical.

## RTF de e-Sword

- Frecuentemente **sin cabecera** `{\rtf1`: empieza en `\pard` o contiene
  grupos `{\b ...}` embebidos en texto plano. `_is_rtf` lo detecta.
- Codepage por defecto `cp1252`; griego/hebreo con fuentes de 8 bits requieren
  `font_codepages.py` / `legacy_translit.py` (vendorizados, aún no conectados a
  la UI: ver `documentacion/TECH_DEBT.md`).

## Tipografía

Tres roles independientes, editables en **Editar → Preferencias**:

- **Interfaz**: `Settings.ui_font_family` / `ui_font_size` (13 px por defecto).
  Alimenta `app.setFont()` y `ui_stylesheet(settings)`.
- **Escritura**: `Settings.font_family` / `font_size` (Noto Serif, 15 px).
  Se aplica con `.scripture` y los títulos en `document_css`.
- **Texto corriente**: `Settings.content_font_family` / `content_font_size`
  (Noto Sans, 13 px) para comentarios, diccionarios, léxico y búsqueda. Es la
  regla `p, div, li, td, th` de `document_css`.

`document_css_for(settings)` es el atajo que usan todas las vistas; no pasar
constantes sueltas. Qt ignora `body { ... }`, por eso el tamaño corriente se
declara en los elementos.

## Temas

`ui/theme.py` es la **única fuente** de color:

- `LIGHT` / `DARK`: `Palette` con `bg, panel, text, muted, accent, link,
  highlight, comment_bg, verse_num`.
- En `DARK` los escalones `bg → panel → panel_alt` y el borde tienen
  contraste suficiente para distinguir paneles, entradas y filas alternas.
- `ui_stylesheet(settings)` → QSS de la app (usa la tipografía de UI).
- `document_css_for(settings)` → CSS embebido en cada `QTextBrowser`.

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

- Todas usan `ui/tooltip.py:TipBubble` (ancho adaptable hasta 600 px), no el
  tooltip nativo de Qt. El documento se **pinta directamente** (sin
  `QTextBrowser` ni viewport) y el alto es
  `documentLayout().documentSize()` con `ceil` + padding + `BOTTOM_EXTRA`
  (5 px de seguridad). Así el último renglón y sus descendentes no se cortan y
  el padding del QSS no altera la medición.
- Notas y referencias resuelven su texto **al pintar**; las referencias pasan
  por `core/refresolver.py:RefResolver` (versículo completo, rango completo o
  capítulo capado a 10 versículos).
- Los números Strong se resuelven **al pasar el ratón** (`RichBrowser`, 180 ms,
  caché) porque cada uno es un `SELECT` al léxico; la cabecera usa la
  abreviatura del léxico, no el título largo.

## Codepages: registro + detección

`font_codepages_for(stem)` cubre los módulos conocidos (Vine, Certeza). Para el
resto, `EswordModule.codepages` **detecta** el codepage por contenido:
`core/legacy_scripts.py` busca rachas de escapes `\'XX` (una palabra griega
produce 4-10 seguidos; un acento español va suelto) y prueba cp1253/cp1255. Si
la decodificación da letras griegas/hebreas ≥55 %, adopta el mapa.

Es conservador a propósito: sin evidencia devuelve `{}` y no toca el texto.
`to_plain`/`to_rich` aceptan `codepages=` explícito; los llamadores pasan
`mod.codepages`.
