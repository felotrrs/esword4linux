# Formato de módulos e-Sword — notas de ingeniería inversa

Documento de referencia. Todo lo aquí descrito se verificó contra el corpus real
de `/home/felipe/StorageA/Biblias/Biblias_esword` (970 archivos, 4,95 GB).

## 1. Contenedor

**Todos** los módulos son bases SQLite 3. Codificación del texto: UTF-16LE en
los módulos antiguos, UTF-8 en los modernos. SQLite lo gestiona de forma
transparente; el driver devuelve `str`.

```
$ file kjv.bblx
SQLite 3.x database ... UTF-16 little endian
```

## 2. Esquemas por tipo

### Biblia — `.bblx` / `.bbli`

```sql
Details (Title, Abbreviation, Information, Version,
         OldTestament, NewTestament, Apocrypha, Strongs, RightToLeft)
Bible   (Book INT, Chapter INT, Verse INT, Scripture TEXT|BLOB)
sqliteplus_license (Name)   -- solo si está cifrado
```

- `Book` 1–66 canónico; 67–73 deuterocanónicos en algunas ediciones.
- `.bbli` = mismo esquema, `Scripture` siempre `TEXT` (plano).
- `.bblx` puede tener `Scripture` como `BLOB` cifrado.

### Comentario, esquema nuevo — `.cmtx`

```sql
Details (Title, Abbreviation, Information, Version)
Books   (Book, Comments)
Chapters(Book, Chapter, Comments)
Verses  (Book, Chapter, Verse, Comments)
```

### Comentario, esquema antiguo — `.cmti` (y algunos `.cmtx`)

```sql
Details (Title, Abbreviation, Information, Version)
BookCommentary   (Book, Comments)
ChapterCommentary(Book, Chapter, Comments)
VerseCommentary  (Book, ChapterBegin, VerseBegin,
                  ChapterEnd, VerseEnd, Comments)
```

`VerseCommentary` cubre un rango: `[ChapterBegin:VerseBegin, ChapterEnd:VerseEnd]`.
En el corpus, `tsk.cmtx` y `comment_rvr1960x_es.cmti` usan este esquema.

### Diccionario — `.dctx` / `.dcti`

```sql
Details (Title, Abbreviation, Information, Version)
Dictionary (Topic NVARCHAR(100), Definition BLOB_TEXT|TEXT)
```

### Léxico — `.lexi` / `.lexx`

Estructuralmente idéntico a diccionario, con tabla `Lexicon`.

### Referencia — `.refi` / `.refx`

```sql
Details   (Title, Abbreviation, Information, Version)
Reference (Chapter, Content)
```

Cada `Chapter` es una entrada temática con HTML rico. En el corpus, 431 módulos
(la mayoría de la carpeta `LIBROS/`) usan esta forma. **Un `.refx` con tabla
`Topics` es un tópico**, no una referencia.

### Tópico — `.topx`

```sql
Topics (Title NVARCHAR(100), Notes TEXT)
```

### Devocional — `.devx`

```sql
Details   (Description, Abbreviation, Comments, Version)
Devotions (Month, Day, Devotion)
```

### Armonía — `.harx`

```sql
Details  (Description, Abbreviation, Comments, Version)
Sections (ID, Title)
Parts    (Section, Part, Reference)
```

`Parts` tiene una fila por referencia: `(Section, Part)` se repite. La unidad
navegable es la sección; sus referencias se deduplican al listar.

### Mapas — `.mapx`

```sql
Details  (Description, Abbreviation, Comments, Version)
Graphics (Title, Details, Picture BLOB)
```

`Picture` es la imagen (PNG/JPEG). **No** se descifra: no es una columna de
contenido textual. `Details` es la leyenda; algunos módulos la cifran con
SQLitePlus sin comprimir (RTF UTF-16LE con cabecera de 5 bytes).

### TWM — `.twm`

```sql
config (name, value)
topics (id, pid, subject, rel_order, content_type)
content(topic_id, data, data2)
topics_wordindex (id, word, priority)
```

El título está en `config` con `name='title'`. `content.data` es RTF.

### Localización — `.lanx`

```sql
Languages (ID, Language, Localized, RightToLeft, Skip)
<Idioma>  (Tag, Caption)   -- una tabla por idioma: Spanish, English, ...
```

Son las cadenas de la interfaz de e-Sword, no contenido bíblico. linuxEsword las
cataloga pero no las usa.

### Encabezados — `.en` / `.es` / `.fr` / `.pt`

```sql
Headings (Book, Chapter, Verse, Title)
```

Títulos de sección sueltos. No son módulos completos; quedan como
`kind=unknown`.

## 3. Cifrado SQLitePlus

Ver `skills/decryption.md` para el detalle. Resumen:

- Marca: tabla `sqliteplus_license`.
- Cifra: **Twofish-128-ECB**, clave `"Heb_4:12"` (16 bytes, padding de ceros).
- Blob: `[0] checksum | [1..3] u24 compressedSize | [4] 0x1F |
  [5..8] u32 expectedSize | [9..] zlib`.
- **`compressedSize` es de 24 bits**, no 16. Leerlo mal rompe los registros
  > 64 KiB (p. ej. artículos largos de ISBE).

## 4. Contenido enriquecido

Tres codificaciones conviven en las mismas columnas:

| Codificación | Detección | Ejemplo |
|---|---|---|
| RTF | `{\rtf`, `\pard`, `{\b`, `\cfN` | RV1960, casi todos los `.cmti` |
| HTML | `<p ...>`, `<span ...>`, `<ref>` | ABP, `.refi` modernos |
| Texto plano | nada de lo anterior | LBLA tras descifrar, `.bbli` |

RTF de e-Sword suele venir **sin cabecera** y con grupos embebidos a mitad de
texto. Codepage por defecto `cp1252`; griego/hebreo con fuentes de 8 bits.

`<ref>Juan 3:16</ref>` = referencia cruzada clicable.

## 5. Numeración de libros

| Rango | Contenido |
|---|---|
| 1–39 | Antiguo Testamento |
| 40–66 | Nuevo Testamento |
| 67–73 | Deuterocanónicos (Tobit, Judit, Sabiduría, Eclesiástico, Baruc, 1–2 Macabeos) |

**Nunca** mapear por número entre fuentes distintas: la numeración de los
deuterocanónicos cambia entre e-Sword, Zefania y LXX. Mapear por nombre.

## 6. Estadísticas del corpus (2026-11)

| Tipo | Archivos | Registros | Tamaño |
|---|---:|---:|---:|
| Referencias | 431 | 17.192 | 740 MB |
| Biblias | 74 | 1.939.160 | 690 MB |
| Diccionarios | 159 | 622.836 | 1.631 MB |
| Comentarios | 110 | 647.505 | 1.269 MB |
| Léxicos | 19 | 157.146 | 425 MB |
| Mapas | 24 | 668 | 161 MB |
| Tópicos | 23 | 786 | 15 MB |
| Devocionales | 12 | 3.659 | 19 MB |
| Armonías | 10 | 5.633 | 0,5 MB |
| TWM | 1 | 1.894 | 0,2 MB |
| **Total** | **863** | **3.396.479** | **4,95 GB** |

970 archivos incluyen también `.lanx`, `.en/.es/.fr/.pt`, `.ocx`, `.dat` y
duplicados; el catálogo marca estos últimos por fingerprint.

Cifrados: **43 módulos / 620.093 registros**.

## 7. Trampas encontradas

| Trampa | Efecto | Solución |
|---|---|---|
| Extensión ≠ tipo | `.refx` clasificado como Referencia | dispatch por tablas |
| `compressedSize` u16 | artículos > 64 KiB no descifran | leer u24 |
| RTF sin cabecera | texto con `\pard` visible | heurística `_is_rtf` |
| RTF con `\par` masivos | huecos gigantes en la lectura | `_tidy()` colapsa `<br>` |
| `Verses` vs `VerseCommentary` | comentario vacío | soportar ambos esquemas |
| `topics` vs `Topics` | confusión TWM/tópico | distinguir caja + `config` |
| Duplicados en carpetas | 2× el mismo módulo | fingerprint sha1 |
| Módulos NT-only | Salmos no existe | `bible.not_available` |
