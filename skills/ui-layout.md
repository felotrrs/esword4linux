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
   proliferación de pestañas.
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

## Panel lateral

- **Un solo clic** carga el módulo (`itemClicked` → `_on_click`). Un clic en
  una categoría la despliega/pliega.
- `itemActivated` (Enter) también carga, para teclado.
- Se oculta con **Ver → Panel de recursos** (Ctrl+B) o el botón ☰ de la
  esquina de las pestañas; el estado se guarda en `Settings.sidebar_visible`.

## BiblePane

- `self._loading` bloquea señales al sincronizar combos (evita cascadas).
- `_current` guarda la referencia; `reload()` renderiza y avisa al
  `CommentaryPane` si el toggle está activo.
- Anclas `<a name="v16">` + `scrollToAnchor`.
- Enlaces: `v:N` (menú de versículo), `ref:<texto>` (navegar), `c:<id>:<ref>`
  (entrada completa en diálogo).
- Columna de lectura centrada con `setMaximumWidth(980)`.

## CommentaryPane

- Cabecera: título · combo de módulos · **Abrir** · **✕** (oculta el panel y
  desmarca el toggle).
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
