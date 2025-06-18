import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout


class FileQuickSearchPopup(QFrame):
    """cursor 生成 - 悬浮文件快速搜索下拉框组件"""

    file_selected = pyqtSignal(str)  # 选中文件信号，参数为文件路径

    def __init__(self, parent=None, file_list=None):
        super().__init__(parent, Qt.WindowType.Popup)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)
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
        self.max_default_files = 20  # 默认最多显示20个

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
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self.list_widget)

        self.refresh_list()

    def set_file_list(self, file_list):
        self.file_list = file_list or []
        self.filtered_files = self.file_list[: self.max_default_files]
        self.refresh_list()

    def on_text_changed(self, text):
        text = text.strip().lower()
        if not text:
            self.filtered_files = self.file_list[: self.max_default_files]
        else:
            self.filtered_files = [f for f in self.file_list if text in f.lower()]
        self.refresh_list()

    def refresh_list(self):
        self.list_widget.clear()

        # 步骤 1: 统计 basename 出现频率
        basename_counts = {}
        for f_path in self.filtered_files:
            basename = os.path.basename(f_path)
            basename_counts[basename] = basename_counts.get(basename, 0) + 1

        for f in self.filtered_files:
            base = os.path.basename(f)
            display_name = base

            # 步骤 2: 判断是否需要添加父文件夹信息
            if basename_counts.get(base, 0) > 1:
                parent_dir = os.path.basename(os.path.dirname(f))
                if parent_dir:  # 避免根目录没有父文件夹
                    display_name = f"{parent_dir}/{base}"

            # 截断长文件名 (原有逻辑可复用或调整)
            if len(display_name) > 32:
                display_name = display_name[:15] + "..." + display_name[-12:]

            item = QListWidgetItem(display_name)
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

    def show_popup(self, pos=None, ref_widget=None):
        self.input.clear()
        self.input.setFocus()
        self.refresh_list()
        # 如果有参考控件，则宽度与其一致或略宽，且顶部对齐
        if ref_widget:
            ref_geom = ref_widget.geometry()
            global_pos = ref_widget.mapToGlobal(ref_geom.topLeft())
            self.setFixedWidth(ref_geom.width() + 40)
            self.move(global_pos.x() - 40, global_pos.y() - 10)
        elif pos:
            self.setFixedWidth(360)
            self.move(pos)
        self.show()
