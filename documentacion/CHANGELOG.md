# Changelog

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
  **Ver → Léxico Strong predeterminado**.
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
  `_duplicados/manifest-*.json`. El catálogo pasó de 970 a 940 módulos.
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
