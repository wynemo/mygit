import sys
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtGui import QPainter, QPainterPath, QPolygon
from PyQt6.QtCore import QPoint

class TrapezoidWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQt6 绘制梯形")
        self.setGeometry(100, 100, 600, 400)

    def paintEvent(self, event):
        painter = QPainter(self)
        
        # 方法1: 使用QPainterPath绘制梯形
        path = QPainterPath()
        # 梯形顶点坐标 (上底较短，下底较长)
        path.moveTo(150, 50)   # 左上顶点
        path.lineTo(250, 50)   # 右上顶点
        path.lineTo(300, 150)  # 右下顶点
        path.lineTo(100, 150)  # 左下顶点
        path.lineTo(150, 50)   # 闭合路径
        
        painter.drawPath(path)
        painter.drawText(175, 180, "方法1: QPainterPath")
        
        # 方法2: 使用QPolygon绘制梯形
        points = [
            QPoint(450, 50),   # 左上
            QPoint(550, 50),   # 右上  
            QPoint(580, 150),  # 右下
            QPoint(420, 150)   # 左下
        ]
        polygon = QPolygon(points)
        painter.drawPolygon(polygon)
        painter.drawText(475, 180, "方法2: QPolygon")
        
        # 方法3: 使用drawLine逐条边绘制
        # 等腰梯形
        painter.drawLine(150, 250, 250, 250)  # 上底
        painter.drawLine(250, 250, 300, 350)  # 右边
        painter.drawLine(300, 350, 100, 350)  # 下底
        painter.drawLine(100, 350, 150, 250)  # 左边
        painter.drawText(175, 380, "方法3: drawLine")
        
        # 方法4: 直角梯形
        trapezoid_path = QPainterPath()
        trapezoid_path.moveTo(450, 250)  # 左上
        trapezoid_path.lineTo(550, 250)  # 右上
        trapezoid_path.lineTo(550, 350)  # 右下
        trapezoid_path.lineTo(400, 350)  # 左下
        trapezoid_path.lineTo(450, 250)  # 闭合
        
        painter.drawPath(trapezoid_path)
        painter.drawText(475, 380, "方法4: 直角梯形")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    widget = TrapezoidWidget()
    widget.show()
    sys.exit(app.exec())
