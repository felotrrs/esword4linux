"""Pseudo-tags de e-Sword y codepages legacy."""

from __future__ import annotations

from pathlib import Path

import pytest

from linuxesword.core.text import is_markup, to_plain, to_rich

CORPUS = Path("/home/felipe/StorageA/Biblias/Biblias_bblx")


# ── pseudo-tags ──────────────────────────────────────────────────────────
def test_red_tag_is_markup_not_literal():
    """Regresión: `<red>` se mostraba como `</red>` literal."""
    raw = "<red>Porque de tal manera amó Dios</red>"
    assert is_markup(raw)
    rich = to_rich(raw)
    assert "&lt;red&gt;" not in rich
    assert "</red>" not in rich
    assert "color:#b03a2e" in rich
    assert to_plain(raw) == "Porque de tal manera amó Dios"


def test_greek_and_hebrew_tags():
    rich = to_rich("<grk>ἀπόθεσις</grk> y <heb>אָב</heb>")
    assert "ἀπόθεσις" in rich and "אָב" in rich
    assert "<grk>" not in rich and "<heb>" not in rich


def test_num_tag_becomes_strong_anchor():
    rich = to_rich("padre <num>H1</num> y Dios <num>G2316</num>")
    assert 'href="strong:H1"' in rich
    assert 'href="strong:G2316"' in rich


def test_strong_hash_link_is_converted():
    rich = to_rich("<a class=nd href='#sG1645'>G1645</a>")
    assert 'href="strong:G1645"' in rich


def test_drop_tags_keep_content():
    rich = to_rich("<Pg>(<heb>אָב</heb>):</Pg> <T>(87)</T>")
    assert "אָב" in rich and "(87)" in rich
    assert "<Pg>" not in rich and "<T>" not in rich


def test_unknown_pseudo_tag_still_detected():
    raw = "texto <J>algo</J> fin"
    assert is_markup(raw) is False or "<J>" not in to_rich(raw)


# ── codepages ────────────────────────────────────────────────────────────
@pytest.mark.skipif(not CORPUS.is_dir(), reason="corpus no disponible")
def test_vine_codepage_fixes_greek():
    """cp1253: sin el hint sale mojibake; con el hint, griego correcto."""
    import sqlite3

    path = CORPUS / "DICCIONARIOS" / "dicc_vine_es_nt_es.dctx"
    if not path.is_file():
        pytest.skip("módulo Vine NT ausente")
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    raw = None
    for (definition,) in conn.execute("select Definition from Dictionary"):
        if "\\f1" in str(definition) and "\\'f" in str(definition):
            raw = str(definition)
            break
    conn.close()
    if raw is None:
        pytest.skip("entrada con griego no encontrada")
    wrong = to_plain(raw)
    right = to_plain(raw, hint="dicc_vine_es_nt_es")
    assert "ἀπόθεσις" in right
    assert "ἀπόθεσις" not in wrong


def test_plain_untouched_when_no_hint():
    assert to_plain("Texto normal con acentos: áéíóú ñ") == "Texto normal con acentos: áéíóú ñ"
