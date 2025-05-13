from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QLabel, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget


class FileHistoryView(QWidget):
    commit_selected = pyqtSignal(str)  # 当选择提交时发出信号

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

    def update_history(self, git_manager):
        """更新文件提交历史"""
        self.history_list.clear()
        # TODO: 实现 git_manager.get_file_commit_history(self.file_path)
        commits = git_manager.get_file_commit_history(self.file_path)
        for commit in commits:
            item = QTreeWidgetItem(self.history_list)
            item.setText(0, commit["hash"][:7])
            item.setText(1, commit["message"])
            item.setText(2, commit["author"])
            item.setText(3, commit["date"])

    def on_commit_clicked(self, item):
        """当点击提交时发出信号"""
        commit_hash = item.text(0)
        self.commit_selected.emit(commit_hash)
