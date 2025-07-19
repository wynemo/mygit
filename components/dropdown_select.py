"""
下拉选择框组件
提供简单的单选下拉功能
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QComboBox, QWidget


class DropdownSelect(QComboBox):
    """简单的下拉选择框组件"""

    selectionChanged = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.connect_signals()

    def setup_ui(self):
        """设置 UI 样式"""
        self.setStyleSheet("""
            QComboBox {
                background-color: white;
                color: #444444;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 8px 12px;
                min-width: 120px;
                font-size: 14px;
            }
            QComboBox:hover {
                border: 1px solid #2196F3;
                background-color: #f8f8f8;
            }
            QComboBox:focus {
                border: 1px solid #2196F3;
                outline: none;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: url(icons/arrow_down.svg);
                width: 12px;
                height: 12px;
                margin-right: 8px;
            }
            QComboBox::down-arrow:hover {
                border-top: 4px solid #2196F3;
            }
            QComboBox QAbstractItemView {
                background-color: white;
                color: #444444;
                border: 1px solid #ccc;
                border-radius: 4px;
                outline: none;
                padding: 4px;
                selection-background-color: #2196F3;
            }
            QComboBox QAbstractItemView::item {
                padding: 8px 12px;
                border: none;
                border-radius: 2px;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #2196F3;
                color: white;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #e3f2fd;
            }
        """)

        # 设置默认文本
        self.addItem("Select...")
        self.setCurrentIndex(0)

    def connect_signals(self):
        """连接信号"""
        self.currentTextChanged.connect(self.on_selection_changed)

    def on_selection_changed(self, text):
        """处理选择变化"""
        if text != "Select...":
            self.selectionChanged.emit(text)

    def add_option(self, text):
        """添加选项"""
        if text not in [self.itemText(i) for i in range(self.count())]:
            self.addItem(text)

    def set_options(self, options):
        """设置选项列表"""
        self.clear()
        self.addItem("Select...")
        for option in options:
            self.addItem(option)
        self.setCurrentIndex(0)

    def get_selected_value(self):
        """获取选中的值"""
        current_text = self.currentText()
        return current_text if current_text != "Select..." else None

    def set_selected_value(self, value):
        """设置选中值"""
        index = self.findText(value)
        if index >= 0:
            self.setCurrentIndex(index)
