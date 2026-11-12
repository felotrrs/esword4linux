# Skills — convenciones de linuxEsword

Cada archivo describe una convención **obligatoria**. Leer el skill del área
antes de crear o modificar código ahí.

## Índice

| Skill | Leer cuando… |
|---|---|
| [`esword-modules.md`](esword-modules.md) | Lees un módulo, añades un tipo o una tabla nueva, o tocas `core/esword/module.py`. |
| [`decryption.md`](decryption.md) | Tocas Twofish, SQLitePlus, claves o el descifrado por columna. |
| [`search-index.md`](search-index.md) | Tocas FTS5, `build_match`, el indexador, el alcance o los estados de índice. |
| [`ui-layout.md`](ui-layout.md) | Tocas ventana, pestañas, panel lateral, vistas o persistencia de layout. |
| [`rendering.md`](rendering.md) | Tocas RTF/HTML, `to_rich`, tipografía, temas o el CSS del documento. |
| [`book-aliases.md`](book-aliases.md) | Tocas libros, alias, detección de referencias o burbujas de pasajes/Strong. |
| [`i18n.md`](i18n.md) | Añades cadenas de UI, un idioma o tocas `tr()`. |
| [`performance.md`](performance.md) | Mides rendimiento, cambias el pool o el tamaño de caché. |

## Regla transversal

Antes de añadir una lista (categorías, libros, colores, cadenas), comprueba si
ya existe en su fuente única (`AGENTS.md`, regla 5). Duplicarla es un defecto.
