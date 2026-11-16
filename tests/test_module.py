"""Structure detection, metadata and pages per module type."""

from __future__ import annotations

from pathlib import Path

import pytest

from esword4linux.core.esword.module import EswordModule

from support import CORPUS, requires_corpus

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

pytestmark = requires_corpus


@pytest.mark.parametrize("rel,structure", CASES)
def test_structure_detection(rel, structure):
    path = CORPUS / rel
    if not path.is_file():
        pytest.skip(f"module not available: {rel}")
    with EswordModule(path) as mod:
        assert mod.structure == structure
        assert mod.title
        assert mod.count_entries() > 0


def test_extension_lies_topics():
    """A `.refx` with a Topics table is a Topic, not a Reference."""
    path = CORPUS / "topic_antiguedades_i_f_josefo_es.topx"
    if not path.is_file():
        pytest.skip("module not available")
    with EswordModule(path) as mod:
        assert mod.structure == "topic"
        assert mod.kind == "topic"


def test_bible_chapter_and_books():
    path = CORPUS / "BIBLIAS" / "bible_rv1960_es_2.bblx"
    if not path.is_file():
        pytest.skip("module not available")
    with EswordModule(path) as mod:
        assert len(mod.books()) == 73  # 66 + deuterocanonical books
        chapter = mod.bible_chapter(43, 3)
        assert len(chapter) >= 36
        assert chapter[0].verse == 1
        assert mod.verse_count(43, 3) == len(chapter)


def test_commentary_for_chapter():
    path = CORPUS / "COMENTARIOS" / "comment_rvr1960x_es.cmti"
    if not path.is_file():
        pytest.skip("module not available")
    with EswordModule(path) as mod:
        comments = mod.chapter_comments(43, 3)
        assert comments, "the RV1960x commentary must have notes in John 3"


def test_commentary_modern_cmtx_range_schema():
    """Modern `.cmtx`: Verses(ChapterBegin, ChapterEnd, VerseBegin, VerseEnd).

    Regression: reading it as (Book, Chapter, Verse) used to fail with
    «no such column: Chapter» and left the module empty.
    """
    path = CORPUS / "COMENTARIOS" / "comment_wesley_en.cmtx"
    if not path.is_file():
        pytest.skip("module not available")
    with EswordModule(path) as mod:
        specs = dict(mod._comment_specs())
        assert specs.get("Verses") == "range"
        comments = mod.chapter_comments(43, 3)
        assert comments, "Wesley must have comments in John 3"
        assert any(page.raw for entries in comments.values() for page in entries)
        assert sum(1 for _ in mod.iter_pages()) > 1000


def test_commentary_old_cmti_schema():
    path = CORPUS / "COMENTARIOS" / "comment_rvr1960x_es.cmti"
    if not path.is_file():
        pytest.skip("module not available")
    with EswordModule(path) as mod:
        specs = dict(mod._comment_specs())
        assert specs.get("VerseCommentary") == "range"
        page = mod.page_by_ref("43:3:16")
        assert page is not None and page.raw


def test_page_by_ref_dictionary():
    path = CORPUS / "lexicon_de_vine_es.lexi"
    if not path.is_file():
        pytest.skip("module not available")
    with EswordModule(path) as mod:
        entries = mod.list_entries(limit=5)
        assert entries
        page = mod.page_by_ref(entries[0][0])
        assert page is not None
        assert page.ref == entries[0][0]


def test_map_picture_utf16_titles():
    """Clarence Larkin: UTF-16LE BLOB titles after entry 9."""
    path = CORPUS / "MAPAS" / "map_larkin_es.mapx"
    if not path.is_file():
        pytest.skip("module not available")
    with EswordModule(path) as mod:
        entries = mod.list_entries(limit=1000)
        assert len(entries) >= 10
        # Every entry, including those that store the title as a blob.
        for ref, _label in entries:
            picture = mod.map_picture(ref)
            assert picture, f"no image for {ref!r}"
            assert picture.startswith(b"GIF8")
        ref = entries[9][0]
        page = mod.page_by_ref(ref)
        assert page is not None and page.title == ref


def test_map_picture_unwraps_lt_header():
    """Some `.mapx` files prepend ``lt\\0\\0`` + size to a BMP."""
    path = CORPUS / "MAPAS" / "map_usos_y_costumbres_de_las_tierras_es.mapx"
    if not path.is_file():
        pytest.skip("module not available")
    with EswordModule(path) as mod:
        entries = mod.list_entries(limit=1000)
        assert entries
        for ref, _label in entries:
            picture = mod.map_picture(ref)
            assert picture, f"no image for {ref!r}"
            assert picture.startswith(b"BM")
            assert not picture.startswith(b"lt\x00\x00")


def test_map_details_uncompressed_sqliteplus_text():
    """Larkin encrypts `Graphics.Details` without zlib; no garbage must be shown."""
    path = CORPUS / "MAPAS" / "map_larkin_es.mapx"
    if not path.is_file():
        pytest.skip("module not available")
    from esword4linux.core.text import to_plain

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
    """Commentaries that only carry `BookCommentary`: entries and reading."""
    path = CORPUS / rel
    if not path.is_file():
        pytest.skip(f"module not available: {rel}")
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
    """Harmonies are browsed by section, with no `Parts` duplicates."""
    path = CORPUS / "ARMONIAS" / "harmony_bdv_es.harx"
    if not path.is_file():
        pytest.skip("module not available")
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
        assert "{\\" not in page.title  # the Section.Title RTF has already been cleaned
        assert "Mat 1:1-17" in page.raw
        assert "Luc 3:23-38" in page.raw


def test_dictionary_schema_commentary_is_classified_as_commentary(tmp_path):
    """Commentaries with a dictionary schema are catalogued as commentaries."""
    from esword4linux.core.catalog import Catalog

    path = CORPUS / "DICCIONARIOS" / "Comentario Biblico Siglo 21.dcti"
    if not path.is_file():
        pytest.skip("module not available")
    cat = Catalog(tmp_path / "catalog.db")
    try:
        meta = cat._probe(path)
    finally:
        cat.close()
    assert meta["structure"] == "dictionary"
    assert meta["kind"] == "commentary"
    assert meta["entries"] > 0
