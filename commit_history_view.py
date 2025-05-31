from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QTreeWidgetItem, QVBoxLayout, QWidget

from custom_tree_widget import CustomTreeWidget
from git_graph_view import GitGraphView


class CommitHistoryView(QWidget):
    commit_selected = pyqtSignal(str)  # 当选择提交时发出信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self.loaded_count = 0  # cursor生成
        self.load_batch_size = 50  # cursor生成
        self.git_manager = None  # cursor生成
        self.branch = None  # cursor生成
        self._loading = False  # cursor生成
        self._all_loaded = False  # cursor生成
        self.filter_text = ""
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        self.setLayout(layout)

        # 添加搜索框
        search_layout = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索提交历史...")
        self.search_edit.textChanged.connect(self.filter_history)
        search_layout.addWidget(self.search_edit)

        # 添加清除按钮
        self.clear_button = QPushButton("清除")
        self.clear_button.clicked.connect(self.clear_search)
        self.clear_button.setMaximumWidth(60)
        search_layout.addWidget(self.clear_button)
        layout.addLayout(search_layout)

        self.history_label = QLabel("提交历史:")
        layout.addWidget(self.history_label)

        # 普通提交历史列表
        self.history_list = CustomTreeWidget()
        self.history_list.set_hover_reveal_columns({1})  # Enable hover for commit message column
        self.history_list.setHeaderLabels(["提交ID", "提交信息", "Branches", "作者", "日期"])
        self.history_list.itemClicked.connect(self.on_commit_clicked)
        self.history_list.currentItemChanged.connect(self.on_current_item_changed)
        self.history_list.setColumnWidth(0, 80)  # Hash
        self.history_list.setColumnWidth(1, 200)  # Message
        self.history_list.setColumnWidth(2, 150)  # Branches
        self.history_list.setColumnWidth(3, 100)  # Author
        self.history_list.setColumnWidth(4, 150)  # Date
        layout.addWidget(self.history_list)

        # 滚动到底部自动加载更多, cursor生成
        self.history_list.verticalScrollBar().valueChanged.connect(self._on_scroll)

        # 默认隐藏清除按钮
        self.clear_button.setVisible(False)

        # 图形化提交历史
        self.history_graph_list = GitGraphView()
        self.history_graph_list.load_repository(".")
        # self.history_graph_list.setHeaderLabels(["提交图", "提交ID", "提交信息", "作者", "日期"])
        # self.history_graph_list.itemClicked.connect(self.on_commit_clicked)
        layout.addWidget(self.history_graph_list)

        self.history_graph_list.hide()  # 默认隐藏

    def update_history(self, git_manager, branch):
        """更新提交历史"""
        self.git_manager = git_manager  # cursor生成
        self.branch = branch  # cursor生成
        self.loaded_count = 0  # cursor生成
        self._all_loaded = False  # cursor生成
        self.history_list.clear()
        self.load_more_commits()  # cursor生成

    def load_more_commits(self):
        """加载更多提交历史 (cursor生成)"""
        if self._loading or self._all_loaded:
            return
        self._loading = True
        print("加载更多提交历史...", self.loaded_count)  # cursor生成
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
            self.branch, self.load_batch_size, self.loaded_count
        )  # cursor生成
        for commit in commits:
            item = QTreeWidgetItem(self.history_list)
            item.setText(0, commit["hash"][:7])  # Commit ID
            item.setText(1, commit["message"])  # Commit Message

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
            item.setText(2, decoration_text)  # Branches (new column)

            item.setText(3, commit["author"])  # Author (index shifted)
            item.setText(4, commit["date"])  # Date (index shifted)
        self.loaded_count += len(commits)  # cursor生成
        if len(commits) < self.load_batch_size:  # 没有更多了
            self._all_loaded = True  # cursor生成
        self._loading = False

        # 加载后自动应用当前过滤
        self._apply_filter()

    def _on_scroll(self, value):
        # 滚动到底部时自动加载更多 cursor生成
        scroll_bar = self.history_list.verticalScrollBar()
        if value == scroll_bar.maximum() and not self._all_loaded:
            print("滚动到底部, 自动加载更多...")  # cursor生成
            self.load_more_commits()

    def on_commit_clicked(self, item):
        """当点击提交时发出信号"""
        commit_hash = item.text(0) or item.text(1)
        self.commit_selected.emit(commit_hash)

    def on_current_item_changed(self, current: QTreeWidgetItem, previous: QTreeWidgetItem):
        if current:
            print(current.text(1))
            self.history_list.show_full_text_for_item(current, 1)
        else:
            self.history_list.hide_overlay()

    def filter_history(self, text):
        """根据输入文本过滤提交历史"""
        self.filter_text = text.strip().lower()
        self.clear_button.setVisible(bool(self.filter_text))
        self._apply_filter()

    def clear_search(self):
        """清除搜索框并恢复所有项目"""
        self.search_edit.clear()
        self.filter_text = ""
        self.clear_button.setVisible(False)
        self._apply_filter()

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
            for col in (0, 1, 3, 4):
                item_text = item.text(col).lower()
                if self.filter_text in item_text:
                    show_item = True
                    break

            item.setHidden(not show_item)
