"""Detección de estructura, metadatos y páginas por tipo de módulo."""

from __future__ import annotations

from pathlib import Path

import pytest

from linuxesword.core.esword.module import EswordModule

CORPUS = Path("/home/felipe/StorageA/Biblias/Biblias_bblx")

CASES = [
    ("BIBLIAS/bible_rv1960_es_2.bblx", "bible"),
    ("COMENTARIOS/comment_rvr1960x_es.cmti", "commentary"),
    ("DICCIONARIOS/dicc_camr_es.dctx", "dictionary"),
    ("04-Vine.lexi", "lexicon"),
    ("devotion_afc_es.devx", "devotion"),
    ("harmony_bdv_es.harx", "harmony"),
    ("map_nasa_es.mapx", "maps"),
    ("twm_diccionario_de_nombres_biblicos_es.twm", "twm"),
]

pytestmark = pytest.mark.skipif(not CORPUS.is_dir(), reason="corpus no disponible")


@pytest.mark.parametrize("rel,structure", CASES)
def test_structure_detection(rel, structure):
    path = CORPUS / rel
    if not path.is_file():
        pytest.skip(f"módulo ausente: {rel}")
    with EswordModule(path) as mod:
        assert mod.structure == structure
        assert mod.title
        assert mod.count_entries() > 0


def test_extension_lies_topics():
    """`.refx` con tabla Topics es un Tópico, no una Referencia."""
    path = CORPUS / "topic_antiguedades_i_f_josefo_es.topx"
    if not path.is_file():
        pytest.skip("módulo ausente")
    with EswordModule(path) as mod:
        assert mod.structure == "topic"
        assert mod.kind == "topic"


def test_bible_chapter_and_books():
    path = CORPUS / "BIBLIAS" / "bible_rv1960_es_2.bblx"
    if not path.is_file():
        pytest.skip("módulo ausente")
    with EswordModule(path) as mod:
        assert len(mod.books()) == 73  # 66 + deuterocanónicos
        chapter = mod.bible_chapter(43, 3)
        assert len(chapter) >= 36
        assert chapter[0].verse == 1
        assert mod.verse_count(43, 3) == len(chapter)


def test_commentary_for_chapter():
    path = CORPUS / "COMENTARIOS" / "comment_rvr1960x_es.cmti"
    if not path.is_file():
        pytest.skip("módulo ausente")
    with EswordModule(path) as mod:
        comments = mod.chapter_comments(43, 3)
        assert comments, "el comentario RV1960x debe tener notas en Juan 3"


def test_page_by_ref_dictionary():
    path = CORPUS / "04-Vine.lexi"
    if not path.is_file():
        pytest.skip("módulo ausente")
    with EswordModule(path) as mod:
        entries = mod.list_entries(limit=5)
        assert entries
        page = mod.page_by_ref(entries[0][0])
        assert page is not None
        assert page.ref == entries[0][0]
