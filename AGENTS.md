# AGENTS.md — linuxEsword

Lector nativo de módulos e-Sword para Linux (PySide6/Qt6). Este archivo son las
reglas doradas + el mapa del sistema + los comandos. El detalle vive en
`skills/` (leer bajo demanda).

## Reglas doradas

1. **La carpeta de recursos es INMUTABLE.** linuxEsword abre cada módulo con
   `mode=ro`. Nunca se escribe, corrige, "limpia" ni reordena un `.bblx`,
   `.cmtx`, `.dctx`, `.lexi`, `.twm`, etc. Si un módulo trae erratas, mojibake o
   entradas duplicadas, se **documenta y se muestra tal cual**. Prohibido
   inventar o rellenar contenido desde otra fuente.

2. **El tipo se decide por ESTRUCTURA, nunca por extensión.** `kind` sale de las
   tablas presentes (`Bible`, `VerseCommentary`, `Dictionary`, `Topics`,
   `Sections`+`Parts`, `Graphics`, `Reference`, `topics`+`config`...). En el
   corpus real hay `.refx` que son tópicos y `.cmtx` con el esquema antiguo.
   La extensión solo sirve para descubrir archivos.

3. **Leer ≠ buscar.** El visor lee del módulo directamente y descifra solo lo
   que muestra. El índice FTS5 existe **únicamente** para buscar. Nunca se
   bloquea la lectura por no tener índice.

4. **El índice es bajo demanda por categoría.** No se indexa todo al arrancar
   (salvo la base declarada en `Settings.preindex`). Cada módulo tiene estado
   `pending → indexing → ready | failed`; el estado vive en `catalog.db`.
   Los **módulos cifrados** se descifran e indexan una vez (menú
   *Índice → Descifrar módulos cifrados*, `make encrypted`) para que queden
   listos para consulta y búsqueda sin esperas.

5. **Una sola fuente por concepto.** Categorías → `core/catalog.py:KIND_ORDER` /
   `KIND_LABELS`. Libros y alias → `core/books.py:BOOKS`. Cadenas de UI →
   `i18n/es.json` + `i18n/en.json` (mismas claves en ambos). Colores y
   tipografía → `ui/theme.py`. No duplicar listas en otros archivos.

6. **Nada de `os.environ.get()` disperso.** La configuración va por
   `core/config.py:Settings`; los defaults de entorno, solo en `_xdg()`.

7. **Cero trabajo pesado en el hilo de UI.** Escaneo e indexación corren en
   `ui/tasks.py:Worker` (QThread) con conexiones SQLite **propias del hilo**
   (`Catalog`/`ContentStore` nuevos dentro del worker). Los objetos del hilo
   principal no se comparten con el worker.

8. **Todo texto de módulo pasa por `core/text.py`.** `to_plain()` para indexar,
   `to_rich()` para mostrar. `to_rich` sanea: elimina `<script>`, descarta tags
   fuera de la lista blanca, convierte `<ref>X</ref>` en `href="ref:X"` y
   colapsa el relleno vertical del RTF. Nunca se inyecta HTML crudo del módulo
   en un `QTextBrowser`.

9. **El núcleo criptográfico/RTF es vendorizado y GPL-3.0.** `twofish.py`,
   `sqliteplus.py`, `rtf.py`, `font_codepages.py` y `legacy_translit.py` vienen
   de `~/StorageC/bible/shared/esword/`. Cualquier cambio local debe pasar por
   `make drift` y documentarse; la cabecera de procedencia no se toca.

10. **La app debe arrancar sin red y sin Wine.** Cualquier dependencia nueva se
    justifica en `documentacion/adr/`.

11. **Rendimiento medido, no supuesto.** Twofish en Python puro rinde ~284
    registros/s/núcleo. Para las biblias cifradas se usa el pool de procesos de
    `core/indexer.py:_parallel_decrypt`. No introducir descifrado secuencial en
    rutas de más de ~2.000 registros sin medirlo.

12. **La UI nunca se queda en blanco.** Si un módulo falla, el visor muestra el
    error (`index_error`/`ModuleError`) y la app sigue viva. Un fallo de un
    módulo no puede tumbar el catálogo.

## Mapa del sistema

```
Carpeta de recursos (ro)                 Caché (~/StorageC/linuxEsword/.cache)
  ├── BIBLIAS/  .bblx .bbli               ├── catalog.db   metadatos + estado
  ├── COMENTARIOS/ .cmti .cmtx             └── content.db   page + page_fts (FTS5)
  ├── DICCIONARIOS/ .dctx .dcti
  ├── LIBROS/ .refi .topx .devx ...              ▲
  └── raíz .lexi .harx .mapx .twm               │
             │                                   │
             ▼                                   │
   core/esword/module.py ── descifra ── core/indexer.py
        │  (Twofish/SQLitePlus)                  │
        │                                        ▼
        │                              core/store.py (FTS5)
        │                                        │
        ▼                                        ▼
   ui/bible_view.py  ◄── lectura directa ──  core/search.py
   ui/library_view.py                        (referencia | strong | texto)
        ▲                                        ▲
        └──────────── ui/main_window.py ─────────┘
                          ▲
                    ui/sidebar.py (catálogo por categoría)
```

| Módulo | Rol |
|---|---|
| `core/esword/module.py` | Abre el SQLite, detecta estructura, extrae metadatos, itera páginas y descifra por columna. Única puerta de entrada a un módulo. |
| `core/esword/sqliteplus.py` | Header SQLitePlus + zlib. Descifra un blob. |
| `core/esword/twofish.py` | Twofish-128-ECB (vendorizado, GPL-3.0). |
| `core/esword/rtf.py` | RTF → texto plano / HTML enriquecido (vendorizado). |
| `core/text.py` | `to_plain` / `to_rich` / `snippet`. Frontera entre indexar y renderizar. |
| `core/catalog.py` | Escaneo incremental, clasificación, fingerprint y duplicados, estado de índice. |
| `core/store.py` | Esquema `page` + `page_fts` FTS5, triggers, `build_match`. |
| `core/indexer.py` | Módulo → páginas → FTS5. Pool de procesos para biblias cifradas. |
| `core/search.py` | Detección de intención y consulta al store. |
| `core/books.py` | IDs e-Sword 1–73, nombres es/en, alias y `parse_reference`. |
| `core/context.py` | `AppContext`: catálogo, store, motor y cache LRU de módulos abiertos. |
| `ui/bible_view.py` | `BiblePane`: navegación, traducción, paralela. El comentario NO va aquí. |
| `ui/commentary_pane.py` | `CommentaryPane`: panel inferior de comentarios del capítulo. |
| `ui/workspace.py` | `Workspace`: pestaña-vista (recurso principal + biblia/paralela/comentario). |
| `ui/entry_dialog.py` | `EntryDialog`: lectura completa de una entrada sin crear pestaña. |
| `ui/library_view.py` | Visor genérico (diccionario, léxico, referencia, mapa, devocional...). |
| `ui/search_view.py` | Caja única con intención y resultados agrupados. |
| `ui/sidebar.py` | Árbol de categorías/módulos; un clic carga el recurso. |
| `ui/main_window.py` | Pestañas-vista, nombres/colores, menús, workers, persistencia. |
| `ui/theme.py` | Paletas claro/oscuro, QSS y CSS de documento. |
| `i18n/` | `tr(key, **kwargs)` sobre catálogos JSON `es`/`en`. |

## Comandos

```bash
make install     # venv + dependencias
make run         # arranca la app
make scan        # escanea la carpeta y pre-indexa la base (CLI)
make encrypted   # descifra e indexa todos los módulos cifrados (una vez)
make test        # pytest
make drift       # compara el núcleo vendorizado con ~/StorageC/bible/shared/esword
make desktop     # instala app + iconos hicolor (16–512 px)
make clean       # borra venv y caché
```

Diagnóstico rápido:

```bash
# ¿qué tipo detecta y cuántas entradas tiene un módulo?
.venv/bin/python -c "
from linuxesword.core.esword.module import EswordModule
m = EswordModule('/ruta/modulo.bblx'); print(m.structure, m.kind, m.encrypted, m.count_entries())"

# ¿qué hay indexado?
.venv/bin/python -c "
from linuxesword.config import Settings
from linuxesword.core.catalog import Catalog
c = Catalog(Settings.load().catalog_db); print(c.counts_by_kind(), c.status_counts())"
```

## Definición de "terminado"

- `make test` en verde (50 pruebas).
- `make drift` sin deriva inesperada del núcleo vendorizado.
- La app arranca con `./run.sh` y muestra la Biblia sin índice.
- Cambio de comportamiento → una línea en `documentacion/CHANGELOG.md`.
- Trabajo abierto → `documentacion/TECH_DEBT.md`.
- Convención nueva → el `skills/*.md` que la posee.

## Si tocas X, lee Y

| Cuándo… | Skill |
|---|---|
| Lees un módulo, añades un tipo o una tabla | `skills/esword-modules.md` |
| Tocas Twofish, SQLitePlus o el cifrado | `skills/decryption.md` |
| Tocas FTS5, el indexador o la búsqueda | `skills/search-index.md` |
| Tocas la ventana, pestañas, panel lateral o vistas | `skills/ui-layout.md` |
| Tocas RTF/HTML, tipografía o temas | `skills/rendering.md` |
| Añades cadenas de UI o un idioma | `skills/i18n.md` |
| Mides rendimiento o cambias el pool | `skills/performance.md` |
