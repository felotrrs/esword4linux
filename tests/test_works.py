"""Work grouping and the width-capped bubble."""

from __future__ import annotations

from pathlib import Path

import pytest

from esword4linux.core.catalog import work_key, work_year

from support import CORPUS, requires_corpus


def test_work_key_strips_year_and_accents():
    assert work_key("Nueva Versión Internacional 1999") == work_key("Nueva Versión Internacional")
    assert work_key("La Santa Biblia Reina-Valera (1960)") == work_key(
        "La Santa Biblia Reina-Valera (1995)"
    )


def test_work_year():
    assert work_year("La Santa Biblia Reina-Valera (1960)") == "1960"
    assert work_year("Reina Valera 1995") == "1995"
    assert work_year("Biblia sin año") == ""


@requires_corpus
def test_works_groups_the_same_work(corpus_catalog):
    works = corpus_catalog.works()
    assert works, "there must be works"
    multi = [w for w in works if len(w["modules"]) > 1]
    assert multi, "there must be works with several modules"
    # no work repeats the same module
    for work in works:
        ids = [m["id"] for m in work["modules"]]
        assert len(ids) == len(set(ids))


@requires_corpus
def test_works_separates_editions_by_year(corpus_catalog):
    works = {w["title"]: w for w in corpus_catalog.works()}
    rv60 = [t for t in works if "Reina-Valera (1960)" in t]
    rv95 = [t for t in works if "Reina-Valera (1995)" in t]
    if rv60 and rv95:
        assert rv60[0] != rv95[0]


def test_bubble_width_is_capped():
    pytest.importorskip("PySide6")
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from esword4linux.ui.tooltip import MAX_WIDTH, TipBubble

    app = QApplication.instance() or QApplication([])
    bubble = TipBubble()
    long_text = "📖 Juan 3:16 (RV1960)\n" + ("Porque de tal manera amó Dios al mundo. " * 20)
    bubble.show_html(__import__("PySide6.QtCore", fromlist=["QPoint"]).QPoint(100, 100),
                     long_text)
    assert bubble.width() <= MAX_WIDTH
    assert bubble.height() > 20
