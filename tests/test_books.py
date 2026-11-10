"""Parser de referencias y nombres de libros."""

from __future__ import annotations

import pytest

from linuxesword.core.books import book_name, parse_reference


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
    ],
)
def test_parse_reference(text, book, chapter, verse, vend):
    ref = parse_reference(text)
    assert ref is not None, text
    assert (ref.book, ref.chapter, ref.verse, ref.verse_end) == (book, chapter, verse, vend)


@pytest.mark.parametrize("text", ["amor", "", "123", "xyz 3:16", "G2316"])
def test_parse_reference_rejects(text):
    assert parse_reference(text) is None


def test_book_names():
    assert book_name(1, "es") == "Génesis"
    assert book_name(1, "en") == "Genesis"
    assert book_name(66, "es") == "Apocalipsis"
    assert book_name(999, "es").startswith("Libro")
