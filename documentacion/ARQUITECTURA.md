# Arquitectura de linuxEsword

## Problema

e-Sword es una aplicación Win32 que en Linux exige Wine, y su UI agrupa la
bibliografía en pestañas fijas por tipo, lo que vuelve incómodo tener cientos
de módulos. linuxEsword ataca las dos cosas:

1. **Lee los módulos de forma nativa** — no hay emulación: los módulos son
   SQLite y se abren directamente.
2. **Reorganiza la experiencia** — una única carpeta de recursos, clasificación
   automática, panel lateral plegable y paneles centrales libres.

## Capas

```
┌──────────────────────────────────────────────────────────────┐
│ ui/            PySide6. Solo presentación y coordinación.    │
│  main_window · sidebar · bible_view · library_view · search  │
├──────────────────────────────────────────────────────────────┤
│ core/          Lógica pura, sin Qt. Testeable sin pantalla.   │
│  catalog · indexer · store · search · books · text · context │
├──────────────────────────────────────────────────────────────┤
│ core/esword/   Acceso al formato. Única frontera con SQLite.  │
│  module · sqliteplus · twofish · rtf · font_codepages         │
├──────────────────────────────────────────────────────────────┤
│ Carpeta de recursos (ro)                                      │
└──────────────────────────────────────────────────────────────┘
```

`core/` no importa PySide6 en ningún punto. Eso permite ejecutar el motor desde
la CLI (`tools/bootstrap.py`) y probarlo sin servidor gráfico.

## Flujo de arranque

```
Settings.load()                     # ~/.config/linuxesword/settings.json
   │
   ├─ AppContext
   │    ├─ Catalog(catalog.db)       # metadatos, estado de índice
   │    ├─ ContentStore(content.db)  # page + page_fts
   │    └─ SearchEngine
   │
   ├─ MainWindow
   │    ├─ Sidebar.refresh()         # árbol desde catalog.db
   │    ├─ BibleView.navigate()      # lectura directa del módulo
   │    └─ QTimer 200 ms → _bootstrap()
   │           ├─ catálogo vacío → Worker: catalog.scan()
   │           └─ hay catálogo   → _auto_index() si falta el preindex
   │
   └─ app.exec()
```

La ventana se muestra **antes** de escanear o indexar. La lectura funciona
desde el primer instante.

## Dos caminos independientes

| | Lectura | Búsqueda |
|---|---|---|
| Fuente | módulo SQLite | `content.db` (FTS5) |
| Coste | 1 `SELECT` (+ descifrado de 1 registro) | consulta al índice |
| Depende del índice | **no** | **sí** |
| Bloquea la UI | no (< 30 ms) | no (< 100 ms) |

Esta separación es la decisión central: permite indexación bajo demanda sin
degradar la experiencia de lectura.

## Escaneo

`Catalog.scan()` recorre `rglob` filtrando por extensión, y para cada archivo:

1. `stat()` → si `size` y `mtime` no cambiaron, se salta (incremental).
2. `_probe()` abre el módulo, detecta estructura, lee `Details` y cuenta
   entradas.
3. `_upsert()` guarda metadatos y `fingerprint` (sha1 de tamaño + primeros
   64 KiB).
4. `_mark_duplicates()` marca copias idénticas por fingerprint; la UI las
   oculta salvo que se pidan.

970 archivos en ~3 s en frío, ~0,1 s en caliente.

## Indexación

```
index_module(row)
   ├─ kind == "bible" and encrypted → _bible_pages_parallel()
   │      SELECT todas las filas → ProcessPoolExecutor → descifrado
   └─ resto → _pages_sequential()
   │
   ├─ store.delete_module(id)        # idempotente
   ├─ store.add_pages(...)           # triggers → page_fts
   └─ catalog.set_status("ready")
```

El worker corre en un `QThread` con conexiones SQLite **creadas dentro del
hilo**. El hilo principal sigue leyendo del módulo sin tocar esas conexiones.

## Búsqueda

```
search(query)
   ├─ parse_reference()  → intent=reference
   ├─ ^[GH]\d+$          → intent=strong   (léxicos + diccionarios)
   └─ resto              → intent=text     (FTS5 + bm25 + snippet)
```

`build_match` cita cada término (evita inyección de sintaxis FTS) y convierte el
último en prefijo. Si `AND` no da resultados, se reintenta con `OR`.

## Persistencia

| Qué | Dónde | Regenerable |
|---|---|---|
| Preferencias, geometría, pestañas | `~/.config/linuxesword/settings.json` | sí |
| Catálogo | `~/StorageC/linuxEsword/.cache/catalog.db` | sí (rescaneo) |
| Índice FTS5 | `~/StorageC/linuxEsword/.cache/content.db` | sí (reindexado) |
| Módulos e-Sword | carpeta de recursos | **no — inmutable** |

## Decisiones (ADR resumidas)

| # | Decisión | Motivo |
|---|---|---|
| 1 | PySide6/Qt6 | `QTextDocument` renderiza bien el HTML de comentarios; LGPL; pip. |
| 2 | Vendorizar `core/esword` | App autocontenida sin atar el layout de un repo de stack; `make drift` evita deriva silenciosa. |
| 3 | Índice bajo demanda | 3,4 M páginas de golpe no aportan valor inmediato; la lectura no lo necesita. |
| 4 | FTS5 en lugar de motor externo | Ya viene en la stdlib (`sqlite3` 3.45); cero servicios. |
| 5 | Caché en StorageC | El home está al 81%; StorageC tiene 136 GB. |
| 6 | Pool de procesos solo para biblias cifradas | 32 núcleos convierten 109 s en ~13 s; el resto no lo justifica. |
| 7 | i18n por JSON, no `.ts`/`lrelease` | Sin paso de build; los agentes editan JSON sin fricción. |
