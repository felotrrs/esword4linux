"""Cadenas de citas múltiples."""

from __future__ import annotations

from linuxesword.core.refchain import parse_reference_chain


def _tuples(result):
    return [(r.book, r.chapter, r.verse, r.verse_end, r.chapter_end)
            for r in result.refs]


def test_user_example_chain():
    result = parse_reference_chain(
        "Gn23:1-6, 2:5-7, 3:4-5, Mar 2:1; Mateo 3:5-4, Jn3:16"
    )
    assert _tuples(result) == [
        (1, 23, 1, 6, None),   # Gn 23:1-6
        (1, 2, 5, 7, None),    # Gn 2:5-7 (hereda libro)
        (1, 3, 4, 5, None),    # Gn 3:4-5
        (41, 2, 1, None, None),  # Mar 2:1
        (40, 3, 5, None, 4),   # Mateo 3:5 → final del cap. 4
        (43, 3, 16, None, None),  # Jn3:16
    ]
    assert result.skipped == []


def test_verse_lists_and_chapter_lists():
    assert _tuples(parse_reference_chain("Sal 23:1,3,5")) == [
        (19, 23, 1, None, None),
        (19, 23, 3, None, None),
        (19, 23, 5, None, None),
    ]
    assert _tuples(parse_reference_chain("Salmos 23, 24")) == [
        (19, 23, None, None, None),
        (19, 24, None, None, None),
    ]


def test_parenthesized_groups():
    result = parse_reference_chain("Juan (1:1-5,7,9), (2:1,3), 3, 4")
    assert _tuples(result) == [
        (43, 1, 1, 5, None),
        (43, 1, 7, None, None),
        (43, 1, 9, None, None),
        (43, 2, 1, None, None),
        (43, 2, 3, None, None),
        (43, 3, None, None, None),
        (43, 4, None, None, None),
    ]


def test_garbage_is_reported_not_fatal():
    result = parse_reference_chain("Gen 1:1, cualquier_tonteria, Marcos 1:2")
    assert _tuples(result) == [(1, 1, 1, None, None), (41, 1, 2, None, None)]
    assert result.skipped == ["cualquier_tonteria"]
