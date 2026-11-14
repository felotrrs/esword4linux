"""Visor de imagen con zoom y controles típicos (mapas, ilustraciones).

Se usa para las entradas de tipo ``maps`` (`.mapx`) y, en general, para
cualquier página que contenga una imagen embebida. Permite:

* Acercar / alejar con la rueda del ratón (centrado en el puntero), o
  manteniendo Ctrl + clic derecho mientras se mueve la rueda.
* Arrastrar la imagen para navegar cuando está más grande que el visor.
* Ajustar a ventana, tamaño real (1:1) y restablecer zoom.
* Mostrar u ocultar la leyenda (texto Details) del mapa.

Los controles de zoom/arrastre/leyenda viven fuera de este widget (en la
cabecera de ``LibraryView``) y se conectan a través de las señales y métodos
públicos que se exponen aquí.

Nota: los eventos de mouse y rueda se capturan mediante un event filter
instalado en el viewport del ``QGraphicsView``, ya que ese view consume los
eventos antes de que lleguen al widget padre.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import (
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ..i18n import tr

ZOOM_IN = 1.25
ZOOM_OUT = 0.8
MIN_ZOOM = 0.1
MAX_ZOOM = 10.0


class ImageViewer(QWidget):
    """Visor de imagen con zoom (rueda) y arrastre (manita)."""

    zoom_changed = Signal(float)
    legend_toggled = Signal(bool)
    # Emitida al cargar una imagen con el texto del tamaño (p. ej. "400 × 300 px").
    image_size = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scale = 1.0
        self._wheel_zoom_enabled = True
        self._pan_enabled = True
        self._pan_button = Qt.LeftButton  # arrastre con clic izquierdo
        self._pan_origin = QPoint()

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
        # Sin DragMode nativo: manejamos el arrastre manualmente vía event
        # filter, para que zoom con rueda y arrastre con manita coexistan.
        self.view.setDragMode(QGraphicsView.DragMode.NoDrag)
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
        # Capturar mouse y wheel directamente en el viewport, ya que el
        # QGraphicsView los consume antes de que lleguen a este widget.
        self.view.viewport().installEventFilter(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.view, 1)

        # Atributo conservado para compatibilidad con pruebas; el texto de
        # píxeles se muestra ahora junto al combobox de Biblia en la cabecera.
        self.lbl_info = QLabel(self)
        self.lbl_info.hide()

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
        return True  # El visor no gestiona la leyenda; lo hace LibraryView.

    def set_legend_visible(self, visible: bool) -> None:
        self.legend_toggled.emit(bool(visible))

    def is_wheel_zoom_enabled(self) -> bool:
        return self._wheel_zoom_enabled

    def set_wheel_zoom_enabled(self, enabled: bool) -> None:
        self._wheel_zoom_enabled = bool(enabled)

    def is_pan_enabled(self) -> bool:
        return self._pan_enabled

    def set_pan_enabled(self, enabled: bool) -> None:
        self._pan_enabled = bool(enabled)

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

    # ── event filter: wheel + pan en el viewport ───────────────────────
    def eventFilter(self, obj, event) -> None:  # type: ignore[override]
        if obj is self.view.viewport():
            if event.type() == QEvent.Wheel:
                return self._viewport_wheel_event(event)
            if event.type() == QEvent.MouseButtonPress:
                return self._viewport_mouse_press(event)
            if event.type() == QEvent.MouseMove:
                return self._viewport_mouse_move(event)
            if event.type() == QEvent.MouseButtonRelease:
                return self._viewport_mouse_release(event)
        return super().eventFilter(obj, event)

    def _viewport_wheel_event(self, event) -> bool:
        if not self.has_image():
            return False
        delta = event.angleDelta().y()
        if delta == 0:
            return False
        ctrl_right = bool(
            event.modifiers() & Qt.ControlModifier
            and event.buttons() & Qt.RightButton
        )
        if not self._wheel_zoom_enabled and not ctrl_right:
            return False
        factor = ZOOM_IN if delta > 0 else ZOOM_OUT
        new_scale = min(MAX_ZOOM, max(MIN_ZOOM, self._scale * factor))
        if abs(new_scale - self._scale) < 1e-6:
            return True
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
        return True

    def _viewport_mouse_press(self, event) -> bool:
        if (
            self._pan_enabled
            and self.has_image()
            and event.button() == self._pan_button
        ):
            self._pan_origin = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return True
        return False

    def _viewport_mouse_move(self, event) -> bool:
        if self._pan_enabled and self.has_image() and event.buttons() & self._pan_button:
            delta = event.pos() - self._pan_origin
            self._pan_origin = event.pos()
            self.view.horizontalScrollBar().setValue(
                self.view.horizontalScrollBar().value() - delta.x()
            )
            self.view.verticalScrollBar().setValue(
                self.view.verticalScrollBar().value() - delta.y()
            )
            return True
        return False

    def _viewport_mouse_release(self, event) -> bool:
        if event.button() == self._pan_button:
            self.setCursor(Qt.CursorShape.ArrowCursor)
            return True
        return False

    def _apply_zoom(self) -> None:
        self.view.resetTransform()
        self.view.scale(self._scale, self._scale)
        self.zoom_changed.emit(self._scale)

    def sizeHint(self) -> QSize:
        return QSize(400, 300)
