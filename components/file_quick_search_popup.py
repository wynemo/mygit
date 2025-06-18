import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout


class FileQuickSearchPopup(QFrame):
    """cursor 生成 - 悬浮文件快速搜索下拉框组件"""

    file_selected = pyqtSignal(str)  # 选中文件信号，参数为文件路径

    def __init__(self, parent=None, file_list=None):
        super().__init__(parent, Qt.WindowType.Popup)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumWidth(280)
        self.setStyleSheet("""
            QFrame { background: #fff; border: 1px solid #aaa; border-radius: 8px; }
            QLineEdit { border: none; background: #f5f5f5; padding: 4px; border-radius: 4px; }
            QListWidget { border: none; background: transparent; }
            QListWidget::item { padding: 4px 8px; }
            QListWidget::item:selected { background: #e6f0fa; }
        """)
        self.file_list = file_list or []
        self.filtered_files = self.file_list.copy()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        self.input = QLineEdit(self)
        self.input.setPlaceholderText("输入文件名搜索…")
        self.input.textChanged.connect(self.on_text_changed)
        self.input.returnPressed.connect(self.on_return_pressed)
        layout.addWidget(self.input)

        self.list_widget = QListWidget(self)
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        layout.addWidget(self.list_widget)

        self.refresh_list()

    def set_file_list(self, file_list):
        self.file_list = file_list or []
        self.filtered_files = self.file_list.copy()
        self.refresh_list()

    def on_text_changed(self, text):
        text = text.strip().lower()
        if not text:
            self.filtered_files = self.file_list.copy()
        else:
            self.filtered_files = [f for f in self.file_list if text in os.path.basename(f).lower()]
        self.refresh_list()

    def refresh_list(self):
        self.list_widget.clear()
        for f in self.filtered_files:
            item = QListWidgetItem(os.path.basename(f))
            item.setToolTip(f)
            item.setData(Qt.ItemDataRole.UserRole, f)
            self.list_widget.addItem(item)
        if self.filtered_files:
            self.list_widget.setCurrentRow(0)

    def on_item_clicked(self, item):
        file_path = item.data(Qt.ItemDataRole.UserRole)
        self.file_selected.emit(file_path)
        self.hide()

    def on_return_pressed(self):
        item = self.list_widget.currentItem()
        if item:
            self.on_item_clicked(item)

    def focusOutEvent(self, event):
        self.hide()
        super().focusOutEvent(event)

    def show_popup(self, pos=None):
        self.input.clear()
        self.input.setFocus()
        self.refresh_list()
        if pos:
            self.move(pos)
        self.show()
