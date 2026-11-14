"""Visor de imagen con zoom y controles típicos (mapas, ilustraciones).

Se usa para las entradas de tipo ``maps`` (`.mapx`) y, en general, para
cualquier página que contenga una imagen embebida. Permite:

* Acercar / alejar con la rueda del ratón (centrado en el puntero), o
  manteniendo Ctrl + clic derecho mientras se mueve la rueda.
* Arrastrar la imagen para navegar cuando está más grande que el visor.
* Ajustar a ventana, tamaño real (1:1) y restablecer zoom.
* Mostrar u ocultar la leyenda (texto Details) del mapa.
* Activar / desactivar por separado el zoom con rueda y el arrastre.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import (
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..i18n import tr

ZOOM_IN = 1.25
ZOOM_OUT = 0.8
MIN_ZOOM = 0.1
MAX_ZOOM = 10.0


class ImageViewer(QWidget):
    """Visor de imagen con zoom (rueda), arrastre y botones de control."""

    zoom_changed = Signal(float)
    legend_toggled = Signal(bool)
    # Emitida al cargar una imagen con el texto del tamaño (p. ej. "400 × 300 px").
    image_size = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scale = 1.0
        self._wheel_zoom_enabled = True
        self._pan_enabled = True

        self.scene = QGraphicsScene(self)
        self._item = QGraphicsPixmapItem()
        self._item.setShapeMode(QGraphicsPixmapItem.BoundingRectShape)
        self.scene.addItem(self._item)
        self.item = self._item

        self.view = QGraphicsView(self.scene, self)
        self.view.setRenderHints(
            self.view.renderHints()
            | QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )
        # Centra el contenido cuando es más pequeño que el viewport
        # (p. ej. mapa en tamaño real 1:1 no queda pegado a la esquina).
        self.view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._update_drag_mode()
        self.view.setTransformationAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse
        )
        self.view.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.view.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.view.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        # ── barra de controles (arriba, botones a la izquierda) ──────────
        self.btn_zoom_in = QToolButton()
        self.btn_zoom_in.setText("+")
        self.btn_zoom_in.setToolTip(tr("image.zoom_in"))
        self.btn_zoom_in.clicked.connect(self.zoom_in)

        self.btn_zoom_out = QToolButton()
        self.btn_zoom_out.setText("-")
        self.btn_zoom_out.setToolTip(tr("image.zoom_out"))
        self.btn_zoom_out.clicked.connect(self.zoom_out)

        self.btn_reset = QToolButton()
        self.btn_reset.setText("1:1")
        self.btn_reset.setToolTip(tr("image.zoom_real"))
        self.btn_reset.clicked.connect(self.reset_zoom)

        self.btn_fit = QToolButton()
        self.btn_fit.setText(tr("image.fit"))
        self.btn_fit.setToolTip(tr("image.fit"))
        self.btn_fit.clicked.connect(self.fit_to_window)

        self.btn_legend = QToolButton()
        self.btn_legend.setText(tr("image.legend"))
        self.btn_legend.setToolTip(tr("image.legend"))
        self.btn_legend.setCheckable(True)
        self.btn_legend.setChecked(True)
        self.btn_legend.clicked.connect(self._on_legend_clicked)

        # Toggle: zoom con rueda del ratón.
        self.btn_wheel_zoom = QToolButton()
        self.btn_wheel_zoom.setText("🔍")
        self.btn_wheel_zoom.setToolTip(tr("image.wheel_zoom"))
        self.btn_wheel_zoom.setCheckable(True)
        self.btn_wheel_zoom.setChecked(self._wheel_zoom_enabled)
        self.btn_wheel_zoom.clicked.connect(self._toggle_wheel_zoom)

        # Toggle: arrastre con manita.
        self.btn_pan = QToolButton()
        self.btn_pan.setText("👋")
        self.btn_pan.setToolTip(tr("image.pan"))
        self.btn_pan.setCheckable(True)
        self.btn_pan.setChecked(self._pan_enabled)
        self.btn_pan.clicked.connect(self._toggle_pan)

        # Atributo conservado para compatibilidad con pruebas; el texto de
        # píxeles se muestra ahora junto al combobox de Biblia en la cabecera.
        self.lbl_info = QLabel(self)
        self.lbl_info.hide()

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(6, 4, 6, 4)
        toolbar.setSpacing(6)
        toolbar.addWidget(self.btn_zoom_in)
        toolbar.addWidget(self.btn_zoom_out)
        toolbar.addWidget(self.btn_reset)
        toolbar.addWidget(self.btn_fit)
        toolbar.addWidget(self.btn_legend)
        toolbar.addWidget(self.btn_wheel_zoom)
        toolbar.addWidget(self.btn_pan)
        toolbar.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(toolbar)
        layout.addWidget(self.view, 1)

    # ── API pública ────────────────────────────────────────────────────
    def set_pixmap(self, pixmap: QPixmap, title: str | None = None) -> None:
        """Muestra un QPixmap ajustado al espacio disponible por defecto."""
        self._item.setPixmap(pixmap)
        self._scale = 1.0
        self.view.resetTransform()
        if not pixmap.isNull():
            self.image_size.emit(f"{pixmap.width()} × {pixmap.height()} px")
            self.lbl_info.setText(f"{pixmap.width()} × {pixmap.height()} px")
            # Ajustar a ventana una vez que el widget tenga su tamaño real.
            QTimer.singleShot(0, self.fit_to_window)
        else:
            self.image_size.emit("")
            self.lbl_info.hide()
            self.zoom_changed.emit(self._scale)

    def set_image_bytes(self, data: bytes, title: str | None = None) -> bool:
        """Carga una imagen desde bytes (PNG/JPEG/GIF…). Devuelve si tuvo éxito."""
        pixmap = QPixmap()
        if not pixmap.loadFromData(data):
            return False
        self.set_pixmap(pixmap, title)
        return True

    def pixmap(self) -> QPixmap:
        return self.item.pixmap()

    def has_image(self) -> bool:
        return not self.item.pixmap().isNull()

    def is_legend_visible(self) -> bool:
        return self.btn_legend.isChecked()

    def set_legend_visible(self, visible: bool) -> None:
        self.btn_legend.setChecked(bool(visible))

    def is_wheel_zoom_enabled(self) -> bool:
        return self._wheel_zoom_enabled

    def set_wheel_zoom_enabled(self, enabled: bool) -> None:
        self._wheel_zoom_enabled = bool(enabled)
        self.btn_wheel_zoom.setChecked(self._wheel_zoom_enabled)

    def is_pan_enabled(self) -> bool:
        return self._pan_enabled

    def set_pan_enabled(self, enabled: bool) -> None:
        self._pan_enabled = bool(enabled)
        self.btn_pan.setChecked(self._pan_enabled)
        self._update_drag_mode()

    def zoom(self, factor: float) -> None:
        """Aplica un factor de zoom relativo al nivel actual."""
        self._scale = min(MAX_ZOOM, max(MIN_ZOOM, self._scale * factor))
        self._apply_zoom()

    def zoom_in(self) -> None:
        self._scale = min(MAX_ZOOM, self._scale * ZOOM_IN)
        self._apply_zoom()

    def zoom_out(self) -> None:
        self._scale = max(MIN_ZOOM, self._scale * ZOOM_OUT)
        self._apply_zoom()

    def reset_zoom(self) -> None:
        """Tamaño real (1:1), la imagen queda centrada en el espacio."""
        self._scale = 1.0
        self._apply_zoom()
        self.view.centerOn(self._item)

    def fit_to_window(self) -> None:
        if self.item.pixmap().isNull():
            return
        self.view.fitInView(
            self.item, Qt.AspectRatioMode.KeepAspectRatio
        )
        tr_ = self.view.transform()
        self._scale = max(tr_.m11(), tr_.m22())
        self.zoom_changed.emit(self._scale)

    def wheelEvent(self, event) -> None:  # type: ignore[override]
        """Rueda del ratón: hace zoom centrado en el puntero.

        Requiere que el zoom con rueda esté habilitado, o bien que se
        mantenga Ctrl + clic derecho presionado mientras se mueve la rueda.
        """
        if not self.has_image():
            event.ignore()
            return
        delta = event.angleDelta().y()
        if delta == 0:
            event.ignore()
            return
        ctrl_right = bool(
            event.modifiers() & Qt.ControlModifier
            and event.buttons() & Qt.RightButton
        )
        if not self._wheel_zoom_enabled and not ctrl_right:
            event.ignore()
            return
        factor = ZOOM_IN if delta > 0 else ZOOM_OUT
        new_scale = min(MAX_ZOOM, max(MIN_ZOOM, self._scale * factor))
        if abs(new_scale - self._scale) < 1e-6:
            event.accept()
            return
        mouse_pos = self.view.mapToScene(event.position().toPoint())
        self._scale = new_scale
        self._apply_zoom()
        new_mouse = self.view.mapToScene(event.position().toPoint())
        delta_scene = new_mouse - mouse_pos
        self.view.horizontalScrollBar().setValue(
            int(self.view.horizontalScrollBar().value() + delta_scene.x())
        )
        self.view.verticalScrollBar().setValue(
            int(self.view.verticalScrollBar().value() + delta_scene.y())
        )
        event.accept()

    def _update_drag_mode(self) -> None:
        if self._pan_enabled:
            self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        else:
            self.view.setDragMode(QGraphicsView.DragMode.NoDrag)

    def _apply_zoom(self) -> None:
        self.view.resetTransform()
        self.view.scale(self._scale, self._scale)
        self.zoom_changed.emit(self._scale)

    def _on_legend_clicked(self, checked: bool) -> None:
        self.legend_toggled.emit(checked)

    def _toggle_wheel_zoom(self, checked: bool) -> None:
        self._wheel_zoom_enabled = bool(checked)

    def _toggle_pan(self, checked: bool) -> None:
        self._pan_enabled = bool(checked)
        self._update_drag_mode()

    def sizeHint(self) -> QSize:
        return QSize(400, 300)
