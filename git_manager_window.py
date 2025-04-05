import os
from PyQt6.QtWidgets import (QMainWindow, QFileDialog, QVBoxLayout, 
                           QWidget, QPushButton, QListWidget, QHBoxLayout, 
                           QLabel, QComboBox, QSplitter, QTreeWidget, QTreeWidgetItem,
                           QTextEdit, QMenu, QToolButton)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from git_manager import GitManager
from diff_viewer import DiffTextEdit
from settings import Settings
from syntax_highlighter import format_diff_content

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
        top_widget.setFixedHeight(40)  # 固定顶部高度
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
        self.history_list = QListWidget()
        self.history_list.itemClicked.connect(self.on_commit_clicked)
        left_layout.addWidget(self.history_list)
        
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
        
        # 添加左右部件到水平分割器
        horizontal_splitter.addWidget(left_widget)
        horizontal_splitter.addWidget(right_widget)
        
        # 设置水平分割器的初始大小比例 (1:2)
        total_width = self.width()
        horizontal_splitter.setSizes([total_width // 3, total_width * 2 // 3])
        
        # 添加上半部分到垂直分割器
        vertical_splitter.addWidget(upper_widget)
        
        # 下半部分：文件差异查看区域
        diff_widget = QWidget()
        diff_widget.setMinimumHeight(100)  # 设置最小高度
        diff_layout = QHBoxLayout()
        diff_layout.setContentsMargins(0, 0, 0, 0)
        diff_widget.setLayout(diff_layout)
        
        # 创建水平分割器用于显示文件差异
        diff_splitter = QSplitter(Qt.Orientation.Horizontal)
        diff_splitter.setChildrenCollapsible(False)
        diff_splitter.setOpaqueResize(False)  # 添加平滑调整
        diff_splitter.setHandleWidth(8)  # 增加分割条宽度，更容易拖动
        diff_layout.addWidget(diff_splitter)
        
        # 左侧差异文本框
        self.left_diff = DiffTextEdit()
        self.left_diff.setReadOnly(True)
        self.left_diff.setMinimumWidth(200)  # 设置最小宽度
        diff_splitter.addWidget(self.left_diff)
        
        # 中间差异文本框（用于merge情况）
        self.middle_diff = DiffTextEdit()
        self.middle_diff.setReadOnly(True)
        self.middle_diff.setMinimumWidth(200)  # 设置最小宽度
        self.middle_diff.hide()  # 默认隐藏
        diff_splitter.addWidget(self.middle_diff)
        
        # 右侧差异文本框
        self.right_diff = DiffTextEdit()
        self.right_diff.setReadOnly(True)
        self.right_diff.setMinimumWidth(200)  # 设置最小宽度
        diff_splitter.addWidget(self.right_diff)
        
        # 设置文本框之间的滚动同步
        self.setup_diff_sync()
        
        # 添加下半部分到垂直分割器
        vertical_splitter.addWidget(diff_widget)
        
        # 设置垂直分割器的初始大小比例 (2:3)
        total_height = self.height()
        vertical_splitter.setSizes([total_height * 2 // 5, total_height * 3 // 5])
        
        # 保存分割器引用以便后续使用
        self.vertical_splitter = vertical_splitter
        self.horizontal_splitter = horizontal_splitter
        self.diff_splitter = diff_splitter
        
        # 从设置中恢复分割器状态
        self.restore_splitter_state()
        
        # 在窗口关闭时保存分割器状态
        self.destroyed.connect(self.save_splitter_state)
        
        # 在初始化完成后，尝试打开上次的文件夹
        last_folder = self.settings.get_last_folder()
        if last_folder and os.path.exists(last_folder):
            self.open_folder(last_folder)
        
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
        self.settings.settings['recent_folders'] = []
        self.settings.settings['last_folder'] = None
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
        
    def update_commit_history(self):
        """更新提交历史"""
        self.history_list.clear()
        if not self.git_manager:
            return
            
        current_branch = self.branch_combo.currentText()
        commits = self.git_manager.get_commit_history(current_branch)
        
        for commit in commits:
            item_text = f"{commit['hash'][:7]} - {commit['message']}\n"
            item_text += f"作者: {commit['author']} 日期: {commit['date']}"
            self.history_list.addItem(item_text)
            
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
        commit_hash = item.text().split()[0]
        self.current_commit = self.git_manager.repo.commit(commit_hash)
        
        try:
            # 获取父提交
            parent = self.current_commit.parents[0] if self.current_commit.parents else None
            
            # 清空之前的显示
            self.changes_tree.clear()
            
            if parent:
                # 获取与父提交的差异
                diff = parent.diff(self.current_commit)
                for change in diff:
                    path_parts = change.a_path.split('/')
                    self.add_file_to_tree(path_parts, change.change_type)
            else:
                # 如果是第一个提交,显示所有文件
                for item in self.current_commit.tree.traverse():
                    if item.type == 'blob':  # 只显示文件,不显示目录
                        path_parts = item.path.split('/')
                        self.add_file_to_tree(path_parts, "新增")
                        
            # 展开所有项
            self.changes_tree.expandAll()
            
            # 调整列宽以适应内容
            self.changes_tree.resizeColumnToContents(0)
            self.changes_tree.resizeColumnToContents(1)
            
            # 清空差异显示
            self.left_diff.clear()
            self.middle_diff.clear()
            self.right_diff.clear()
                        
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
        return '/'.join(path_parts)
            
    def setup_diff_sync(self):
        """设置差异文本框之间的滚动同步"""
        # 左右文本框互相同步
        self.left_diff.add_sync_scroll(self.right_diff)
        self.right_diff.add_sync_scroll(self.left_diff)
        
        # 中间文本框与左右都同步
        self.middle_diff.add_sync_scroll(self.left_diff)
        self.middle_diff.add_sync_scroll(self.right_diff)
        self.left_diff.add_sync_scroll(self.middle_diff)
        self.right_diff.add_sync_scroll(self.middle_diff)
        
    def on_file_clicked(self, item):
        """当点击文件项时显示文件差异 (Revised Implementation)"""
        if not self.current_commit or not item or item.childCount() > 0:
            return
            
        try:
            file_path = self.get_full_path(item)
            parents = self.current_commit.parents
            is_merge = len(parents) > 1
            
            # Default contents
            old_content = ""
            new_content = ""
            parent1_content = "" # For merge base (optional, could use parent[0])
            parent2_content = "" # For merge source
            
            # --- Fetch Content ---
            try:
                new_content = self.current_commit.tree[file_path].data_stream.read().decode('utf-8', errors='replace')
            except KeyError:
                 # File might have been deleted in this commit, check diff status
                 print(f"File {file_path} not found in current commit tree.")
                 # If deleted, new_content remains ""
            except Exception as e:
                 print(f"Error reading current content for {file_path}: {e}")
                 self.left_diff.setPlainText(f"Error reading current content:\n{e}")
                 self.middle_diff.clear()
                 self.right_diff.clear()
                 return

            if is_merge:
                try:
                    parent1_content = parents[0].tree[file_path].data_stream.read().decode('utf-8', errors='replace')
                except KeyError: pass # File might not exist in parent 1
                except Exception as e: print(f"Error reading parent1 content: {e}")
                try:
                    parent2_content = parents[1].tree[file_path].data_stream.read().decode('utf-8', errors='replace')
                except KeyError: pass # File might not exist in parent 2
                except Exception as e: print(f"Error reading parent2 content: {e}")
                # For 3-way diff, 'old_content' often refers to the common ancestor (base)
                # Finding the merge base can be complex, let's stick to comparing parents to current for now
                old_content = parent1_content # Left view compares parent1 vs current
                # Middle view shows current
                # Right view compares parent2 vs current
                
            elif parents: # Single parent commit
                try:
                    old_content = parents[0].tree[file_path].data_stream.read().decode('utf-8', errors='replace')
                except KeyError: 
                     # File added in this commit, old_content remains ""
                     pass 
                except Exception as e:
                    print(f"Error reading parent content for {file_path}: {e}")
                    old_content = f"(Error reading parent content: {e})"
            else: # Initial commit
                 old_content = "" # No parent, so old content is empty

            # --- 清空并重置滚动条 ---
            self.left_diff.clear()
            self.middle_diff.clear()
            self.right_diff.clear()
            self.left_diff.verticalScrollBar().setValue(0)
            self.middle_diff.verticalScrollBar().setValue(0)
            self.right_diff.verticalScrollBar().setValue(0)

            # --- 处理并显示内容 ---
            if is_merge:
                self.middle_diff.show()

                # --- 计算高亮所需差异 ---
                # 1. 比较 Parent 1 vs New Content, 获取 P1 删除/修改的行 (old1) 和 New 新增/修改的行 (new1)
                old_line_info1, new_line_info1 = format_diff_content(parent1_content, new_content)
                # 2. 比较 Parent 2 vs New Content, 获取 P2 删除/修改的行 (old2) 和 New 新增/修改的行 (new2)
                old_line_info2, new_line_info2 = format_diff_content(parent2_content, new_content)

                # --- 计算中间视图的综合高亮信息 --- 
                middle_highlight_info = []
                dict_new_info1 = dict(new_line_info1) # 转为字典以提高查找效率
                dict_new_info2 = dict(new_line_info2)
                num_lines_new = len(new_content.splitlines())

                for ln in range(1, num_lines_new + 1):
                    status1 = dict_new_info1.get(ln, 'normal')
                    status2 = dict_new_info2.get(ln, 'normal')
                    final_status = 'normal'

                    # 如果相对于 P1 或 P2 是 'add'，则最终标记为 'add'
                    if status1 == 'add' or status2 == 'add':
                        final_status = 'add'
                    # TODO: 可以扩展处理 'modify' 等类型, 需要 format_diff_content 支持

                    if final_status != 'normal':
                        middle_highlight_info.append((ln, final_status))
                # --- 综合高亮计算结束 ---

                # --- 设置视图内容和高亮 ---
                # 左侧视图: 显示 Parent 1 内容, 高亮相对于 New 被删除/修改的行
                self.left_diff.setPlainText(parent1_content)
                self.left_diff.set_diff_info(old_line_info1) # 应用 old_line_info1
                self.left_diff.rehighlight()

                # 中间视图: 显示 New Content 内容, 高亮相对于 P1 或 P2 新增/修改的行
                self.middle_diff.setPlainText(new_content)
                self.middle_diff.set_diff_info(middle_highlight_info) # 应用综合高亮信息
                self.middle_diff.rehighlight()

                # 右侧视图: 显示 Parent 2 内容, 高亮相对于 New 被删除/修改的行
                self.right_diff.setPlainText(parent2_content)
                self.right_diff.set_diff_info(old_line_info2) # 应用 old_line_info2
                self.right_diff.rehighlight()

            else: # 普通差异 (或初始提交) - 保持原有逻辑
                self.middle_diff.hide()

                # 计算差异
                old_line_info, new_line_info = format_diff_content(old_content, new_content)

                # 设置文本和高亮
                self.left_diff.setPlainText(old_content if old_content else "(新文件)")
                self.left_diff.set_diff_info(old_line_info)
                self.left_diff.rehighlight()

                self.right_diff.setPlainText(new_content if new_content else "(文件已删除)")
                self.right_diff.set_diff_info(new_line_info)
                self.right_diff.rehighlight()

        except Exception as e:
            # 通用错误处理
            print(f"Error displaying file diff for {item.text(0)}: {e}")
            import traceback
            traceback.print_exc() # Print detailed traceback
            self.left_diff.setPlainText(f"获取文件差异失败:\n{traceback.format_exc()}")
            self.middle_diff.clear()
            self.right_diff.clear()

    def save_splitter_state(self):
        """保存所有分割器的状态"""
        self.settings.settings['vertical_splitter'] = [pos for pos in self.vertical_splitter.sizes()]
        self.settings.settings['horizontal_splitter'] = [pos for pos in self.horizontal_splitter.sizes()]
        self.settings.settings['diff_splitter'] = [pos for pos in self.diff_splitter.sizes()]
        self.settings.save_settings()
        
    def restore_splitter_state(self):
        """恢复所有分割器的状态"""
        # 恢复垂直分割器状态
        vertical_sizes = self.settings.settings.get('vertical_splitter')
        if vertical_sizes:
            self.vertical_splitter.setSizes(vertical_sizes)
            
        # 恢复水平分割器状态
        horizontal_sizes = self.settings.settings.get('horizontal_splitter')
        if horizontal_sizes:
            self.horizontal_splitter.setSizes(horizontal_sizes)
            
        # 恢复差异分割器状态
        diff_sizes = self.settings.settings.get('diff_splitter')
        if diff_sizes:
            self.diff_splitter.setSizes(diff_sizes)
            
    def resizeEvent(self, event):
        """处理窗口大小改变事件"""
        super().resizeEvent(event)
        # 如果没有保存的分割器状态,则使用默认比例
        if not self.settings.settings.get('vertical_splitter'):
            total_height = self.height()
            # 调整比例，让下半部分占据更多空间
            self.vertical_splitter.setSizes([total_height * 1 // 3, total_height * 2 // 3])
        if not self.settings.settings.get('horizontal_splitter'):
            total_width = self.width()
            self.horizontal_splitter.setSizes([total_width // 3, total_width * 2 // 3])