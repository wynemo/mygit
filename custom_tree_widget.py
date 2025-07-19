import logging
from functools import partial

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QMenu,
)

from components.git_reset_dialog import GitResetDialog
from components.hover_reveal_tree_widget import HoverRevealTreeWidget
from git_manager import GitManager
from utils import get_main_window_by_parent


class CustomTreeWidget(HoverRevealTreeWidget):
    empty_scrolled_signal = pyqtSignal()  # cursor 生成
    resized = pyqtSignal()  # cursor 生成：新增 resized 信号

    def __init__(self, parent=None):
        super().__init__(parent)
        # cursor 生成：添加无数据提示标签
        self.no_data_label = QLabel("请尝试往下滚动加载更多数据", self.viewport())
        self.no_data_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_data_label.setStyleSheet("color: grey; font-size: 16px;")
        self.no_data_label.hide()

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

        # cursor 生成：连接 resized 信号
        self.resized.connect(self._reposition_no_data_label)
        self.viewport().installEventFilter(self)

    def eventFilter(self, source, event):
        """捕获 resize 事件并发送 resized 信号"""
        if source == self.viewport() and event.type() == QEvent.Type.Resize:
            self.resized.emit()
        return super().eventFilter(source, event)

    def _reposition_no_data_label(self):
        """重新定位无数据提示标签，使其居中"""
        if self.no_data_label.isVisible():
            self.no_data_label.setGeometry(self.viewport().rect())
            self.no_data_label.adjustSize()

    def show_no_data_message(self, message):
        """显示无数据/全部隐藏的提示信息"""
        self.no_data_label.setText(message)
        self.no_data_label.show()
        self._reposition_no_data_label()

    def hide_no_data_message(self):
        """隐藏无数据/全部隐藏的提示信息"""
        self.no_data_label.hide()

    def _merge_branch(self, git_manager, branch_name):
        """执行合并分支操作"""
        error = git_manager.merge_branch(branch_name)
        if error:
            get_main_window_by_parent(self).notification_widget.show_message(f"合并失败：{error}")
        else:
            self.parent().update_history(self.parent().git_manager, self.parent().branch)
            get_main_window_by_parent(self).notification_widget.show_message(f"成功合并分支：{branch_name}")

    def show_context_menu(self, position):
        item = self.itemAt(position)
        if not item:
            return

        menu = QMenu(self)

        # 添加原有的复制功能
        copy_commit_action = menu.addAction("copy commit")
        copy_commit_action.triggered.connect(partial(self.copy_commit_to_clipboard, item))
        copy_commit_message_action = menu.addAction("copy commit message")
        copy_commit_message_action.triggered.connect(partial(self.copy_commmit_message_to_clipboard, item))

        # 新增"与工作区比较"菜单项
        compare_action = menu.addAction("与工作区比较")
        compare_action.triggered.connect(partial(self._compare_commit_with_workspace, item))

        # 获取父窗口 (CommitHistoryView) 以访问 GitManager
        parent = self.parent()
        while parent and not hasattr(parent, "git_manager"):
            parent = parent.parent()

        if parent and hasattr(parent, "git_manager") and parent.git_manager:
            git_manager = parent.git_manager
            repo = git_manager.repo
            current_branch = repo.active_branch

            # 添加 "Reset current branch to here" 菜单项
            reset_action = menu.addAction("reset current branch to here")
            reset_action.triggered.connect(
                partial(self._reset_branch_to_commit, item, git_manager, current_branch.name)
            )

            # 从 item 获取分支信息 (假设分支信息在第 1 列)
            item_branches = item.text(1).split(", ")

            # 创建 Checkout 菜单，并为关联的每个分支添加入口
            checkout_menu = menu.addMenu("Checkout")
            checkout_action_added = False

            for branch_name_str in item_branches:
                branch_name_str = branch_name_str.strip()
                if not branch_name_str:
                    continue

                # 提取用于 checkout 的分支名
                # 对于 "☁️ origin/feature", 我们需要 "feature"。git checkout 会自动创建本地分支并跟踪远程分支。
                # 对于 "main", 我们需要 "main"。
                checkout_target_name = branch_name_str
                if checkout_target_name.startswith("☁️ origin/"):
                    checkout_target_name = checkout_target_name.strip("☁️").lstrip().split("/", 1)[1]

                if checkout_target_name == "HEAD":
                    continue
                # 仅当不是当前分支时才显示
                if checkout_target_name != current_branch.name:
                    action = checkout_menu.addAction(branch_name_str)
                    action.triggered.connect(partial(self._checkout_branch, git_manager, checkout_target_name))
                    checkout_action_added = True

            # 如果没有可切换的分支，则移除 "Checkout" 菜单
            if not checkout_action_added:
                menu.removeAction(checkout_menu.menuAction())

            # 检查是否是远程分支且当前分支跟踪它
            for branch_name in item_branches:
                if branch_name.startswith("☁️ origin/"):
                    _branch_name = branch_name.strip("☁️").lstrip()
                else:
                    _branch_name = branch_name
                if not _branch_name:
                    continue
                try:
                    if current_branch.commit.hexsha != repo.refs[_branch_name].commit.hexsha:
                        merge_action = menu.addAction(f"Merge {_branch_name}")
                        merge_action.triggered.connect(partial(self._merge_branch, git_manager, _branch_name))
                except Exception:
                    logging.exception("检查分支状态失败 item_branches: %s", item_branches)

        menu.exec(self.mapToGlobal(position))

    def _reset_branch_to_commit(self, item, git_manager: "GitManager", current_branch_name):
        if not item:
            return

        commit_hash = item.data(0, Qt.ItemDataRole.UserRole)
        commit_message = item.text(0)

        dialog = GitResetDialog(current_branch_name, commit_hash, commit_message, self)
        if dialog.exec():
            mode = dialog.get_selected_mode()
            # todo test it
            error = git_manager.reset_branch(commit_hash, mode)
            if error:
                get_main_window_by_parent(self).notification_widget.show_message(f"重置失败：{error}")
            else:
                self.parent().update_history(self.parent().git_manager, self.parent().branch)
                get_main_window_by_parent(self).notification_widget.show_message(
                    f"成功将分支 {current_branch_name} 重置到 {commit_hash[:7]}"
                )

    def copy_commit_to_clipboard(self, item):
        if item:
            full_hash = item.data(0, Qt.ItemDataRole.UserRole)
            if full_hash:
                print("commit is", full_hash)
                QApplication.clipboard().setText(full_hash)
            else:
                print("no hash data found")
        else:
            print("item is None")

    def copy_commmit_message_to_clipboard(self, item):
        if item:
            print("commit message is", item.text(0))
            QApplication.clipboard().setText(item.text(0))
        else:
            print("item is None")

    def _checkout_branch(self, git_manager, branch_name):
        """执行分支切换操作"""
        main_window = get_main_window_by_parent(self)
        if not main_window:
            logging.error("无法获取主窗口实例，无法显示通知。")
            # Fallback to print if main_window is not found
            error = git_manager.switch_branch(branch_name)
            if error:
                print(f"切换分支失败：{error}")
            else:
                print(f"已切换到分支：{branch_name}")
            return

        error = git_manager.switch_branch(branch_name)
        if error:
            main_window.notification_widget.show_message(f"切换分支失败：{error}")
        else:
            main_window.notification_widget.show_message(f"已成功切换到分支：{branch_name}")
            # Potentially update UI elements if needed, e.g., branch display in main window
            if hasattr(main_window, "update_branches_on_top_bar"):
                main_window.update_branches_on_top_bar()
            if hasattr(main_window, "update_commit_history"):
                main_window.update_commit_history()
            if hasattr(main_window, "workspace_explorer") and hasattr(
                main_window.workspace_explorer, "refresh_file_tree"
            ):
                main_window.workspace_explorer.refresh_file_tree()

    def _compare_commit_with_workspace(self, item):
        """比较指定提交与工作区的差异，并将变更文件添加到 WorkspaceExplorer.file_tree 中"""
        if not item:
            print("未选中任何提交")
            return

        commit_hash = item.data(0, Qt.ItemDataRole.UserRole)  # 从 UserRole 数据获取完整 hash
        parent = self.parent()
        while parent and not hasattr(parent, "git_manager"):
            parent = parent.parent()

        if parent and hasattr(parent, "git_manager") and parent.git_manager:
            git_manager: "GitManager" = parent.git_manager
            changed_files = git_manager.compare_commit_with_workspace(commit_hash)
            workspace_explorer = get_main_window_by_parent(self).workspace_explorer
            if changed_files:
                # 获取 WorkspaceExplorer 实例
                if workspace_explorer:
                    # 清空现有文件树
                    workspace_explorer.file_changes_view.changes_tree.clear()
                    # 添加变更文件到 file_changes_view
                    for file in changed_files:
                        workspace_explorer.file_changes_view.add_file_to_tree(
                            file.split("/"), "modified", is_comparing_with_workspace=True
                        )
                    workspace_explorer.file_changes_view.commit_hash = commit_hash
                    workspace_explorer.file_changes_view.other_commit_hash = git_manager.repo.head.commit.hexsha
                    print(f"已将变更文件添加到工作区文件树（提交 {commit_hash}）")
                    # 模拟点击侧边栏的'变更'按钮
                    get_main_window_by_parent(self).side_bar.changes_btn.click()
                else:
                    print("未找到 WorkspaceExplorer 实例")
            else:
                # 显示无差异信息到文件变化视图
                if workspace_explorer:
                    workspace_explorer.file_changes_view.show_no_differences_message(commit_hash)
                    print(f"已将无差异信息显示到文件变化视图（提交 {commit_hash}）")
                    # 模拟点击侧边栏的'变更'按钮
                    get_main_window_by_parent(self).side_bar.changes_btn.click()
                else:
                    print("未找到 WorkspaceExplorer 实例")
        else:
            print("无法获取 GitManager 实例")

    def wheelEvent(self, event):
        """重写滚轮事件，当没有有效滚动条时触发信号"""
        scroll_bar = self.verticalScrollBar()

        # 当滚动条不可见或不可用时触发
        if not scroll_bar.isVisible() or not scroll_bar.isEnabled() or scroll_bar.value() == scroll_bar.maximum():
            # if not self.no_data_label.isVisible():
            self.empty_scrolled_signal.emit()

        super().wheelEvent(event)  # 确保正常滚动行为
