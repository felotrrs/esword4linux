# linuxEsword

Lector **nativo para Linux** de módulos de e-Sword. Sin Wine, sin emulación de
Windows y sin la UI de pestañas fijas del programa original.

- Abre **cualquier** módulo e-Sword desde **una única carpeta de recursos**.
- **Clasifica automáticamente** cada módulo por su estructura SQL (no por la
  extensión: en el corpus real hay `.refx` que son tópicos y `.cmtx` con el
  esquema antiguo de comentarios).
- **Panel lateral organizable**: agrupa hasta en tres niveles
  (**tipo → idioma → obra**) y permite filtrar por varios tipos e idiomas a la
  vez. Plegable con `Ctrl+B`; conserva un ancho mínimo cuando está visible.
- **Combo de traducción agrupado por idioma**, igual que el combo de la vista
  paralela; al desplegarlo se ven todas las versiones ordenadas. La lista de términos de diccionarios se
  puede ocultar/mostrar con un asa, sin perder el acceso al texto.
- **Caja de citas múltiples** en la Biblia: `Gn23:1-6, 2:5-7; Mar 2:1; Jn3:16`
  sustituye la vista del capítulo por la colección de versículos (también en la
  vista paralela) y permite volver con ↩.
- **Pestañas-vista**: cada pestaña («Pestaña A», «Pestaña B»…) agrupa su propio
  recurso principal y, si es una biblia, su biblia paralela y su comentario.
  Pestaña coloreada completa, texto en negrita al seleccionar, tinte pálido en
  las demás, botón ＋ estilo navegador y renombrado/color por menú contextual.
- **Comentario en panel inferior** (división vertical, ~28 %), no dentro del
  texto bíblico. El panel alterna **Comentario ⇄ Léxico**.
- **Notas y Léxico navegables**: burbuja propia (ancho adaptable, color
  distinto) al pasar el ratón; al pulsar `(B)` se abre el comentario emparejado
  con esa biblia y se salta a la nota; al pulsar `G2316` se abre el léxico
  elegido.
- **Burbujas también en la bibliografía**: diccionarios y comentarios enlazan
  sus citas (incluidas las de texto plano) y muestran el versículo.
- **Búsqueda unificada**: referencia (`Juan 3:16`), número Strong (`G2316`) o
  texto libre, con resaltado y salto directo al módulo.
- **Preferencias** (`Ctrl+,`): tema, idioma de la interfaz y tipografía
  independiente para la UI, la Escritura y el texto de comentarios,
  diccionarios y búsqueda, con vista previa en vivo.

## Estado

| Área | Estado |
|---|---|
| Lector SQLite e-Sword (11 tipos) | ✅ |
| Descifrado SQLitePlus (Twofish-128) | ✅ 43 módulos del corpus |
| Catálogo por estructura + dedup | ✅ 970 archivos |
| Índice FTS5 bajo demanda | ✅ |
| Biblia + comentario en panel inferior + paralela | ✅ |
| Pestañas-vista con color pleno y botón ＋ | ✅ |
| Notas/Léxico con burbuja y navegación | ✅ |
| Diccionarios / léxicos / mapas / devocionales | ✅ |
| UI bilingüe es/en (en caliente) | ✅ |
| Preferencias de tema, idioma y tipografía | ✅ |
| Bibliografía agrupada/filtrada por tipo e idioma | ✅ |
| Citas múltiples con vista de colección | ✅ |
| Iconos de aplicación (hicolor 16–512) | ✅ |
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
/home/felipe/StorageA/Biblias/Biblias_esword
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
  core/          catálogo, índice FTS5, búsqueda, libros (books.yaml), i18n
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
