"""Tests for the heuristic classification system and the image viewer."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

from esword4linux.core.catalog import KIND_ORDER, KIND_LABELS, ROLE_LABELS
from esword4linux.ui.image_viewer import ImageViewer
from esword4linux.ui.tab_bar import ColoredTabBar


def test_kind_labels_and_roles_contain_book():
    assert "book" in KIND_ORDER
    assert "book" in KIND_LABELS
    assert "book" in ROLE_LABELS
    assert KIND_LABELS["book"] == ("Libros", "Books")
    assert ROLE_LABELS["book"] == ("Libro", "Book")


def test_image_viewer_zoom_and_fit():
    pytest.importorskip("PySide6")
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])

    viewer = ImageViewer()
    viewer.resize(800, 600)
    viewer.show()
    app.processEvents()

    # Test pixmap
    pm = QPixmap(400, 300)
    pm.fill(Qt.GlobalColor.blue)
    viewer.set_pixmap(pm, "Mapa de prueba")
    app.processEvents()

    assert viewer.lbl_info.text() == "400 × 300 px"
    assert viewer._item is not None

    # Zoom in
    scale_before = viewer.view.transform().m11()
    viewer.zoom(1.5)
    app.processEvents()
    assert viewer.view.transform().m11() > scale_before

    # Reset
    viewer.reset_zoom()
    app.processEvents()
    assert abs(viewer.view.transform().m11() - 1.0) < 1e-4

    viewer.deleteLater()


def test_tab_bar_with_icon():
    pytest.importorskip("PySide6")
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])

    tab_bar = ColoredTabBar()
    tab_bar.resize(400, 40)
    tab_bar.addTab("Pestaña 1")
    tab_bar.addTab("Buscar")

    # Dummy icon
    icon_pm = QPixmap(16, 16)
    icon_pm.fill(Qt.GlobalColor.red)
    from PySide6.QtGui import QIcon
    tab_bar.setTabIcon(1, QIcon(icon_pm))
    tab_bar.show()
    app.processEvents()

    # tabSizeHint must account for the icon width
    size = tab_bar.tabSizeHint(1)
    assert size.width() >= 90
    tab_bar.deleteLater()
