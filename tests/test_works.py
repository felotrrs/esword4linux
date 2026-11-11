"""Agrupación por obra y burbuja de ancho limitado."""

from __future__ import annotations

from pathlib import Path

import pytest

from linuxesword.core.catalog import work_key, work_year

CORPUS = Path("/home/felipe/StorageA/Biblias/Biblias_bblx")


def test_work_key_strips_year_and_accents():
    assert work_key("Nueva Versión Internacional 1999") == work_key("Nueva Versión Internacional")
    assert work_key("La Santa Biblia Reina-Valera (1960)") == work_key(
        "La Santa Biblia Reina-Valera (1995)"
    )


def test_work_year():
    assert work_year("La Santa Biblia Reina-Valera (1960)") == "1960"
    assert work_year("Reina Valera 1995") == "1995"
    assert work_year("Biblia sin año") == ""


pytestmark = pytest.mark.skipif(not CORPUS.is_dir(), reason="corpus no disponible")


def test_works_groups_the_same_work():
    from linuxesword.config import Settings
    from linuxesword.core.catalog import Catalog

    catalog = Catalog(Settings.load().catalog_db)
    works = catalog.works()
    assert works, "debe haber obras"
    multi = [w for w in works if len(w["modules"]) > 1]
    assert multi, "debe haber obras con varios módulos"
    # ninguna obra repite el mismo módulo
    for work in works:
        ids = [m["id"] for m in work["modules"]]
        assert len(ids) == len(set(ids))


def test_works_separates_editions_by_year():
    from linuxesword.config import Settings
    from linuxesword.core.catalog import Catalog

    catalog = Catalog(Settings.load().catalog_db)
    works = {w["title"]: w for w in catalog.works()}
    rv60 = [t for t in works if "Reina-Valera (1960)" in t]
    rv95 = [t for t in works if "Reina-Valera (1995)" in t]
    if rv60 and rv95:
        assert rv60[0] != rv95[0]


def test_bubble_width_is_capped():
    pytest.importorskip("PySide6")
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from linuxesword.ui.tooltip import MAX_WIDTH, TipBubble

    app = QApplication.instance() or QApplication([])
    bubble = TipBubble()
    long_text = "📖 Juan 3:16 (RV1960)\n" + ("Porque de tal manera amó Dios al mundo. " * 20)
    bubble.show_html(__import__("PySide6.QtCore", fromlist=["QPoint"]).QPoint(100, 100),
                     long_text)
    assert bubble.width() <= MAX_WIDTH
    assert bubble.height() > 20
