# Changelog

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
