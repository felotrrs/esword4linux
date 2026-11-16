"""Image viewer with zoom and pan for maps and illustrations.

Used for ``maps`` entries (`.mapx`) and, in general, for any page containing
an embedded image. It allows:

* Zoom in / out with the mouse wheel (centered on the pointer).
* Drag the image with the left button to pan when it is larger than the
  viewer.
* Fit to window and actual size (1:1).

Mouse gestures are handled internally; there are no control buttons in the
UI.
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

ZOOM_IN = 1.25
ZOOM_OUT = 0.8
MIN_ZOOM = 0.1
MAX_ZOOM = 10.0


class ImageViewer(QWidget):
    """Image viewer with zoom (wheel) and pan (hand with the left button)."""

    zoom_changed = Signal(float)
    legend_toggled = Signal(bool)
    # Emitted when an image loads, with the size text (e.g. "400 × 300 px").
    image_size = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scale = 1.0
        self._wheel_zoom_enabled = True
        self._pan_enabled = True
        self._pan_button = Qt.LeftButton  # pan with the left button
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
        # Center the content when it is smaller than the viewport
        # (e.g. a map at actual 1:1 size is not stuck to the corner).
        self.view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # No native DragMode: pan is handled manually via an event filter,
        # so wheel zoom and hand pan coexist.
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
        # Capture mouse and wheel directly in the viewport, since
        # QGraphicsView consumes them before they reach the parent widget.
        self.view.viewport().installEventFilter(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.view, 1)

        # Attribute kept for test compatibility; the pixel text is now shown
        # next to the Bible combo in the header.
        self.lbl_info = QLabel(self)
        self.lbl_info.hide()

    # ── public API ─────────────────────────────────────────────────────
    def set_pixmap(self, pixmap: QPixmap, title: str | None = None) -> None:
        """Show a QPixmap fitted to the available space by default."""
        self._item.setPixmap(pixmap)
        self._scale = 1.0
        self.view.resetTransform()
        if not pixmap.isNull():
            self.image_size.emit(f"{pixmap.width()} × {pixmap.height()} px")
            self.lbl_info.setText(f"{pixmap.width()} × {pixmap.height()} px")
            # Fit to window once the widget has its real size.
            QTimer.singleShot(0, self.fit_to_window)
        else:
            self.image_size.emit("")
            self.lbl_info.hide()
            self.zoom_changed.emit(self._scale)

    def set_image_bytes(self, data: bytes, title: str | None = None) -> bool:
        """Load an image from bytes (PNG/JPEG/GIF...). Returns whether it succeeded."""
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
        return True  # The viewer does not manage the legend; LibraryView does.

    def set_legend_visible(self, visible: bool) -> None:
        self.legend_toggled.emit(bool(visible))

    def zoom(self, factor: float) -> None:
        """Apply a zoom factor relative to the current level."""
        self._scale = min(MAX_ZOOM, max(MIN_ZOOM, self._scale * factor))
        self._apply_zoom()

    def zoom_in(self) -> None:
        self._scale = min(MAX_ZOOM, self._scale * ZOOM_IN)
        self._apply_zoom()

    def zoom_out(self) -> None:
        self._scale = max(MIN_ZOOM, self._scale * ZOOM_OUT)
        self._apply_zoom()

    def reset_zoom(self) -> None:
        """Actual size (1:1); the image stays centered in the space."""
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

    # ── event filter: wheel + pan in the viewport ──────────────────────
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
        if not self._wheel_zoom_enabled:
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
