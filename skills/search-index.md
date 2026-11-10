# Índice y búsqueda (FTS5)

## Principio

**Leer no depende del índice.** El visor consulta el módulo y descifra lo que
muestra. El índice existe solo para buscar.

Consecuencia de diseño: la app es usable desde el primer segundo, aunque no
haya nada indexado; la búsqueda avisa `search.no_index` hasta que se indexe.

## Esquema (`content.db`)

```sql
page(id PK, module_id, kind, ref, title, body, book, chapter, verse, ord)
  UNIQUE(module_id, ref)
page_fts USING fts5(body, title,
                    content='page', content_rowid='id',
                    tokenize="unicode61 remove_diacritics 2")
```

- `content='page'` → FTS5 de contenido externo: el texto no se duplica.
- `remove_diacritics 2` → `amor` encuentra `amór`, `Génesis` = `Genesis`.
- Triggers `page_ai` / `page_ad` / `page_au` mantienen FTS en sincronía. No
  insertar en `page_fts` a mano.

## Unidad indexable por tipo

| `kind` | Página | `ref` |
|---|---|---|
| `bible` | un versículo | `43:3:16` |
| `commentary` | un comentario de versículo/capítulo/libro | `43:3:16` / `43:3` |
| `dictionary`, `lexicon` | una entrada | el `Topic` |
| `reference` | un capítulo temático | el `Chapter` |
| `topic` | un tema | el `Title` |
| `devotion` | un día | `03-16` |
| `harmony` | una parte | `sección:parte` |
| `maps` | una entrada (título + pie) | el `Title` |
| `twm` | un tema | el `id` |

## `build_match`

Entrada de usuario → expresión MATCH.

```
"amor"             → "amor"*
"amor de dios"     → "amor" AND "de" AND "dios"*
'"en el principio"' → "en el principio"
```

- El **último** término se hace prefijo: búsqueda mientras se escribe.
- Si el `AND` no devuelve nada, `ContentStore.search()` reintenta con
  `build_match_or` (OR de términos). No cambiar este fallback sin medir: es lo
  que hace que "amor de dios" no quede vacío.
- Los términos se citan siempre: evita que `AND`, `OR`, `NEAR`, `*` o `-` del
  usuario rompan la consulta.

**Nunca** interpolar el texto del usuario directamente en el SQL de MATCH.

## Estado de indexación

Vive en `catalog.db`:

```
pending → indexing → ready | failed
```

- `indexer.index_module()` marca `indexing`, escribe páginas y marca `ready`.
- Un fallo deja `failed` + `index_error` (primeros 400 chars).
- Las páginas se borran y reinsertan por módulo: `store.delete_module()`.
- El catálogo no reindexa si `size`+`mtime` no cambian (escaneo incremental).

## Alcance de la búsqueda

`SearchEngine.indexed_module_ids(kinds)` devuelve solo módulos `ready`. El
`SearchView` filtra por categoría con el combo de alcance. Si el alcance queda
vacío, la UI explica que hay que indexar.

## Intenciones

`core/search.py:search()` decide en este orden:

1. `parse_reference()` → `intent="reference"` (no toca FTS).
2. `^[GH]\d+$` → `intent="strong"`, alcance léxicos + diccionarios.
3. resto → `intent="text"`, FTS con `bm25()` + `snippet()`.

El orden importa: `Juan 3:16` no debe llegar nunca a FTS.

## Reglas de rendimiento

- `LIMIT` siempre. La UI pide 200; se muestran 80 por grupo.
- `snippet()` con 24 tokens es suficiente; subirlo multiplica el coste.
- Indexar una biblia plana: ~6 s (35k versículos). Cifrada: ~13 s con pool.
- El índice completo del corpus son ~3,4 M páginas; **nunca** se construye de
  golpe salvo que el usuario lo pida explícitamente.

## Migrar el esquema

Si cambia `SCHEMA` en `core/store.py`, el `CREATE TABLE IF NOT EXISTS` no
actualiza una base existente. Borra `.cache/content.db` (es regenerable) y
documenta el cambio. No hay migraciones incrementales: el índice es caché.
