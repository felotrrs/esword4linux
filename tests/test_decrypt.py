"""Descifrado SQLitePlus (Twofish-128) sobre vectores y módulos reales."""

from __future__ import annotations

from pathlib import Path

import pytest

from linuxesword.core.esword.sqliteplus import decrypt_payload, self_test
from linuxesword.core.esword.twofish import self_test as twofish_self_test

CORPUS = Path("/home/felipe/StorageA/Biblias/Biblias_esword")


def test_twofish_vector():
    assert twofish_self_test()


def test_sqliteplus_vectors():
    assert self_test()


def test_no_key_fails():
    with pytest.raises(Exception):
        decrypt_payload(b"\x00" * 16, "clave_incorrecta")


@pytest.mark.skipif(not CORPUS.is_dir(), reason="corpus no disponible")
def test_decrypt_real_bible():
    """La LBLA está cifrada: el primer versículo debe ser Génesis 1:1."""
    from linuxesword.core.esword.module import EswordModule

    path = CORPUS / "BIBLIAS" / "bible_lbla_es.bblx"
    if not path.is_file():
        pytest.skip("módulo LBLA no disponible")
    with EswordModule(path) as mod:
        assert mod.encrypted
        page = mod.bible_verse(1, 1, 1)
        assert page is not None
        assert "En el principio" in page.raw


@pytest.mark.skipif(not CORPUS.is_dir(), reason="corpus no disponible")
def test_plaintext_bible_not_encrypted():
    from linuxesword.core.esword.module import EswordModule

    path = CORPUS / "BIBLIAS" / "bible_rv1960_es_2.bblx"
    if not path.is_file():
        pytest.skip("módulo RV1960 no disponible")
    with EswordModule(path) as mod:
        assert not mod.encrypted
        assert mod.structure == "bible"
        assert mod.chapter_count(19) == 150
