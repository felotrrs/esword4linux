"""Detección de estructura, metadatos y páginas por tipo de módulo."""

from __future__ import annotations

from pathlib import Path

import pytest

from linuxesword.core.esword.module import EswordModule

CORPUS = Path("/home/felipe/StorageA/Biblias/Biblias_esword")

CASES = [
    ("BIBLIAS/bible_rv1960_es_2.bblx", "bible"),
    ("COMENTARIOS/comment_rvr1960x_es.cmti", "commentary"),
    ("DICCIONARIOS/dicc_camr_es.dctx", "dictionary"),
    ("lexicon_de_vine_es.lexi", "lexicon"),
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


def test_commentary_modern_cmtx_range_schema():
    """`.cmtx` moderno: Verses(ChapterBegin, ChapterEnd, VerseBegin, VerseEnd).

    Regresión: leerlo como (Book, Chapter, Verse) rompía con
    «no such column: Chapter» y dejaba el módulo vacío.
    """
    path = CORPUS / "COMENTARIOS" / "comment_wesley_en.cmtx"
    if not path.is_file():
        pytest.skip("módulo ausente")
    with EswordModule(path) as mod:
        specs = dict(mod._comment_specs())
        assert specs.get("Verses") == "range"
        comments = mod.chapter_comments(43, 3)
        assert comments, "Wesley debe tener comentarios en Juan 3"
        assert any(page.raw for entries in comments.values() for page in entries)
        assert sum(1 for _ in mod.iter_pages()) > 1000


def test_commentary_old_cmti_schema():
    path = CORPUS / "COMENTARIOS" / "comment_rvr1960x_es.cmti"
    if not path.is_file():
        pytest.skip("módulo ausente")
    with EswordModule(path) as mod:
        specs = dict(mod._comment_specs())
        assert specs.get("VerseCommentary") == "range"
        page = mod.page_by_ref("43:3:16")
        assert page is not None and page.raw


def test_page_by_ref_dictionary():
    path = CORPUS / "lexicon_de_vine_es.lexi"
    if not path.is_file():
        pytest.skip("módulo ausente")
    with EswordModule(path) as mod:
        entries = mod.list_entries(limit=5)
        assert entries
        page = mod.page_by_ref(entries[0][0])
        assert page is not None
        assert page.ref == entries[0][0]


def test_map_picture_utf16_titles():
    """Clarence Larkin: títulos BLOB UTF-16LE después de la entrada 9."""
    path = CORPUS / "MAPAS" / "map_larkin_es.mapx"
    if not path.is_file():
        pytest.skip("módulo ausente")
    with EswordModule(path) as mod:
        entries = mod.list_entries(limit=1000)
        assert len(entries) >= 10
        # Todas las entradas, incluidas las que guardan el título como blob.
        for ref, _label in entries:
            picture = mod.map_picture(ref)
            assert picture, f"sin imagen para {ref!r}"
            assert picture.startswith(b"GIF8")
        ref = entries[9][0]
        page = mod.page_by_ref(ref)
        assert page is not None and page.title == ref


def test_map_picture_unwraps_lt_header():
    """Algunos `.mapx` anteponen ``lt\\0\\0`` + tamaño a un BMP."""
    path = CORPUS / "MAPAS" / "map_usos_y_costumbres_de_las_tierras_es.mapx"
    if not path.is_file():
        pytest.skip("módulo ausente")
    with EswordModule(path) as mod:
        entries = mod.list_entries(limit=1000)
        assert entries
        for ref, _label in entries:
            picture = mod.map_picture(ref)
            assert picture, f"sin imagen para {ref!r}"
            assert picture.startswith(b"BM")
            assert not picture.startswith(b"lt\x00\x00")


def test_map_details_uncompressed_sqliteplus_text():
    """Larkin cifra `Graphics.Details` sin zlib; no debe mostrarse basura."""
    path = CORPUS / "MAPAS" / "map_larkin_es.mapx"
    if not path.is_file():
        pytest.skip("módulo ausente")
    from linuxesword.core.text import to_plain

    with EswordModule(path) as mod:
        page = mod.page_by_ref(" 3 - The Perspective of Prophecy")
        assert page is not None
        plain = to_plain(page.raw, hint=mod.stem)
        assert "THE PERSPECTIVE OF PROPHECY" in plain
        assert "\ufffd" not in plain
        assert not plain.startswith("Ä")


BOOK_ONLY_COMMENTARIES = [
    "COMENTARIOS/Nuevo Auxiliar Biblico Manley.cmti",
    "COMENTARIOS/A Traves de la Biblia - Myer Pearlman.cmti",
    "COMENTARIOS/Auxiliar Biblico Portavoz.cmti",
]


@pytest.mark.parametrize("rel", BOOK_ONLY_COMMENTARIES)
def test_commentary_with_only_book_entries(rel):
    """Comentarios que solo traen `BookCommentary`: entradas y lectura."""
    path = CORPUS / rel
    if not path.is_file():
        pytest.skip(f"módulo ausente: {rel}")
    with EswordModule(path) as mod:
        assert mod.count_entries() > 0
        entries = mod.list_entries(limit=1000)
        assert entries
        assert len(entries) == mod.count_entries()
        ref, label = entries[0]
        page = mod.page_by_ref(ref)
        assert page is not None
        assert page.ref == ref
        assert page.title == label
        assert page.raw.strip()


def test_harmony_entries_grouped_by_section():
    """Las armonías se navegan por sección, sin duplicados de `Parts`."""
    path = CORPUS / "ARMONIAS" / "harmony_bdv_es.harx"
    if not path.is_file():
        pytest.skip("módulo ausente")
    with EswordModule(path) as mod:
        entries = mod.list_entries(limit=10000)
        refs = [ref for ref, _label in entries]
        assert refs
        assert len(refs) == len(set(refs))
        assert len(entries) == mod.count_entries()
        assert sum(1 for _ in mod.iter_pages()) == len(entries)
        ref, label = entries[2]
        page = mod.page_by_ref(ref)
        assert page is not None
        assert page.ref == ref
        assert page.title == label
        assert "{\\" not in page.title  # el RTF del Section.Title ya se limpió
        assert "Mat 1:1-17" in page.raw
        assert "Luc 3:23-38" in page.raw


def test_dictionary_schema_commentary_is_classified_as_commentary(tmp_path):
    """Los comentarios con esquema de diccionario se catalogan como comentarios."""
    from linuxesword.core.catalog import Catalog

    path = CORPUS / "DICCIONARIOS" / "Comentario Biblico Siglo 21.dcti"
    if not path.is_file():
        pytest.skip("módulo ausente")
    cat = Catalog(tmp_path / "catalog.db")
    try:
        meta = cat._probe(path)
    finally:
        cat.close()
    assert meta["structure"] == "dictionary"
    assert meta["kind"] == "commentary"
    assert meta["entries"] > 0
