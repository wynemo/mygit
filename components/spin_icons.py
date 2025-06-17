from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QLabel, QPushButton, QWidget


class RotatingAnimationMixin:
    def __init__(self, img_path: str, target_size: int = 20):
        self.target_size = target_size
        self.original_pixmap = QPixmap(img_path).scaled(
            self.target_size,
            self.target_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.angle = 0

        # 定时器控制旋转
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.rotate)

    def get_rotated_pixmap(self):
        """
        获取旋转后的图标。
        """
        self.angle = (self.angle + 3) % 360

        # 1. 创建画布
        canvas = QPixmap(self.target_size, self.target_size)
        canvas.fill(Qt.GlobalColor.transparent)

        # 2. 用 QPainter 在中心旋转并绘制
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # 3. 变换原点到中心，然后旋转
        center = self.target_size / 2
        painter.translate(center, center)
        painter.rotate(self.angle)
        painter.translate(-center, -center)

        # 4. 绘制原图
        painter.drawPixmap(0, 0, self.original_pixmap)
        painter.end()

        return canvas

    def rotate(self):
        pass

    def start(self):
        self.timer.start(16)  # 大约 60 FPS

    def stop(self):
        self.timer.stop()


class RotatingLabel(RotatingAnimationMixin, QLabel):
    def __init__(self, png_path):
        QLabel.__init__(self)
        RotatingAnimationMixin.__init__(self, png_path)
        self.start()

    def rotate(self):
        self.setPixmap(self.get_rotated_pixmap())


class SpinningButtonIcon(RotatingAnimationMixin, QPushButton):
    def __init__(self, img_path: str, spin_img_path: str, text: str | None = None, parent: QWidget | None = None):
        QPushButton.__init__(self, QIcon(img_path), text, parent)
        RotatingAnimationMixin.__init__(self, spin_img_path)

    def rotate(self):
        self.setIcon(QIcon(self.get_rotated_pixmap()))
