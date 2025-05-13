from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QLabel, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget


class FileHistoryView(QWidget):
    def __init__(self, file_path, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        self.setLayout(layout)

        self.history_label = QLabel(f"文件历史: {self.file_path}")
        layout.addWidget(self.history_label)

        self.history_list = QTreeWidget()
        self.history_list.setHeaderLabels(["提交ID", "提交信息", "作者", "日期"])
        self.history_list.itemClicked.connect(self.on_commit_clicked)
        self.history_list.setColumnWidth(0, 80)  # Hash
        self.history_list.setColumnWidth(1, 200)  # Message
        self.history_list.setColumnWidth(2, 100)  # Author
        self.history_list.setColumnWidth(3, 150)  # Date
        layout.addWidget(self.history_list)
