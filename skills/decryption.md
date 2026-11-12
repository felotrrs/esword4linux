# Descifrado SQLitePlus (Twofish-128)

## Qué está cifrado

Solo los módulos que traen la tabla `sqliteplus_license` (también llamada
SQLitePlus). En el corpus son **43 de 970**, no todos.

```
$ python -c "..."; # ver más abajo
Bible 74 módulos → 19 cifrados
Commentary 110 → 6
Dictionary 159 → 5
```

El resto es SQLite plano: no hay nada que descifrar y no debe pasarse por
Twofish (coste inútil).

## Esquema

```
blob cifrado
   │  Twofish-128-ECB, clave "Heb_4:12" (16 bytes, padding de ceros)
   ▼
header de 9 bytes
   [0]      checksum/bitfield (se ignora)
   [1..3]   u24 LE compressedSize   ← ¡24 bits, no 16!
   [4]      magia 0x1F
   [5..8]   u32 LE expectedSize
   ▼
zlib stream (desde el byte 9, longitud compressedSize - 4)
   ▼
payload descifrado (RTF, HTML o texto)
```

**Trampa documentada**: leer `compressedSize` como `u16` trunca los registros
cuyo stream zlib supera 64 KiB (p. ej. artículos largos de ISBE) y hace fallar
el descifrado de todo el módulo. Se lee como `u24`.

## Clave

`DEFAULT_SQLITEPLUS_KEY = "Heb_4:12"`. Se puede sobreescribir por módulo
(`EswordModule(path, crypt_key=...)`) para módulos de terceros.

## Desempeño

Twofish en Python puro: **~284 registros/s por núcleo**.

| Corpus cifrado | 1 núcleo | 16 procesos |
|---|---|---|
| 620.093 registros | ~36 min | ~1-2 min |

Por eso `core/indexer.py` usa `ProcessPoolExecutor` para biblias cifradas
(`_parallel_decrypt`) y cae a secuencial si el pool falla.

**Lectura bajo demanda**: mostrar un versículo descifra 1 blob (~3 ms). No hay
problema en descifrar en el hilo de UI para una entrada suelta; sí lo hay para
un capítulo completo de un módulo cifrado (30-40 blobs ≈ 120 ms). Si se nota,
cachear el capítulo.

## Reglas

1. **No inventar contenido.** Si un blob no descifra, se omite y se registra en
   `mod.warnings` / `catalog.set_status(..., "failed", ...)`. Nunca se
   sustituye por texto de otra fuente.
2. **No descifrar columnas que no son contenido.** Solo las de
   `CONTENT_COLUMNS` (`Scripture`, `Comments`, `Definition`, `Notes`,
   `Content`, `Devotion`, `Details`, `data`, `Reference`). Un `Picture` de
   `.mapx` es una imagen: descifrarlo la corrompe.
3. **El núcleo es vendorizado.** `twofish.py`, `sqliteplus.py`, `rtf.py`,
   `font_codepages.py`, `legacy_translit.py` vienen de
   `~/StorageC/bible/shared/esword/`. `make drift` compara hashes. Si cambias
   algo, documenta el motivo en `documentacion/CHANGELOG.md`.
4. **`sqliteplus.py` solo cambia el import** (`from .twofish import Twofish128`).
   Cualquier otro cambio es deriva y hay que justificarlo.

## Verificar

```bash
.venv/bin/python -c "
from linuxesword.core.esword.sqliteplus import self_test
from linuxesword.core.esword.twofish import self_test as t
assert t() and self_test(); print('vectores OK')"

.venv/bin/python -c "
from linuxesword.core.esword.module import EswordModule
m = EswordModule('/home/felipe/StorageA/Biblias/Biblias_esword/BIBLIAS/bible_lbla_es.bblx')
print(m.encrypted, m.bible_verse(1,1,1).raw)"
```
