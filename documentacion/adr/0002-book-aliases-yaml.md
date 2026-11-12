# ADR-0002 — Libros y alias en YAML (PyYAML)

- **Fecha**: 2026-11-11
- **Estado**: aceptada

## Contexto

La tabla de libros vivía en `core/books.py` como tuplas Python con alias
es/en. Al añadir nombres y abreviaturas de otras tradiciones aparecieron dos
problemas:

1. **No había una fuente legible** donde revisar o ampliar alias: cada nuevo
   formato (`Luk`, `Jhn`, `Rth`, `Ezk`, prefijos `I/II`, `Primera de…`,
   nombres franceses o portugueses) obligaba a editar código.
2. **Faltaban alias reales del corpus** (el registro del proyecto Bible tiene
   cientos) y los libros numerados duplicaban variantes con prefijo.

La app debe seguir arrancando **sin red**; el YAML se lee una vez al importar.

## Decisión

Mover libros, nombres y alias a `src/linuxesword/core/books.yaml`, cargado por
`core/books.py`. El YAML separa:

- `families`: series numeradas con `default` y `books` (p. ej. Corintios
  1→46, 2→47) y alias base sin número;
- `books`: los 73 IDs e-Sword con nombres `es/en/fr/pt`, abreviaturas y alias
  explícitos.

Se añade **PyYAML>=6** como dependencia de ejecución.

## Alternativas consideradas

| Opción | Por qué no |
|---|---|
| **Mantener tuplas Python** | Es la situación actual: ilegible para ampliar alias y propensa a duplicar variantes. |
| **JSON** | El usuario y el proyecto Bible usan YAML; JSON no admite comentarios ni listas multilínea legibles. |
| **TOML** | `tomllib` exige Python ≥3.11 y el proyecto declara ≥3.10; además el esquema anidado por idioma queda más verboso. |
| **Parser YAML propio** | Superficie de error innecesaria para un archivo de datos que se lee una vez. |
| **Leer el YAML del proyecto Bible en runtime** | Acopla linuxEsword a otra instalación y rompe el arranque sin ese repo. |

## Consecuencias

**Positivas**

- Una sola fuente para los 73 libros y todos sus alias; añadir un idioma es
  añadir un bloque en el YAML.
- Los tests verifican IDs, nombres y formatos sin tocar código de carga.
- El YAML se empaqueta con `package-data` (`linuxesword.core`).

**Negativas**

- Nueva dependencia pequeña (~700 KB) y un paso de instalación más.
- Un YAML mal formado impide arrancar; el loader lanza un error explícito con
  la ruta del archivo.
