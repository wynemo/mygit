import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath
from PyQt6.QtWidgets import QApplication, QWidget


class TriangleWidget(QWidget):
    """
    cursor 生成
    一个用于绘制三角形的 QWidget。
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQt6 绘制三角形")
        self.setGeometry(100, 100, 400, 300)  # 设置窗口位置和大小

    def paintEvent(self, event):
        """
        绘制事件处理函数，用于在窗口上进行绘制。
        """
        painter = QPainter(self)
        # 启用抗锯齿，使图形边缘更平滑
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 设置画笔，用于绘制三角形的边框
        painter.setPen(QColor(Qt.GlobalColor.black))  # 黑色边框
        painter.setPen(Qt.PenStyle.SolidLine)  # 实线
        painter.setPen(2)  # 2像素宽

        # 设置画刷，用于填充三角形内部
        painter.setBrush(QColor(Qt.GlobalColor.red))  # 红色填充

        # 创建一个 QPainterPath 对象来定义三角形的形状
        path = QPainterPath()

        # 移动到第一个顶点 (100, 50) - 直角顶点
        path.moveTo(100, 50)
        # 连接到第二个顶点 (250, 50) - 水平边
        path.lineTo(250, 50)
        # 连接到第三个顶点 (100, 200) - 垂直边
        path.lineTo(100, 200)
        # 闭合路径，连接回第一个顶点，形成直角三角形
        path.lineTo(100, 50)

        # 绘制路径（直角三角形）
        painter.drawPath(path)

        # 也可以使用 QPolygonF 来绘制填充多边形（包括三角形）
        # from PyQt6.QtCore import QPointF
        # points = [QPointF(100, 50), QPointF(250, 250), QPointF(50, 250)]
        # polygon = QPolygonF(points)
        # painter.drawPolygon(polygon)

        painter.end()  # 结束绘制


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TriangleWidget()
    window.show()
    sys.exit(app.exec())
