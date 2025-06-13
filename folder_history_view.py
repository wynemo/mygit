import logging
from datetime import datetime
from functools import partial
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QLabel, QMenu, QTreeWidgetItem, QVBoxLayout, QWidget

from hover_reveal_tree_widget import HoverRevealTreeWidget
from utils import get_main_window_by_parent

if TYPE_CHECKING:
    pass


class FolderHistoryView(QWidget):  # Renamed class
    # compare_with_working_requested = pyqtSignal(str, str, str) # Commented out as it's file-specific

    def __init__(self, folder_path, parent=None):  # Changed file_path to folder_path
        super().__init__(parent)
        self.folder_path = folder_path  # Changed file_path to folder_path
        self.git_manager = None
        self.setup_ui()

        # 尝试从父窗口获取 git_manager
        main_window = get_main_window_by_parent(self)
        # print("FolderHistoryView main_window", id(main_window), main_window) # Adjusted print statement

        # print(f"has git manager: {hasattr(main_window, 'git_manager')}")
        if hasattr(main_window, "git_manager") and main_window.git_manager:
            # print("获取到 git_manager")
            self.git_manager = main_window.git_manager
            self.update_history()

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        self.setLayout(layout)

        self.history_label = QLabel(f"文件夹历史：{self.folder_path}")  # Updated label text
        layout.addWidget(self.history_label)

        self.history_list = HoverRevealTreeWidget()
        self.history_list.set_hover_reveal_columns({1})
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
        """更新文件夹的提交历史"""  # Updated docstring
        if not self.git_manager:
            return

        self.history_list.clear()
        try:
            # relative_path = os.path.relpath(self.folder_path, self.git_manager.repo.working_dir)
            # logging.info(f"Fetching history for folder: {relative_path}")

            # Assume get_folder_commit_history returns a list of dicts:
            # [{'hash': '...', 'message': '...', 'author': '...', 'date': datetime_obj}, ...]
            # This method needs to be implemented in git_manager.py
            commits = self.git_manager.get_folder_commit_history(self.folder_path)
            print("commits", commits)

            if not commits:
                item = QTreeWidgetItem()
                item.setText(0, "此文件夹没有提交历史。")
                self.history_list.addTopLevelItem(item)
                logging.info("No commit history found for folder %s", self.folder_path)
                return

            for commit_data in commits:
                item = QTreeWidgetItem()
                # 提交 ID, 短哈希
                item.setText(0, commit_data.get("hash", "")[:7])
                # 提交信息
                item.setText(1, commit_data.get("message", "无提交信息"))
                # 作者
                item.setText(2, commit_data.get("author", "未知作者"))
                # 日期
                commit_date = commit_data.get("date")
                if isinstance(commit_date, datetime):
                    item.setText(3, commit_date.strftime("%Y-%m-%d %H:%M:%S"))
                elif isinstance(commit_date, str):  # If date is already string formatted
                    item.setText(3, commit_date)
                else:
                    item.setText(3, "无效日期")

                # 存储完整哈希值用于后续操作
                item.setData(0, Qt.ItemDataRole.UserRole, commit_data.get("hash"))  # UserRole is more standard
                self.history_list.addTopLevelItem(item)

            # Ensure headers are correct, this might be redundant if set in setup_ui but good for clarity
            self.history_list.setHeaderLabels(["提交 ID", "提交信息", "作者", "日期"])

        except AttributeError:
            # This might happen if git_manager or repo is None, or get_folder_commit_history is not yet implemented
            logging.exception("Git manager or method not available")
            item = QTreeWidgetItem()
            item.setText(0, "无法加载历史：Git仓库或方法未初始化。")
            self.history_list.addTopLevelItem(item)
        except Exception as e:  # Catch other potential exceptions from git_manager
            item = QTreeWidgetItem()
            item.setText(0, f"无法加载历史：{e!s}")
            logging.exception("获取文件夹历史失败")
            self.history_list.addTopLevelItem(item)

    def on_commit_clicked(self, item: QTreeWidgetItem):
        """当用户点击提交记录时触发"""
        commit_hash = item.data(0, Qt.ItemDataRole.UserRole)  # Retrieve full hash
        if commit_hash:
            logging.info(f"提交记录被点击: Commit {commit_hash}, 文件夹: {self.folder_path}")
            get_main_window_by_parent(self).on_commit_selected(commit_hash)
        else:
            logging.warning("无法获取点击的提交记录哈希值。")

    def show_context_menu(self, position):
        # 将位置转换为视口坐标
        viewport_pos = self.history_list.viewport().mapFrom(self, position)
        item = self.history_list.itemAt(viewport_pos)

        if not item:
            logging.warning(
                "folder history view item is None at position %s (viewport: %s)", position, viewport_pos
            )  # Updated log
            return
        menu = QMenu(self)
        copy_commit_action = menu.addAction("复制提交ID")  # Changed to Chinese
        copy_commit_action.triggered.connect(partial(self.copy_commit_to_clipboard, item))
        copy_commit_message_action = menu.addAction("复制提交信息")  # Changed to Chinese
        copy_commit_message_action.triggered.connect(partial(self.copy_commmit_message_to_clipboard, item))

        # "与工作区比较" 菜单项可能不直接适用于文件夹，或者需要不同实现
        # Commenting out for now
        """
        compare_action = menu.addAction("与工作区比较")
        repo_path = self.git_manager.repo.working_dir
        relative_path = os.path.relpath(self.folder_path, repo_path) # Changed file_path to folder_path
        # print("relative_path", relative_path, item.data(3, 256)) # item.data(3,256) was file specific
        # compare_action.triggered.connect(
        #     lambda: self.compare_with_working_requested.emit(relative_path, item.text(0), item.data(3, 256))
        # )
        # menu.addAction(compare_action)
        """

        menu.exec(self.mapToGlobal(position))

    def copy_commit_to_clipboard(self, item):
        if item:
            # print("commit is", item.text(0))
            QApplication.clipboard().setText(item.text(0))
        else:
            logging.warning("No item selected to copy commit ID")  # Changed print to logging

    def copy_commmit_message_to_clipboard(self, item):
        if item:
            commit_message = item.text(1)  # Column 1 is "提交信息"
            QApplication.clipboard().setText(commit_message)
            logging.info("提交信息已复制到剪贴板: %s...", commit_message[:30])
        else:
            logging.warning("未选择任何提交项，无法复制提交信息。")  # Changed print to logging, in Chinese
