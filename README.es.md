# esword4linux

**Lector nativo para Linux de módulos de e-Sword — sin Wine y sin contenido incluido.**

[English](README.md) · [Guía de instalación detallada (English)](docs/INSTALL.md) · [Documentación](docs/README.md) · [Cambios](docs/CHANGELOG.md)

<p align="center">
  <img src="packaging/icons/hicolor/256x256/apps/esword4linux.png" alt="Icono de esword4linux" width="128">
</p>

esword4linux abre los módulos SQLite que ya posees desde **una única carpeta
elegida por ti**. Clasifica cada archivo por la estructura de su base de datos,
no por la extensión, y no modifica ni un byte de tu biblioteca.

> **Este repositorio no incluye biblias, comentarios, diccionarios ni ningún
> otro módulo de e-Sword.** En el primer arranque eliges la carpeta que contiene
> tus propios módulos. Los módulos de e-Sword son propiedad de sus respectivos
> editores.

## Características

- **Una sola carpeta de módulos.** Lee cualquier módulo compatible en su sitio,
  en modo de solo lectura.
- **Detección por estructura.** Un `.refx` que en realidad es un tópico o un
  `.cmtx` con el esquema antiguo de comentarios se clasifican correctamente.
- **Pestañas-vista.** Cada pestaña tiene su recurso principal, su biblia paralela
  y su panel de comentario. Al seleccionar un módulo se reutiliza la pestaña
  activa; `Ctrl+T` crea otra.
- **Panel lateral organizable.** Agrupa por tipo, idioma y obra, combina hasta
  tres niveles y filtra por varios tipos o idiomas a la vez (`Ctrl+B` lo pliega).
- **Lectura bíblica.** Traducción paralela, navegación por capítulos, cadenas de
  citas múltiples, burbujas de versículos y de números Strong.
- **Paneles de comentario y léxico.** El comentario se empareja con la biblia
  activa y se muestra en el panel inferior; el léxico Strong usa ese mismo panel.
- **Búsqueda unificada.** Una sola caja entiende referencias bíblicas, números
  Strong y texto libre. El índice FTS5 es opcional y solo se construye cuando tú
  lo pides.
- **Módulos cifrados.** Los módulos SQLitePlus/Twofish-128 se pueden leer e
  indexar.
- **Interfaz bilingüe.** Español e inglés, con cambio en caliente.
- **Tipografía legible.** Fuentes independientes para interfaz, Escritura y texto
  corriente; temas claro y oscuro.

## Requisitos

El entorno de referencia para v0.5.0 es:

- **Linux Mint 22.3** (base Ubuntu 24.04/noble), Cinnamon/X11
- **Python 3.12.3**
- Una sesión gráfica de escritorio. Esta guía se verificó en X11; el paquete de
  PySide6 incluye un plugin de Wayland, pero Wayland no se verificó.
- **Conexión a Internet la primera vez** que ejecutes `./run.sh` o
  `make install`, para descargar las dependencias de Python desde PyPI. Una vez
  creado el entorno virtual, los arranques normales funcionan sin red.

El proyecto declara Python 3.10 o superior. Otras versiones basadas en
Debian/Ubuntu no se verificaron para v0.5.0.

### Dependencias del sistema en Linux Mint / Ubuntu

```bash
sudo apt update
sudo apt install -y python3 python3-venv
sudo apt install -y libegl1 libgl1 libxkbcommon-x11-0 libxcb-cursor0 \
    libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 \
    libxcb-render-util0 libxcb-shape0 libxcb-xkb1
```

Si instalas desde Git o usas los comandos `make`, instala también:

```bash
sudo apt install -y git make
```

Si usas los ejemplos de terminal para descargar archivos, instala también
`curl` y `unzip`:

```bash
sudo apt install -y curl unzip
```

Estas instrucciones no necesitan `python3-pip`: el entorno virtual crea su
propio `pip`. Los nombres de los paquetes Qt se verificaron en Linux Mint 22.3
contra el plugin `libqxcb.so` real de PySide6.

## Instalación

Los requisitos detallados, la solución de problemas y las notas de
desinstalación están en [`docs/INSTALL.md`](docs/INSTALL.md) (en inglés).

### Desde Git

```bash
git clone https://github.com/felotrrs/esword4linux.git
cd esword4linux
./run.sh
```

El primer `./run.sh` crea `.venv`, instala PySide6-Essentials y PyYAML desde
PyPI y abre la aplicación. Este primer paso necesita Internet. Los arranques
posteriores usan el entorno ya creado y funcionan sin red.

Para desarrollo, `make install` crea el mismo entorno virtual e instala además
el extra `dev` (`pytest`):

```bash
make install
make run
```

### Desde un archivo ZIP/TAR de código fuente

Descarga el código fuente de v0.5.0 desde GitHub:

- [esword4linux v0.5.0 tar.gz](https://github.com/felotrrs/esword4linux/archive/refs/tags/v0.5.0.tar.gz)
- [esword4linux v0.5.0 zip](https://github.com/felotrrs/esword4linux/archive/refs/tags/v0.5.0.zip)

Extráelo con tu gestor de archivos o desde una terminal:

```bash
curl -L -o esword4linux-v0.5.0.tar.gz \
  https://github.com/felotrrs/esword4linux/archive/refs/tags/v0.5.0.tar.gz
tar -xzf esword4linux-v0.5.0.tar.gz
cd esword4linux-0.5.0
./run.sh
```

Para el ZIP, sustituye la descarga y la extracción por
`curl -L -o esword4linux-v0.5.0.zip ...` y `unzip esword4linux-v0.5.0.zip`.
Los ejemplos de terminal usan `curl`, `tar` y `unzip`; también puedes usar el
gestor de archivos.

### Primer arranque

En el primer inicio, esword4linux pide la carpeta que contiene tus módulos de
e-Sword (`.bblx`, `.bbli`, `.cmtx`, `.cmti`, `.dctx`, `.lexi`, `.refx`, `.topx`,
`.devx`, `.harx`, `.mapx`, `.twm`…). Si cancelas, la aplicación se cierra.
Puedes cambiar la carpeta después desde **Archivo → Cambiar carpeta de módulos**.

## Lanzamiento

Desde el checkout:

```bash
./run.sh
```

O, después de `make install`:

```bash
make run
```

### Lanzador de escritorio

Después de que `./run.sh` o `make install` hayan creado el entorno virtual,
ejecuta:

```bash
make desktop
```

Esto instala `~/.local/share/applications/esword4linux.desktop` y los iconos de
la aplicación en `~/.local/share/icons/hicolor/`. El lanzador usa el script
`run.sh` de la **ubicación actual del checkout**; si mueves o borras el
checkout, la entrada del menú deja de funcionar. Ejecuta `make desktop` de nuevo
desde la nueva ubicación para repararla.

La entrada del menú puede tardar un momento en aparecer, o puede requerir cerrar
y volver a iniciar sesión.

## Desinstalación

v0.5.0 no tiene instalador para todo el sistema ni un objetivo `make uninstall`.
La aplicación se ejecuta desde el checkout y guarda los datos de usuario por
separado.

1. Borra la carpeta del checkout (por ejemplo `esword4linux` o
   `esword4linux-0.5.0`).
2. Si ejecutaste `make desktop`, elimina el lanzador y los iconos:

   ```bash
   rm -f ~/.local/share/applications/esword4linux.desktop
   rm -f ~/.local/share/icons/hicolor/*/apps/esword4linux.png
   gtk-update-icon-cache -f -t ~/.local/share/icons/hicolor 2>/dev/null || true
   update-desktop-database ~/.local/share/applications 2>/dev/null || true
   ```

Tus preferencias y la caché de búsqueda se **conservan** por defecto:

- `~/.config/esword4linux/` (preferencias)
- `~/.cache/esword4linux/` (catálogo e índice de búsqueda)

Elimínalos manualmente solo si quieres una desinstalación completamente limpia:

```bash
rm -rf ~/.config/esword4linux ~/.cache/esword4linux
```

esword4linux nunca modifica tu carpeta de módulos de e-Sword. Bórrala solo si
quieres eliminar tus propios módulos.

`make clean` elimina únicamente `.venv`, `.pytest_cache` y el `.cache` del
repositorio; **no** elimina la configuración/caché XDG ni el lanzador y los
iconos del escritorio.

## Leer no es indexar

La lectura es directa y no necesita índice. El primer escaneo solo recoge
metadatos para que el panel lateral muestre tu biblioteca.

Genera los índices de búsqueda solo cuando quieras:

- **Índice → Indexar esta categoría** para un tipo de módulo
- **Índice → Indexar todo** para toda la biblioteca
- **Índice → Descifrar módulos cifrados** para módulos SQLitePlus
- o desde la línea de comandos:

```bash
make scan          # solo metadatos
make encrypted     # descifra e indexa módulos cifrados (explícito)
python tools/bootstrap.py --kind bible
python tools/bootstrap.py --all
```

Ningún módulo se indexa ni se descifra automáticamente al arrancar.

## Estado de distribución

**v0.5.0 es solo código fuente.** Se distribuye como código Git y como los
archivos fuente generados automáticamente por GitHub desde el tag. No se
proporciona ningún paquete DEB, AppImage, Flatpak ni Snap.

## Ubicación de los datos

| Qué | Dónde |
|---|---|
| Módulos | Tu propia carpeta, en solo lectura |
| Preferencias | `~/.config/esword4linux/settings.json` |
| Catálogo | `~/.cache/esword4linux/catalog.db` |
| Índice de búsqueda | `~/.cache/esword4linux/content.db` |

El catálogo y el índice son regenerables. Borrar la caché es seguro; tus módulos
no se tocan.

## Familias de módulos compatibles

| Familia | Extensiones típicas | Detección |
|---|---|---|
| Biblias | `.bblx`, `.bbli` | tabla `Bible` |
| Comentarios | `.cmtx`, `.cmti` | `Verses`, `VerseCommentary`, `BookCommentary` o `ChapterCommentary` |
| Diccionarios | `.dctx`, `.dcti`, `.twm` | `Dictionary`, o `topics` + `config` |
| Léxicos | `.lexi`, `.lexx` | `Lexicon` |
| Libros / referencias | `.refx`, `.refi`, `.topx` | `Reference` o `Topics`, refinado por contenido |
| Devocionales | `.devx` | `Devotions` o `Devotional` |
| Armonías | `.harx` | `Sections` + `Parts` |
| Mapas | `.mapx` | `Graphics` |

La extensión solo sirve para descubrir archivos. El tipo siempre sale de la
estructura SQL.

## Desarrollo

```bash
make install
make test
```

La suite se ejecuta sin ningún módulo de e-Sword. Las pruebas que necesitan
módulos reales se omiten salvo que indiques un corpus:

```bash
ESWORD4LINUX_TEST_CORPUS=/ruta/a/tus/modulos .venv/bin/python -m pytest -q
```

Nunca hagas commit de módulos. `.gitignore` bloquea a propósito las extensiones
habituales de e-Sword.

Consulta [AGENTS.md](AGENTS.md) para las reglas del proyecto,
[CONTRIBUTING.md](CONTRIBUTING.md) para el flujo de desarrollo y [docs/](docs/)
para arquitectura, notas de formato, deuda técnica y ADRs.

## Licencia

**GPL-3.0**. El descifrador Twofish es un port de
[KingJamesPureBibleSearch](https://github.com/dewhisna/KingJamesPureBibleSearch)
(© Donna Whisnant, GPL-3.0). Ver [LICENSE](LICENSE) y
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Los módulos de e-Sword son propiedad de sus respectivos titulares. esword4linux
es solo un lector: no distribuye ni modifica su contenido.
