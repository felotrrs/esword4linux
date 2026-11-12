"""Visor interactivo de imágenes (mapas, gráficos, ilustraciones).

Proporciona zoom suave con la rueda del ratón, paneo con arrastre, botones de
control (acercar, alejar, ajustar a ventana, 100%) y modo pantalla completa.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QAction, QColor, QKeySequence, QPainter, QPixmap
from PySide6.QtWidgets import (
    QDialog, QGraphicsPixmapItem, QGraphicsScene, QGraphicsView, QHBoxLayout,
    QLabel, QPushButton, QSizePolicy, QToolButton, QVBoxLayout, QWidget,
)

from ..i18n import tr
from .theme import palette


class _ZoomableGraphicsView(QGraphicsView):
    def __init__(self, scene: QGraphicsScene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setFrameShape(QGraphicsView.Shape.NoFrame)

    def wheelEvent(self, event) -> None:  # noqa: N802
        delta = event.angleDelta().y()
        if delta > 0:
            factor = 1.18
        elif delta < 0:
            factor = 1.0 / 1.18
        else:
            return
        self.scale(factor, factor)


class ImageViewer(QWidget):
    """Widget autónomo para inspeccionar ilustraciones y mapas."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap = QPixmap()
        self._item: QGraphicsPixmapItem | None = None
        self._title = ""
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Barra de herramientas flotante / superior de control
        self.toolbar = QWidget()
        tb_row = QHBoxLayout(self.toolbar)
        tb_row.setContentsMargins(8, 4, 8, 4)
        tb_row.setSpacing(4)

        self.lbl_info = QLabel("")
        self.lbl_info.setObjectName("appSubtitle")
        tb_row.addWidget(self.lbl_info)
        tb_row.addStretch(1)

        self.btn_zoom_out = QToolButton()
        self.btn_zoom_out.setText("−")
        self.btn_zoom_out.setToolTip(tr("common.zoom_out", default="Alejar (Rueda abajo)"))
        self.btn_zoom_out.clicked.connect(lambda: self.zoom(1.0 / 1.25))
        tb_row.addWidget(self.btn_zoom_out)

        self.btn_fit = QToolButton()
        self.btn_fit.setText("⛶")
        self.btn_fit.setToolTip(tr("common.zoom_fit", default="Ajustar a ventana"))
        self.btn_fit.clicked.connect(self.fit_in_view)
        tb_row.addWidget(self.btn_fit)

        self.btn_reset = QToolButton()
        self.btn_reset.setText("1:1")
        self.btn_reset.setToolTip(tr("common.zoom_100", default="Tamaño real (100%)"))
        self.btn_reset.clicked.connect(self.reset_zoom)
        tb_row.addWidget(self.btn_reset)

        self.btn_zoom_in = QToolButton()
        self.btn_zoom_in.setText("+")
        self.btn_zoom_in.setToolTip(tr("common.zoom_in", default="Acercar (Rueda arriba)"))
        self.btn_zoom_in.clicked.connect(lambda: self.zoom(1.25))
        tb_row.addWidget(self.btn_zoom_in)

        self.btn_fullscreen = QToolButton()
        self.btn_fullscreen.setText("↗")
        self.btn_fullscreen.setToolTip(tr("common.fullscreen", default="Ver ampliado / pantalla completa"))
        self.btn_fullscreen.clicked.connect(self._open_dialog)
        tb_row.addWidget(self.btn_fullscreen)

        layout.addWidget(self.toolbar)

        self.scene = QGraphicsScene(self)
        self.view = _ZoomableGraphicsView(self.scene, self)
        layout.addWidget(self.view, 1)

    def set_pixmap(self, pixmap: QPixmap, title: str = "") -> None:
        self._pixmap = pixmap
        self._title = title
        self.scene.clear()
        if pixmap and not pixmap.isNull():
            self._item = self.scene.addPixmap(pixmap)
            self.scene.setSceneRect(QRectF(pixmap.rect()))
            self.lbl_info.setText(f"{pixmap.width()} × {pixmap.height()} px")
            self.fit_in_view()
        else:
            self._item = None
            self.lbl_info.setText("")

    def zoom(self, factor: float) -> None:
        self.view.scale(factor, factor)

    def reset_zoom(self) -> None:
        self.view.resetTransform()

    def fit_in_view(self) -> None:
        if self._item and not self._pixmap.isNull():
            self.view.resetTransform()
            self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

    def _open_dialog(self) -> None:
        if self._pixmap.isNull():
            return
        dlg = QDialog(self.window())
        dlg.setWindowTitle(self._title or tr("kind.maps"))
        dlg.resize(1100, 750)
        dlg_layout = QVBoxLayout(dlg)
        dlg_layout.setContentsMargins(6, 6, 6, 6)
        viewer = ImageViewer(dlg)
        viewer.btn_fullscreen.hide()
        viewer.set_pixmap(self._pixmap, self._title)
        dlg_layout.addWidget(viewer)
        dlg.exec()
