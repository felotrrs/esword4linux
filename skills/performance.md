# Rendimiento — presupuestos y mediciones

## Presupuestos

| Operación | Presupuesto | Real |
|---|---|---|
| Abrir la app y mostrar la Biblia | < 1,5 s | ~0,9 s (sin indexar) |
| Cambiar de capítulo | < 60 ms | ~10-25 ms |
| Buscar en 72k páginas indexadas | < 100 ms | ~10-20 ms |
| Escanear 970 archivos (incremental) | < 1 s | ~0,1 s |
| Escanear desde cero | < 10 s | ~3 s |
| Indexar una biblia plana (35k v.) | < 15 s | ~6 s |
| Indexar una biblia cifrada (31k v.) | < 30 s | ~13 s (pool) |
| Mostrar un capítulo con comentario | < 100 ms | ~30 ms |

Si un cambio empeora un presupuesto > 2×, se justifica en el PR o se revierte.

## Dónde se va el tiempo

1. **Descifrado Twofish** (Python puro, ~284 reg/s/núcleo). Es el único coste
   real. Se paraleliza con `ProcessPoolExecutor` en
   `core/indexer.py:_parallel_decrypt`, con `workers = min(16, cpus-1)` y
   `chunks = ceil(n/workers)`. El pickling de 31k blobs (~3 MB) es despreciable.
2. **RTF → texto** al indexar. ~0,15 ms por versículo. Aceptable.
3. **FTS5**: la inserción dispara los triggers. ~6 s para 35k versículos.

## Reglas

1. **No descifrar lo que no se va a usar.** `iter_pages()` es un generador; el
   visor usa `bible_chapter()` / `page_by_ref()`, no `iter_pages()`.
2. **No indexar todo al arrancar.** Solo `Settings.preindex` (LBLA, RV1960,
   comentario RV1960x). El resto, bajo demanda.
3. **Pool solo para lotes grandes.** `_parallel_decrypt` cae a secuencial si
   `len(blobs) < 2000`: el arranque del pool cuesta ~1 s y no compensa.
4. **Una consulta por capítulo, no por versículo.** `chapter_comments()`.
5. **`LIMIT` siempre** en listas y búsquedas.
6. **Caché en StorageC, no en el home.** El home tiene 25 GB libres (81% usado);
   StorageC tiene 136 GB. `Settings.cache_dir` apunta a
   `~/StorageC/linuxEsword/.cache`.

## Medir

```bash
# Escaneo + indexación base con tiempos
.venv/bin/python tools/bootstrap.py

# Tiempo de búsqueda
.venv/bin/python - <<'PY'
from linuxesword.config import Settings
from linuxesword.core.context import AppContext
ctx = AppContext(Settings.load())
for q in ["amor", "fe", "principio", "Juan 3:16"]:
    r = ctx.search.search(q)
    print(f"{q!r:16} {r.intent:9} {len(r.hits):4} hits  {r.elapsed_ms:6.1f} ms")
PY
```

## Tamaño de la caché

| Corpus | Páginas | `content.db` |
|---|---|---|
| 3 módulos base | 72.102 | ~25 MB |
| Todo el corpus (estimado) | ~3,4 M | ~1,5-2,5 GB |

`content.db` es **regenerable**: ante corrupción o cambio de esquema, se borra.
