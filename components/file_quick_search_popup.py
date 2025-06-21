import os

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QFrame, QLabel, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout

from utils import get_main_window_by_parent


class FileQuickSearchPopup(QFrame):
    """cursor 生成 - 悬浮文件快速搜索下拉框组件"""

    file_selected = pyqtSignal(str)  # 选中文件信号，参数为文件路径

    def __init__(self, parent=None, file_list=None):
        super().__init__(parent, Qt.WindowType.Popup)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumWidth(280)
        # qlabel 不要边框
        self.setStyleSheet("""
            QFrame { background: #fff; border: 1px solid #aaa; }
            QLineEdit { border: none; background: #f5f5f5; padding: 4px; border-radius: 4px; }
            QListWidget { border: none; background: transparent; }
            QListWidget::item:selected { background: #e6f0fa; }
            QLabel { border: none; }
        """)
        self.file_list = file_list or []
        self.filtered_files = self.file_list.copy()
        self.max_default_files = 20  # 默认最多显示20个

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        self.input = QLineEdit(self)
        self.input.setPlaceholderText("输入文件名搜索…")
        
        # 添加搜索延时计时器
        self.search_timer = QTimer(self)
        self.search_timer.setInterval(500)  # 设置延时为 500 毫秒
        self.search_timer.setSingleShot(True)  # 设置为单次触发
        self.search_timer.timeout.connect(self.perform_search)
        
        self.input.textChanged.connect(self.on_text_changed)
        self.input.returnPressed.connect(self.on_return_pressed)
        layout.addWidget(self.input)

        self.list_widget = QListWidget(self)
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self.list_widget)

    def set_file_list(self, file_list):
        self.file_list = file_list or []
        self.filtered_files = self.file_list[: self.max_default_files]
        self.refresh_list()

    def on_text_changed(self, text):
        # 停止之前的计时器
        self.search_timer.stop()
        # 保存搜索文本
        self.search_text = text
        # 启动计时器
        self.search_timer.start()
        
    def perform_search(self):
        text = self.search_text.strip().lower()
        if not text:
            self.filtered_files = self.file_list[: self.max_default_files]
        else:
            main_window = get_main_window_by_parent(self)
            git_repo_path = main_window.git_manager.repo.working_dir
            self.filtered_files = [f for f in self.file_list if text in os.path.relpath(f, git_repo_path).lower()]
        self.refresh_list()

    def refresh_list(self):
        self.list_widget.clear()

        for f in self.filtered_files:
            base = os.path.basename(f)
            display_name = base

            # 获取git 仓库路径
            main_window = get_main_window_by_parent(self)
            git_repo_path = main_window.git_manager.repo.working_dir

            # 获取 f 的文件夹
            folder_path = os.path.dirname(f)

            # 获取 f的文件夹 相对于仓库的路径
            relative_path = os.path.relpath(folder_path, git_repo_path)
            label = None
            if relative_path and relative_path != ".":
                # 14px font color black + 11px color gray
                label = QLabel(
                    f"""<span style='font-size: 14px; color: black;'>{base}</span>
                    <span style='font-size: 11px; color: gray;'>{relative_path}</span>"""
                )
                label.setTextFormat(Qt.TextFormat.RichText)  # **非常重要：设置文本格式为富文本**

            # todo 后面再说吧
            # 截断长文件名 (原有逻辑可复用或调整)
            # if len(display_name) > 100:
            #     display_name = display_name[:50] + "..." + display_name[-12:]

            item = QListWidgetItem(display_name)

            item.setToolTip(f)
            _font = item.font()
            _font.setPointSize(14)
            item.setFont(_font)
            item.setData(Qt.ItemDataRole.UserRole, f)
            self.list_widget.addItem(item)
            if label:
                item.setSizeHint(label.sizeHint())  # 调整项目高度以适应 Label
                self.list_widget.setItemWidget(item, label)  # 把 Label 设置为项目的控件

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
