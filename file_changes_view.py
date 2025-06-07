from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QLabel,
    QMenu,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


class FileChangesView(QWidget):
    file_selected = pyqtSignal(str, str)  # 当选择文件时发出信号
    compare_with_working_requested = pyqtSignal(str)  # 请求与工作区比较

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.commit_hash = None

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        self.setLayout(layout)

        self.changes_label = QLabel("文件变化：")
        layout.addWidget(self.changes_label)

        self.changes_tree = QTreeWidget()
        self.changes_tree.setHeaderLabels(["文件", "状态"])
        self.changes_tree.setColumnCount(2)
        self.changes_tree.itemClicked.connect(self.on_file_clicked)
        self.changes_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.changes_tree.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.changes_tree)

    def update_changes(self, git_manager, commit):
        """更新文件变化列表"""
        self.changes_tree.clear()
        self.commit_hash = commit.hexsha

        try:
            parent = commit.parents[0] if commit.parents else None

            if parent:
                diff = parent.diff(commit)
                for change in diff:
                    path_parts = change.b_path.split("/") if change.change_type == "R" else change.a_path.split("/")
                    self.add_file_to_tree(path_parts, change.change_type, old_path=change.a_path)
            else:
                for item in commit.tree.traverse():
                    if item.type == "blob":
                        path_parts = item.path.split("/")
                        self.add_file_to_tree(path_parts, "新增")

            self.changes_tree.expandAll()
            self.changes_tree.resizeColumnToContents(0)
            self.changes_tree.resizeColumnToContents(1)

        except Exception as e:
            error_item = QTreeWidgetItem(self.changes_tree)
            error_item.setText(0, f"获取文件变化失败：{e!s}")

    def add_file_to_tree(self, path_parts, status, parent=None, old_path=None):
        """递归添加文件到树形结构"""
        if not path_parts:
            return

        current_part = path_parts[0]
        found_item = None

        if parent is None:
            root = self.changes_tree.invisibleRootItem()
            for i in range(root.childCount()):
                if root.child(i).text(0) == current_part:
                    found_item = root.child(i)
                    break
        else:
            for i in range(parent.childCount()):
                if parent.child(i).text(0) == current_part:
                    found_item = parent.child(i)
                    break

        if found_item is None:
            found_item = QTreeWidgetItem(self.changes_tree) if parent is None else QTreeWidgetItem(parent)
            found_item.setText(0, current_part)

            if len(path_parts) == 1:
                if status == "R":
                    found_item.setText(1, f"{old_path} -> {'/'.join(path_parts)}")
                else:
                    found_item.setText(1, status)

        if len(path_parts) > 1:
            self.add_file_to_tree(path_parts[1:], status, found_item, old_path)

    def get_full_path(self, item):
        """获取树形项的完整路径"""
        path_parts = []
        while item:
            path_parts.insert(0, item.text(0))
            item = item.parent()
        return "/".join(path_parts)

    def on_file_clicked(self, item):
        """当点击文件时发出信号"""
        if item and item.childCount() == 0:
            self.file_selected.emit(self.get_full_path(item), self.commit_hash)

    def show_context_menu(self, position):
        """显示右键菜单"""
        item = self.changes_tree.itemAt(position)
        if item and item.childCount() == 0:
            menu = QMenu()
            compare_action = QAction("与工作区比较", self)
            compare_action.triggered.connect(lambda: self.compare_with_working_requested.emit(self.get_full_path(item)))
            menu.addAction(compare_action)
            menu.exec(self.changes_tree.viewport().mapToGlobal(position))
