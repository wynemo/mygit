import logging
import os

from PyQt6.QtCore import QEvent, QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QGuiApplication, QIcon
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QSplitter,
    QTabBar,
    QTabWidget,  # 添加 QTabWidget 导入
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from commit_detail_view import CommitDetailView
from compare_view import CompareView
from components.notification_widget import NotificationWidget
from components.spin_icons import RotatingLabel
from dialogs.settings_dialog import SettingsDialog
from file_changes_view import FileChangesView
from git_manager import GitManager
from settings import settings
from threads import FetchThread, PullThread, PushThread  # Import PullThread and PushThread
from views.commit_history_view import CommitHistoryView
from views.folder_history_view import FolderHistoryView
from views.side_bar_widget import SideBarWidget
from views.top_bar_widget import TopBarWidget  # Import TopBarWidget
from workspace_explorer import WorkspaceExplorer


class GitChangeHandler(FileSystemEventHandler, QObject):
    """Handles file system events from watchdog and signals the main window."""

    file_changed = pyqtSignal(str, str, str)  # (event_type, path, is_directory)
    git_changed = pyqtSignal(str, str)  # (event_type, path) for git-specific changes

    def on_any_event(self, event):
        """
        This method is called for any event.
        We monitor specific .git directory files to detect git operations.
        """
        event_type = event.event_type
        path = event.src_path
        is_directory = "directory" if event.is_directory else "file"

        # Check if this is a git-related change we care about
        if self._is_git_change_of_interest(path):
            logging.debug("Git watchdog event: %s on %s", event_type, path)
            self.git_changed.emit(event_type, path)
            return

        # Ignore other .git directory changes to prevent loops
        if ".git" in event.src_path.split(os.sep):
            return

        logging.debug("Watchdog event: %s on %s (%s)", event_type, path, is_directory)
        self.file_changed.emit(event_type, path, is_directory)

    def _is_git_change_of_interest(self, path):
        """Check if the path is a git file we want to monitor for history updates."""
        git_paths_of_interest = [".git/refs/", ".git/logs/HEAD", ".git/HEAD", ".git/FETCH_HEAD", ".git/ORIG_HEAD"]

        for git_path in git_paths_of_interest:
            if git_path in path:
                return True
        return False


class GitManagerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(self.tr("Git Manager"))

        # Get screen geometry and set window size
        screen = QGuiApplication.primaryScreen()
        if screen:
            geometry = screen.availableGeometry()
            self.setGeometry(
                geometry.x() + int(geometry.width() * 0.1),
                geometry.y() + int(geometry.height() * 0.1),
                int(geometry.width() * 0.8),
                int(geometry.height() * 0.8),
            )
        else:
            # Fallback if screen info is not available
            self.resize(1024, 768)

        self.git_manager = None
        self.current_commit = None
        self.settings = settings
        self.notification_widget = NotificationWidget(self)
        self.bottom_widget_visible = True  # 添加状态标记

        # Watchdog observer for file system changes
        self.observer = None
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setSingleShot(True)
        self.refresh_timer.setInterval(1000)  # 1-second delay to debounce refreshes
        self.refresh_timer.timeout.connect(self._throttled_refresh)

        # Git history refresh timer
        self.git_refresh_timer = QTimer(self)
        self.git_refresh_timer.setSingleShot(True)
        self.git_refresh_timer.setInterval(500)  # 0.5-second delay for git changes
        self.git_refresh_timer.timeout.connect(self._throttled_git_refresh)

        # 创建主窗口部件
        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        # 创建主布局
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_widget.setLayout(main_layout)

        # Instantiate TopBarWidget
        self.top_bar = TopBarWidget(self)
        main_layout.addWidget(self.top_bar)

        # 添加侧边栏
        self.side_bar = SideBarWidget()

        # Connect signals from TopBarWidget to GitManagerWindow methods
        self.top_bar.open_folder_requested.connect(self.open_folder_dialog)

        # Connect side bar button signals
        self.side_bar.project_button_clicked.connect(self.on_project_button_clicked)
        self.side_bar.commit_button_clicked.connect(self.on_commit_button_clicked)
        self.side_bar.changes_button_clicked.connect(self.on_changes_button_clicked)
        self.side_bar.search_button_clicked.connect(self.on_search_button_clicked)
        self.top_bar.recent_folder_selected.connect(self.open_folder)
        self.top_bar.clear_recent_folders_requested.connect(self.clear_recent_folders)
        self.top_bar.branch_changed.connect(self.on_branch_changed)
        self.top_bar.commit_requested.connect(self.show_commit_dialog)
        self.top_bar.settings_requested.connect(self.show_settings_dialog)
        self.top_bar.toggle_bottom_panel_requested.connect(self.toggle_bottom_widget)
        self.top_bar.toggle_left_panel_requested.connect(self.toggle_left_panel)

        # Initial population of TopBarWidget UI elements
        # self.update_recent_menu_on_top_bar() # Called later in __init__
        # self.update_branches_on_top_bar() # Called later in __init__

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

        # 创建 Fetch/Pull/Push 按钮布局
        git_button_layout = QHBoxLayout()
        git_button_layout.setContentsMargins(0, 0, 0, 0)
        git_button_layout.setSpacing(15)
        git_button_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)  # 左对齐

        self.fetch_button = QToolButton()
        self.fetch_button.setIcon(QIcon("icons/fetch.svg"))
        self.fetch_button.setText("Fetch")
        self.fetch_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.fetch_button.clicked.connect(self.fetch_repo)
        git_button_layout.addWidget(self.fetch_button)

        self.pull_button = QToolButton()
        self.pull_button.setIcon(QIcon("icons/pull.svg"))
        self.pull_button.setText("Pull")
        self.pull_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.pull_button.clicked.connect(self.pull_repo)
        git_button_layout.addWidget(self.pull_button)

        self.push_button = QToolButton()
        self.push_button.setIcon(QIcon("icons/push.svg"))
        self.push_button.setText("Push")
        self.push_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.push_button.clicked.connect(self.push_repo)
        git_button_layout.addWidget(self.push_button)

        # --- Spinner Label ---
        self.spinner_label = RotatingLabel("icons/spin.png")
        self.spinner_label.hide()
        git_button_layout.addWidget(self.spinner_label)

        git_widget = QWidget()
        git_widget.setLayout(git_button_layout)

        # 创建主要视图组件
        self.commit_history_view = CommitHistoryView()  # 左侧
        self.file_changes_view = FileChangesView()  # 右侧
        self.commit_detail_view = CommitDetailView()  # commit 详细信息视图

        # 添加一个 CompareView, 默认隐藏，点击"提交历史"也隐藏
        # 切换到单个文件历史的标签页时，才显示
        # 点击标签页里的 FileHistoryView 的 commit 时，触发 FileHistoryView.on_commit_clicked 根据拿到的文件路径 commit 信息 这个 CompareView 需要对改动进行显示
        self.compare_view = CompareView(self)  # 右侧
        self.compare_view.hide()

        # 这个 tab 包含提交历史和单个文件历史，文件历史可以有多个标签
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
        self.tab_widget.addTab(self.commit_history_view, self.tr("Commit History"))
        self.tab_widget.currentChanged.connect(self.on_tab_changed)

        # 提交历史标签页，不可关闭
        self.tab_widget.tabBar().setTabButton(0, QTabBar.ButtonPosition.LeftSide, None)

        # 连接信号
        self.commit_history_view.commit_selected.connect(self.on_commit_selected)
        self.file_changes_view.file_selected.connect(self.on_file_selected)
        self.file_changes_view.compare_with_working_requested.connect(self.show_compare_with_working_dialog)
        self.file_changes_view.edit_file_requested.connect(self.on_edit_file_requested)

        # 创建右侧垂直分割器，用于放置文件变化视图和 commit 详细信息视图
        right_splitter = QSplitter(Qt.Orientation.Vertical)
        right_splitter.addWidget(self.file_changes_view)
        right_splitter.addWidget(self.commit_detail_view)
        right_splitter.setSizes([300, 200])  # 设置初始比例

        # 添加到布局
        v_git_and_tab_layout = QVBoxLayout()
        v_git_and_tab_layout.setContentsMargins(10, 10, 10, 10)
        v_git_and_tab_layout.setSpacing(15)
        git_and_tab_widget = QWidget()
        git_and_tab_widget.setLayout(v_git_and_tab_layout)
        v_git_and_tab_layout.addWidget(git_widget)
        v_git_and_tab_layout.addWidget(self.tab_widget)
        horizontal_splitter.addWidget(git_and_tab_widget)
        horizontal_splitter.addWidget(right_splitter)
        horizontal_splitter.addWidget(self.compare_view)

        # 添加工作区浏览器
        self.workspace_explorer = WorkspaceExplorer(self)

        self.compare_tab_widget = self.workspace_explorer.tab_widget

        # 创建左侧面板分割器 (包含侧边栏和工作区浏览器)
        left_panel_splitter = QSplitter(Qt.Orientation.Horizontal)
        left_panel_splitter.setChildrenCollapsible(False)
        left_panel_splitter.setOpaqueResize(False)
        left_panel_splitter.setHandleWidth(8)  # 分隔条的宽度为 8 像素
        left_panel_splitter.addWidget(self.side_bar)
        left_panel_splitter.addWidget(self.workspace_explorer)
        # left_panel_splitter.setSizes([200, 600])  # 设置初始比例

        # 将左侧面板分割器添加到主垂直分割器
        vertical_splitter.addWidget(left_panel_splitter)

        # 添加下半部分到垂直分割器
        vertical_splitter.addWidget(bottom_widget)

        # 调整垂直分割器的比例 (例如：6:2, 上半部分占 6/8, 下半部分占 2/8)
        total_height = self.height()
        vertical_splitter.setSizes(
            [
                total_height * 5 // 8,  # Top section (workspace explorer)
                total_height * 3 // 8,  # Bottom section (commit history, changes, details)
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
        if hasattr(self, "top_bar"):  # Ensure top_bar exists before calling its methods
            self.top_bar.update_toggle_button_icon(self.bottom_widget_visible)

        # 左侧面板显示状态
        self.left_panel_visible = self.settings.settings.get("left_panel_visible", True)
        self.workspace_explorer.set_left_panel_visible(self.left_panel_visible)
        if hasattr(self, "top_bar"):
            self.top_bar.update_toggle_left_panel_icon(self.left_panel_visible)

        # 在初始化完成后，尝试打开上次的文件夹 (this will call update_branches_on_top_bar and update_recent_menu_on_top_bar)
        last_folder = self.settings.get_last_folder()
        if last_folder and os.path.exists(last_folder):
            self.open_folder(last_folder)
        else:
            # If no last folder, still update top_bar for initial state (e.g. disabled buttons)
            self.update_branches_on_top_bar()
            self.update_recent_menu_on_top_bar()

        # Final updates for initial state if not covered by open_folder
        self.update_recent_menu_on_top_bar()
        self.update_branches_on_top_bar()
        if hasattr(self, "top_bar"):
            self.top_bar.update_toggle_button_icon(self.bottom_widget_visible)

        # Ensure notification_widget is initially positioned
        self.reposition_notification_widget()

    def start_watching_folder(self, folder_path):
        """Starts the watchdog observer for the given folder."""
        self.stop_watching_folder()  # Stop any previous observer

        event_handler = GitChangeHandler()
        event_handler.file_changed.connect(self.handle_file_change)
        event_handler.git_changed.connect(self.handle_git_change)

        self.observer = Observer()
        self.observer.schedule(event_handler, folder_path, recursive=True)
        self.observer.start()
        logging.info("Started watching folder for changes: %s", folder_path)

    def stop_watching_folder(self):
        """Stops the watchdog observer if it's running."""
        if self.observer and self.observer.is_alive():
            self.observer.stop()
            self.observer.join()  # Wait for the thread to finish
            self.observer = None
            logging.info("Stopped watching folder.")

    def handle_file_change(self, event_type, path, is_directory):
        """Handles detailed file system change events."""
        logging.debug("File change event: %s - %s (%s)", event_type, path, is_directory)

        # 更新文件索引管理器
        if hasattr(self, "workspace_explorer") and self.workspace_explorer:
            self._handle_file_index_update(event_type, path, is_directory)

        self.schedule_refresh(event_type, path, is_directory)

    def on_edit_file_requested(self, file_path):
        """处理编辑文件请求"""
        try:
            # 构建完整文件路径
            full_path = os.path.join(self.git_manager.repo.working_dir, file_path)
            if os.path.exists(full_path):
                self.workspace_explorer.open_file_in_tab(full_path)
            else:
                logging.warning("File not found: %s", full_path)
        except Exception:
            logging.exception("Error opening file for editing: %s", file_path)

    def _handle_file_index_update(self, event_type, path, is_directory):
        """处理文件变更，更新索引"""
        if is_directory == "directory":
            return  # 忽略目录变更

        try:
            if event_type == "created":
                self.workspace_explorer.file_index_manager.add_file(path, self.workspace_explorer.workspace_path)
            elif event_type == "deleted":
                self.workspace_explorer.file_index_manager.remove_file(path)
            elif event_type == "modified":
                self.workspace_explorer.file_index_manager.update_file(path, self.workspace_explorer.workspace_path)
            elif event_type == "moved":
                # 处理文件移动 - 这需要源路径和目标路径
                # watchdog 的 moved 事件会有 dest_path 属性
                pass
        except Exception:
            logging.exception("更新文件索引时出错")

    def handle_git_change(self, event_type, path):
        """Handles git-specific file system change events."""
        logging.debug("Git change event: %s - %s", event_type, path)
        self.schedule_git_refresh(event_type, path)

    def schedule_refresh(self, event_type=None, path=None, is_directory=None):
        """Schedules a UI refresh, debouncing multiple requests."""
        # 保存参数以便在 _throttled_refresh 中使用
        self._pending_event_type = event_type
        self._pending_path = path
        self._pending_is_directory = is_directory
        self.refresh_timer.start()

    def schedule_git_refresh(self, event_type=None, path=None):
        """Schedules a git history refresh, debouncing multiple requests."""
        # 保存参数以便在 _throttled_git_refresh 中使用
        self._pending_git_event_type = event_type
        self._pending_git_path = path
        self.git_refresh_timer.start()

    def _throttled_refresh(self):
        """The actual refresh method called after a delay."""
        # 获取保存的参数
        event_type = getattr(self, "_pending_event_type", None)
        path = getattr(self, "_pending_path", None)
        is_directory = getattr(self, "_pending_is_directory", None)

        logging.debug("FileSystemWatcher triggered refresh.")
        logging.debug("Refresh parameters: event_type=%s, path=%s, is_directory=%s", event_type, path, is_directory)

        if self.git_manager and self.git_manager.repo:
            logging.info("Window is active, refreshing file tree.")
            self.workspace_explorer.refresh_file_tree()
            self.workspace_explorer.handle_file_event(path, event_type)

        # 清理参数
        self._pending_event_type = None
        self._pending_path = None
        self._pending_is_directory = None

    def _throttled_git_refresh(self):
        """The actual git refresh method called after a delay."""
        # 获取保存的参数
        event_type = getattr(self, "_pending_git_event_type", None)
        path = getattr(self, "_pending_git_path", None)

        logging.debug("Git FileSystemWatcher triggered refresh.")
        logging.debug("Git refresh parameters: event_type=%s, path=%s", event_type, path)

        if self.git_manager and self.git_manager.repo:
            logging.info("Git change detected, refreshing commit history and branches.")
            # 更新提交历史
            self.update_commit_history()
            # 更新分支列表
            self.update_branches_on_top_bar()
            # 刷新工作区状态（可能有新的未跟踪文件等）
            self.workspace_explorer.refresh_file_tree()

        # 清理参数
        self._pending_git_event_type = None
        self._pending_git_path = None

    def show_commit_dialog(self):
        """显示提交对话框"""
        if not self.git_manager:
            return
        self.workspace_explorer.show_commit_dialog()

    # def update_recent_menu(self): # Removed, logic moved to TopBarWidget or adapted
    #     """更新最近文件夹菜单 - This method is now in TopBarWidget"""
    #     # This method will now call self.top_bar.update_recent_menu()
    #     # with self.settings.get_recent_folders()
    #     pass

    def update_recent_menu_on_top_bar(self):
        """Helper to update recent folders on TopBarWidget."""
        if hasattr(self, "top_bar"):
            recent_folders = self.settings.get_recent_folders()
            # Filter out non-existent folders before passing to top_bar
            valid_recent_folders = [f for f in recent_folders if os.path.exists(f)]
            self.top_bar.update_recent_menu(valid_recent_folders)

    def clear_recent_folders(self):
        """清除最近文件夹记录"""
        self.settings.settings["recent_folders"] = []
        self.settings.settings["last_folder"] = None
        self.settings.save_settings()
        # self.update_recent_menu() # Now call the TopBarWidget's method
        self.update_recent_menu_on_top_bar()

    def open_folder_dialog(self):
        """打开文件夹选择对话框"""
        folder_path = QFileDialog.getExistingDirectory(self, self.tr("Select Git Repository"))
        if folder_path:
            self.open_folder(folder_path)

    def open_folder(self, folder_path):
        """打开指定的文件夹"""
        # 关闭所有非提交历史标签页
        while self.tab_widget.count() > 1:
            self.tab_widget.removeTab(1)

        # 关闭 workspace_explorer 中的所有标签页
        if hasattr(self.workspace_explorer, "tab_widget"):
            while self.workspace_explorer.tab_widget.count() > 0:
                self.workspace_explorer.tab_widget.removeTab(0)

        self.git_manager = GitManager(folder_path)
        if self.git_manager.initialize():
            # 添加到最近文件夹列表
            self.settings.add_recent_folder(folder_path)
            self.update_recent_menu_on_top_bar()

            # 更新 UI
            self.update_branches_on_top_bar()
            self.update_commit_history()

            # 更新工作区浏览器
            self.workspace_explorer.git_manager = self.git_manager
            self.workspace_explorer.set_workspace_path(folder_path)
            self.workspace_explorer.git_manager = self.git_manager
            self.workspace_explorer.file_tree.git_manager = self.git_manager
            self.start_watching_folder(folder_path)
            self.setWindowTitle(f"{self.tr('Git Manager')} - {folder_path}")
            # 设置工作目录
            os.chdir(folder_path)
        else:
            self.commit_history_view.history_list.clear()
            self.notification_widget.show_message(f"{self.tr('Selected folder is not a valid Git repository')}")
            if hasattr(self, "top_bar"):
                self.top_bar.set_buttons_enabled(False)  # Disable buttons if repo init fails

    # def update_branches(self): # Partially removed/adapted
    #     """更新分支列表 - This method will now primarily fetch data and call TopBarWidget's update"""
    #     # The part that updates self.branch_combo is removed.
    #     # Data fetching remains.
    #     pass

    def update_branches_on_top_bar(self):
        """Fetches branch data and updates the TopBarWidget."""
        if hasattr(self, "top_bar"):  # Ensure top_bar exists
            if not self.git_manager or not self.git_manager.repo:  # Check if git_manager and its repo are valid
                self.top_bar.update_branches([], None)
                self.top_bar.set_buttons_enabled(False)
                return

            branches = self.git_manager.get_branches()
            default_branch = self.git_manager.get_default_branch()

            # Add "all" option. TopBarWidget's update_branches should handle its placement.
            # Ensure "all" is handled gracefully if it's not a real branch.
            branches_for_combo = [*branches, "all"]

            self.top_bar.update_branches(branches_for_combo, default_branch)
            self.top_bar.set_buttons_enabled(True)

    def update_commit_history(self):
        """更新提交历史"""
        if not self.git_manager:
            return

        current_branch = ""
        if hasattr(self, "top_bar") and self.top_bar:
            current_branch = self.top_bar.get_current_branch()
        else:  # Should not happen if top_bar is initialized correctly
            logging.warning("TopBar not available in update_commit_history")
            return

        if current_branch == "all":  # "all" might be a special value not directly from git branches
            self.commit_history_view.load_history_graph(self.git_manager)
            self.commit_history_view.history_graph_list.show()
            self.commit_history_view.history_list.hide()

        else:
            self.commit_history_view.update_history(self.git_manager, current_branch)
            self.commit_history_view.history_graph_list.hide()
            self.commit_history_view.history_list.show()

    def on_branch_changed(self, branch: str):
        """当分支组合框中的选定分支改变时，尝试切换分支并更新 UI。"""
        if not self.git_manager or not self.git_manager.repo:
            # 如果仓库未加载或无效，则不执行任何操作
            return

        if not branch or branch == self.git_manager.get_default_branch():
            # 如果选择的分支为空或与当前活动分支相同，则不执行任何操作
            # 这也防止了在加载时或以编程方式设置分支组合框时尝试不必要的切换
            # self.update_commit_history() # 仍然更新历史记录，以防万一 (如果 branch_combo 信号本身会触发这个，可能不需要)
            return

        # 尝试切换分支
        error_message = self.git_manager.switch_branch(branch)

        if error_message:
            # 切换失败，显示错误通知
            self.notification_widget.show_message(f"{self.tr('Failed to switch branch')}：{error_message}")
            # 将分支组合框恢复到实际的活动分支
            actual_active_branch = self.git_manager.get_default_branch()
            if actual_active_branch:
                self.top_bar.branch_combo.blockSignals(True)
                self.top_bar.branch_combo.setCurrentText(actual_active_branch)
                self.top_bar.branch_combo.blockSignals(False)
        else:
            # 切换成功
            self.notification_widget.show_message(
                f"{self.tr('Successfully switched to branch')}：{branch}"
            )  # 可选：成功提示
            # 更新 UI 组件以反映分支更改
            logging.debug("on_branch_changed, refresh_file_tree")
            self.workspace_explorer.refresh_file_tree()
            # self.update_branches_on_top_bar() # 确保组合框状态正确（如果需要，但 setCurrentText 应该已处理）
            # update_commit_history 会被连接到 branch_combo 的 activated 信号，
            # 如果我们上面 blockSignals 并手动设置 setCurrentText,
            # 这里的 branch_changed 信号可能不会再次触发 update_commit_history。
            # 因此，在成功切换后显式调用它以确保历史记录已更新。
            self.update_commit_history()
            # 确保 GitManager 内部状态（如果将来有的话）也反映了新分支
            # （目前 get_default_branch() 会从 repo.active_branch 获取，所以应该是最新的）

    def on_commit_selected(self, commit_hash):
        """当选择提交时更新文件变化视图"""
        if not self.git_manager:
            return
        self.current_commit = self.git_manager.repo.commit(commit_hash)
        self.file_changes_view.update_changes(self.git_manager, self.current_commit)
        # cursor 生成 - 同时更新 commit 详细信息视图
        self.commit_detail_view.update_commit_detail(self.git_manager, self.current_commit)

    def on_file_selected(self, file_path, commit_hash=None, other_commit_hash=None, is_comparing_with_workspace=False):
        """当选择文件时，在 TabWidget 中显示比较视图"""
        _commit = self.git_manager.repo.commit(commit_hash) if commit_hash else self.current_commit
        if not _commit or not self.git_manager:
            return
        other_commit = self.git_manager.repo.commit(other_commit_hash) if other_commit_hash else None
        self._on_file_selected(
            file_path, _commit, other_commit=other_commit, is_comparing_with_workspace=is_comparing_with_workspace
        )

    def _on_file_selected(self, file_path, current_commit, other_commit=None, is_comparing_with_workspace=False):
        # 生成一个唯一的标签页标识符，例如 "commit_hash:file_path"
        # 为简化，我们先用 file_path 作为标题，并检查是否已存在
        # 更健壮的方式是存储一个映射：tab_key -> tab_index

        tab_title = os.path.basename(file_path)
        commit_short_hash = current_commit.hexsha[:7]
        unique_tab_title = f"{tab_title} @ {commit_short_hash}"

        # 检查是否已存在具有相同唯一标题的标签页
        for i in range(self.compare_tab_widget.count()):
            if self.compare_tab_widget.tabText(i) == unique_tab_title:
                self.compare_tab_widget.setCurrentIndex(i)
                return

        # 如果不存在，创建新的 CompareView 实例并添加
        compare_view_instance = CompareView(self)
        compare_view_instance.show_diff(
            self.git_manager,
            current_commit,
            file_path,
            other_commit=other_commit,
            is_comparing_with_workspace=is_comparing_with_workspace,
        )

        new_tab_index = self.compare_tab_widget.addTab(compare_view_instance, unique_tab_title)
        self.compare_tab_widget.setCurrentIndex(new_tab_index)

    # def close_compare_tab(self, index):
    #     """关闭比较视图的标签页"""
    #     widget_to_close = self.compare_tab_widget.widget(index)
    #     self.compare_tab_widget.removeTab(index)
    #     if widget_to_close:
    #         widget_to_close.deleteLater() # 确保 Qt 对象被正确删除

    def show_compare_with_working_dialog(self, file_path, commit_hash=None, old_file_path=None):
        """显示与工作区比较的对话框"""
        try:
            _commit = self.git_manager.repo.commit(commit_hash) if commit_hash else self.current_commit
            if not _commit or not self.git_manager:
                return

            # 调用 _on_file_selected 方法，传递 is_comparing_with_workspace=True
            self._on_file_selected(
                old_file_path or file_path, _commit, other_commit=None, is_comparing_with_workspace=True
            )

        except Exception:
            logging.exception("比较文件失败")

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
        # 如果没有保存的分割器状态，则使用默认比例
        if not self.settings.settings.get("vertical_splitter"):
            total_height = self.height()
            # 调整垂直分割器的默认比例
            self.vertical_splitter.setSizes([total_height * 5 // 8, total_height * 3 // 8])
        if not self.settings.settings.get("horizontal_splitter"):  # 主水平分割器
            total_width = self.width()  # 这是上半部分的宽度
            # horizontal_splitter 在 upper_widget 中，其宽度应基于 upper_widget
            # 不过，在初始化时设置比例通常足够，resizeEvent 更多是窗口整体调整后的事情
            # 我们在 __init__ 中已设置了 horizontal_splitter.setSizes
            # 此处可以保持原样或针对性调整
            pass  # horizontal_splitter 的宽度由其父控件和初始比例决定

        self.reposition_notification_widget()

    def reposition_notification_widget(self):
        """Repositions the notification widget, typically called on resize or init."""
        if hasattr(self, "notification_widget") and self.notification_widget:
            x = self.width() - self.notification_widget.width() - 10  # 10 for margin
            y = self.height() - self.notification_widget.height() - 10  # 10 for margin
            self.notification_widget.move(x, y)
            # Ensure it's raised if visible, though show_message handles this too
            if self.notification_widget.isVisible():
                self.notification_widget.raise_()

    def show_settings_dialog(self):
        """显示设置对话框"""
        dialog = SettingsDialog(self)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.show()

    def close_tab(self, index):
        """关闭标签页"""
        # 不允许关闭提交历史标签页 (假设它总是索引 0)
        if index == 0:
            return

        self.tab_widget.removeTab(index)

    def on_tab_changed(self, index):
        """当标签页改变时"""
        widget = self.tab_widget.widget(index)
        right_splitter = self.horizontal_splitter.widget(1)

        if index == 0 or isinstance(widget, FolderHistoryView):
            self.compare_view.hide()
            # cursor 生成 - 显示右侧分割器（包含文件变化视图和 commit 详细信息视图）
            right_splitter.show()
        else:
            self.compare_view.show()
            # cursor 生成 - 隐藏右侧分割器
            right_splitter.hide()

        # 确保提交历史和文件历史有相同的宽度
        # 保存当前的分割器大小比例，以便在切换标签时保持一致
        current_sizes = self.horizontal_splitter.sizes()
        min_widgets_count = 2
        if len(current_sizes) >= min_widgets_count:
            # 计算左侧面板应该占据的固定宽度
            total_width = sum(current_sizes)
            left_panel_width = total_width // 3  # 固定为总宽度的1/3

            if index == 0 or isinstance(widget, FolderHistoryView):
                # 提交历史标签页：左侧1/3，右侧2/3
                self.horizontal_splitter.setSizes([left_panel_width, total_width - left_panel_width, 0])
            else:
                # 文件历史标签页：左侧1/3，右侧隐藏，对比视图占据剩余空间
                self.horizontal_splitter.setSizes([left_panel_width, 0, total_width - left_panel_width])

    def toggle_bottom_widget(self):
        """切换底部面板的显示状态"""
        self.bottom_widget_visible = not self.bottom_widget_visible
        self.bottom_widget.setVisible(self.bottom_widget_visible)
        if hasattr(self, "top_bar"):
            self.top_bar.update_toggle_button_icon(self.bottom_widget_visible)

        # 保存状态到设置
        self.settings.settings["bottom_widget_visible"] = self.bottom_widget_visible
        self.settings.save_settings()

    def toggle_left_panel(self):
        """切换左侧面板（文件树）显示状态"""
        self.left_panel_visible = not self.left_panel_visible
        self.workspace_explorer.set_left_panel_visible(self.left_panel_visible)
        if hasattr(self, "top_bar"):
            self.top_bar.update_toggle_left_panel_icon(self.left_panel_visible)
        self.settings.settings["left_panel_visible"] = self.left_panel_visible
        self.settings.save_settings()

    def fetch_repo(self):
        """获取仓库（使用线程）"""
        if not self.git_manager:
            return

        if hasattr(self, "top_bar") and self.top_bar:
            self.start_spinning()
        QApplication.processEvents()  # Ensure UI updates like spinner start

        self.fetch_thread = FetchThread(self.git_manager)
        self.fetch_thread.finished.connect(self.handle_fetch_finished)
        self.fetch_thread.start()

    def handle_fetch_finished(self, success, error_message):
        """处理 fetch 操作完成"""
        try:
            if not success and error_message:
                self.notification_widget.show_message(f"{self.tr('Fetch failed')}：{error_message}")
                logging.error(f"Fetch failed: {error_message}")
            elif success:
                self.notification_widget.show_message(f"{self.tr('Fetch successful')}.")
                logging.info("Fetch successful.")
                self.update_commit_history()  # Update history as fetch can update remote-tracking branches
        finally:
            self.stop_spinning()
            QApplication.processEvents()  # Ensure UI updates like spinner stop

    def pull_repo(self):
        """拉取仓库（使用线程）"""
        if not self.git_manager:
            return

        # 显示加载动画
        if hasattr(self, "top_bar") and self.top_bar:
            self.start_spinning()
            QApplication.processEvents()

        # 创建并启动线程
        self.pull_thread = PullThread(self.git_manager)
        self.pull_thread.finished.connect(self.handle_pull_finished)
        self.pull_thread.start()

    def handle_pull_finished(self, success, error_message):
        """处理 pull 操作完成"""
        try:
            if success:
                self.update_commit_history()
                # Optionally show success: self.notification_widget.show_message("Pull successful.")
                logging.info("Pull successful.")
            elif error_message:  # Only show notification if there's an error message
                self.notification_widget.show_message(f"{self.tr('Pull failed')}：{error_message}")
                logging.error(f"Pull failed: {error_message}")  # More specific logging
        finally:
            # 停止加载动画
            if hasattr(self, "top_bar") and self.top_bar:
                self.stop_spinning()
            QApplication.processEvents()  # Ensure UI updates

    def push_repo(self):
        """推送仓库"""
        if not self.git_manager:
            # Consider disabling push button via top_bar if no git_manager
            return
        if hasattr(self, "top_bar") and self.top_bar:
            self.start_spinning()
            QApplication.processEvents()  # Ensure UI updates
        # 创建并启动线程
        self.push_thread = PushThread(self.git_manager)
        self.push_thread.finished.connect(self.handle_push_finished)
        self.push_thread.start()

    def on_project_button_clicked(self):
        """处理工程按钮点击事件"""
        self.workspace_explorer.show_file_tree()

    def on_commit_button_clicked(self):
        """处理提交按钮点击事件"""
        if hasattr(self, "top_bar"):
            self.top_bar.commit_requested.emit()

    def on_changes_button_clicked(self):
        """处理变更按钮点击事件"""
        self.workspace_explorer.show_file_changes_view()

    def on_search_button_clicked(self):
        """处理搜索按钮点击事件"""
        self.workspace_explorer.show_file_search_widget()

    def handle_push_finished(self, success, error_message):
        """处理 push 操作完成"""
        try:
            if success:
                self.update_commit_history()
                self.notification_widget.show_message(f"{self.tr('Push successful')}.")
                logging.info("Push successful.")
            elif error_message:  # Only show notification if there's an error message
                self.notification_widget.show_message(f"{self.tr('Push failed')}：{error_message}")
                logging.error(f"Push failed: {error_message}")  # More specific logging
        finally:
            # 停止加载动画
            if hasattr(self, "top_bar") and self.top_bar:
                self.stop_spinning()
            QApplication.processEvents()  # Ensure UI updates

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
        self.commit_history_view.clear_search()

        short_hash_to_find = commit_hash[:7]
        found_item = None

        # Initial search
        # 初始搜索：遍历当前已加载的提交项
        for i in range(history_list.topLevelItemCount()):
            item = history_list.topLevelItem(i)
            if item:
                # 从 UserRole 获取完整哈希值进行比较
                full_hash_in_item = item.data(0, Qt.ItemDataRole.UserRole)
                if full_hash_in_item and full_hash_in_item.startswith(short_hash_to_find):
                    found_item = item
                    break

        # If not found and not all commits are loaded, try loading more
        # 如果未找到且并非所有提交都已加载，则尝试加载更多
        if not found_item and not self.commit_history_view._all_loaded:
            logging.info(
                "GitManagerWindow: Commit %s not found initially, attempting to load more commits.",
                short_hash_to_find,
            )
            while not found_item and not self.commit_history_view._all_loaded:
                self.commit_history_view.load_more_commits()  # 加载更多批次的提交
                # Re-search after loading more
                # 重新搜索（包括新加载的项）
                for i in range(history_list.topLevelItemCount()):
                    item = history_list.topLevelItem(i)
                    if item:
                        full_hash_in_item = item.data(0, Qt.ItemDataRole.UserRole)
                        if full_hash_in_item and full_hash_in_item.startswith(short_hash_to_find):
                            found_item = item
                            break  # 找到后跳出内部循环
                if found_item:
                    logging.info("GitManagerWindow: Found commit %s after loading more.", short_hash_to_find)
                    break  # 找到后跳出外部 while 循环
                if self.commit_history_view._all_loaded:
                    logging.info(
                        "GitManagerWindow: All commits loaded, but commit %s still not found.",
                        short_hash_to_find,
                    )
                    break  # 如果所有提交已加载但仍未找到，则跳出循环

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
        # 移除基于窗口激活的文件树刷新逻辑，因为现在使用文件监控自动刷新

    def closeEvent(self, event):
        """Ensure the watchdog observer is stopped on close."""
        self.save_splitter_state()
        # 保存 WorkspaceExplorer 的分割器状态
        if hasattr(self, "workspace_explorer") and self.workspace_explorer:
            self.workspace_explorer.save_splitter_state()
        self.stop_watching_folder()
        super().closeEvent(event)

    def keyPressEvent(self, event):
        """Handle key press events for shortcuts."""
        # Check for Command + Shift + F (Mac) or Control + Shift + F (Windows/Linux)
        is_f_key = event.key() == Qt.Key.Key_F
        is_shift = event.modifiers() & Qt.KeyboardModifier.ShiftModifier

        # Check for Control on Windows/Linux OR Command on Mac
        is_primary_modifier = (event.modifiers() & Qt.KeyboardModifier.ControlModifier) or (
            event.modifiers() & Qt.KeyboardModifier.MetaModifier
        )

        if is_f_key and is_shift and is_primary_modifier:
            self.side_bar.search_btn.click()
        else:
            super().keyPressEvent(event)

    def start_spinning(self):
        self.spinner_label.show()

    def stop_spinning(self):
        self.spinner_label.hide()
