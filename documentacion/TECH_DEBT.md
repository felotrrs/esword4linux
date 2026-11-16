# Deuda técnica

Trabajo abierto, consciente y no bloqueante. Orden aproximado por impacto.

## Resuelto en 0.4.4

- Burbujas con la última línea cortada o a medias por el padding del
  `QTextBrowser`; ahora el documento se pinta directamente.
- Palabras hebreas invisibles en las entradas Strong por aplanar los saltos de
  línea en un párrafo RTL.
- Citas que ocultaban libro/capítulo y no tenían forma de restaurarlos.
- Checkbox de vista paralela sin marca de verificación.
- Botón «Strong» renombrado a «Léxico»; icono de About como icono por defecto.

## Resuelto en 0.4.3

- Burbujas con espacios verticales por tags de cierre huérfanos (`</p>`).
- Inconsistencia de alto/corte en burbujas; ahora hay un formato y medición únicos.
- Botón de la lista de términos de biblioteca no era consistente con Recursos.
- Recursos con un solo criterio de agrupación; ahora hay filtros/agrupaciones combinables.
- Enter en Buscar exigía clic en «Ir a …» para referencias.
- Biblia con flechas verticales de capítulo y combo paralelo siempre visible.
- Falta de caja de citas múltiples al estilo del proyecto Bible.
- «Pestaña A» no se retraducía al cambiar de idioma.
- Checkbox de vista paralela poco visible en tema oscuro.
- Icono con damero/tarjeta de fondo pintados.

## Resuelto en 0.4.2

- Burbujas con la última línea cortada (alto calculado con el layout real).
- Panel de recursos y lista de términos de biblioteca que desaparecían al
  arrastrar el divisor; ahora tienen mínimos, splitters no colapsables y botón
  de recuperación.
- Strong y comentarios no refrescaban las burbujas hasta pulsar «Abrir».
- Detección de idioma con falsos positivos por autores/palabras inglesas.
- Falta de vista «Por idioma» y de filtro en el combo de traducción.
- Poco contraste entre fondos del tema oscuro.
- Icono por defecto antiguo; ahora `linuxesword2.webp` genera también hicolor.

## Resuelto en 0.4.1

- Burbujas estrechas/cortadas y cabecera con el título largo de la obra.
- Biblia con márgenes laterales por `stretch` (ahora ocupa todo el ancho).
- Alias de libros hardcodeados y formatos de pasaje sin reconocer
  (prefijos I/II, `1ª`, `Jn 3,16`, listas `, 27-30` / `; 7.11`, nombres
  multi-palabra y abreviaturas `Luk`/`Jhn`/`Rth`/`Ezk`…).

## Resuelto en 0.4.0

- Panel lateral sin tope de ancho y con asa arriba.
- Las pestañas no crecían al plegar el panel.
- La Biblia no crecía horizontalmente.
- Tooltip nativo ancho y del color de los paneles → burbuja propia.
- Sin burbujas en diccionarios/léxicos/comentarios.
- Léxico Strong no elegible.
- Griego legacy en módulos fuera del registro vendorizado.
- Duplicados sin listado ni herramienta.

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
| 1 | **Codepages legacy** | ✅ Resuelto: registro + detección automática por contenido (0.4.0). | — |
| 2 | **Strong's en el texto** | ✅ Resuelto en 0.3.0: ancla + burbuja + panel Strong inferior. | — |
| 3 | **Deuterocanónicos** | Se muestran (libros 67–73) pero los nombres dependen de `core/books.yaml`; falta verificar edición por edición que la numeración coincida con el contenido. | Bajo |
| 4 | **`.lanx` / `headings.*`** | Se catalogan como `unknown` y aparecen en "Sin clasificar". Podrían ocultarse o etiquetarse como "Recursos de e-Sword". | Bajo |
| 5 | **Duplicados** | ✅ Resuelto en 0.4.0: `tools/deduplicate.py` (sha256) + cuarentena con manifiesto. | — |
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
| 13 | **Burbujas y tipografía** | Las burbujas de `ui/tooltip.py` usan un CSS fijo y no siguen las preferencias de fuente. | Bajo |
| 14 | **Accesibilidad** | Sin atajos configurables ni navegación por teclado más allá de Ctrl+F/Ctrl+R/Ctrl+Q. | Bajo |
| 15 | **Iconos** | La UI usa glifos de texto (`●○✕🔒`) en vez de un set de iconos. | Bajo |

## Ingeniería

| # | Tema | Detalle | Impacto |
|---|---|---|---|
| 16 | **Twofish en C** | gcc 13.3 disponible: una extensión C reduciría el descifrado ~50-100×. Hoy se compensa con 16 procesos. | Bajo |
| 17 | **Migraciones de esquema** | `content.db` no tiene versionado; un cambio de esquema exige borrarlo. | Bajo |
| 18 | **Empaquetado** | No hay AppImage/Flatpak; se ejecuta desde el checkout con `run.sh`. | Bajo |
| 19 | **Tests de UI** | 184 pruebas; las de widgets (`test_ui_layout`, `test_theme`, `test_tooltip`) usan `QApplication` en modo `offscreen` sin `pytest-qt`. Falta cubrir más flujos completos de ventana. | Bajo |
| 20 | **Deriva del núcleo** | `make drift` existe pero no corre en un hook; depende de que alguien lo ejecute. | Bajo |
