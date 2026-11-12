# Libros, alias y referencias

## Fuente única

`core/books.yaml` es la **única** definición de:

- los 73 libros e-Sword (`id` 1–73);
- sus nombres en `es`, `en`, `fr` y `pt`;
- abreviaturas y alias de distintas tradiciones editoriales.

`core/books.py` carga el YAML, normaliza y expone `BOOKS`, `book_name()`,
`book_abbrev()`, `resolve_book()` y `parse_reference()`. **No crear listas de
libros o alias en otros módulos, tests, documentación ni en la UI.**

Procedencia: los alias base se importaron de `shared/book_aliases.yaml` del
proyecto Bible; aquí viven en `core/books.yaml` para que linuxEsword arranque
sin depender de ese repo.

## Esquema del YAML

```yaml
books:
  genesis:
    id: 1
    names: {es: Génesis, en: Genesis, fr: Genèse, pt: Gênesis}
    abbreviations: {es: [gn, gen], en: [gen, ge]}
    aliases:
      es: [genesis, gen, gn, ge]
      en: [genesis, gen, gn, ge]
      fr: [genèse, genese, gen, gn]
      pt: [gênesis, genesis, gen, gn]
```

No hace falta enumerar variantes de acentos, mayúsculas o puntos: el loader
aplica NFD, minúsculas, quita diacríticos y puntos, y colapsa espacios. Sí hay
que añadir **ortografías reales distintas** (`gen` y `gn`, `jhn` y `john`).

## Libros numerados

Las series (Samuel, Reyes, Crónicas, Corintios, Tesalonicenses, Timoteo, Pedro,
cartas de Juan, Macabeos) se declaran una vez en `families`:

```yaml
families:
  corinthians:
    default: 46        # forma sin número → 1 Corintios
    books: {1: 46, 2: 47}
    aliases: [corintios, cor, co, corinthians, corinthiens]
```

`resolve_book()` entiende `1`, `2`, `3`, `I`, `II`, `III`,
`Primera/Segunda/Tercera`, `1ª`, `1a`, `1ra`, `first/second/third`, etc.
No se duplican alias con prefijo en el YAML.

`john_letters` tiene `default: null` a propósito: «Juan»/«John» sin número es
el Evangelio (43), no 1 Juan (62).

## Detección en texto (`core/refs.py`)

`find_reference_spans()` enlaza las citas de la bibliografía y devuelve un span
por sub-referencia. Formatos cubiertos:

```
Ex. 32.1–6      Ex. 7.8ss        (He. 5.4; 7.11)
(Ex. 4:14, 27-30)   Exo_28:1; Heb_5:4   Jn 3,16
I Samuel 1:1    Primera de Corintios 13:4   Génesis 1-3
The Wisdom of Solomon 2:23   Cantar de los Cantares 1:1
```

- Coma como separador capítulo–versículo (`Jn 3,16`) y como continuación
  (`Ex. 4:14, 27-30`).
- Capítulo–versículo con `.`, `:`, `,` o espacio.
- Nombres de varias palabras: se intentan extensiones a la izquierda hasta 6
  palabras (`_extend_book`), sin construir una alternancia gigante.
- Libros que no existen en la numeración 1–73 (`1 Esdras`, `3 Macc`) **no se
  enlazan a otro libro**: se descartan.
- `SCAN_CHARS = 200_000` para que las citas del final de entradas largas también
  se enlacen.

## Burbujas

`core/refresolver.py:RefResolver` es la única implementación de la burbuja de
pasaje (la usan la Biblia, la biblioteca y el comentario):

- versículo único → texto completo, sin `snippet`;
- rango → todos los versículos del rango;
- capítulo o rango abierto → máximo `MAX_VERSES = 10`;
- si hay más, se añade `tooltip.more_verses` con el número restante.

`core/strong.py:StrongIndex.tooltip()` usa solo la **abreviatura** del léxico en
la cabecera (no el título largo), capa la entrada a 2500 caracteres y, si se
corta, remite al panel Léxico para leerla completa.

## Al añadir un idioma o un alias

1. Edita solo `core/books.yaml` (nombres y alias).
2. Añade un caso en `tests/test_books.py` / `tests/test_matching.py`.
3. `make test` en verde y comprueba que `./run.sh` arranca.
