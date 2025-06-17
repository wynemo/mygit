from PyQt6.QtCore import QRectF, Qt, QTimer
from PyQt6.QtGui import QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QLabel, QPushButton, QWidget


class RotatingAnimationMixin:
    def __init__(self, img_path: str, target_size: int = 20):
        self.target_size = target_size
        self.angle = 0

        # Determine if file is SVG
        if img_path.lower().endswith(".svg"):
            self.is_svg = True
            self.svg_renderer = QSvgRenderer(img_path)
            if not self.svg_renderer.isValid():
                raise ValueError(f"Invalid SVG file: {img_path}")
        else:
            self.is_svg = False
            self.original_pixmap = QPixmap(img_path)
            if self.original_pixmap.isNull():
                raise ValueError(f"Failed to load image: {img_path}")
            self.original_pixmap = self.original_pixmap.scaled(
                self.target_size,
                self.target_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        # Setup rotation timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.rotate)

    def get_rotated_pixmap(self):
        """Generate rotated pixmap with smooth rendering for both SVG and bitmap images"""
        self.angle = (self.angle + 3) % 360  # Increment rotation angle

        canvas = QPixmap(self.target_size, self.target_size)
        canvas.fill(Qt.GlobalColor.transparent)

        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        center = self.target_size / 2
        painter.translate(center, center)
        painter.rotate(self.angle)
        painter.translate(-center, -center)

        if self.is_svg:
            self.svg_renderer.render(painter, QRectF(0, 0, self.target_size, self.target_size))
        else:
            painter.drawPixmap(0, 0, self.original_pixmap)

        painter.end()
        return canvas

    def rotate(self):
        """Rotation handler to be implemented by child classes"""
        pass

    def start(self):
        """Start rotation animation (~60 FPS)"""
        self.timer.start(16)

    def stop(self):
        """Stop rotation animation"""
        self.timer.stop()


class RotatingLabel(RotatingAnimationMixin, QLabel):
    def __init__(self, img_path: str):
        QLabel.__init__(self)
        RotatingAnimationMixin.__init__(self, img_path)
        self.start()

    def rotate(self):
        self.setPixmap(self.get_rotated_pixmap())


class SpinningButtonIcon(RotatingAnimationMixin, QPushButton):
    def __init__(self, img_path: str, spin_img_path: str, text: str | None = None, parent: QWidget | None = None):
        QPushButton.__init__(self, QIcon(img_path), text, parent)
        RotatingAnimationMixin.__init__(self, spin_img_path)

    def rotate(self):
        self.setIcon(QIcon(self.get_rotated_pixmap()))
