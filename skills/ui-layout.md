# UI — ventana, pestañas y vistas

## Estructura

```
QMainWindow
└── QSplitter (horizontal)
    ├── Sidebar        (260–460 px, categorías + módulos)
    └── QTabWidget     (pestañas cerrables y reordenables)
        ├── [0] BibleView    — fija, no cerrable
        ├── [1] SearchView   — fija, no cerrable
        └── [2..] LibraryView — una por módulo abierto
```

`FIXED_TABS = 2` en `ui/main_window.py`. Cambiar ese número obliga a revisar
`open_module()`, `_close_tab()` y la restauración de estado.

## Reglas

1. **Las dos primeras pestañas no se cierran.** `_close_tab()` ignora
   `index < FIXED_TABS`. El usuario puede reordenar, pero no destruirlas.
2. **Una pestaña por módulo.** `_index_tabs[module_id] = índice`. Abrir un
   módulo ya abierto cambia de pestaña, no crea otra. Al cerrar se reindexa el
   mapa entero: los índices de pestaña se desplazan.
3. **Los índices de pestaña se recalculan al cerrar.** No confiar en el orden
   anterior tras `removeTab()`.
4. **Nunca recrear pestañas para cambiar el tema.** Usar
   `LibraryView.reload_theme()` y `BibleView.reload()`. Recrear pierde la
   selección y salta de pestaña.
5. **Persistencia**: `Settings.window_geometry` (base64) y
   `Settings.open_tabs` (lista de `module_id`). Se guarda en `closeEvent`.
6. **Toda operación larga va por `ui/tasks.py:Worker`.** El worker crea sus
   propias conexiones (`Catalog`/`ContentStore`) dentro del hilo; no se pasan
   objetos del hilo principal.
7. **El panel lateral se deshabilita mientras hay un worker**
   (`sidebar.setEnabled(False)`), y se rehabilita en `_worker_finished`.

## BibleView

- Barra: traducción · libro · capítulo · ◀▶ · paralela · comentarios · 🔍
- `self._loading` bloquea señales mientras se sincronizan combos (evita
  cascadas `currentIndexChanged`).
- Render: un `QTextBrowser` por columna. En paralela, `self.second`.
- Anclas: `<a name="v16">` + `scrollToAnchor(f"v{verse}")`.
- Enlaces soportados en `_on_anchor`:
  - `v:N` → menú del versículo (copiar, buscar selección)
  - `c:<module_id>:<ref>` → abre el módulo de comentario en una pestaña
  - `ref:<texto>` → navega a esa referencia (viene de `<ref>` de los módulos)
- Comentarios en línea: **una** consulta por capítulo
  (`chapter_comments()`), no una por versículo.

## LibraryView

- Izquierda: filtro + A-Z + `QListWidget`.
- Derecha: `QTextBrowser` con la entrada.
- `MAX_ENTRIES = 3000` en la lista. El filtro usa `LIKE '%x%'` (`contains=True`);
  el salto A-Z usa `LIKE 'x%'` (`contains=False`). No intercambiarlos.
- Mapas: `mod.map_picture(ref)` → `QTextDocument.addResource` + `<img src="map:...">`.

## Añadir una vista nueva

1. `QWidget` con `Signal` hacia `MainWindow` (no al revés).
2. Registrarla en `MainWindow._build_ui()` o abrirla desde `open_module()`.
3. Si tiene tema propio, exponer `reload_theme()`.
4. Añadir sus cadenas a `i18n/es.json` **y** `i18n/en.json`.

## Trampas conocidas de Qt

- `QTextDocument` **ignora** `color` inline en `<a>`: usar
  `<font color="...">` dentro del ancla.
- Los `class` del CSS del documento funcionan, pero la especificidad no es la
  de un navegador: si algo no aplica, usar `<font>`/`style` inline.
- `QLabel` con `wordWrap` dentro de un `QSplitter` no calcula bien el alto: usar
  widgets de ancho fijo o un `<a>` por letra con `setFixedWidth`.
- `processEvents()` **no** dispara un `QTimer` de 180 ms: en pruebas hay que
  esperar de verdad (o llamar al slot directamente).
