"""Reference parser and book names."""

from __future__ import annotations

import pytest

from esword4linux.core.books import book_name, parse_reference


@pytest.mark.parametrize(
    "text,book,chapter,verse,vend",
    [
        ("Juan 3:16", 43, 3, 16, None),
        ("Jn 3.16", 43, 3, 16, None),
        ("1 Corintios 13:4-7", 46, 13, 4, 7),
        ("1 Cor 13:4-7", 46, 13, 4, 7),
        ("Sal 23", 19, 23, None, None),
        ("Salmos 119:105", 19, 119, 105, None),
        ("Génesis 1:1", 1, 1, 1, None),
        ("Genesis 1:1", 1, 1, 1, None),
        ("Apocalipsis 22:21", 66, 22, 21, None),
        ("Rev 22:21", 66, 22, 21, None),
        ("2 Timoteo 3:16", 55, 3, 16, None),
        ("Hechos 2:38", 44, 2, 38, None),
        ("  1a Corintios 13:4 ", 46, 13, 4, None),
        # Editorial prefixes: I/II, Primera/Segunda and the 1ª/1ra ordinals.
        ("I Samuel 1:1", 9, 1, 1, None),
        ("II Reyes 2:1", 12, 2, 1, None),
        ("Primera de Corintios 13:4", 46, 13, 4, None),
        ("Tercera de Juan 1:2", 64, 1, 2, None),
        ("1ª Corintios 13:4", 46, 13, 4, None),
        ("1ra Corintios 13:4", 46, 13, 4, None),
        # Separators and abbreviations from other traditions.
        ("Jn 3,16", 43, 3, 16, None),
        ("1 P 1:3", 60, 1, 3, None),
        ("1Pedro 1:3", 60, 1, 3, None),
        ("Luk 1:1-4", 42, 1, 1, 4),
        ("Jhn 1:1-5", 43, 1, 1, 5),
        ("Deu 12:16", 5, 12, 16, None),
        ("Pro 1:1", 20, 1, 1, None),
        ("Amo 9:9", 30, 9, 9, None),
        ("Rth 2:14", 8, 2, 14, None),
        ("Ezk 16:8", 26, 16, 8, None),
        ("Mrk 15:34", 41, 15, 34, None),
        ("Éxo 15:2", 2, 15, 2, None),
        ("Núm 23:22", 4, 23, 22, None),
        # Names in French and Portuguese.
        ("Jean 3:16", 43, 3, 16, None),
        ("1 Corinthiens 13:4", 46, 13, 4, None),
        ("João 3:16", 43, 3, 16, None),
        ("1 Coríntios 13:4", 46, 13, 4, None),
        ("San Juan 3:16", 43, 3, 16, None),
        ("S. Juan 3:16", 43, 3, 16, None),
    ],
)
def test_parse_reference(text, book, chapter, verse, vend):
    ref = parse_reference(text)
    assert ref is not None, text
    assert (ref.book, ref.chapter, ref.verse, ref.verse_end) == (book, chapter, verse, vend)


def test_parse_chapter_range():
    ref = parse_reference("Génesis 1-3")
    assert ref is not None
    assert (ref.book, ref.chapter, ref.chapter_end) == (1, 1, 3)
    assert ref.label() == "Génesis 1-3"


@pytest.mark.parametrize("text", ["1 Esdras 8:2", "3 Macc 3:21", "Enoch 2:1"])
def test_parse_unsupported_deuterocanonical(text):
    # Not in the e-Sword 1–73 numbering: better not to invent the book.
    assert parse_reference(text) is None


@pytest.mark.parametrize("text", ["amor", "", "123", "xyz 3:16", "G2316"])
def test_parse_reference_rejects(text):
    assert parse_reference(text) is None


def test_book_names():
    assert book_name(1, "es") == "Génesis"
    assert book_name(1, "en") == "Genesis"
    assert book_name(1, "fr") == "Genèse"
    assert book_name(43, "pt") == "João"
    assert book_name(66, "es") == "Apocalipsis"
    assert book_name(999, "es").startswith("Libro")
