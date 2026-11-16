"""References, Bible↔commentary pairing and the Strong index."""

from __future__ import annotations

from pathlib import Path

import pytest

from esword4linux.core.refs import find_reference_spans, link_references

from support import CORPUS, requires_corpus


# ── references ───────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "text,expected",
    [
        ("Ver Juan 3:16", ["Juan 3:16"]),
        ("(Ex. 32:4; Ps. 106:19)", ["Éxodo 32:4", "Salmos 106:19"]),
        ("Exo_28:1; Heb_5:4", ["Éxodo 28:1", "Hebreos 5:4"]),
        ("1 Corintios 13:4-7", ["1 Corintios 13:4-7"]),
        ("Sal 23", ["Salmos 23"]),
        # Abbreviations from other traditions found in the bibliographies.
        ("Luk 1:1-4", ["Lucas 1:1-4"]),
        ("Jhn 1:1-5", ["Juan 1:1-5"]),
        ("Deu 12:16", ["Deuteronomio 12:16"]),
        ("Pro 1:1", ["Proverbios 1:1"]),
        ("Amo 9:9", ["Amós 9:9"]),
        ("Rth 2:14", ["Rut 2:14"]),
        ("Ezk 16:8", ["Ezequiel 16:8"]),
        ("Mrk 15:34", ["Marcos 15:34"]),
        ("Jua 1:51", ["Juan 1:51"]),
        # Note marker «i» before the citation: it must not block the link.
        ("i Mat 24:30", ["Mateo 24:30"]),
        # Prefixes and names from several languages.
        ("I Samuel 1:1", ["1 Samuel 1:1"]),
        ("II Reyes 2:1", ["2 Reyes 2:1"]),
        ("Primera de Corintios 13:4", ["1 Corintios 13:4"]),
        ("1a de Corintios 13:4", ["1 Corintios 13:4"]),
        ("Tercera de Juan 1:2", ["3 Juan 1:2"]),
        ("San Juan 3:16", ["Juan 3:16"]),
        ("Jean 3:16", ["Juan 3:16"]),
        ("João 3:16", ["Juan 3:16"]),
        ("The Wisdom of Solomon 2:23", ["Sabiduría 2:23"]),
        ("Cantar de los Cantares 1:1", ["Cantares 1:1"]),
        ("Hechos de los Apóstoles 2:38", ["Hechos 2:38"]),
    ],
)
def test_find_reference_spans(text, expected):
    spans = find_reference_spans(text)
    assert [s.ref_text for s in spans] == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Ex. 4:14, 27-30", [
            ("Ex. 4:14", "Éxodo 4:14"),
            ("27-30", "Éxodo 4:27-30"),
        ]),
        ("He. 5.4; 7.11", [
            ("He. 5.4", "Hebreos 5:4"),
            ("7.11", "Hebreos 7:11"),
        ]),
        ("Jn 3:16,17", [
            ("Jn 3:16", "Juan 3:16"),
            ("17", "Juan 3:17"),
        ]),
        ("Génesis 1-3", [("Génesis 1-3", "Génesis 1-3")]),
    ],
)
def test_continuation_spans(text, expected):
    spans = find_reference_spans(text)
    assert [(s.text, s.ref_text) for s in spans] == expected


@pytest.mark.parametrize("text", ["1 Esdras 8:2", "2 Esdras 1:2", "3 Macc 3:21"])
def test_unsupported_books_are_not_linked(text):
    # Not in the e-Sword 1–73 numbering: linking «Esdras» or «Macc»
    # would show a passage from another book.
    assert find_reference_spans(text) == []


def test_scan_reaches_late_references():
    text = ("x " * 12_000) + "Juan 3:16"
    assert [s.ref_text for s in find_reference_spans(text)] == ["Juan 3:16"]


@pytest.mark.parametrize(
    "text",
    ["nota 3 del año 1856", "sin referencias aquí", ""],
)
def test_no_false_positives(text):
    assert find_reference_spans(text) == []


def test_link_references_skips_existing_anchors():
    html = '<p>Ver <a href="ref:Juan 3:16">Juan 3:16</a> y Sal 23</p>'
    out = link_references(html)
    assert out.count('href="ref:Juan 3:16"') == 1
    assert 'href="ref:Salmos 23"' in out


# ── pairing and Strong ───────────────────────────────────────────────────
pytestmark_corpus = requires_corpus


@pytestmark_corpus
def test_commentary_match_rv1960(corpus_context):
    from esword4linux.core.commentary import best_commentary

    ctx = corpus_context
    bible = ctx.catalog.by_rel_path("BIBLIAS/bible_rv1960_es_2.bblx")
    if bible is None:
        pytest.skip("RV1960 not available")
    matched = best_commentary(
        bible, ctx.commentaries(),
        bible_module=ctx.module(bible), open_module=ctx.module,
    )
    assert matched is not None
    assert "rvr1960" in matched["rel_path"].lower()


@pytestmark_corpus
def test_commentary_match_avoids_false_positive(corpus_context):
    from esword4linux.core.commentary import best_commentary

    ctx = corpus_context
    bible = ctx.catalog.by_rel_path("BIBLIAS/Nueva Biblia Viva.bbli")
    if bible is None:
        pytest.skip("NBV not available")
    assert best_commentary(
        bible, ctx.commentaries(),
        bible_module=ctx.module(bible), open_module=ctx.module,
    ) is None


@pytestmark_corpus
def test_strong_index_lookup(corpus_context):
    ctx = corpus_context
    assert ctx.strong.available()
    body = ctx.strong.lookup("G2316")
    assert body, "G2316 must have an entry"
    assert "θεός" in body or "Dios" in body
    assert ctx.strong.lookup("Z99999") == ""
