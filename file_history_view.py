import logging
import os
from datetime import datetime
from functools import partial

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QApplication, QLabel, QMenu, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget


class FileHistoryView(QWidget):
    compare_with_working_requested = pyqtSignal(str, str)  # 新增信号

    def __init__(self, file_path, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.git_manager = None
        self.setup_ui()

        # 尝试从父窗口获取 git_manager
        main_window = self.window()
        print("FileHistoryView main_window", id(main_window), main_window)

        print(f"has git manager: {hasattr(main_window, 'git_manager')}")
        if hasattr(main_window, "git_manager") and main_window.git_manager:
            print("获取到 git_manager")
            self.git_manager = main_window.git_manager
            self.update_history()

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        self.setLayout(layout)

        self.history_label = QLabel(f"文件历史：{self.file_path}")
        layout.addWidget(self.history_label)

        self.history_list = QTreeWidget()
        self.history_list.setHeaderLabels(["提交 ID", "提交信息", "作者", "日期"])
        self.history_list.itemClicked.connect(self.on_commit_clicked)
        self.history_list.setColumnWidth(0, 80)  # Hash
        self.history_list.setColumnWidth(1, 200)  # Message
        self.history_list.setColumnWidth(2, 100)  # Author
        self.history_list.setColumnWidth(3, 150)  # Date
        layout.addWidget(self.history_list)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def update_history(self):
        """更新文件的提交历史"""
        if not self.git_manager:
            return

        self.history_list.clear()
        try:
            # 获取相对于 git 仓库根目录的文件路径
            repo_path = self.git_manager.repo.working_dir
            relative_path = os.path.relpath(self.file_path, repo_path)

            # 使用 git log 命令获取文件的提交历史
            commits = []
            for commit in self.git_manager.repo.iter_commits(paths=relative_path):
                commits.append(commit)

            # 添加到历史列表
            for commit in commits:
                item = QTreeWidgetItem()
                # 提交 ID, 短哈希
                item.setText(0, commit.hexsha[:7])
                # 提交信息
                item.setText(1, commit.summary)
                # 作者
                item.setText(2, commit.author.name)
                # 日期
                commit_date = datetime.fromtimestamp(commit.committed_date)
                item.setText(3, commit_date.strftime("%Y-%m-%d %H:%M:%S"))
                # 存储完整哈希值用于后续操作
                item.setData(0, 256, commit.hexsha)  # Qt.ItemDataRole.UserRole = 256

                self.history_list.addTopLevelItem(item)
                logging.debug(f"Added commit {commit.hexsha[:7]} to history list for file {relative_path}")
        except Exception as e:
            item = QTreeWidgetItem()
            item.setText(0, f"获取历史失败：{e!s}")
            self.history_list.addTopLevelItem(item)

    def on_commit_clicked(self, item):
        """当用户点击提交记录时触发"""
        # 需要改为在右侧显示文件变化
        # 根据拿到的文件路径 commit 信息 这个 GitManagerWindow.compare_view 需要对改动进行显示
        commit_hash = item.data(0, 256)  # Qt.ItemDataRole.UserRole = 256
        if commit_hash:
            # 尝试在主窗口的标签页中打开比较视图
            main_window = self.window()
            if hasattr(main_window, "compare_view"):
                # 获取相对于 git 仓库根目录的文件路径
                repo_path = self.git_manager.repo.working_dir
                relative_path = os.path.relpath(self.file_path, repo_path)

                current_commit = main_window.git_manager.repo.commit(commit_hash)
                main_window.compare_view.show_diff(main_window.git_manager, current_commit, relative_path)

    def show_context_menu(self, position):
        # 将位置转换为视口坐标
        viewport_pos = self.history_list.viewport().mapFrom(self, position)
        item = self.history_list.itemAt(viewport_pos)

        if not item:
            logging.warning("file history view item is None at position %s (viewport: %s)", position, viewport_pos)
            return
        menu = QMenu(self)
        copy_commit_action = menu.addAction("copy commit")
        copy_commit_action.triggered.connect(partial(self.copy_commit_to_clipboard, item))
        copy_commit_message_action = menu.addAction("copy commit message")
        copy_commit_message_action.triggered.connect(partial(self.copy_commmit_message_to_clipboard, item))
        # 添加"与工作区比较"菜单项
        compare_action = menu.addAction("与工作区比较")
        repo_path = self.git_manager.repo.working_dir
        relative_path = os.path.relpath(self.file_path, repo_path)
        compare_action.triggered.connect(lambda: self.compare_with_working_requested.emit(relative_path, item.text(0)))
        menu.addAction(compare_action)
        menu.exec(self.mapToGlobal(position))

    def copy_commit_to_clipboard(self, item):
        if item:
            print("commit is", item.text(0))
            QApplication.clipboard().setText(item.text(0))
        else:
            print("item is None")

    def copy_commmit_message_to_clipboard(self, item):
        if item:
            print("commit is", item.text(0))
            QApplication.clipboard().setText(item.text(1))
        else:
            print("item is None")
