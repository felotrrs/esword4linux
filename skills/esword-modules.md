# Módulos e-Sword — lectura y clasificación

## Hecho fundamental

**Todos** los módulos e-Sword modernos son bases SQLite. No hay formato
propietario binario que parsear: hay que abrir el SQLite y mirar las tablas.

```
$ file kjv.bblx
SQLite 3.x database ... UTF-16 little endian
```

## La extensión miente

El corpus real (`/home/felipe/StorageA/Biblias/Biblias_bblx`, 970 archivos)
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
| `reference` | `Reference` | `reference` |
| `topic` | `Topics` | `topic` |
| `twm` | `topics` (+ `config`, `content`) | `twm` |

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
