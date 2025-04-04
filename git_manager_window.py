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
        main_widget.setLayout(main_layout)
        
        # 创建顶部控制区域
        top_layout = QHBoxLayout()
        main_layout.addLayout(top_layout)
        
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
        main_layout.addWidget(vertical_splitter)
        
        # 上半部分容器
        upper_widget = QWidget()
        upper_layout = QVBoxLayout()
        upper_widget.setLayout(upper_layout)
        
        # 创建水平分割器（用于提交历史和文件变化）
        horizontal_splitter = QSplitter(Qt.Orientation.Horizontal)
        upper_layout.addWidget(horizontal_splitter)
        
        # 左侧提交历史区域
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_widget.setLayout(left_layout)
        
        self.history_label = QLabel("提交历史:")
        left_layout.addWidget(self.history_label)
        self.history_list = QListWidget()
        self.history_list.itemClicked.connect(self.on_commit_clicked)
        left_layout.addWidget(self.history_list)
        
        # 右侧文件变化区域
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        right_widget.setLayout(right_layout)
        
        self.changes_label = QLabel("文件变化:")
        right_layout.addWidget(self.changes_label)
        
        # 使用QTreeWidget替代QTextEdit
        self.changes_tree = QTreeWidget()
        self.changes_tree.setHeaderLabels(["文件", "状态"])
        self.changes_tree.setColumnCount(2)
        self.changes_tree.itemClicked.connect(self.on_file_clicked)
        right_layout.addWidget(self.changes_tree)
        
        # 添加左右部件到水平分割器
        horizontal_splitter.addWidget(left_widget)
        horizontal_splitter.addWidget(right_widget)
        horizontal_splitter.setSizes([400, 800])
        
        # 添加上半部分到垂直分割器
        vertical_splitter.addWidget(upper_widget)
        
        # 下半部分：文件差异查看区域
        diff_widget = QWidget()
        diff_layout = QVBoxLayout()
        diff_widget.setLayout(diff_layout)
        
        self.diff_label = QLabel("文件差异:")
        diff_layout.addWidget(self.diff_label)
        
        # 创建水平分割器用于显示文件差异
        diff_splitter = QSplitter(Qt.Orientation.Horizontal)
        diff_layout.addWidget(diff_splitter)
        
        # 左侧差异文本框
        self.left_diff = DiffTextEdit()
        self.left_diff.setReadOnly(True)
        diff_splitter.addWidget(self.left_diff)
        
        # 中间差异文本框（用于merge情况）
        self.middle_diff = DiffTextEdit()
        self.middle_diff.setReadOnly(True)
        self.middle_diff.hide()  # 默认隐藏
        diff_splitter.addWidget(self.middle_diff)
        
        # 右侧差异文本框
        self.right_diff = DiffTextEdit()
        self.right_diff.setReadOnly(True)
        diff_splitter.addWidget(self.right_diff)
        
        # 设置文本框之间的滚动同步
        self.setup_diff_sync()
        
        # 添加下半部分到垂直分割器
        vertical_splitter.addWidget(diff_widget)
        
        # 设置垂直分割器的初始大小
        vertical_splitter.setSizes([400, 400])
        
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

            # --- Clear and Reset Scroll ---
            self.left_diff.clear()
            self.middle_diff.clear()
            self.right_diff.clear()
            self.left_diff.verticalScrollBar().setValue(0)
            self.middle_diff.verticalScrollBar().setValue(0)
            self.right_diff.verticalScrollBar().setValue(0)

            # --- Process Diff and Apply ---
            if is_merge:
                self.middle_diff.show()
                
                # Compare Parent1 vs Current (for left view)
                old_line_info1, _ = format_diff_content(parent1_content, new_content)
                # Compare Parent2 vs Current (for right view - need info for parent2 side)
                old_line_info2, new_line_info2_vs_p2 = format_diff_content(parent2_content, new_content) # We need diff relative to P2 for right view highlighting

                # Left view: Parent 1 content, highlighted based on diff with Current
                self.left_diff.setPlainText(parent1_content) 
                self.left_diff.set_diff_info(old_line_info1) # Highlight based on changes FROM parent1
                self.left_diff.rehighlight()

                # Middle view: Current content (no diff highlighting needed relative to itself)
                self.middle_diff.setPlainText(new_content)
                self.middle_diff.set_diff_info([]) # No diff markers
                self.middle_diff.rehighlight()

                # Right view: Parent 2 content, highlighted based on diff with Current
                self.right_diff.setPlainText(parent2_content) 
                self.right_diff.set_diff_info(old_line_info2) # Highlight based on changes FROM parent2
                self.right_diff.rehighlight()

            else: # Normal diff (or initial commit)
                self.middle_diff.hide()
                
                # Get structured diff info
                old_line_info, new_line_info = format_diff_content(old_content, new_content)
                
                # Left view: Old content, highlighted if removed/changed
                self.left_diff.setPlainText(old_content if old_content else "(New File)")
                self.left_diff.set_diff_info(old_line_info)
                self.left_diff.rehighlight()

                # Right view: New content, highlighted if added/changed
                self.right_diff.setPlainText(new_content if new_content else "(File Deleted)")
                self.right_diff.set_diff_info(new_line_info)
                self.right_diff.rehighlight()
                
        except Exception as e:
            # General error handling
            print(f"Error displaying file diff for {item.text(0)}: {e}")
            import traceback
            traceback.print_exc() # Print detailed traceback
            self.left_diff.setPlainText(f"获取文件差异失败:\n{traceback.format_exc()}")
            self.middle_diff.clear()
            self.right_diff.clear()