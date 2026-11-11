"""Referencias, emparejamiento biblia↔comentario e índice Strong."""

from __future__ import annotations

from pathlib import Path

import pytest

from linuxesword.core.refs import find_reference_spans, link_references

CORPUS = Path("/home/felipe/StorageA/Biblias/Biblias_bblx")


# ── referencias ──────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "text,expected",
    [
        ("Ver Juan 3:16", ["Juan 3:16"]),
        ("(Ex. 32:4; Ps. 106:19)", ["Éxodo 32:4", "Salmos 106:19"]),
        ("Exo_28:1; Heb_5:4", ["Éxodo 28:1", "Hebreos 5:4"]),
        ("1 Corintios 13:4-7", ["1 Corintios 13:4-7"]),
        ("Sal 23", ["Salmos 23"]),
    ],
)
def test_find_reference_spans(text, expected):
    spans = find_reference_spans(text)
    assert [s.ref_text for s in spans] == expected


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


# ── emparejamiento y Strong ──────────────────────────────────────────────
pytestmark_corpus = pytest.mark.skipif(not CORPUS.is_dir(), reason="corpus no disponible")


@pytestmark_corpus
def test_commentary_match_rv1960():
    from linuxesword.config import Settings
    from linuxesword.core.commentary import best_commentary
    from linuxesword.core.context import AppContext

    ctx = AppContext(Settings.load())
    bible = ctx.catalog.by_rel_path("BIBLIAS/bible_rv1960_es_2.bblx")
    if bible is None:
        pytest.skip("RV1960 ausente")
    matched = best_commentary(
        bible, ctx.commentaries(),
        bible_module=ctx.module(bible), open_module=ctx.module,
    )
    assert matched is not None
    assert "rvr1960" in matched["rel_path"].lower()


@pytestmark_corpus
def test_commentary_match_avoids_false_positive():
    from linuxesword.config import Settings
    from linuxesword.core.commentary import best_commentary
    from linuxesword.core.context import AppContext

    ctx = AppContext(Settings.load())
    bible = ctx.catalog.by_rel_path("BIBLIAS/Nueva Biblia Viva.bbli")
    if bible is None:
        pytest.skip("NBV ausente")
    assert best_commentary(
        bible, ctx.commentaries(),
        bible_module=ctx.module(bible), open_module=ctx.module,
    ) is None


@pytestmark_corpus
def test_strong_index_lookup():
    from linuxesword.config import Settings
    from linuxesword.core.context import AppContext

    ctx = AppContext(Settings.load())
    assert ctx.strong.available()
    body = ctx.strong.lookup("G2316")
    assert body, "G2316 debe tener entrada"
    assert "θεός" in body or "Dios" in body
    assert ctx.strong.lookup("Z99999") == ""
