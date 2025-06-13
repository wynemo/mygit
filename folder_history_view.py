import logging
from datetime import datetime
from functools import partial
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QLabel, QMenu, QTreeWidgetItem, QVBoxLayout, QWidget

from hover_reveal_tree_widget import HoverRevealTreeWidget
from utils import get_main_window_by_parent

if TYPE_CHECKING:
    import git


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
            # TODO: 通知主窗口显示此提交的详细信息 (commit_hash)
            # Example: get_main_window().show_commit_details(commit_hash)

            # TODO: 通知主窗口显示此提交中在 folder_path 下的文件变更 (commit_hash, self.folder_path)
            # Example: get_main_window().show_changes_in_folder_for_commit(commit_hash, self.folder_path)
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

        # "显示所有受影响的文件" 菜单项在文件夹上下文中已经是默认行为，或者需要调整
        # For folder history, this action is implicitly what the main view might show for a commit.
        # Keeping it for now, but its role might change.
        show_all_affected_files_action = menu.addAction("显示此提交中受影响的文件")  # Changed to Chinese & clarified
        show_all_affected_files_action.triggered.connect(
            partial(self.show_all_affected_files_in_commit, item)
        )  # Renamed method

        menu.exec(self.mapToGlobal(position))

    def copy_commit_to_clipboard(self, item):
        if item:
            # print("commit is", item.text(0))
            QApplication.clipboard().setText(item.text(0))
        else:
            logging.warning("No item selected to copy commit ID")  # Changed print to logging

    def show_all_affected_files_in_commit(self, item):  # Renamed method
        """显示选定提交中，此文件夹内所有受影响的文件"""  # Updated docstring
        if not item:
            logging.warning("未选择任何提交项，无法显示受影响文件。")  # Updated log, in Chinese
            return

        commit_hash = item.data(0, Qt.ItemDataRole.UserRole)  # Retrieve full hash
        if not commit_hash:
            logging.warning("无法获取所选提交的哈希值。")  # Updated log, in Chinese
            return

        logging.info("右键菜单：显示提交 %s 中文件夹 %s 内受影响的文件。", commit_hash, self.folder_path)

        try:
            # 获取 git.Commit 对象 (assuming git_manager.repo.commit() is available)
            commit_object: git.Commit = self.git_manager.repo.commit(commit_hash)

            main_window = get_main_window_by_parent(self)  # Use utility to get main window reliably
            if not main_window:
                logging.error("无法获取主窗口实例。")
                return

            if not hasattr(main_window, "file_changes_view"):
                logging.error("FileChangesView 在主窗口中未找到。可能需要调整或等待其初始化。")
                return

            file_changes_view = main_window.file_changes_view

            # 调用 update_changes 方法，传递 commit 对象和 folder_path 作为过滤器
            # The FileChangesView.update_changes method will need to handle the path_filter argument
            file_changes_view.update_changes(self.git_manager, commit_object, path_filter=self.folder_path)

            # 切换到显示变更的视图 (e.g., a tab in a QTabWidget)
            if hasattr(main_window, "side_bar") and hasattr(main_window.side_bar, "changes_btn"):
                main_window.side_bar.changes_btn.click()  # Simulate click to switch to changes view
                logging.info("已切换到文件变更视图。")
            else:
                logging.warning("无法找到侧边栏变更按钮来自动切换视图。")

        except Exception:
            logging.exception(
                "显示提交 %s 中受影响的文件失败 (文件夹: %s)",
                commit_hash,
                self.folder_path,
            )
            # Optionally, show an error message to the user via a dialog or status bar

    def copy_commmit_message_to_clipboard(self, item):
        if item:
            commit_message = item.text(1)  # Column 1 is "提交信息"
            QApplication.clipboard().setText(commit_message)
            logging.info("提交信息已复制到剪贴板: %s...", commit_message[:30])
        else:
            logging.warning("未选择任何提交项，无法复制提交信息。")  # Changed print to logging, in Chinese
