from abc import ABC, abstractmethod

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QPixmap
from PyQt6.QtWidgets import QLabel

# 搞个抽象基类， rorate, start stop 三个方法
# 用python的abc模块实现


class RotatingIconBase(ABC):
    @abstractmethod
    def rotate(self):
        pass

    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def stop(self):
        pass


class RotatingIcon(QLabel):
    def __init__(self, png_path):
        super().__init__()
        self.target_size = 20  # 你想要的尺寸
        self.original_pixmap = QPixmap(png_path).scaled(
            self.target_size,
            self.target_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.angle = 0
        self.setPixmap(self.original_pixmap)

        # 定时器控制旋转
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.rotate)
        self.timer.start(16)  # 大约 60 FPS

    def rotate(self):
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

        self.setPixmap(canvas)
