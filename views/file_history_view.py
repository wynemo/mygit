import logging
import os
from datetime import datetime
from functools import partial
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QApplication, QLabel, QMenu, QTreeWidgetItem, QVBoxLayout, QWidget

from components.hover_reveal_tree_widget import HoverRevealTreeWidget
from utils import get_main_window

if TYPE_CHECKING:
    import git


class FileHistoryView(QWidget):
    compare_with_working_requested = pyqtSignal(str, str, str)  # 新增信号

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

        self.history_list = HoverRevealTreeWidget()
        self.history_list.set_hover_reveal_columns({1})
        self.history_list.setHeaderLabels(["提交信息", "作者", "日期"])
        self.history_list.itemClicked.connect(self.on_commit_clicked)
        self.history_list.setColumnWidth(0, 200)  # Message
        self.history_list.setColumnWidth(1, 100)  # Author
        self.history_list.setColumnWidth(2, 150)  # Date
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

            # 一次性获取所有需要的信息，避免后续查询
            log_output = self.git_manager.repo.git.log(
                "--follow",
                "--name-status",
                "--pretty=format:%H|%an|%ct|%s",  # hash|author|timestamp|subject
                relative_path,
            )

            if not log_output.strip():
                logging.info("No commits found for file %s", relative_path)
                return

            # 直接解析并添加到界面，不创建 commit 对象
            for line in log_output.strip().split("\n"):
                if not line.strip():
                    continue

                logging.debug("line is %s", line)
                parts = line.split("|", 3)

                # 建议在 file_history_view.py 的 update_history 方法中添加以下代码来解析文件变更状态：

                _file_path = None
                if len(parts) < 4:
                    # 处理重命名格式：R100    oldfile    newfile
                    if line.startswith("R") or line.startswith("C"):
                        parts = line.split("\t")
                        if len(parts) >= 3:
                            print(f"文件重命名/复制：{parts[1]} -> {parts[2]}")
                            _file_path = parts[2]
                    else:
                        # 处理普通变更格式：A/M/D    filename
                        parts = line.split("\t")
                        if len(parts) >= 2:
                            status_map = {"A": "新增", "M": "修改", "D": "删除"}
                            print(f"文件{status_map.get(line[0], line[0])}: {parts[1]}")
                            _file_path = parts[1]
                    self.history_list.topLevelItem(self.history_list.topLevelItemCount() - 1).setData(
                        2, 256, _file_path
                    )
                    continue

                commit_hash, author_name, timestamp_str, message = parts

                item = QTreeWidgetItem()
                # 提交信息
                item.setText(0, message)
                # 作者
                item.setText(1, author_name)
                # 日期
                try:
                    commit_date = datetime.fromtimestamp(int(timestamp_str))
                    item.setText(2, commit_date.strftime("%Y-%m-%d %H:%M:%S"))
                except (ValueError, OSError):
                    item.setText(2, "Invalid Date")

                # 存储完整哈希值用于后续操作（存储在第0列的data中）
                item.setData(0, 256, commit_hash)

                self.history_list.addTopLevelItem(item)
                # logging.debug(f"Added commit {commit.hexsha[:7]} to history list for file {relative_path}")
        except Exception as e:
            item = QTreeWidgetItem()
            item.setText(0, f"获取历史失败：{e!s}")
            logging.exception("获取文件历史失败")
            self.history_list.addTopLevelItem(item)

    def on_commit_clicked(self, item):
        """当用户点击提交记录时触发"""
        # 需要改为在右侧显示文件变化
        # 根据拿到的文件路径 commit 信息 这个 GitManagerWindow.compare_view 需要对改动进行显示
        commit_hash = item.data(0, 256)  # Qt.ItemDataRole.UserRole = 256
        file_path = item.data(2, 256)
        if commit_hash:
            # 尝试在主窗口的标签页中打开比较视图
            main_window = self.window()
            if hasattr(main_window, "compare_view"):
                current_commit: git.Commit = main_window.git_manager.repo.commit(commit_hash)
                main_window.compare_view.show_diff(main_window.git_manager, current_commit, file_path)
                # 切换到统一视图
                if main_window.compare_view.stacked_widget.currentIndex() == 0:
                    main_window.compare_view.toggle_view_mode()

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
        print("relative_path", relative_path, item.data(3, 256))
        compare_action.triggered.connect(
            lambda: self.compare_with_working_requested.emit(relative_path, item.data(0, 256)[:7], item.data(2, 256))
        )
        menu.addAction(compare_action)

        # 添加 "显示所有受影响的文件" 菜单项
        show_all_affected_files_action = menu.addAction("显示所有受影响的文件")
        show_all_affected_files_action.triggered.connect(partial(self.show_all_affected_files, item))

        menu.exec(self.mapToGlobal(position))

    def copy_commit_to_clipboard(self, item):
        if item:
            commit_hash = item.data(0, 256)
            print("commit is", commit_hash)
            QApplication.clipboard().setText(commit_hash)
        else:
            print("item is None")

    def show_all_affected_files(self, item):
        """显示所有受影响的文件"""
        if not item:
            logging.warning("file history view item is None")
            return

        commit_hash = item.data(0, 256)
        if not commit_hash:
            logging.warning("commit hash is None")
            return

        try:
            # 获取 git.Commit 对象
            commit: git.Commit = self.git_manager.repo.commit(commit_hash)

            # 获取 WorkspaceExplorer 窗口
            main_window = self.window()
            if not hasattr(main_window, "workspace_explorer"):
                logging.error("WorkspaceExplorer not found")
                return

            workspace_explorer = main_window.workspace_explorer

            # 获取 FileChangesView
            if not hasattr(workspace_explorer, "file_changes_view"):
                logging.error("FileChangesView not found")
                return

            file_changes_view = workspace_explorer.file_changes_view

            # 调用 update_changes 方法
            file_changes_view.update_changes(self.git_manager, commit)

            # 触发 SideBarWidget.changes_btn 点击
            main_window = get_main_window()
            if hasattr(main_window, "side_bar"):
                try:
                    main_window.side_bar.changes_btn.click()
                except Exception as e:
                    logging.warning("触发 changes_btn 点击失败：%s", e)

        except Exception as e:
            logging.exception("显示所有受影响的文件失败")
            print(f"显示所有受影响的文件失败：{e!s}")

    def copy_commmit_message_to_clipboard(self, item):
        if item:
            print("commit message is", item.text(0))
            QApplication.clipboard().setText(item.text(0))
        else:
            print("item is None")
