# Módulos e-Sword — lectura y clasificación

## Hecho fundamental

**Todos** los módulos e-Sword modernos son bases SQLite. No hay formato
propietario binario que parsear: hay que abrir el SQLite y mirar las tablas.

```
$ file kjv.bblx
SQLite 3.x database ... UTF-16 little endian
```

## La extensión miente

El corpus real (`/home/felipe/StorageA/Biblias/Biblias_esword`, 970 archivos)
contiene:

- `.refx` con tabla `Topics` → son **Tópicos**, no Referencias.
- `.cmtx` con `VerseCommentary` → esquema **antiguo** de comentarios, no el
  nuevo (`Books`/`Chapters`/`Verses`).
- `.bbli` → misma estructura que `.bblx` pero con `Scripture` TEXT (sin cifrar).

Por eso `EswordModule._detect_structure()` decide por tablas, en este orden:

| Estructura | Tablas | `kind` |
|---|---|---|
| `bible` | `Bible` | `bible` |
| `commentary` | `Verses` \| `VerseCommentary` \| `BookCommentary` \| `ChapterCommentary` | `commentary` |
| `dictionary` | `Dictionary` | `dictionary` |
| `lexicon` | `Lexicon` | `lexicon` |
| `devotion` | `Devotions` \| `Devotional` | `devotion` |
| `harmony` | `Sections` + `Parts` | `harmony` |
| `maps` | `Graphics` | `maps` |
| `reference` | `Reference` | `reference` (citas bíblicas) \| `book` (capítulos de libro) |
| `topic` | `Topics` | `topic` \| `book` |
| `twm` | `topics` (+ `config`, `content`) | `dictionary` \| `book` \| `topic` |

**Excepción de catálogo**: algunos comentarios se distribuyen con esquema de
diccionario (`Dictionary`, una entrada por capítulo). `Catalog._probe()` los
cataloga como `commentary` si el título o la abreviatura contienen
«comentario»/«commentary»; la estructura leída sigue siendo `dictionary`.

**Heurística de contenido**: `EswordModule._detect_kind()` analiza el contenido real de
las tablas:
- En `Reference`, si las entradas de `Chapter` son citas bíblicas (`libro:cap:ver`), es `reference`;
  si son capítulos o tratados literarios, se clasifica como `book`.
- En `twm`, el contenido de `config` y los términos de `topics` deciden si es `dictionary` (ej. Hitchcock),
  `book` o `topic`.
- Módulos con 0 entradas o solo tablas de interfaz (`localize`, `headings`) se ocultan por defecto en la UI.

**El orden importa**: `topics` (TWM) y `Topics` (tópico) solo se distinguen por
la caja del nombre y por la presencia de `config`.

## Metadatos

`Details` no tiene esquema fijo:

- `.bblx` / `.cmti` / `.refi` / `.dctx` → `Title, Abbreviation, Information, Version`
- `.devx` / `.harx` / `.mapx` → `Description, Abbreviation, Comments, Version`
- `.twm` → no tiene `Details`; el título está en `config` (`name='title'`)

`EswordModule.details()` normaliza: busca `Title` y cae a `Description`, y
`Information` cae a `Comments`.

## Añadir un tipo nuevo

1. Añade la detección en `_detect_structure()` **antes** de las que puedan
   colisionar por nombre de tabla.
2. Añade `_pages_<structure>()` que produzca `Page(ref, title, raw, order)`.
3. Añade la entrada en `core/catalog.py:KIND_LABELS` y `KIND_ORDER` (fuente única).
4. Añade `page_by_ref()` para que el visor no tenga que recorrer el módulo.
5. Añade `list_entries()` si el visor necesita un índice navegable.
6. Añade el caso en `iter_pages()` (dispatch) — es implícito por nombre.
7. Prueba en `tests/test_module.py` con un módulo real del corpus.

## Consultas: nunca recorras el módulo para una entrada

`get_page(ref)` itera todo el módulo: es el **fallback**. Usa `page_by_ref(ref)`
y `bible_chapter(book, chapter)`, que hacen `SELECT` directo. Un diccionario de
21.000 entradas no puede recorrer 21.000 filas cada vez que el usuario pulsa
una letra.

## Mapas e ilustraciones (`.mapx`)

`Graphics` guarda `Title`, `Details` (leyenda) y `Picture` (BLOB de imagen).
Dos particularidades del corpus, ya resueltas en `EswordModule`:

- **Títulos BLOB UTF-16LE**: en `map_larkin_es.mapx` las entradas 10+ guardan
  `Title` como bytes. Hay que decodificarlo con `_text_value()` y localizar la
  fila por `rowid` (`_graphics_rowid()`); un `WHERE Title=?` contra el texto
  decodificado no encuentra nada.
- **Envoltorio `lt\0\0` + tamaño**: algunos módulos (`map_usos_y_costumbres…`,
  `map_lba`, `map_rva`, `map_abb`) anteponen 8 bytes a un BMP. `_unwrap_picture()`
  los quita para que Qt pueda cargar la imagen.
- **Leyenda cifrada sin zlib**: `map_larkin_es.mapx` cifra `Details` con
  SQLitePlus pero guarda RTF UTF-16LE sin comprimir (cabecera de 5 bytes con
  magia `0x1F`). `decrypt_payload()` falla al buscar el stream zlib;
  `_decode_uncompressed_sqliteplus()` reconoce ese formato y devuelve el texto.

## Comentarios con solo `BookCommentary`

`ABN-Manley`, `ATB-M-Pearlman` y `ABP-Willmington` tienen
`VerseCommentary`/`ChapterCommentary` vacías y todo el texto en
`BookCommentary`. Dos reglas:

- `count_entries()` suma **todas** las tablas de `_comment_specs()`, no solo la
  primera que exista (antes devolvía 0 y el catálogo ocultaba el módulo).
- `page_by_ref()` acepta refs de una sola parte (`"43"`) para los comentarios
  de libro, además de `"43:3"` y `"43:3:16"`.

## Armonías (`.harx`)

`Parts` tiene una fila **por referencia**, de modo que varias filas comparten
`(Section, Part)`. La unidad navegable es la **sección**: una `Page` por
`Section` con el título limpio (sin RTF) y todas sus referencias en `raw`
(deduplicadas, una por línea). `list_entries()` devuelve una entrada por
sección y `page_by_ref("3")` la reconstruye. El antiguo `"3:1"` se acepta como
alias, pero el `ref` canónico es la sección.


## Errores esperados

| Error | Causa | Política |
|---|---|---|
| `ModuleError: no se pudo abrir` | archivo movido o corrupto | el catálogo lo marca `failed`; la UI sigue viva |
| Entrada vacía tras descifrar | clave SQLitePlus distinta | se omite con warning; **nunca** se rellena |
| `0` entradas | módulo vacío de origen (p. ej. `LXX/`) | se muestra `lib.empty` |

## Duplicados

`tools/deduplicate.py` agrupa por tamaño y confirma con **sha256**. El
`keep_score` decide qué copia se conserva:

1. carpeta canónica del tipo (`BIBLIAS`/`COMENTARIOS`/`DICCIONARIOS`/`LIBROS`) +30;
2. nombre normalizado e-Sword (`bible_`, `comment_`, `dicc_`…) +20;
3. similitud del nombre con el título interno ×12;
4. nombre más descriptivo (longitud) como desempate.

`--apply` mueve las sobrantes a `_duplicados/<fecha>/` y escribe manifiesto
(ruta, sha256, copia conservada). Nunca borra por defecto.

`Catalog.scan()` **excluye** `_duplicados/` (y VCS/ocultas) y purga las filas
de módulos que ya no están en disco. El orden importa: **primero purgar,
después `_mark_duplicates()`**; al revés quedan `duplicate_of` colgando de
filas borradas y el módulo desaparece de la barra sin motivo.

## Léxico Strong con respaldo

`StrongIndex._resolve_page(code)` prueba el léxico elegido y, si no tiene la
entrada, recorre los candidatos. Así un léxico solo-hebreo no deja vacíos los
números griegos (`G2316`). El tooltip muestra la abreviatura del léxico del que
salió la entrada, no la del elegido.
