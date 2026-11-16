# UI — pestañas-vista, paneles y vistas

## Modelo

```
QMainWindow
└── QSplitter (horizontal)
    ├── Sidebar                (ocultable: Ctrl+B o botón ☰)
    └── QTabWidget
        ├── [0] SearchView     — fija, sin botón de cierre
        └── [1..] Workspace    — «Pestaña A», «Pestaña B», … con color
```

Un **Workspace** es una pestaña-vista: agrupa un recurso principal y, si ese
recurso es una biblia, su propia biblia paralela y su propio comentario.

```
Workspace
└── QStackedWidget
    ├── BiblePane                    (si el recurso principal es biblia)
    │   ├── toolbar  (traducción · libro · capítulo · paralela · comentario)
    │   └── QSplitter(Vertical)
    │       ├── QSplitter(Horizontal)  principal | paralela
    │       └── CommentaryPane         (inferior, ~28 %)
    └── LibraryView                  (cualquier otro tipo)
```

## Reglas

1. **Seleccionar un recurso NO crea pestaña.** El clic en el panel lateral
   carga el recurso como **principal de la pestaña activa**
   (`MainWindow.open_resource`). Crear pestaña es una acción explícita
   (`＋`, `Ctrl+T`).
2. **Una pestaña = un grupo.** Cambiar de recurso dentro de una pestaña
   reemplaza su recurso principal; no acumula materiales.
3. **Paralela y comentario solo existen en modo biblia.** Si el recurso
   principal no es una biblia, `Workspace` muestra `LibraryView` y la toolbar
   de biblia desaparece. No hay «vista paralela de diccionarios».
4. **`FIXED_TABS = 1`.** La pestaña «Buscar» no se cierra (se le quita el botón
   con `setTabButton(0, RightSide, None)`). No reordenar el supuesto: si cambia
   el número, revisar `_close_tab()`.
5. **Nunca cerrar la última pestaña-vista.** `_close_tab()` muestra
   `workspace.last` y aborta.
6. **El comentario va en su propio panel inferior**, no dentro del texto
   bíblico. `CommentaryPane` hace **una** consulta por capítulo
   (`chapter_comments`), nunca una por versículo.
7. **«Leer completo» abre un diálogo, no una pestaña** (`EntryDialog`). Evita
   proliferación de pestañas. El badge «emparejado con…» no usa el diálogo:
   cambia el módulo del `CommentaryPane` y lo muestra en el panel inferior
   (`open_inline` → `BiblePane._show_commentary_inline`).
8. **Todo trabajo largo va por `ui/tasks.py:Worker`** con conexiones SQLite
   creadas dentro del hilo. El panel lateral se deshabilita mientras corre.

## Nombres y colores de pestaña

- Nombre por defecto: `tr("workspace.default_name", letter="A")` → «Pestaña A».
  `_next_name()` usa la primera letra libre; si se renombra, la letra se libera.
- Color: `TAB_COLORS` (8 tonos). Se pinta un punto de 12 px como icono de
  pestaña (`color_dot`).
- Menú contextual de la pestaña: **Renombrar**, **Color**, **Cerrar**.
- El estado (`name`, `color`, `main_rel`, `parallel`, `parallel_rel`,
  `commentary`, `commentary_rel`, `split`) se persiste en
  `Settings.workspaces` y se restaura en `_restore_state()`.

## Menús y preferencias

- **Archivo** → escanear, carpeta, salir. **Editar** → Preferencias (`Ctrl+,`).
  **Ver** → panel lateral, sin clasificar y léxico Strong. **Índice** y
  **Ayuda** cierran la barra.
- Tema, idioma y tipografía viven **solo** en Preferencias, con pestañas
  «Apariencia» e «Idioma». No duplicar esas opciones en el menú Ver.
- Al aceptar: `MainWindow._open_preferences()` aplica tema (`_set_theme`),
  idioma (`_set_locale` → `_retranslate_ui`) y tipografía
  (`_apply_typography` → QSS + `reload_theme()` de cada vista).

## Panel lateral

- **Un solo clic** carga el módulo (`itemClicked` → `_on_click`). Un clic en
  una categoría la despliega/pliega.
- `itemActivated` (Enter) también carga, para teclado.
- Se oculta con **Ver → Panel de recursos** (Ctrl+B) o el botón ☰ de la
  esquina de las pestañas; el estado se guarda en `Settings.sidebar_visible`.
- Con el panel **visible** el `QSplitter` no es colapsable y el dock tiene
  mínimo `SIDEBAR_MIN_WIDTH + SIDEBAR_HANDLE_WIDTH` (240 + 15 px). Arrastrar
  el divisor nunca lo deja desaparecer; al ocultarlo queda solo el asa de 15 px.
- Los botones de filtro «tipo» e «idioma» van pegados y alineados a la
  izquierda: no insertar un `stretch` entre ellos.

## BiblePane

- `self._loading` bloquea señales al sincronizar combos (evita cascadas).
- `_current` guarda la referencia; `reload()` renderiza y avisa al
  `CommentaryPane` si el toggle está activo.
- Anclas `<a name="v16">` + `scrollToAnchor`.
- Enlaces: `v:N` (menú de versículo), `ref:<texto>` (navegar), `c:<id>:<ref>`
  (entrada completa en diálogo).
- **Sin tope lateral**: el `QTextBrowser` ocupa todo el ancho del panel; el
  margen de lectura lo da el padding (`8px 18px`) del QSS. Los `stretch`
  laterales se eliminaron porque dejaban ~17 % de ancho sin usar.
- **Combo de traducción** (`fill_bible_combo`): desplegable, agrupado por
  idioma y ordenado por abreviatura/título. Conserva la selección por
  `rel_path`; el combo de la vista paralela usa el mismo agrupado y se oculta
  si la paralela está desmarcada.
- **Caja de citas** (`core/refchain.py` + `ui/citation_pane.py`): acepta
  `Gn23:1-6, 2:5-7; Mar 2:1; Jn3:16`, hereda libro/capítulo y **sustituye la
  vista principal** por la colección agrupada por capítulo. El botón ↩ vuelve
  al capítulo. Libro, capítulo y flechas ◀ ▶ siguen siempre visibles en modo
  citas: ocultarlos dejaba la barra sin forma de volver a la navegación normal.
  La vista paralela muestra la misma colección en la traducción secundaria.
- La barra no usa flechas verticales de capítulo: el capítulo es editable sin
  botones y se navega con ◀ ▶.

## CommentaryPane

- Cabecera: título · badge de emparejamiento · combo de módulos · **Abrir** ·
  **✕** (oculta el panel y desmarca el toggle).
- El badge «emparejado con…» emite `open_inline`; `BiblePane` muestra este
  mismo panel y se desplaza al versículo actual. No abre `EntryDialog`.
- Renderiza por versículo con encabezado «Juan 3:16» y el texto completo.
- Si el texto supera `MAX_CHARS` (9 000), recorta y ofrece «Leer completo».

## Trampas conocidas de Qt

- `isVisible()` es **falso** mientras la ventana no se ha mostrado: no usarlo
  para decidir si renderizar. Usar el estado del toggle.
- `QTextDocument` ignora `color` inline en `<a>`: usar `<font color>` dentro.
- `QLabel` con `wordWrap` dentro de `QSplitter` no calcula bien el alto.
- `processEvents()` no dispara un `QTimer` de 180 ms: en pruebas, esperar.
- `QTabWidget.setMovable(True)` permite mover la pestaña fija; es inocuo
  (el cierre sigue bloqueado por índice).
- `QFontComboBox` es **editable** por defecto y parece una caja de texto. Para
  elegir fuente en Preferencias se usa un `QComboBox` no editable con
  `QFontDatabase.families()`.

## Barra de pestañas propia (`ui/tab_bar.py`)

QSS no permite color por pestaña (`QTabBar` no tiene `:nth-child`), así que
`ColoredTabBar` pinta a mano:

- **seleccionada**: color pleno + texto en **negrita** con contraste calculado
  por luminancia; **no seleccionada**: tinte pálido (18 %) + texto atenuado.
- botón de cierre con `CLOSE_MARGIN` derecho (no pegado al borde).
- botón **＋** dibujado detrás de la última pestaña, con hit-testing propio
  (`new_tab_requested`).
- el color viaja con la pestaña porque se guarda en `setTabData()`.

`QTabWidget.setTabsClosable(False)`: el cierre lo pinta la barra. La conexión
`tabBar().tabCloseRequested → _close_tab` es explícita.

## Panel lateral plegable

`SidebarDock` = `[Sidebar][asa vertical de 15 px]`. El asa (`#sidebarHandle`)
queda siempre visible en el borde: `‹` cuando está abierto, `›` cuando está
plegado. `toggle_sidebar()` guarda el ancho previo en `_sidebar_width` y lo
restaura al reabrir.

## Panel inferior apilado

`QStackedWidget{ CommentaryPane, StrongPane }` + dos `QToolButton` checkables
en una `QButtonGroup` exclusiva (`Comentario`, `Léxico`). El estado va a
`Settings.bottom_page` y `show_commentary_inline`; al pulsar de nuevo el botón
activo se oculta el panel.

## Panel lateral: organizador de filtros y agrupaciones

`Sidebar` combina hasta **tres niveles de agrupación** (`kind`, `language`,
`work`) en orden, más **filtros múltiples** por tipo e idioma y el filtro de
texto. Se persiste en `Settings.sidebar_grouping`, `sidebar_kind_filters` y
`sidebar_language_filters`. Los títulos «Agrupar» y «Filtrar» ocupan una línea
completa cada uno, con un espacio vertical entre ambos bloques.

- **kind** — categorías (`KIND_ORDER`).
- **work** — `Catalog.works()` agrupa por título normalizado; el año separa
  ediciones cuando conviven varios dentro del mismo título base.
- **language** — `module.language` (`es`, `en`, `fr`, `pt`, `de`, `it`, `la`,
  `grc`, `hbo`, `und`) con etiquetas `lang.*`.
  `detect_language()` combina título/abreviatura, marcador de archivo, muestra
  corta de contenido y alfabetos originales; `METADATA_VERSION` fuerza un
  re-escaneo de metadatos cuando cambia la heurística.

El árbol se construye de forma anidada y el filtro de texto es recursivo:
si coincide con un grupo, muestra todos sus descendientes.

## Panel de términos de LibraryView

`LibraryView` (diccionarios, léxicos, referencias…) tiene su propio
`QSplitter` entre la lista de términos y el detalle:

- lista con mínimo `LIST_MIN_WIDTH` (220 px) y detalle con
  `DETAIL_MIN_WIDTH` (240 px); `setChildrenCollapsible(False)`;
- botón `☰` **siempre visible en la cabecera** para ocultar/mostrar la lista;
- estado en `Settings.library_list_visible` y ancho en
  `Settings.library_list_width`;
- stretch `0` para la lista y `1` para el detalle: al ensanchar la ventana
  crece el texto, no la lista.

## Burbujas (`ui/tooltip.py`)

`TipBubble` sustituye al tooltip nativo por una tarjeta pintada directamente
desde un `QTextDocument` (sin `QTextBrowser`, viewport ni scrollbars): fondo
`#23262e`, borde izquierdo de acento, **ancho adaptable hasta 600 px** y
cabecera en dorado. La cabecera es compacta (referencia o abreviatura del
léxico, nunca el título largo de la obra). Cada línea del cuerpo es un bloque
independiente, de modo que las palabras hebreas conservan su dirección RTL.
El alto es `documentLayout().documentSize()` + padding + un margen inferior de
5 px: la última línea y sus descendentes nunca quedan cortados. Los pasajes
muestran hasta 10 versículos completos (`RefResolver.MAX_VERSES`); las entradas
del léxico se capan a 2500 caracteres (con aviso para abrir la entrada completa
en el panel Léxico).
`RichBrowser` extrae los `title=` del HTML a su mapa interno (para que Qt no
muestre el suyo) y resuelve los Strong al vuelo. Al cambiar de léxico o de
comentario se invalidan las cachés con `RichBrowser.clear_all_caches()`.

## Léxico Strong predeterminado

El combo del panel Léxico lista los 15 léxicos que indexan por `G####`/`H####`
(★ = activo). Cambiarlo llama a `StrongIndex.set_default()`, que persiste
`settings.strong_rel`, invalida la caché y refresca las burbujas al instante
(igual que el combo de comentarios actualiza las notas del capítulo). También
está en **Ver → Léxico Strong predeterminado**.
