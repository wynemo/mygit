import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

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
        top_layout.addWidget(self.commit_button)

        # 创建设置按钮
        self.settings_button = QToolButton()
        self.settings_button.setText("⚙")  # 使用齿轮符号
        self.settings_button.clicked.connect(self.show_settings_dialog)
        top_layout.addWidget(self.settings_button)

        # 创建垂直分割器
        vertical_splitter = QSplitter(Qt.Orientation.Vertical)
        vertical_splitter.setChildrenCollapsible(False)
        vertical_splitter.setOpaqueResize(False)  # 添加平滑调整
        vertical_splitter.setHandleWidth(8)  # 增加分割条宽度，更容易拖动
        main_layout.addWidget(vertical_splitter)

        # 上半部分容器
        upper_widget = QWidget()
        upper_widget.setMinimumHeight(100)  # 设置最小高度
        upper_layout = QHBoxLayout()
        upper_layout.setContentsMargins(0, 0, 0, 0)
        upper_widget.setLayout(upper_layout)

        # 创建水平分割器（用于提交历史和文件变化）
        horizontal_splitter = QSplitter(Qt.Orientation.Horizontal)
        horizontal_splitter.setChildrenCollapsible(False)
        horizontal_splitter.setOpaqueResize(False)  # 添加平滑调整
        horizontal_splitter.setHandleWidth(8)  # 增加分割条宽度，更容易拖动
        upper_layout.addWidget(horizontal_splitter)

        # 创建主要视图组件
        self.commit_history_view = CommitHistoryView()
        self.file_changes_view = FileChangesView()
        self.compare_view = CompareView()

        # 连接信号
        self.commit_history_view.commit_selected.connect(self.on_commit_selected)
        self.file_changes_view.file_selected.connect(self.on_file_selected)
        self.file_changes_view.compare_with_working_requested.connect(
            self.show_compare_with_working_dialog
        )

        # 添加到布局
        horizontal_splitter.addWidget(self.commit_history_view)
        horizontal_splitter.addWidget(self.file_changes_view)

        # 添加上半部分到垂直分割器
        vertical_splitter.addWidget(upper_widget)

        # 添加工作区浏览器
        self.workspace_explorer = WorkspaceExplorer()
        vertical_splitter.addWidget(self.workspace_explorer)

        # 添加比较视图
        vertical_splitter.addWidget(self.compare_view)

        # 调整垂直分割器的比例(2:3:3)
        total_height = self.height()
        vertical_splitter.setSizes(
            [
                total_height * 2 // 8,  # 提交历史区域
                total_height * 3 // 8,  # diff查看区域
                total_height * 3 // 8,  # 工作区浏览器
            ]
        )

        # 设置水平分割器的初始大小比例 (1:2)
        total_width = self.width()
        horizontal_splitter.setSizes([total_width // 3, total_width * 2 // 3])

        # 保存分割器引用以便后续使用
        self.vertical_splitter = vertical_splitter
        self.horizontal_splitter = horizontal_splitter

        # 从设置中恢复分割器状态
        self.restore_splitter_state()

        # 在窗口关闭时保存分割器状态
        self.destroyed.connect(self.save_splitter_state)

        # 在初始化完成后，尝试打开上次的文件夹
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
        else:
            self.commit_history_view.history_list.clear()
            self.commit_history_view.history_list.addItem("所选文件夹不是有效的Git仓库")

    def update_branches(self):
        """更新分支列表"""
        self.branch_combo.clear()
        branches = self.git_manager.get_branches()
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

    def on_file_selected(self, file_path):
        """当选择文件时更新比较视图"""
        if not self.current_commit:
            return
        self.compare_view.show_diff(self.git_manager, self.current_commit, file_path)

    def show_compare_with_working_dialog(self, file_path):
        """显示与工作区比较的对话框"""
        try:
            # 获取历史版本的文件内容
            old_content = (
                self.current_commit.tree[file_path]
                .data_stream.read()
                .decode("utf-8", errors="replace")
            )

            # 获取工作区的文件内容
            working_file_path = os.path.join(
                self.git_manager.repo.working_dir, file_path
            )
            if os.path.exists(working_file_path):
                with open(
                    working_file_path, "r", encoding="utf-8", errors="replace"
                ) as f:
                    new_content = f.read()
            else:
                new_content = ""

            # 创建并显示比较对话框
            # todo 这个要改造，看readme里的todo
            dialog = CompareWithWorkingDialog(
                f"比较 {file_path}", old_content, new_content, self
            )
            dialog.exec()

        except Exception as e:
            print(f"比较文件失败: {str(e)}")

    def save_splitter_state(self):
        """保存所有分割器的状态"""
        self.settings.settings["vertical_splitter"] = [
            pos for pos in self.vertical_splitter.sizes()
        ]
        self.settings.settings["horizontal_splitter"] = [
            pos for pos in self.horizontal_splitter.sizes()
        ]
        self.settings.save_settings()

    def restore_splitter_state(self):
        """恢复所有分割器的状态"""
        # 恢复垂直分割器状态
        vertical_sizes = self.settings.settings.get("vertical_splitter")
        if vertical_sizes:
            self.vertical_splitter.setSizes(vertical_sizes)

        # 恢复水平分割器状态
        horizontal_sizes = self.settings.settings.get("horizontal_splitter")
        if horizontal_sizes:
            self.horizontal_splitter.setSizes(horizontal_sizes)

    def resizeEvent(self, event):
        """处理窗口大小改变事件"""
        super().resizeEvent(event)
        # 如果没有保存的分割器状态,则使用默认比例
        if not self.settings.settings.get("vertical_splitter"):
            total_height = self.height()
            # 调整比例，让下半部分占据更多空间
            self.vertical_splitter.setSizes(
                [total_height * 1 // 3, total_height * 2 // 3]
            )
        if not self.settings.settings.get("horizontal_splitter"):
            total_width = self.width()
            self.horizontal_splitter.setSizes([total_width // 3, total_width * 2 // 3])

    def show_settings_dialog(self):
        """显示设置对话框"""
        dialog = SettingsDialog(self)
        dialog.exec()
