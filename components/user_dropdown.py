import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget


class UserDropdown(QWidget):
    clicked = pyqtSignal()

    def __init__(self, text="User", parent=None):
        super().__init__(parent)
        self.text = text
        self.setup_ui()
        self.setFixedHeight(32)
        self.setStyleSheet("""
            UserDropdown {
                background-color: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 6px;
                padding: 6px 12px;
            }
            UserDropdown:hover {
                background-color: #e9ecef;
                border-color: #dee2e6;
            }
        """)

    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        # 左侧文字标签
        self.text_label = QLabel(self.text)
        self.text_label.setStyleSheet("""
            QLabel {
                color: #495057;
                font-size: 14px;
                font-weight: 500;
                background: transparent;
                border: none;
            }
        """)
        layout.addWidget(self.text_label)

        # 添加弹性空间，将箭头推到右边
        layout.addStretch()

        # 右侧箭头图标
        self.arrow_label = QLabel()
        self.load_arrow_icon()
        layout.addWidget(self.arrow_label)

    def load_arrow_icon(self):
        """加载SVG箭头图标"""
        svg_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "icons", "chevron-down.svg")

        if os.path.exists(svg_path):
            # 使用QSvgRenderer渲染SVG
            renderer = QSvgRenderer(svg_path)

            # 创建一个16x16的像素图
            pixmap = QPixmap(16, 16)
            pixmap.fill(Qt.GlobalColor.transparent)

            # 渲染SVG到像素图
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()

            self.arrow_label.setPixmap(pixmap)
        else:
            # 如果SVG文件不存在，使用文本箭头作为后备
            self.arrow_label.setText("▼")
            self.arrow_label.setStyleSheet("""
                QLabel {
                    color: #6c757d;
                    font-size: 12px;
                    background: transparent;
                    border: none;
                }
            """)

    def mousePressEvent(self, event):
        """处理鼠标点击事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def set_text(self, text):
        """设置显示文字"""
        self.text = text
        self.text_label.setText(text)
