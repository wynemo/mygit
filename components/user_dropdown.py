import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QPixmap, QCursor
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget, QVBoxLayout, QFrame

"""
  使用方法：
  # 设置选中项
  dropdown.set_selected_item("张三")

  # 清除选中项
  dropdown.clear_selected_item()

  # 监听清除信号
  dropdown.clear_selection.connect(your_handler)
"""


class DropdownPopup(QFrame):
    """下拉框弹出窗口"""
    item_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 创建主容器
        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #e9ecef;
                border-radius: 6px;
            }
        """)

        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # 添加 "Select..." 选项
        select_item = QLabel("Select...")
        select_item.setStyleSheet("""
            QLabel {
                color: #6c757d;
                font-size: 13px;
                padding: 8px 12px;
                background: transparent;
                border: none;
            }
            QLabel:hover {
                background-color: #f8f9fa;
            }
        """)
        select_item.setMinimumHeight(32)
        select_item.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        select_item.mousePressEvent = lambda _: self._on_item_clicked("Select...")
        container_layout.addWidget(select_item)

        # 添加示例用户项（可以根据需要动态添加）
        sample_users = ["me", "John Doe", "Jane Smith"]
        for user in sample_users:
            user_item = QLabel(user)
            user_item.setStyleSheet("""
                QLabel {
                    color: #495057;
                    font-size: 13px;
                    padding: 8px 12px;
                    background: transparent;
                    border: none;
                }
                QLabel:hover {
                    background-color: #f8f9fa;
                }
            """)
            user_item.setMinimumHeight(32)
            user_item.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            user_item.mousePressEvent = lambda _, u=user: self._on_item_clicked(u)
            container_layout.addWidget(user_item)

        layout.addWidget(container)

    def _on_item_clicked(self, item_text):
        """处理选项点击"""
        self.item_selected.emit(item_text)
        self.hide()

    def show_at_position(self, position):
        """在指定位置显示弹出框"""
        # 设置最小宽度，确保与下拉框宽度一致
        self.setMinimumWidth(150)
        self.move(position)
        self.show()


class UserDropdown(QWidget):
    clicked = pyqtSignal()
    clear_selection = pyqtSignal()

    def __init__(self, text="User", parent=None):
        super().__init__(parent)
        self.text = text
        self.selected_item = None
        self.dropdown_popup = None
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
            }
        """)
        self.clear_button.hide()
        self.clear_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
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
            self._show_dropdown()
            self.clicked.emit()
        super().mousePressEvent(event)

    def _show_dropdown(self):
        """显示下拉框"""
        if not self.dropdown_popup:
            self.dropdown_popup = DropdownPopup(self)
            self.dropdown_popup.item_selected.connect(self._on_item_selected)

        # 计算弹出框位置
        global_pos = self.mapToGlobal(self.rect().bottomLeft())
        self.dropdown_popup.show_at_position(global_pos)

    def _on_item_selected(self, item_text):
        """处理选项选择"""
        if item_text != "Select...":
            self.set_selected_item(item_text)

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
