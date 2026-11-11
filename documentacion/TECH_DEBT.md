# Deuda técnica

Trabajo abierto, consciente y no bloqueante. Orden aproximado por impacto.

## Resuelto en 0.3.0

- Pseudo-tags de e-Sword (`</red>`, `</grk>`…) mostrados literalmente.
- Griego cp1253/cp1255 sin decodificar (Vine NT/AT).
- Referencias cruzadas y notas sin burbuja ni navegación.
- Números Strong sin acceso al léxico.
- Pestañas de un solo color (punto) y botón de cierre pegado al borde.

## Resuelto en 0.2.0

- Comentarios en panel inferior propio (antes incrustados en el texto).
- Una pestaña por módulo → pestañas-vista con grupo biblia + paralela +
  comentario.
- Vista paralela y comentario ocultos cuando el recurso no es biblia.
- Panel de recursos ocultable (`Ctrl+B`).
- Un clic carga el recurso (antes: doble clic).
- Esquema moderno de comentarios `.cmtx` (`Verses` con rangos).
- Descifrado masivo de módulos cifrados (`make encrypted`).
- Iconos de aplicación instalados con `make desktop`.

## Datos / formato

| # | Tema | Detalle | Impacto |
|---|---|---|---|
| 1 | **Codepages legacy** | ✅ Resuelto en 0.3.0: conectados vía `hint` (stem) en `to_plain`/`to_rich`. | — |
| 2 | **Strong's en el texto** | ✅ Resuelto en 0.3.0: ancla + burbuja + panel Strong inferior. | — |
| 3 | **Deuterocanónicos** | Se muestran (libros 67–73) pero los nombres dependen de `core/books.py`; falta verificar edición por edición que la numeración coincida con el contenido. | Bajo |
| 4 | **`.lanx` / `headings.*`** | Se catalogan como `unknown` y aparecen en "Sin clasificar". Podrían ocultarse o etiquetarse como "Recursos de e-Sword". | Bajo |
| 5 | **Duplicados** | Se detectan por fingerprint (tamaño + 64 KiB) y se ocultan; no hay UI para revisarlos ni elegir cuál conservar. | Bajo |
| 6 | **Imágenes de mapas** | Se muestran a ancho fijo 760 px; falta zoom y ajuste a ventana. | Bajo |

## Índice / búsqueda

| # | Tema | Detalle | Impacto |
|---|---|---|---|
| 7 | **Indexación completa** | Solo se preindexan 3 módulos. Indexar las 10 categorías son ~3,4 M páginas y ~2 GB; hay que medir y trocear con progreso cancelable. | Medio |
| 8 | **Indexación cancelable** | El worker respeta `requestInterruption()` pero `Indexer` no consulta la bandera entre módulos. | Medio |
| 9 | **Búsqueda por proximidad** | `NEAR` de FTS5 no se usa; "amor dios" busca ambos términos en cualquier orden/posición. | Bajo |
| 10 | **Resaltado en el visor** | Al saltar desde un resultado no se resalta el término en el texto del módulo. | Bajo |
| 11 | **Búsqueda en mapas** | Solo se indexa título + pie, no el contenido de la imagen (obvio). | — |

## UI

| # | Tema | Detalle | Impacto |
|---|---|---|---|
| 12 | **Dividir una pestaña en dos grupos** | Las pestañas se reordenan y cada una tiene su split vertical (biblia/comentario) y horizontal (paralela), pero no se pueden tener dos grupos independientes dentro de la misma pestaña. | Medio |
| 13 | **Idioma en caliente** | Cambiar de idioma pide reiniciar. | Bajo |
| 14 | **Accesibilidad** | Sin atajos configurables ni navegación por teclado más allá de Ctrl+F/Ctrl+R/Ctrl+Q. | Bajo |
| 15 | **Iconos** | La UI usa glifos de texto (`●○✕🔒`) en vez de un set de iconos. | Bajo |

## Ingeniería

| # | Tema | Detalle | Impacto |
|---|---|---|---|
| 16 | **Twofish en C** | gcc 13.3 disponible: una extensión C reduciría el descifrado ~50-100×. Hoy se compensa con 16 procesos. | Bajo |
| 17 | **Migraciones de esquema** | `content.db` no tiene versionado; un cambio de esquema exige borrarlo. | Bajo |
| 18 | **Empaquetado** | No hay AppImage/Flatpak; se ejecuta desde el checkout con `run.sh`. | Bajo |
| 19 | **Tests de UI** | 48 pruebas cubren el núcleo; no hay pruebas de widgets (requerirían `pytest-qt`). | Medio |
| 20 | **Deriva del núcleo** | `make drift` existe pero no corre en un hook; depende de que alguien lo ejecute. | Bajo |
