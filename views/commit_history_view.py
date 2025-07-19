from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLineEdit, QTreeWidgetItem, QVBoxLayout, QWidget

from custom_tree_widget import CustomTreeWidget
from git_graph_view import GitGraphView

if TYPE_CHECKING:
    from git_manager import GitManager  # Assuming GitManager is defined in git_manager.py


class CommitHistoryView(QWidget):
    commit_selected = pyqtSignal(str)  # 当选择提交时发出信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self.loaded_count = 0  # cursor 生成
        self.load_batch_size = 50  # cursor 生成
        self.git_manager: GitManager | None = None  # cursor 生成
        self.branch = None  # cursor 生成
        self._loading = False  # cursor 生成
        self._all_loaded = False  # cursor 生成
        self.filter_text = ""
        self.search_timer = QTimer(self)
        self.search_timer.setInterval(500)  # 设置延时为 500 毫秒
        self.search_timer.setSingleShot(True)  # 设置为单次触发
        self.search_timer.timeout.connect(self._apply_filter)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        self.setLayout(layout)

        # 添加搜索框
        search_layout = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("当搜索以后，可尝试往下滚动加载更多数据进行搜索...")
        self.search_edit.textChanged.connect(self.filter_history)
        self.search_edit.setMaximumWidth(350)  # 设置搜索框最大宽度，使其变窄

        # 添加清除动作到搜索框内
        self.clear_action = QAction(self.search_edit)
        self.clear_action.setIcon(
            QIcon.fromTheme("edit-clear")
            or self.style().standardIcon(self.style().StandardPixmap.SP_LineEditClearButton)
        )
        self.clear_action.triggered.connect(self.clear_search)
        self.search_edit.addAction(self.clear_action, QLineEdit.ActionPosition.TrailingPosition)

        search_layout.addWidget(self.search_edit)

        # 添加下拉框
        self.branch_combo = QComboBox()
        self.branch_combo.addItem("Branch")
        self.branch_combo.setMinimumWidth(80)
        search_layout.addWidget(self.branch_combo)

        self.user_combo = QComboBox()
        self.user_combo.addItem("User")
        self.user_combo.setMinimumWidth(80)
        search_layout.addWidget(self.user_combo)

        self.date_combo = QComboBox()
        self.date_combo.addItem("Date")
        self.date_combo.setMinimumWidth(80)
        search_layout.addWidget(self.date_combo)

        # 添加伸缩空间使搜索框左对齐
        search_layout.addStretch()
        layout.addLayout(search_layout)

        # 普通提交历史列表
        self.history_list = CustomTreeWidget(self)
        self.history_list.empty_scrolled_signal.connect(self.load_more_commits)
        self.history_list.set_hover_reveal_columns({0})  # Enable hover for commit message column
        self.history_list.setHeaderLabels(["提交信息", "Branches", "作者", "日期"])
        self.history_list.itemClicked.connect(self.on_commit_clicked)
        self.history_list.currentItemChanged.connect(self.on_current_item_changed)
        self.history_list.setColumnWidth(0, 200)  # Message
        self.history_list.setColumnWidth(1, 150)  # Branches
        self.history_list.setColumnWidth(2, 100)  # Author
        self.history_list.setColumnWidth(3, 150)  # Date
        layout.addWidget(self.history_list)

        # 滚动到底部自动加载更多，cursor 生成
        self.history_list.verticalScrollBar().valueChanged.connect(self._on_scroll)

        # 默认隐藏清除动作
        self.clear_action.setVisible(False)

        # 图形化提交历史
        self.history_graph_list = GitGraphView()
        self.history_graph_list.commit_item_clicked.connect(self.on_commit_clicked)
        layout.addWidget(self.history_graph_list)

        self.history_graph_list.hide()  # 默认隐藏

        # cursor 生成：初始检查数据状态
        self._check_and_display_no_data_message()

    def update_history(self, git_manager, branch):
        """更新提交历史"""
        self.git_manager = git_manager  # cursor 生成
        self.branch = branch  # cursor 生成
        self.loaded_count = 0  # cursor 生成
        self._all_loaded = False  # cursor 生成
        self.history_list.clear()
        self.load_more_commits()  # cursor 生成

    def load_history_graph(self, git_manager):
        print("更新提交历史...")  # cursor 生成
        # 加载图形视图的仓库
        if git_manager and git_manager.repo:
            self.history_graph_list.load_repository(git_manager.repo.working_dir)

    def load_more_commits(self):
        """加载更多提交历史 (cursor 生成)"""
        if self._loading or self._all_loaded:
            return
        self._loading = True
        print("加载更多提交历史...", self.loaded_count)  # cursor 生成
        if not self.git_manager or not self.branch:
            self._loading = False
            return

        remote_names = []
        if self.git_manager and self.git_manager.repo:
            remote_names = [remote.name for remote in self.git_manager.repo.remotes]
        else:
            # Fallback if git_manager or repo isn't fully initialized here, though it should be.
            remote_names = ["origin"]

        commits = self.git_manager.get_commit_history(
            self.branch, self.load_batch_size, self.loaded_count, include_remotes=True
        )  # cursor 生成
        for commit in commits:
            item = QTreeWidgetItem(self.history_list)
            item.setData(0, Qt.ItemDataRole.UserRole, commit["hash"])  # 存储完整哈希
            item.setText(0, commit["message"])  # Commit Message

            decorations = commit.get("decorations", [])
            processed_decorations = []
            for ref_name in decorations:
                is_remote = False
                for r_name in remote_names:
                    if ref_name.startswith(f"{r_name}/"):
                        is_remote = True
                        break

                if is_remote:
                    processed_decorations.append(f"☁️ {ref_name}")
                else:
                    processed_decorations.append(ref_name)
            decoration_text = ", ".join(processed_decorations)
            item.setText(1, decoration_text)  # Branches

            item.setText(2, commit["author"])  # Author
            item.setText(3, commit["date"])  # Date
        self.loaded_count += len(commits)  # cursor 生成
        if len(commits) < self.load_batch_size:  # 没有更多了
            self._all_loaded = True  # cursor 生成
        self._loading = False

        # 加载后自动应用当前过滤
        self._apply_filter()

    def _on_scroll(self, value):
        # 滚动到底部时自动加载更多 cursor 生成
        scroll_bar = self.history_list.verticalScrollBar()
        if value == scroll_bar.maximum() and not self._all_loaded:
            print("滚动到底部，自动加载更多...")  # cursor 生成
            self.load_more_commits()

    def on_commit_clicked(self, item_or_sha):
        """当点击提交时发出信号"""
        commit_hash = ""
        if isinstance(item_or_sha, QTreeWidgetItem):
            # Clicked from the QTreeWidget (history_list)
            # Get the full hash from UserRole data
            commit_hash = item_or_sha.data(0, Qt.ItemDataRole.UserRole)
        elif isinstance(item_or_sha, str):
            # Clicked from the GitGraphView (history_graph_list)
            # The argument is already the commit SHA (full or short)
            commit_hash = item_or_sha

        if commit_hash:  # Ensure we have a hash before emitting
            self.commit_selected.emit(commit_hash)
        else:
            # Optional: Handle cases where commit_hash couldn't be determined
            print(f"Warning: Could not determine commit hash from item: {item_or_sha}")

    def on_current_item_changed(self, current: QTreeWidgetItem, previous: QTreeWidgetItem):
        if current:
            print(current.text(0))
            self.history_list.show_full_text_for_item(current, 0)
        else:
            self.history_list.hide_overlay()

    def filter_history(self, text):
        """根据输入文本过滤提交历史"""
        self.filter_text = text.strip().lower()
        self.clear_action.setVisible(bool(self.filter_text))
        self.search_timer.start()  # 启动或重启计时器

    def clear_search(self):
        """清除搜索框并恢复所有项目"""
        self.search_edit.clear()
        self.filter_text = ""
        self.clear_action.setVisible(False)
        self._apply_filter()

    def _check_and_display_no_data_message(self):
        """检查并显示/隐藏无数据提示信息"""
        visible_items_count = 0
        total_items = self.history_list.topLevelItemCount()

        if total_items == 0:
            self.history_list.show_no_data_message("请尝试往下滚动加载更多数据")
            return

        for i in range(total_items):
            item = self.history_list.topLevelItem(i)
            if not item.isHidden():
                visible_items_count += 1

        if visible_items_count == 0:
            self.history_list.show_no_data_message("请尝试往下滚动加载更多数据")
        else:
            self.history_list.hide_no_data_message()

    def _apply_filter(self):
        """应用过滤逻辑到所有项目"""
        # 遍历所有项目
        for i in range(self.history_list.topLevelItemCount()):
            item = self.history_list.topLevelItem(i)
            # 如果没有过滤文本，显示所有项目
            if not self.filter_text:
                item.setHidden(False)
                continue

            # 检查各列的匹配情况 (0: id, 1: message, 3: author, 4: date)
            show_item = False
            # 检查完整哈希
            full_hash = item.data(0, Qt.ItemDataRole.UserRole)
            if full_hash and self.filter_text in full_hash.lower():
                show_item = True

            if not show_item:  # 如果完整哈希没有匹配，则检查其他列
                for col in range(self.history_list.columnCount()):
                    item_text = item.text(col).lower()
                    if self.filter_text in item_text:
                        show_item = True
                        break

            item.setHidden(not show_item)

        # cursor 生成：过滤完成后检查数据状态
        self._check_and_display_no_data_message()