# ADR-0001 — Cliente nativo en PySide6/Qt6, sin Wine

- **Fecha**: 2026-11-10
- **Estado**: aceptada

## Contexto

e-Sword solo existe para Windows. En Linux corría bajo Wine, con dos problemas:

1. **Fragilidad**: dependía de un symlink de instalación, de controles OCX
   registrados (`ComboList.ocx`, `RichEdit.ocx`), de `wmp11` y de un prefijo
   64-bit con clases en `Wow6432Node`. Un solo eslabón roto producía un fallo
   silencioso (`c0000135` por stderr, código de salida 0).
2. **UI inadecuada**: la bibliografía se agrupa en pestañas fijas por tipo; con
   970 módulos (431 de referencias) la navegación es inmanejable.

Se necesita un cliente que abra **cualquier** módulo desde una carpeta única,
clasifique automáticamente y permita paneles libres con búsqueda real.

## Decisión

Aplicación **nativa** en **PySide6 (Qt 6)**, leyendo los módulos SQLite
directamente, sin capa de compatibilidad.

## Alternativas consideradas

| Opción | Por qué no |
|---|---|
| **Mantener Wine** | No resuelve el problema de UI ni la fragilidad. La app seguiría dependiendo de OCX y del prefijo. |
| **GTK4 + PyGObject** | Ya instalado, pero el renderizado de HTML rico de comentarios es pobre; requeriría WebKit2GTK para igualar `QTextDocument`. |
| **PyQt5** | Qt5 EOL; sin las APIs de Qt6. |
| **Electron / Tauri** | Excelente renderizado web, pero 150-300 MB de RAM para una app de lectura y un stack distinto al del resto del entorno. |

## Consecuencias

**Positivas**

- Arranque < 1,5 s; lectura de capítulo ~20 ms; sin emulación.
- `QTextDocument` renderiza RTF→HTML y HTML de módulos con calidad suficiente.
- `QTreeView`/`QTabWidget` cubren el panel lateral plegable y las pestañas
  cerrables/reordenables pedidas.
- Una sola dependencia (`PySide6-Essentials`, LGPLv3), instalable con pip.

**Negativas**

- ~120 MB de wheels en el venv.
- Hay que implementar a mano lo que e-Sword ya hacía (navegación, comparación,
  búsqueda). Es exactamente el objetivo del proyecto.
- La UI queda atada a Qt; la lógica no (ver `documentacion/ARQUITECTURA.md`:
  `core/` no importa PySide6).

## Nota sobre licencias

El descifrador Twofish es un port GPL-3.0 de KingJamesPureBibleSearch
(© Donna Whisnant). Por eso linuxEsword se distribuye como **GPL-3.0**. PySide6
es LGPLv3 y es compatible.
