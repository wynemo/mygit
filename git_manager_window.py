import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QFont
from PyQt6.QtWidgets import (QComboBox, QFileDialog, QHBoxLayout, QLabel,
                             QListWidget, QMainWindow, QMenu, QPushButton,
                             QSplitter, QToolButton, QTreeWidget,
                             QTreeWidgetItem, QVBoxLayout, QWidget, QDialog,
                             QFormLayout, QDialogButtonBox, QLineEdit)

from commit_graph import CommitGraphView
from diff_calculator import GitDiffCalculator
from git_manager import GitManager
from settings import Settings
from commit_dialog import CommitDialog
from settings_dialog import SettingsDialog
from text_diff_viewer import DiffViewer, MergeDiffViewer


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

        # 添加设置按钮
        self.settings_button = QToolButton()

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

        # 左侧提交历史区域
        left_widget = QWidget()
        left_widget.setMinimumWidth(200)  # 设置最小宽度
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(5, 5, 5, 5)
        left_widget.setLayout(left_layout)

        self.history_label = QLabel("提交历史:")
        left_layout.addWidget(self.history_label)
        # Replace QListWidget with QTreeWidget
        self.history_list = QTreeWidget()
        self.history_list.setHeaderLabels(["提交ID", "提交信息", "作者", "日期"])
        self.history_list.itemClicked.connect(self.on_commit_clicked)
        # Set column widths
        self.history_list.setColumnWidth(0, 80)  # Hash
        self.history_list.setColumnWidth(1, 200)  # Message
        self.history_list.setColumnWidth(2, 100)  # Author
        self.history_list.setColumnWidth(3, 150)  # Date
        left_layout.addWidget(self.history_list)

        # 替换原来的 history_list
        self.history_graph_list = CommitGraphView()
        self.history_graph_list.setHeaderLabels(["提交图", "提交ID", "提交信息", "作者", "日期"])
        self.history_graph_list.itemClicked.connect(self.on_commit_clicked)
        left_layout.addWidget(self.history_graph_list)

        # 设置列宽
        self.history_graph_list.setColumnWidth(0, 150)  # 图形列
        self.history_graph_list.setColumnWidth(1, 80)   # Hash
        self.history_graph_list.setColumnWidth(2, 200)  # Message
        self.history_graph_list.setColumnWidth(3, 100)  # Author
        self.history_graph_list.setColumnWidth(4, 150)  # Date

        self.history_graph_list.hide()  # 默认隐藏提交图视图

        # 右侧文件变化区域
        right_widget = QWidget()
        right_widget.setMinimumWidth(200)  # 设置最小宽度
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(5, 5, 5, 5)
        right_widget.setLayout(right_layout)

        self.changes_label = QLabel("文件变化:")
        right_layout.addWidget(self.changes_label)

        self.changes_tree = QTreeWidget()
        self.changes_tree.setHeaderLabels(["文件", "状态"])
        self.changes_tree.setColumnCount(2)
        self.changes_tree.itemClicked.connect(self.on_file_clicked)
        right_layout.addWidget(self.changes_tree)

        self.changes_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.changes_tree.customContextMenuRequested.connect(self.show_file_context_menu)

        # 添加左右部件到水平分割器
        horizontal_splitter.addWidget(left_widget)
        horizontal_splitter.addWidget(right_widget)

        # 设置水平分割器的初始大小比例 (1:2)
        total_width = self.width()
        horizontal_splitter.setSizes([total_width // 3, total_width * 2 // 3])

        # 添加上半部分到垂直分割器
        vertical_splitter.addWidget(upper_widget)

        # 下半部分：文件差异查看区域
        self.diff_viewer = DiffViewer()
        self.merge_diff_viewer = MergeDiffViewer()
        self.merge_diff_viewer.hide()  # 默认隐藏三向对比视图

        diff_container = QWidget()
        diff_layout = QVBoxLayout()
        diff_layout.setContentsMargins(0, 0, 0, 0)
        diff_container.setLayout(diff_layout)
        diff_layout.addWidget(self.diff_viewer)
        diff_layout.addWidget(self.merge_diff_viewer)

        vertical_splitter.addWidget(diff_container)

        # 设置垂直分割器的初始大小比例 (2:3)
        total_height = self.height()
        vertical_splitter.setSizes([total_height * 2 // 5, total_height * 3 // 5])

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

    def show_file_context_menu(self, position):
        """显示文件的右键菜单"""
        item = self.changes_tree.itemAt(position)
        if item and item.childCount() == 0:  # Only show menu for files, not directories
            menu = QMenu()
        
        # Create menu actions
        view_action = QAction("查看文件", self)
        copy_path_action = QAction("复制文件路径", self)
        revert_action = QAction("还原更改", self)
        compare_action = QAction("与工作区比较", self)  # 新增菜单项
        
        # Add actions to menu
        menu.addAction(view_action)
        menu.addAction(copy_path_action)
        menu.addAction(revert_action)
        menu.addAction(compare_action)  # 添加到菜单
        
        # Connect actions to placeholder functions
        view_action.triggered.connect(lambda: print(f"查看文件: {self.get_full_path(item)}"))
        copy_path_action.triggered.connect(lambda: print(f"复制路径: {self.get_full_path(item)}"))
        revert_action.triggered.connect(lambda: print(f"还原更改: {self.get_full_path(item)}"))
        compare_action.triggered.connect(lambda: self.compare_with_working(item))
        
        # Show the menu at cursor position
        menu.exec(self.changes_tree.viewport().mapToGlobal(position))

    def compare_with_working(self, item):
        """比较选中的历史版本文件与工作区文件"""
        try:
            file_path = self.get_full_path(item)
        
            # 获取历史版本的文件内容
            old_content = (
                self.current_commit.tree[file_path]
                .data_stream.read()
                .decode("utf-8", errors="replace")
            )
            
            # 获取工作区的文件内容
            working_file_path = os.path.join(self.git_manager.repo.working_dir, file_path)
            if os.path.exists(working_file_path):
                with open(working_file_path, 'r', encoding='utf-8', errors='replace') as f:
                    new_content = f.read()
            else:
                new_content = ""

            # 创建并显示比较对话框
            dialog = CompareWithWorkingDialog(
                f"比较 {file_path}",
                old_content,
                new_content,
                self
            )
            dialog.exec()
        
        except Exception as e:
            print(f"比较文件失败: {str(e)}")

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
        else:
            self.history_list.clear()
            self.history_list.addItem("所选文件夹不是有效的Git仓库")

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
            self.history_graph_list.clear()
            self.history_list.hide()
            self.history_graph_list.show()
            graph_data = self.git_manager.get_commit_graph("main")
    
            # 设置提交图数据
            self.history_graph_list.set_commit_data(graph_data)
        
            # 添加提交信息到列表
            for commit in graph_data['commits']:
                item = QTreeWidgetItem(self.history_graph_list)
                item.setText(1, commit['hash'][:7])
                item.setText(2, commit['message'])
                item.setText(3, commit['author'])
                item.setText(4, commit['date'])
        else:
            self.history_list.clear()
            self.history_graph_list.hide()
            self.history_list.show()
            commits = self.git_manager.get_commit_history(current_branch)

            for commit in commits:
                item = QTreeWidgetItem(self.history_list)
                item.setText(0, commit['hash'][:7])
                item.setText(1, commit['message'])
                item.setText(2, commit['author'])
                item.setText(3, commit['date'])

    def on_branch_changed(self, branch):
        """当分支改变时更新提交历史"""
        if self.git_manager:
            self.update_commit_history()

    def add_file_to_tree(self, path_parts, status, parent=None):
        """递归添加文件到树形结构"""
        if not path_parts:
            return

        # 检查当前层级是否已存在
        current_part = path_parts[0]
        found_item = None

        if parent is None:
            root = self.changes_tree.invisibleRootItem()
            for i in range(root.childCount()):
                if root.child(i).text(0) == current_part:
                    found_item = root.child(i)
                    break
        else:
            for i in range(parent.childCount()):
                if parent.child(i).text(0) == current_part:
                    found_item = parent.child(i)
                    break

        if found_item is None:
            # 创建新项
            if parent is None:
                found_item = QTreeWidgetItem(self.changes_tree)
            else:
                found_item = QTreeWidgetItem(parent)
            found_item.setText(0, current_part)

            # 只在叶子节点显示状态
            if len(path_parts) == 1:
                found_item.setText(1, status)

        # 递归处理剩余路径
        if len(path_parts) > 1:
            self.add_file_to_tree(path_parts[1:], status, found_item)

    def on_commit_clicked(self, item):
        """当点击提交历史项时显示文件变化"""
        if not self.git_manager or not self.git_manager.repo:
            return

        # 从item文本中提取commit hash
        commit_hash = item.text(0) or item.text(1)
        # print(f'commit_hash is {commit_hash} text is {item.text(0)}')
        self.current_commit = self.git_manager.repo.commit(commit_hash)

        try:
            # 获取父提交
            parent = (
                self.current_commit.parents[0] if self.current_commit.parents else None
            )

            # 清空之前的显示
            self.changes_tree.clear()

            if parent:
                # 获取与父提交的差异
                diff = parent.diff(self.current_commit)
                for change in diff:
                    path_parts = change.a_path.split("/")
                    self.add_file_to_tree(path_parts, change.change_type)
            else:
                # 如果是第一个提交,显示所有文件
                for item in self.current_commit.tree.traverse():
                    if item.type == "blob":  # 只显示文件,不显示目录
                        path_parts = item.path.split("/")
                        self.add_file_to_tree(path_parts, "新增")

            # 展开所有项
            self.changes_tree.expandAll()

            # 调整列宽以适应内容
            self.changes_tree.resizeColumnToContents(0)
            self.changes_tree.resizeColumnToContents(1)

            # 清空差异显示
            # self.diff_viewer.clear()

        except Exception as e:
            self.changes_tree.clear()
            error_item = QTreeWidgetItem(self.changes_tree)
            error_item.setText(0, f"获取文件变化失败: {str(e)}")

    def get_full_path(self, item):
        """获取树形项的完整路径"""
        path_parts = []
        while item:
            path_parts.insert(0, item.text(0))
            item = item.parent()
        return "/".join(path_parts)

    def on_file_clicked(self, item):
        """当点击文件项时显示文件差异"""
        if not self.current_commit or not item or item.childCount() > 0:
            return

        try:
            file_path = self.get_full_path(item)
            parents = self.current_commit.parents

            # 获取当前提交的文件内容
            try:
                current_content = (
                    self.current_commit.tree[file_path]
                    .data_stream.read()
                    .decode("utf-8", errors="replace")
                )
            except KeyError:
                print(f"File {file_path} not found in current commit tree.")
                current_content = ""
            except Exception as e:
                print(f"Error reading current content for {file_path}: {e}")
                return

            # 获取父提交的文件内容
            parent_content = ""
            if parents:
                try:
                    parent_content = (
                        parents[0]
                        .tree[file_path]
                        .data_stream.read()
                        .decode("utf-8", errors="replace")
                    )
                except KeyError:
                    pass
                except Exception as e:
                    print(f"Error reading parent content for {file_path}: {e}")
                    parent_content = ""

            # 获取 git diff 输出
            git_diff_output = None
            if parents:
                try:
                    git_diff_output = self.git_manager.repo.git.diff(
                        parents[0].hexsha, self.current_commit.hexsha, "--", file_path
                    )
                except Exception as e:
                    print(f"Error getting git diff for {file_path}: {e}")

            # 根据父提交数量自动判断使用双向还是三向对比
            if len(parents) <= 1:
                # 使用双向对比
                self.diff_viewer.show()
                self.merge_diff_viewer.hide()
                diff_calculator = GitDiffCalculator(git_diff_output)
                self.diff_viewer.diff_calculator = diff_calculator
                self.diff_viewer.set_texts(parent_content, current_content)
            else:
                # 使用三向对比
                self.diff_viewer.hide()
                self.merge_diff_viewer.show()

                # 获取第二个父提交的内容
                parent2_content = ""
                git_diff_output2 = None
                try:
                    parent2_content = (
                        parents[1]
                        .tree[file_path]
                        .data_stream.read()
                        .decode("utf-8", errors="replace")
                    )
                    # 获取第二个父提交的差异
                    git_diff_output2 = self.git_manager.repo.git.diff(
                        parents[1].hexsha, self.current_commit.hexsha, "--", file_path
                    )
                except KeyError:
                    pass
                except Exception as e:
                    print(f"Error reading parent2 content for {file_path}: {e}")

                # 为三向对比创建两个差异计算器
                diff_calculator1 = GitDiffCalculator(git_diff_output)
                diff_calculator2 = GitDiffCalculator(git_diff_output2)
                # todo 这个感觉有问题，ai估计每处理好

                # 设置差异计算器
                self.merge_diff_viewer.diff_calculator = diff_calculator1
                self.merge_diff_viewer.set_texts(
                    parent_content, current_content, parent2_content
                )

        except Exception as e:
            print(f"Error displaying file diff for {item.text(0)}: {e}")
            import traceback

            traceback.print_exc()

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


class CompareWithWorkingDialog(QDialog):
    def __init__(self, title, old_content, new_content, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(800, 600)
        
        layout = QVBoxLayout(self)
        self.diff_viewer = DiffViewer()
        layout.addWidget(self.diff_viewer)
        
        self.diff_viewer.set_texts(old_content, new_content)
