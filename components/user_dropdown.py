import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget


class UserDropdown(QWidget):
    clicked = pyqtSignal()
    clear_selection = pyqtSignal()

    def __init__(self, text="User", parent=None):
        super().__init__(parent)
        self.text = text
        self.selected_item = None
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
        layout.setSpacing(2)

        # 左侧文字标签
        self.text_label = QLabel(self.text)
        self.text_label.setStyleSheet("""
            QLabel {
                color: #495057;
                font-size: 13px;
                font-weight: 500;
                background: transparent;
                border: none;
            }
        """)
        layout.addWidget(self.text_label)

        # 选中项标签（初始隐藏）
        self.selected_label = QLabel()
        self.selected_label.setStyleSheet("""
            QLabel {
                color: #007bff;
                font-size: 13px;
                font-weight: 500;
                background: transparent;
                border: none;
                margin-left: 8px;
            }
        """)
        self.selected_label.hide()
        layout.addWidget(self.selected_label)

        # X 按钮（初始隐藏）
        self.clear_button = QLabel()
        self.clear_button.setText("×")
        self.clear_button.setStyleSheet("""
            QLabel {
                color: #6c757d;
                font-size: 16px;
                font-weight: bold;
                background: transparent;
                border: none;
                padding: 0 4px;
                margin-left: 4px;
            }
            QLabel:hover {
                color: #dc3545;
                cursor: pointer;
            }
        """)
        self.clear_button.hide()
        self.clear_button.mousePressEvent = self._on_clear_clicked
        layout.addWidget(self.clear_button)

        # 右侧箭头图标
        self.arrow_label = QLabel()
        self.load_arrow_icon()
        layout.addWidget(self.arrow_label)

    def load_arrow_icon(self):
        """加载 SVG 箭头图标"""
        svg_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "icons", "chevron-down.svg")

        if os.path.exists(svg_path):
            # 使用 QSvgRenderer 渲染 SVG
            renderer = QSvgRenderer(svg_path)

            # 创建一个 16x16 的像素图
            pixmap = QPixmap(16, 16)
            pixmap.fill(Qt.GlobalColor.transparent)

            # 渲染 SVG 到像素图
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()

            self.arrow_label.setPixmap(pixmap)
        else:
            # 如果 SVG 文件不存在，使用文本箭头作为后备
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

    def set_selected_item(self, item_text):
        """设置选中项"""
        self.selected_item = item_text
        if item_text:
            self.selected_label.setText(item_text)
            self.selected_label.show()
            self.clear_button.show()
        else:
            self.selected_label.hide()
            self.clear_button.hide()

    def clear_selected_item(self):
        """清除选中项"""
        self.selected_item = None
        self.selected_label.hide()
        self.clear_button.hide()

    def _on_clear_clicked(self, event):
        """处理清除按钮点击事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clear_selected_item()
            self.clear_selection.emit()
        # 阻止事件传播，避免触发组件的 clicked 信号
        event.accept()
