import logging
import os

from PyQt6.QtCore import QEvent, QSize, Qt  # Added QEvent
from PyQt6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QSplitter,
    QTabBar,
    QTabWidget,  # 添加 QTabWidget 导入
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from commit_detail_view import CommitDetailView
from commit_dialog import CommitDialog
from commit_history_view import CommitHistoryView
from compare_view import CompareView
from compare_with_working_dialog import CompareWithWorkingDialog
from file_changes_view import FileChangesView
from git_manager import GitManager
from settings import Settings
from settings_dialog import SettingsDialog
from workspace_explorer import WorkspaceExplorer


class GitManagerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Git Manager")
        self.setGeometry(100, 100, 1200, 800)
        self.git_manager = None
        self.current_commit = None
        self.settings = Settings()
        self.bottom_widget_visible = True  # 添加状态标记

        # 创建主窗口部件
        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        # 创建主布局
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_widget.setLayout(main_layout)

        # 创建顶部控制区域
        top_widget = QWidget()
        top_widget.setFixedHeight(100)  # 固定顶部高度
        top_layout = QHBoxLayout()
        top_widget.setLayout(top_layout)
        main_layout.addWidget(top_widget)

        # 创建打开文件夹按钮和最近文件夹按钮的容器
        folder_layout = QHBoxLayout()

        # 创建打开文件夹按钮
        self.open_button = QPushButton("打开文件夹")
        self.open_button.clicked.connect(self.open_folder_dialog)
        folder_layout.addWidget(self.open_button)

        # 创建最近文件夹按钮
        self.recent_button = QToolButton()
        self.recent_button.setText("最近")
        self.recent_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

        # 创建最近文件夹菜单
        self.recent_menu = QMenu(self)
        self.recent_button.setMenu(self.recent_menu)
        self.update_recent_menu()

        folder_layout.addWidget(self.recent_button)
        top_layout.addLayout(folder_layout)

        # 创建分支选择下拉框
        self.branch_label = QLabel("当前分支:")
        self.branch_combo = QComboBox()
        self.branch_combo.currentTextChanged.connect(self.on_branch_changed)
        top_layout.addWidget(self.branch_label)
        top_layout.addWidget(self.branch_combo)

        # 添加提交按钮
        self.commit_button = QPushButton("提交")
        self.commit_button.clicked.connect(self.show_commit_dialog)
        self.commit_button.setFixedSize(80, 24)  # Set a smaller fixed size
        top_layout.addWidget(self.commit_button)

        # 创建设置按钮
        self.settings_button = QToolButton()
        self.settings_button.setText("⚙")  # 使用齿轮符号
        self.settings_button.clicked.connect(self.show_settings_dialog)
        top_layout.addWidget(self.settings_button)

        # 创建获取/推送/拉取按钮组
        repo_action_layout = QHBoxLayout()
        repo_action_layout.setSpacing(0)  # 减小按钮之间的间距

        # 获取按钮
        self.fetch_button = QToolButton()
        icon = QIcon("icons/fetch.svg")  # 假设图标路径
        icon.addPixmap(QPixmap("icons/fetch.svg"), QIcon.Mode.Normal, QIcon.State.On)  # 设置图标
        self.fetch_button.setIcon(icon)
        self.fetch_button.setIconSize(QSize(24, 24))  # 设置图标大小
        self.fetch_button.setToolTip("获取")
        self.fetch_button.clicked.connect(self.fetch_repo)  # 连接到相应的槽函数
        repo_action_layout.addWidget(self.fetch_button)

        # 拉取按钮 (带有向下箭头)
        self.pull_button = QToolButton()
        self.pull_button.setIcon(QIcon("icons/pull.svg"))  # 假设图标路径
        self.pull_button.setIconSize(QSize(24, 24))  # 设置图标大小
        self.pull_button.setToolTip("拉取")
        self.pull_button.clicked.connect(self.pull_repo)  # 连接到相应的槽函数
        repo_action_layout.addWidget(self.pull_button)

        # 推送按钮 (带有向上箭头)
        self.push_button = QToolButton()
        self.push_button.setIcon(QIcon("icons/push.svg"))  # 假设图标路径
        self.push_button.setIconSize(QSize(24, 24))  # 设置图标大小
        self.push_button.setToolTip("推送")
        self.push_button.clicked.connect(self.push_repo)  # 连接到相应的槽函数
        repo_action_layout.addWidget(self.push_button)

        top_layout.addLayout(repo_action_layout)

        # 创建切换底部面板按钮
        self.toggle_bottom_button = QToolButton()
        self.toggle_bottom_button.setFixedSize(24, 24)  # 设置固定大小
        self.update_toggle_button_icon()  # 设置初始图标
        self.toggle_bottom_button.clicked.connect(self.toggle_bottom_widget)
        top_layout.addWidget(self.toggle_bottom_button)

        # 创建垂直分割器
        vertical_splitter = QSplitter(Qt.Orientation.Vertical)
        vertical_splitter.setChildrenCollapsible(False)
        vertical_splitter.setOpaqueResize(False)  # 添加平滑调整
        vertical_splitter.setHandleWidth(8)  # 增加分割条宽度，更容易拖动
        main_layout.addWidget(vertical_splitter)

        # 下半部分容器
        self.bottom_widget = bottom_widget = QWidget()
        bottom_widget.setMinimumHeight(100)  # 设置最小高度
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_widget.setLayout(bottom_layout)

        # 创建水平分割器（用于提交历史和文件变化）
        horizontal_splitter = QSplitter(Qt.Orientation.Horizontal)
        horizontal_splitter.setChildrenCollapsible(False)
        horizontal_splitter.setOpaqueResize(False)  # 添加平滑调整
        horizontal_splitter.setHandleWidth(8)  # 增加分割条宽度，更容易拖动
        bottom_layout.addWidget(horizontal_splitter)

        # 创建主要视图组件
        self.commit_history_view = CommitHistoryView()  # 左侧
        self.file_changes_view = FileChangesView()  # 右侧
        self.commit_detail_view = CommitDetailView()  # commit详细信息视图

        # 添加一个 CompareView, 默认隐藏, 点击"提交历史"也隐藏
        # 切换到单个文件历史的标签页时,才显示
        # 点击标签页里的FileHistoryView的commit时,触发 FileHistoryView.on_commit_clicked 根据拿到的文件路径 commit信息 这个CompareView需要对改动进行显示
        self.compare_view = CompareView(self)  # 右侧
        self.compare_view.hide()

        # 这个tab 包含提交历史和单个文件历史, 文件历史可以有多个标签
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.TabPosition.North)
        self.tab_widget.setStyleSheet(
            """
            QTabWidget::tab-bar {
                left: 5px; /* 或者 0px, 根据您的偏好 */
            }
        """
        )
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.addTab(self.commit_history_view, "提交历史")
        self.tab_widget.currentChanged.connect(self.on_tab_changed)

        # 提交历史标签页，不可关闭
        self.tab_widget.tabBar().setTabButton(0, QTabBar.ButtonPosition.LeftSide, None)

        # 连接信号
        self.commit_history_view.commit_selected.connect(self.on_commit_selected)
        self.file_changes_view.file_selected.connect(self.on_file_selected)
        self.file_changes_view.compare_with_working_requested.connect(self.show_compare_with_working_dialog)

        # 创建右侧垂直分割器，用于放置文件变化视图和commit详细信息视图
        right_splitter = QSplitter(Qt.Orientation.Vertical)
        right_splitter.addWidget(self.file_changes_view)
        right_splitter.addWidget(self.commit_detail_view)
        right_splitter.setSizes([300, 200])  # 设置初始比例

        # 添加到布局
        horizontal_splitter.addWidget(self.tab_widget)
        horizontal_splitter.addWidget(right_splitter)
        horizontal_splitter.addWidget(self.compare_view)

        # 添加工作区浏览器
        self.workspace_explorer = WorkspaceExplorer()

        self.compare_tab_widget = self.workspace_explorer.tab_widget

        # 将右侧区域的分割器添加到主垂直分割器
        vertical_splitter.addWidget(self.workspace_explorer)

        # 添加下半部分到垂直分割器
        vertical_splitter.addWidget(bottom_widget)

        # 调整垂直分割器的比例 (例如: 6:2, 上半部分占 6/8, 下半部分占 2/8)
        total_height = self.height()
        vertical_splitter.setSizes(
            [
                total_height * 6 // 8,  # 提交历史和文件变化区域
                total_height * 2 // 8,  # 工作区和比较视图区域
            ]
        )

        # 设置主水平分割器的初始大小比例 (1:2)
        total_width = self.width()
        horizontal_splitter.setSizes([total_width // 3, total_width * 2 // 3])

        # 保存分割器引用以便后续使用
        self.vertical_splitter = vertical_splitter
        self.horizontal_splitter = horizontal_splitter

        # 从设置中恢复分割器状态
        self.restore_splitter_state()

        # 在窗口关闭时保存分割器状态
        self.destroyed.connect(self.save_splitter_state)

        # 从设置中恢复底部面板状态
        self.bottom_widget_visible = self.settings.settings.get("bottom_widget_visible", True)
        self.bottom_widget.setVisible(self.bottom_widget_visible)
        self.update_toggle_button_icon()

        # 在初始化完成后,尝试打开上次的文件夹
        last_folder = self.settings.get_last_folder()
        if last_folder and os.path.exists(last_folder):
            self.open_folder(last_folder)

    def show_commit_dialog(self):
        """显示提交对话框"""
        if not self.git_manager:
            return

        dialog = CommitDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            pass

    def update_recent_menu(self):
        """更新最近文件夹菜单"""
        self.recent_menu.clear()
        recent_folders = self.settings.get_recent_folders()

        for folder in recent_folders:
            if os.path.exists(folder):  # 只显示仍然存在的文件夹
                action = QAction(folder, self)
                action.triggered.connect(lambda checked, f=folder: self.open_folder(f))
                self.recent_menu.addAction(action)

        if recent_folders:
            self.recent_menu.addSeparator()
            clear_action = QAction("清除最近记录", self)
            clear_action.triggered.connect(self.clear_recent_folders)
            self.recent_menu.addAction(clear_action)

    def clear_recent_folders(self):
        """清除最近文件夹记录"""
        self.settings.settings["recent_folders"] = []
        self.settings.settings["last_folder"] = None
        self.settings.save_settings()
        self.update_recent_menu()

    def open_folder_dialog(self):
        """打开文件夹选择对话框"""
        folder_path = QFileDialog.getExistingDirectory(self, "选择Git仓库")
        # macos 上 QFileDialog.getExistingDirectory 有时候选择"文件夹对话框" 灰色的 无法打开文件夹
        # 再有bug 可以考虑用 QFileDialog.Option.DontUseNativeDialog
        # 就是这个没有保存最近打开的文件夹路径 每次都要重新选
        # 极有可能与输入法有关 error messaging the mach port for IMKCFRunLoopWakeUpReliable
        if folder_path:
            self.open_folder(folder_path)

    def open_folder(self, folder_path):
        """打开指定的文件夹"""
        self.git_manager = GitManager(folder_path)
        if self.git_manager.initialize():
            # 添加到最近文件夹列表
            self.settings.add_recent_folder(folder_path)
            self.update_recent_menu()

            # 更新UI
            self.update_branches()
            self.update_commit_history()

            # 更新工作区浏览器
            self.workspace_explorer.set_workspace_path(folder_path)
            self.workspace_explorer.git_manager = self.git_manager
            self.workspace_explorer.refresh_file_tree()
        else:
            self.commit_history_view.history_list.clear()
            self.commit_history_view.history_list.addItem("所选文件夹不是有效的Git仓库")

    def update_branches(self):
        """更新分支列表"""
        self.branch_combo.clear()
        if not self.git_manager:
            return
        branches = self.git_manager.get_branches()
        default_branch = self.git_manager.get_default_branch()

        # 将默认分支移到列表开头
        if default_branch and default_branch in branches:
            branches.remove(default_branch)
            branches.insert(0, default_branch)

        self.branch_combo.addItems(branches)
        self.branch_combo.addItems(["all"])

    def update_commit_history(self):
        """更新提交历史"""
        if not self.git_manager:
            return

        current_branch = self.branch_combo.currentText()
        if current_branch == "all":
            self.commit_history_view.update_history(self.git_manager, "main")
        else:
            self.commit_history_view.update_history(self.git_manager, current_branch)

    def on_branch_changed(self, branch):
        """当分支改变时更新提交历史"""
        if self.git_manager:
            self.update_commit_history()

    def on_commit_selected(self, commit_hash):
        """当选择提交时更新文件变化视图"""
        if not self.git_manager:
            return
        self.current_commit = self.git_manager.repo.commit(commit_hash)
        self.file_changes_view.update_changes(self.git_manager, self.current_commit)
        # cursor生成 - 同时更新commit详细信息视图
        self.commit_detail_view.update_commit_detail(self.git_manager, self.current_commit)

    def on_file_selected(self, file_path):
        """当选择文件时，在TabWidget中显示比较视图"""
        if not self.current_commit or not self.git_manager:
            return
        self._on_file_selected(file_path, self.current_commit)

    def _on_file_selected(self, file_path, current_commit):
        # 生成一个唯一的标签页标识符, 例如 "commit_hash:file_path"
        # 为简化, 我们先用 file_path 作为标题, 并检查是否已存在
        # 更健壮的方式是存储一个映射: tab_key -> tab_index

        tab_title = os.path.basename(file_path)
        commit_short_hash = current_commit.hexsha[:7]
        unique_tab_title = f"{tab_title} @ {commit_short_hash}"

        # 检查是否已存在具有相同唯一标题的标签页
        for i in range(self.compare_tab_widget.count()):
            if self.compare_tab_widget.tabText(i) == unique_tab_title:
                self.compare_tab_widget.setCurrentIndex(i)
                return

        # 如果不存在，创建新的CompareView实例并添加
        compare_view_instance = CompareView(self)
        compare_view_instance.show_diff(self.git_manager, current_commit, file_path)

        new_tab_index = self.compare_tab_widget.addTab(compare_view_instance, unique_tab_title)
        self.compare_tab_widget.setCurrentIndex(new_tab_index)

    # def close_compare_tab(self, index):
    #     """关闭比较视图的标签页"""
    #     widget_to_close = self.compare_tab_widget.widget(index)
    #     self.compare_tab_widget.removeTab(index)
    #     if widget_to_close:
    #         widget_to_close.deleteLater() # 确保Qt对象被正确删除

    def show_compare_with_working_dialog(self, file_path):
        """显示与工作区比较的对话框"""
        try:
            # 获取历史版本的文件内容
            old_content = self.current_commit.tree[file_path].data_stream.read().decode("utf-8", errors="replace")

            # 获取工作区的文件内容
            working_file_path = os.path.join(self.git_manager.repo.working_dir, file_path)
            if os.path.exists(working_file_path):
                with open(working_file_path, "r", encoding="utf-8", errors="replace") as f:
                    new_content = f.read()
            else:
                new_content = ""

            # 创建并显示比较对话框
            # todo 这个要改造, 看readme里的todo
            dialog = CompareWithWorkingDialog(f"比较 {file_path}", old_content, new_content, self)
            dialog.exec()

        except Exception as e:
            print(f"比较文件失败: {e!s}")

    def save_splitter_state(self):
        """保存所有分割器的状态"""
        self.settings.settings["vertical_splitter"] = list(self.vertical_splitter.sizes())
        self.settings.settings["horizontal_splitter"] = list(self.horizontal_splitter.sizes())
        self.settings.save_settings()

    def restore_splitter_state(self):
        """恢复所有分割器的状态"""
        # 恢复垂直分割器状态
        vertical_sizes = self.settings.settings.get("vertical_splitter")
        if vertical_sizes and len(vertical_sizes) == len(self.vertical_splitter.sizes()):
            self.vertical_splitter.setSizes(vertical_sizes)

        # 恢复水平分割器状态
        horizontal_sizes = self.settings.settings.get("horizontal_splitter")
        if horizontal_sizes and len(horizontal_sizes) == len(self.horizontal_splitter.sizes()):
            self.horizontal_splitter.setSizes(horizontal_sizes)

    def resizeEvent(self, event):
        """处理窗口大小改变事件"""
        super().resizeEvent(event)
        # 如果没有保存的分割器状态,则使用默认比例
        if not self.settings.settings.get("vertical_splitter"):
            total_height = self.height()
            # 调整垂直分割器的默认比例 (例如: 2:6)
            self.vertical_splitter.setSizes([total_height * 6 // 8, total_height * 2 // 8])
        if not self.settings.settings.get("horizontal_splitter"):  # 主水平分割器
            total_width = self.width()  # 这是上半部分的宽度
            # horizontal_splitter 在 upper_widget 中, 其宽度应基于 upper_widget
            # 不过, 在初始化时设置比例通常足够, resizeEvent 更多是窗口整体调整后的事情
            # 我们在 __init__ 中已设置了 horizontal_splitter.setSizes
            # 此处可以保持原样或针对性调整
            pass  # horizontal_splitter 的宽度由其父控件和初始比例决定

    def show_settings_dialog(self):
        """显示设置对话框"""
        dialog = SettingsDialog(self)
        dialog.exec()

    def close_tab(self, index):
        """关闭标签页"""
        # 不允许关闭提交历史标签页(假设它总是索引0)
        if index == 0:
            return

        self.tab_widget.removeTab(index)

    def on_tab_changed(self, index):
        """当标签页改变时"""
        if index == 0:
            self.compare_view.hide()
            # cursor生成 - 显示右侧分割器（包含文件变化视图和commit详细信息视图）
            right_splitter = self.horizontal_splitter.widget(1)
            right_splitter.show()
        else:
            self.compare_view.show()
            # cursor生成 - 隐藏右侧分割器
            right_splitter = self.horizontal_splitter.widget(1)
            right_splitter.hide()

    def update_toggle_button_icon(self):
        """更新切换按钮的图标"""
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 绘制方框
        painter.setPen(QColor(0, 0, 0))
        painter.drawRect(2, 2, 20, 20)

        # 根据状态填充下半部分
        if self.bottom_widget_visible:
            painter.fillRect(2, 12, 20, 10, QColor(0, 0, 0))
        else:
            painter.fillRect(2, 12, 20, 10, QColor(255, 255, 255))

        painter.end()
        self.toggle_bottom_button.setIcon(QIcon(pixmap))

    def toggle_bottom_widget(self):
        """切换底部面板的显示状态"""
        self.bottom_widget_visible = not self.bottom_widget_visible
        self.bottom_widget.setVisible(self.bottom_widget_visible)
        self.update_toggle_button_icon()

        # 保存状态到设置
        self.settings.settings["bottom_widget_visible"] = self.bottom_widget_visible
        self.settings.save_settings()

    def fetch_repo(self):
        """获取仓库"""
        if not self.git_manager:
            return
        self.git_manager.fetch()

    def pull_repo(self):
        """拉取仓库"""
        if not self.git_manager:
            return
        self.git_manager.pull()

    def push_repo(self):
        """推送仓库"""
        if not self.git_manager:
            return
        self.git_manager.push()

    def handle_blame_click_from_editor(self, commit_hash: str):
        """
        Handles a blame annotation click from a SyncedTextEdit instance opened in the workspace.
        Selects the commit in CommitHistoryView and switches to the history tab.
        """
        logging.info("GitManagerWindow: Received blame click from editor for commit: %s", commit_hash)

        if not hasattr(self, "commit_history_view") or not self.commit_history_view:
            logging.error("GitManagerWindow: commit_history_view is not available.")
            return

        history_list = self.commit_history_view.history_list

        short_hash_to_find = commit_hash[:7]
        found_item = None

        # Initial search
        for i in range(history_list.topLevelItemCount()):
            item = history_list.topLevelItem(i)
            if item and item.text(0) == short_hash_to_find:
                found_item = item
                break

        # If not found and not all commits are loaded, try loading more
        if not found_item and not self.commit_history_view._all_loaded:
            logging.info(
                "GitManagerWindow: Commit %s not found initially, attempting to load more commits.",
                short_hash_to_find,
            )
            while not found_item and not self.commit_history_view._all_loaded:
                self.commit_history_view.load_more_commits()
                # Re-search after loading more
                for i in range(history_list.topLevelItemCount()):
                    item = history_list.topLevelItem(i)
                    if item and item.text(0) == short_hash_to_find:
                        found_item = item
                        break
                if found_item:
                    logging.info("GitManagerWindow: Found commit %s after loading more.", short_hash_to_find)
                    break
                if self.commit_history_view._all_loaded:
                    logging.info(
                        "GitManagerWindow: All commits loaded, but commit %s still not found.",
                        short_hash_to_find,
                    )
                    break

        if found_item:
            history_list.setCurrentItem(found_item)
            history_list.scrollToItem(found_item, QAbstractItemView.ScrollHint.PositionAtCenter)

            if hasattr(self.commit_history_view, "on_commit_clicked"):
                self.commit_history_view.on_commit_clicked(found_item)
            else:
                logging.error("GitManagerWindow: on_commit_clicked method not found in commit_history_view.")

            if hasattr(self, "tab_widget") and self.tab_widget:
                self.tab_widget.setCurrentIndex(0)  # Switch to "提交历史" tab
                logging.info("GitManagerWindow: Switched to '提交历史' tab and selected commit %s.", short_hash_to_find)
            else:
                logging.warning("GitManagerWindow: tab_widget not found, cannot switch tabs.")
        else:
            # This 'else' corresponds to the 'if found_item:' after the loop or initial find.
            # It should be at the same indentation level.
            logging.warning(
                "GitManagerWindow: Commit %s (full: %s) not found in history_list even after attempting to load all.",
                short_hash_to_find,
                commit_hash,
            )

    def changeEvent(self, event: QEvent):
        super().changeEvent(event)
        if event.type() == QEvent.Type.ActivationChange:
            if self.isActiveWindow():
                # print("Window activated, refreshing file tree...") # Optional: for debugging
                if hasattr(self, "workspace_explorer") and self.workspace_explorer:
                    if self.git_manager and self.git_manager.repo:  # Ensure git repo is loaded
                        self.workspace_explorer.refresh_file_tree()
