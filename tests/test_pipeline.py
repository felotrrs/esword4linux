"""Pipeline completo: escaneo → catálogo → índice FTS5 → búsqueda."""

from __future__ import annotations

from pathlib import Path

import pytest

from linuxesword.core.catalog import Catalog
from linuxesword.core.indexer import Indexer
from linuxesword.core.search import SearchEngine
from linuxesword.core.store import ContentStore, build_match, build_match_or

CORPUS = Path("/home/felipe/StorageA/Biblias/Biblias_esword")
BIBLE = "BIBLIAS/bible_rv1960_es_2.bblx"
COMMENT = "COMENTARIOS/comment_rvr1960x_es.cmti"

pytestmark = pytest.mark.skipif(not CORPUS.is_dir(), reason="corpus no disponible")


def test_build_match():
    assert build_match("amor") == '"amor"*'
    assert build_match("amor de dios") == '"amor" AND "de" AND "dios"*'
    assert build_match('"en el principio"') == '"en el principio"'
    assert build_match("") == ""
    assert "OR" in build_match_or("amor de dios")


@pytest.fixture()
def corpus(tmp_path):
    if not (CORPUS / BIBLE).is_file() or not (CORPUS / COMMENT).is_file():
        pytest.skip("módulos base ausentes")
    res = tmp_path / "resources"
    res.mkdir()
    (res / "bible_rv1960.bblx").symlink_to(CORPUS / BIBLE)
    (res / "comment.cmti").symlink_to(CORPUS / COMMENT)
    return res


def test_scan_and_index(tmp_path, corpus):
    catalog = Catalog(tmp_path / "catalog.db")
    store = ContentStore(tmp_path / "content.db")
    try:
        result = catalog.scan(corpus)
        assert result.total == 2
        assert result.added == 2
        kinds = catalog.counts_by_kind()
        assert kinds.get("bible") == 1
        assert kinds.get("commentary") == 1

        indexer = Indexer(catalog, store)
        outcome = indexer.index_paths(["bible_rv1960.bblx", "comment.cmti"])
        assert outcome["indexed"] == 2
        assert outcome["pages"] >= 40000
        assert store.total_pages() >= 40000

        engine = SearchEngine(catalog, store)

        ref = engine.search("Juan 3:16")
        assert ref.intent == "reference"
        assert ref.reference.book == 43

        free = engine.search("principio")
        assert free.intent == "text"
        assert free.hits
        assert any("principio" in h.snippet.lower() for h in free.hits)

        assert engine.search("G2316").intent == "strong"

        # el índice está en alcance solo para módulos ready
        ids = engine.indexed_module_ids()
        assert len(ids) == 2
    finally:
        catalog.close()
        store.close()


def test_rescan_is_incremental(tmp_path, corpus):
    catalog = Catalog(tmp_path / "catalog.db")
    try:
        catalog.scan(corpus)
        again = catalog.scan(corpus)
        assert again.added == 0
        assert again.skipped == 2
    finally:
        catalog.close()
