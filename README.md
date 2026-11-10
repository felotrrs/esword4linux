# linuxEsword

Lector **nativo para Linux** de módulos de e-Sword. Sin Wine, sin emulación de
Windows y sin la UI de pestañas fijas del programa original.

- Abre **cualquier** módulo e-Sword desde **una única carpeta de recursos**.
- **Clasifica automáticamente** cada módulo por su estructura SQL (no por la
  extensión: en el corpus real hay `.refx` que son tópicos y `.cmtx` con el
  esquema antiguo de comentarios).
- **Panel lateral** con las bibliografías agrupadas por categoría y plegables.
- **Paneles centrales modificables**: pestañas cerrables, reordenables y vista
  paralela de dos traducciones.
- **Comentario junto al versículo**, tomado del módulo de comentarios que elijas.
- **Búsqueda unificada**: referencia (`Juan 3:16`), número Strong (`G2316`) o
  texto libre, con resaltado y salto directo al módulo.

## Estado

| Área | Estado |
|---|---|
| Lector SQLite e-Sword (11 tipos) | ✅ |
| Descifrado SQLitePlus (Twofish-128) | ✅ 43 módulos del corpus |
| Catálogo por estructura + dedup | ✅ 970 archivos |
| Índice FTS5 bajo demanda | ✅ |
| Biblia + comentario en línea + paralela | ✅ |
| Diccionarios / léxicos / mapas / devocionales | ✅ |
| UI bilingüe es/en | ✅ |
| Empaquetado `.desktop` | ✅ |

## Arranque rápido

```bash
cd ~/StorageC/linuxEsword
./run.sh          # crea el venv la primera vez y abre la app
```

o:

```bash
make install
make run
```

La primera ejecución escanea la carpeta de recursos y pre-indexa **LBLA**,
**RV1960** y el **comentario RV1960x** para que la búsqueda funcione de
inmediato. Leer la Biblia no depende del índice: funciona aunque la indexación
siga en curso.

## Carpeta de recursos

Por defecto:

```
/home/felipe/StorageA/Biblias/Biblias_bblx
```

Se puede cambiar desde **Archivo → Cambiar carpeta de recursos**. linuxEsword
**nunca escribe** en esa carpeta: la abre en modo `ro`.

## Caché

El catálogo y el índice viven en `~/StorageC/linuxEsword/.cache/` (el home está
al 81% de uso; StorageC tiene 136 GB libres).

| Archivo | Contenido |
|---|---|
| `catalog.db` | metadatos de los 970 archivos, estado de indexación |
| `content.db` | páginas planas + FTS5 (búsqueda) |

## Estructura

```
src/linuxesword/
  core/esword/   lector SQLite, Twofish/SQLitePlus, RTF (vendorizado)
  core/          catálogo, índice FTS5, búsqueda, libros, i18n
  ui/            PySide6: ventana, panel lateral, biblia, biblioteca, búsqueda
skills/          convenciones del proyecto (leer antes de tocar cada área)
documentacion/   arquitectura, formato e-Sword, changelog, deuda técnica
```

## Licencia

**GPL-3.0**. El descifrador Twofish es un port de
[KingJamesPureBibleSearch](https://github.com/dewhisna/KingJamesPureBibleSearch)
(© Donna Whisnant, GPL-3.0). Ver `LICENSE` y la cabecera de
`core/esword/twofish.py`.

Los módulos e-Sword son propiedad de sus respectivos titulares. linuxEsword es
un lector: no distribuye ni modifica su contenido.
