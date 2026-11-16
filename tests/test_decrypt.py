"""SQLitePlus (Twofish-128) decryption over vectors and real modules."""

from __future__ import annotations

from pathlib import Path

import pytest

from esword4linux.core.esword.sqliteplus import decrypt_payload, self_test
from esword4linux.core.esword.twofish import self_test as twofish_self_test

from support import CORPUS, requires_corpus


def test_twofish_vector():
    assert twofish_self_test()


def test_sqliteplus_vectors():
    assert self_test()


def test_no_key_fails():
    with pytest.raises(Exception):
        decrypt_payload(b"\x00" * 16, "clave_incorrecta")


@requires_corpus
def test_decrypt_real_bible():
    """The LBLA is encrypted: its first verse must be Genesis 1:1."""
    from esword4linux.core.esword.module import EswordModule

    path = CORPUS / "BIBLIAS" / "bible_lbla_es.bblx"
    if not path.is_file():
        pytest.skip("LBLA module not available")
    with EswordModule(path) as mod:
        assert mod.encrypted
        page = mod.bible_verse(1, 1, 1)
        assert page is not None
        assert "En el principio" in page.raw


@requires_corpus
def test_plaintext_bible_not_encrypted():
    from esword4linux.core.esword.module import EswordModule

    path = CORPUS / "BIBLIAS" / "bible_rv1960_es_2.bblx"
    if not path.is_file():
        pytest.skip("RV1960 module not available")
    with EswordModule(path) as mod:
        assert not mod.encrypted
        assert mod.structure == "bible"
        assert mod.chapter_count(19) == 150
