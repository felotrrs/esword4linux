"""Detección de idioma de los módulos de biblioteca."""

from __future__ import annotations

import pytest

from linuxesword.core.catalog import (
    LANGUAGE_ORDER, METADATA_VERSION, Catalog, detect_language,
)


@pytest.mark.parametrize(
    "title,abbr,filename,expected",
    [
        # El título dice «Spanish Reina-Valera»: es español aunque contenga
        # palabras inglesas y el autor se llame Smith.
        ("1909 Spanish Reina-Valera w/ Strong's Numbers", "SRV+",
         "bible_srv_es_1.bblx", "es"),
        ("BqSTB-JSmith Sermones y Bosquejos de toda la Biblia por James K. Smith",
         "BqSTB-JSmith", "Sermones.cmti", "es"),
        ("Comentario Jamieson-Fausset-Brown", "JFB", "Comentario.cmti", "es"),
        ("King James Version w/ Strong's Numbers", "KJV", "bible_kjv_en.bblx", "en"),
        ("A Harmony of the Gospels", "Robertson", "harmony_robertson_en.harx", "en"),
        ("Louis Segond", "LSG", "bible_lsg_fr.bblx", "fr"),
        ("Bíblia Almeida", "ARC", "bible_arc_pt.bblx", "pt"),
        ("Luther Bibel", "LUT", "bibel_de.bblx", "de"),
        ("La Sacra Bibbia Riveduta", "RIV", "bibbia_it.bblx", "it"),
        ("Septuagint", "LXX", "bible_lxx_grc.bblx", "grc"),
        ("Tanach", "HOT", "bible_hot_hbo.bblx", "hbo"),
    ],
)
def test_detect_language(title, abbr, filename, expected):
    assert detect_language(title, abbr, filename) == expected


def test_content_sample_disambiguates():
    # Título neutro; la muestra de contenido decide.
    assert detect_language("Obra", "X", "modulo.bblx",
                           sample="Y vio Dios que la luz era buena y apartó Dios la luz de las tinieblas.") == "es"
    assert detect_language("Work", "X", "module.bblx",
                           sample="And God saw the light, that it was good: and God divided the light from the darkness.") == "en"


def test_language_order_and_metadata_version(tmp_path):
    assert LANGUAGE_ORDER[0] == "es" and "und" in LANGUAGE_ORDER
    catalog = Catalog(tmp_path / "catalog.db")
    try:
        assert catalog.needs_metadata_refresh()
        catalog.set_meta("metadata_version", METADATA_VERSION)
        assert not catalog.needs_metadata_refresh()
    finally:
        catalog.close()
