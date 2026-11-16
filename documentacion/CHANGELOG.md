# Changelog

## 0.4.7 — 2026-11-15

### Añadido

- **Editar → Preferencias**: suite de tipografía con fuente y tamaño para la
  interfaz, el texto bíblico y el texto corriente (comentarios, diccionarios,
  léxico y búsqueda). Incluye vista previa en vivo y «Restablecer».
- Las preferencias se guardan en `Settings` (`ui_font_*`, `font_*`,
  `content_font_*`) y se aplican a la QSS y a `document_css` sin reiniciar.

### Corregido

- **Icono oficial**: `linuxesword3.jpeg` pasa a ser el icono real de la app.
  `tools/make_icons.py` recorta la tarjeta redondeada del JPEG (elimina el
  damero pintado) y genera `linuxesword.png` con transparencia, que usan la
  ventana, «Acerca de» y los tamaños hicolor 16–512 px.
- **Filtros del panel lateral**: «tipo» e «idioma» quedan juntos y alineados a
  la izquierda; se elimina el `stretch` intermedio.
- **«Emparejado con…»**: el badge ya no abre una ventana emergente; cambia el
  comentario del panel inferior y se desplaza al versículo actual.

## 0.4.6 — 2026-11-15

### Corregido

- **Leyenda de mapas cifrada sin zlib**: `map_larkin_es.mapx` guarda
  `Graphics.Details` con cifrado SQLitePlus pero RTF UTF-16LE sin comprimir.
  Se reconoce la cabecera de 5 bytes (magia `0x1F`) y se decodifica el texto,
  en lugar de mostrar los bytes aleatorios como caracteres extraños.
- **Imágenes de mapas e ilustraciones**: se decodifican los títulos BLOB
  UTF-16LE (`map_larkin_es.mapx`) para que la lista, `page_by_ref` y
  `map_picture` encuentren todas las entradas, y se quita el envoltorio `lt\0\0`
  + tamaño que algunos `.mapx` anteponen al BMP
  (`map_usos_y_costumbres_de_las_tierras_es`, `map_lba`, `map_rva`, `map_abb`,
  entre otros).
- **Controles de mapa visibles**: la barra con `+`, `-`, `1:1`, «Ajustar» y
  «Leyenda» vuelve a mostrarse al seleccionar una entrada de mapas. La leyenda
  respeta su botón y, si falta la imagen, se muestra el aviso en el panel.
- **Badge «emparejado con…»**: vuelve a ser clickeable y abre el comentario
  emparejado; ahora conserva la ruta del módulo al pintar el badge.
- **Comentarios solo de libro**: `ABN-Manley`, `ATB-M-Pearlman` y
  `ABP-Willmington` tienen `VerseCommentary` vacía y todo el texto en
  `BookCommentary`. `count_entries()` suma las tablas reales (antes devolvía 0
  y el catálogo los ocultaba) y `page_by_ref()` acepta refs de libro (`"43"`),
  así que sus entradas ya muestran texto.
- **Comentarios con esquema de diccionario**: «Comentario Bíblico Siglo 21»
  (`.dcti` y `.dctx`) y «Comentario Expositivo del N. T. Mateo de D.Burt» pasan
  de la categoría Diccionarios a Comentarios sin alterar el módulo.
- **Armonías**: la unidad navegable es la sección. Cada entrada agrupa todas
  las referencias de `Parts` (sin registros duplicados), limpia el RTF del
  `Section.Title` y usa un `ref` único de sección. El índice FTS5 deja de
  conservar solo la última referencia de cada `(sección, parte)`.
- **Reindexado por metadatos**: si un escaneo cambia el tipo, la estructura o
  el número de entradas de un módulo, su índice de contenido queda `pending`
  para reconstruirlo con la nueva unidad indexable.

## 0.4.5 — 2026-11-12

### Añadido

- **Visor interactivo de mapas e ilustraciones (`ImageViewer`)**: control de zoom suave con la rueda del ratón, arrastre con mano (pan), botones flotantes de acercar/alejar/100%/ajustar a ventana y visualización en diálogo a pantalla completa.
- **Categoría y detección de Libros (`book`)**: sistema heurístico que diferencia entre tablas `Reference` con citas bíblicas cruzadas (`reference`) y obras/tratados literarios con capítulos secuenciales (`book`).
- **Clasificación heurística de módulos TWM**: los módulos `.twm` se reclasifican según su contenido real como diccionarios, libros o tópicos, eliminando su estatus de categoría paria.
- **Icono de lupa en la pestaña Buscar**: renderizado vectorial nítido en `ColoredTabBar` que se adapta a la paleta del tema.
- **Ocultamiento de módulos de sistema / vacíos**: los módulos sin entradas o de interfaz (`headings`, `localize`) no se muestran por defecto en el panel lateral, con opción en *Ver → Mostrar archivos sin contenido / sin clasificar*.

### Cambiado

- **Consistencia visual en filtros**: los botones Tipo e Idioma ahora van juntos en el layout con el mismo estilo, tipografía, padding y bordes que los selectores de Agrupar.
- **Tokens semánticos de tema**: `Palette` incorpora `success`, `error` y `strong` para unificar colores de estado en el árbol de recursos y texto bíblico respetando los temas claro y oscuro.
- **Botones de cierre compactos**: los paneles de Comentario y Léxico usan botones ✕ circulares y discretos (`#closeButton`).

## 0.4.4 — 2026-11-12

### Corregido

- **Burbujas**: se sustituye el `QTextBrowser` interno por un widget que pinta
  directamente un `QTextDocument`. El padding global del QSS ya no recorta el
  viewport, el alto se mide sobre el ancho real y hay un margen inferior de
  seguridad: la última línea (incluidos descendentes) nunca queda cortada ni a
  medias.
- **Hebreo en las burbujas del léxico**: `StrongIndex.tooltip()` conserva los
  saltos de línea del módulo (palabra hebrea, transliteración y definición).
  Cada línea es un bloque independiente y la palabra hebrea se muestra con
  tamaño de cabeza, sin que el RTL arrastre al resto del texto.
- **Citas**: activar la colección ya no oculta los combos de libro/capítulo ni
  las flechas de navegación. Siempre se puede volver a la Biblia con ellos o
  con ↩.
- **Vista paralela**: el checkbox muestra una marca de verificación dibujada
  por `CheckMarkStyle`, además del color de acento al marcarse.
- **Icono por defecto**: se usa el icono del diálogo «Acerca de»
  (`linuxesword-about.png`) y se regeneran `linuxesword.png` y hicolor 16–512.

### Cambiado

- El botón y el panel **Strong** pasan a llamarse **Léxico**.
- **Recursos**: «Filtrar» es ahora un título de sección a todo el ancho, como
  «Agrupar», con un espacio vertical que separa ambos bloques de controles.
- **Carpeta de recursos por defecto**: se actualiza a
  `/home/felipe/StorageA/Biblias/Biblias_esword` (el corpus renombró la carpeta
  `Biblias_bblx`). Afecta al valor inicial de `Settings` y a las pruebas que
  dependen del corpus.

### Pruebas

- 175 pruebas recogidas: 169 en verde y 6 omitidas porque el corpus actual no
  incluye esos módulos. Se añade cobertura de widgets en modo `offscreen` para
  burbujas (alto, hebreo, líneas), checkmark, organizador de Recursos y modo
  citas, sin depender de `pytest-qt`.

## 0.4.3 — 2026-11-11

### Corregido

- **Burbujas estandarizadas**: cuerpo sin líneas vacías ni restos de HTML, una
  línea por versículo, altura medida del layout real y último renglón sin
  cortes. Se eliminaron los tooltips nativos residuales.
- **Tags huérfanos**: `</p>` sueltos en módulos como RVR1960x ya no parten un
  versículo en dos bloques (causaban el hueco vertical).
- **Paneles recuperables**: la lista de términos de diccionarios usa un asa
  vertical `‹/›` como Recursos, con mínimo de ancho y estado persistido.
- **Strong/comentarios** aplican el cambio de material al instante, sin pulsar
  «Abrir».
- **Búsqueda**: Enter sobre una referencia navega directamente a la Biblia.
- **Biblia**: sin flechas verticales de capítulo; el combo paralelo se oculta
  si la vista paralela está desmarcada; checkbox con contraste en oscuro.
  Se retiraron el botón «Citas» y la flecha de ocultar panel; la búsqueda usa
  la selección o, si no hay, la referencia actual.
- **Combo de traducción**: desplegable no editable; al abrirlo se ven todas las
  versiones agrupadas por idioma.
- **«Pestaña A»**: los nombres automáticos se recalculan al cambiar de idioma
  y los menús se retraducen en caliente.
- **Icono**: se elimina el damero/tarjeta de fondo del WebP y se genera un PNG
  con transparencia real; hicolor se regenera desde el icono limpio.

### Añadido

- **Organizador de Recursos**: hasta tres niveles de agrupación
  (tipo/idioma/obra) y filtros múltiples por tipo e idioma, persistidos.
- **Caja de citas múltiples** en la propia barra de la Biblia: al pulsar
  Enter, la colección sustituye la vista del capítulo (también en la paralela)
  y se puede volver a la Biblia con ↩.
- Tooltips de ayuda en los controles principales.

## 0.4.2 — 2026-11-11

### Corregido

- **Alto de las burbujas**: se calcula desde el layout real del documento y
  los márgenes/bordes del marco; la última línea ya no queda cortada.
- **Paneles laterales irrecuperables**: el panel de recursos tiene mínimo de
  240 px + asa y su splitter no es colapsable. La lista de términos de
  diccionarios/léxicos tiene mínimo de 220 px y un botón `☰` siempre visible
  para ocultarla/recuperarla (estado y ancho persistidos).
- **Burbujas Strong/comentarios desactualizadas**: al cambiar de léxico o de
  comentario se invalidan las cachés de `RichBrowser` y `_comments_cache`, se
  regeneran las notas del capítulo y el cambio se aplica sin pulsar «Abrir».
- **Detección de idioma**: se priorizan título/abreviatura, marcador de archivo,
  muestra de contenido y alfabetos originales; se eliminaron los nombres de
  autores que confundían español con inglés. `METADATA_VERSION` fuerza un
  re-escaneo de metadatos para actualizar el catálogo existente.
- **Contraste del tema oscuro**: escalones de fondo más marcados, bordes más
  visibles y filas alternas en los árboles/listas.

### Añadido

- **Tercera vista «Por idioma»** en Recursos, con etiquetas i18n y grupos por
  `module.language`.
- **Combo de traducción agrupado por idioma y ordenado**; al desplegarlo se
  ven todas las versiones. La vista paralela usa el mismo agrupado.
- **Nuevo icono por defecto** `linuxesword2.webp`; `make desktop` genera los
  PNG de hicolor desde ese WebP. El diálogo «Acerca de» conserva su logo.
- Pruebas de alto de burbuja, contraste, idiomas, filtro de traducciones y
  paneles recuperables.

## 0.4.1 — 2026-11-11

### Corregido

- **Burbujas de bibliografía**: el ancho ya se adapta al texto (hasta 600 px) y
  la cabecera solo muestra la referencia o la abreviatura del léxico, no el
  título largo de la obra. Los pasajes muestran el texto completo (sin
  `snippet`) y los capítulos/rangos se capan a **10 versículos** con aviso de
  los restantes. Las entradas Strong se capan a 2500 caracteres, con aviso
  para abrir la entrada completa en el panel Strong.
- **La Biblia ocupa todo el ancho horizontal**: se quitaron los `stretch`
  laterales que dejaban ~17 % del panel como margen.
- **Normalización de libros y pasajes**: la tabla de libros y alias pasa a
  `core/books.yaml` (nombres es/en/fr/pt). Se reconocen prefijos `I/II/III`,
  `Primera/Segunda/Tercera`, `1ª/1a/1ra`, abreviaturas como `Luk`, `Jhn`,
  `Deu`, `Pro`, `Amo`, `Rth`, `Ezk`, `Mrk`, separadores `Jn 3,16` y listas
  `Ex. 4:14, 27-30` / `He. 5.4; 7.11`. Los `<ref>` con listas se dividen en
  enlaces por sub-referencia. Los libros ausentes de la numeración 1–73
  (`1 Esdras`, `3 Macc`) no se enlazan a otro libro.

### Añadido

- `PyYAML>=6` y ADR-0002; `skills/book-aliases.md` documenta el esquema.
- Pruebas de formatos, continuaciones, nombres multi-palabra, tope de
  versículos y ancho de burbuja.

## 0.4.0 — 2026-11-10

### Añadido

- **Panel lateral con dos vistas** (`Por tipo` / `Por obra`), persistidas:
  la vista por tipo para encontrar un léxico sin saber de qué obra es; la
  vista por obra agrupa 947 módulos en **846 obras** (85 con varios módulos:
  texto + notas + léxico). El año separa ediciones (RV1960 ≠ RV1995).
- **Burbuja propia** (`TipBubble`): tarjeta oscura independiente del tema,
  borde de acento, **ancho máximo 380 px** y cabecera en dorado. Sustituye al
  tooltip nativo, que heredaba el color de los paneles y no limitaba el ancho.
- **Burbujas en toda la bibliografía**: diccionarios, léxicos y comentarios
  enlazan sus citas —tanto `<ref>` como **texto plano** (`Neh. 8:15`,
  `2Co 4:6`)— y muestran el versículo al pasar el ratón.
- **Léxico Strong predeterminado elegible**: el combo del panel Strong lista
  los 15 léxicos Strong (★ = activo) y fija el de las burbujas; también en
  **Ver → Léxico Strong predeterminado**. Si el léxico elegido no cubre ese
  idioma (p. ej. uno solo de hebreo y se pide `G2316`), se resuelve con
  **respaldo automático** al primer candidato que tenga la entrada, y la
  burbuja indica de qué léxico sale.
- **Detección automática de codepages legacy** (`core/legacy_scripts.py`):
  reconoce cp1253/cp1255 por rachas de escapes RTF y corrige el griego de
  módulos fuera del registro vendorizado (p. ej. `dicc_strong__esp_es.dctx`
  pasa de `èåïäßäáêôïò` a `θεοδίδακτος`).
- **`tools/deduplicate.py`** + **`documentacion/DUPLICADOS.md`**: informe
  completo de duplicados exactos (sha256) y de «misma obra, archivos
  distintos», con política de conservación y cuarentena reversible.
- **`make dedup`**.

### Corregido

- **El panel lateral no crecía**: tenía `setMaximumWidth(460)`; ahora el árbol
  ocupa todo el ancho que se le dé.
- **Las pestañas no crecían al ocultar el panel**: el dock conservaba sus
  290 px. Ahora se acota a 16 px y el contenido recupera el espacio.
- **Asa del panel a media altura**: pasa a altura fija (15×26) alineada arriba.
- **La Biblia no crecía horizontalmente**: se quitó el tope de 980 px; ahora
  ocupa el ancho como la zona de comentario.

### Biblioteca

- **23 copias duplicadas movidas a cuarentena** (113,9 MB) con manifiesto en
  `_duplicados/manifest-*.json`. El catálogo pasó de 969 a 946 módulos.
- El escaneo **excluye `_duplicados/`**, VCS y carpetas ocultas, y **purga del
  catálogo** los módulos que ya no existen en disco (`ScanResult.removed`).
- Reindexados los 12 módulos cuyo texto tenía pseudo-tags literales o
  mojibake en el índice FTS5.

## 0.3.0 — 2026-11-10

### Añadido

- **Pseudo-tags de e-Sword** (`<red>`, `<blu>`, `<grk>`, `<heb>`, `<num>`,
  `<Pg>`, `<T>`, `<trn>`, `<Hebr>`, `<SHE…>`…) convertidos a HTML semántico.
  Antes se mostraban literalmente como `</red>` porque la detección de HTML no
  los reconocía (20 tipos inventariados sobre los 863 módulos).
- **Griego/hebreo legacy**: se conectan `font_codepages.py` (cp1253/cp1255) y
  `legacy_translit.py` con el stem del módulo. `dicc_vine_es_nt_es` pasa de
  `ἀðüèåóéò` a `ἀπόθεσις`. Los ficheros vendorizados no se tocan.
- **Burbujas**: notas y referencias resuelven su texto al pintar (atributo
  `title`, tooltip nativo); los números Strong se resuelven al pasar el ratón
  con caché (`RichBrowser`, 180 ms).
- **Clic en un marcador de nota** → abre el comentario si estaba cerrado,
  salta al módulo emparejado con esa biblia, hace scroll a la nota y mantiene
  el foco en el versículo.
- **Clic en un número Strong** → el panel inferior pasa a **Strong** con la
  entrada completa (lexema, transliteración, morfología).
- **Panel inferior apilado**: `Comentario ⇄ Strong` con selector en la barra.
- **Emparejamiento biblia↔comentario** automático y visible: identidad
  (tokens/año/abreviatura) + **cobertura real** de los marcadores del texto.
  RV1960 → RVR1960x; LBLA → LBLA; sin coincidencia no inventa.
- **Pestañas con color pleno**: `ColoredTabBar` pinta fondo, texto en negrita
  cuando está seleccionada, tinte pálido cuando no, cierre con margen y botón
  **＋** estilo navegador detrás de la última pestaña.
- **Panel lateral plegable** con asa en su propio borde (`‹`/`›`).

### Corregido

- Referencias falsas: `_abbrev()` devolvía espacios y el bonus de subcadena
  emparejaba cualquier comentario.
- Coste de render: las notas y referencias se resuelven con los datos ya
  cargados del capítulo (cero consultas extra por versículo).

## 0.2.0 — 2026-11-10

### Cambiado (modelo de interfaz)

- **Pestañas-vista (`Workspace`)** en lugar de una pestaña por módulo. Cada
  pestaña agrupa un recurso principal y, si es biblia, su propia biblia
  paralela y su propio comentario. Nombres automáticos «Pestaña A/B/C…»,
  color asignable y renombrado por menú contextual. Persistencia completa del
  grupo (traducción, paralela, comentario, alturas).
- **Comentario en panel propio**, en la parte inferior y con división vertical
  (~28 %), en vez de incrustado entre versículos.
- **Seleccionar un recurso ya no abre pestaña**: se carga como recurso
  principal de la pestaña activa. Crear pestaña es explícito (`＋`, `Ctrl+T`).
- **Paralela y comentario solo con biblias.** Un diccionario ya no muestra
  controles de biblia (la «vista paralela de diccionarios» desaparece).
- **«Leer completo» abre un diálogo**, no una pestaña.

### Añadido

- **Un clic carga el recurso** en el panel lateral; un clic en la categoría la
  pliega/despliega.
- **Panel de recursos ocultable**: `Ctrl+B`, menú *Ver → Panel de recursos* y
  botón `☰` junto a las pestañas; el estado se persiste.
- **Iconos de la aplicación**: icono plano (ventana, lanzador, hicolor
  16–512 px) e ilustrado (diálogo *Acerca de*). Instalación con
  `make desktop`.
- **`make encrypted` / menú Índice**: descifra e indexa de una vez todos los
  módulos cifrados (23 módulos / ~620 k registros) para que queden listos.
- **Comentarios con esquema moderno**: soporte de `.cmtx` con
  `Verses(ChapterBegin, ChapterEnd, VerseBegin, VerseEnd)` además del antiguo
  `VerseCommentary`. Antes fallaba con «no such column: Chapter».
- Pruebas de regresión para los dos esquemas de comentario (50 en total).

### Corregido

- El panel de comentario no se refrescaba porque `isVisible()` es falso antes
  de mostrar la ventana; ahora depende del toggle.
- La pestaña fija «Buscar» ya no muestra un botón de cierre inerte.
- Carpeta duplicada `~/StorageC/linuxesword`: era un artefacto de una escritura
  con otra capitalización (contenía solo `__main__.py`). Eliminada.

## 0.1.0 — 2026-11-10

Primera versión funcional.

### Añadido

- **Lector nativo de módulos e-Sword** (`core/esword/module.py`): SQLite
  `mode=ro`, detección de estructura por tablas (11 tipos), metadatos
  normalizados, páginas por tipo y consultas directas (`bible_chapter`,
  `page_by_ref`, `chapter_comments`).
- **Descifrado SQLitePlus** con Twofish-128-ECB (núcleo vendorizado, GPL-3.0).
  Verificado sobre LBLA (31.102 versículos cifrados).
- **Catálogo** (`core/catalog.py`): escaneo incremental de la carpeta de
  recursos, clasificación por estructura, fingerprint sha1 y detección de
  duplicados, estado de indexación persistente.
- **Índice FTS5** (`core/store.py`, `core/indexer.py`): tabla `page` con
  contenido externo, `remove_diacritics 2`, triggers de sincronía, búsqueda por
  prefijo y fallback AND→OR. Indexación bajo demanda por categoría.
- **Descifrado paralelo** con `ProcessPoolExecutor` para biblias cifradas:
  109 s → ~13 s (31k versículos).
- **Búsqueda unificada** (`core/search.py`): referencia (`Juan 3:16`), Strong
  (`G2316`) y texto libre, con detección de intención.
- **UI PySide6**: panel lateral por categorías plegables, pestañas cerrables y
  reordenables, Biblia con navegación libro/capítulo, vista paralela de dos
  traducciones, comentarios en línea bajo cada versículo, visor genérico para
  10 tipos de módulo, buscador con resultados agrupados y resaltado.
- **Temas claro/oscuro** y tipografía serif para Escritura.
- **i18n es/en** por catálogos JSON, español por defecto.
- **Persistencia** de geometría, pestañas abiertas, traducción y tema.
- **Preindexado base** al primer arranque: LBLA, RV1960 y comentario RV1960x
  (72.102 páginas en ~20 s).
- **Empaquetado**: `run.sh`, `Makefile`, `.desktop`, `pyproject.toml`.
- **48 pruebas** (`make test`).
- **Documentación**: `AGENTS.md`, 7 skills, arquitectura, formato e-Sword.

### Corregido

- **eSword (Wine) no arrancaba en silencio**: el symlink
  `~/StorageC/wine/drive_c/Program Files (x86)/e-Sword` apuntaba a
  `~/StorageC/Biblias/Biblias_bblx`, que no existe (los módulos se movieron a
  StorageA). Wine devolvía `c0000135` por stderr y código 0, invisible desde el
  `.desktop`. Repuntado a `/home/felipe/StorageA/Biblias/Biblias_bblx`; esto
  también repara el registro de `ComboList.ocx` y `RichEdit.ocx`, que apuntaban
  a la misma ruta rota.

### Notas

- El corpus tiene 43 módulos cifrados; el resto es SQLite plano.
- La caché vive en `~/StorageC/linuxEsword/.cache/` (el home está al 81%).
- `content.db` es regenerable; `catalog.db` se reconstruye con un rescaneo.
