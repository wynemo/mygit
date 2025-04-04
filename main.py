import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QFileDialog, QVBoxLayout, 
                           QWidget, QPushButton, QListWidget, QHBoxLayout, 
                           QLabel, QComboBox, QSplitter, QTreeWidget, QTreeWidgetItem,
                           QTextEdit, QMenu, QToolButton, QScrollBar)
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QFont, QAction, QTextCursor
from git_manager import GitManager
from syntax_highlighter import CodeHighlighter, format_diff_content
from settings import Settings

class DiffTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont('Courier New', 10))
        self.highlighter = CodeHighlighter(self.document())
        self.sync_scrolls = []  # 同步滚动的其他编辑器列表
        self.is_scrolling = False  # 防止递归滚动
        
        # 监听滚动条变化
        self.verticalScrollBar().valueChanged.connect(self.on_scroll_changed)
        self.horizontalScrollBar().valueChanged.connect(self.on_horizontal_scroll_changed)
        
    def add_sync_scroll(self, other_edit):
        """添加需要同步滚动的编辑器"""
        if other_edit not in self.sync_scrolls:
            self.sync_scrolls.append(other_edit)
            
    def remove_sync_scroll(self, other_edit):
        """移除同步滚动的编辑器"""
        if other_edit in self.sync_scrolls:
            self.sync_scrolls.remove(other_edit)
            
    def on_scroll_changed(self, value):
        """垂直滚动条值改变时的处理"""
        if not self.is_scrolling:
            self.is_scrolling = True
            # 计算滚动百分比
            maximum = self.verticalScrollBar().maximum()
            if maximum == 0:
                percentage = 0
            else:
                percentage = value / maximum
                
            # 同步其他编辑器的滚动
            for edit in self.sync_scrolls:
                other_maximum = edit.verticalScrollBar().maximum()
                edit.verticalScrollBar().setValue(int(percentage * other_maximum))
            self.is_scrolling = False
            
    def on_horizontal_scroll_changed(self, value):
        """水平滚动条值改变时的处理"""
        if not self.is_scrolling:
            self.is_scrolling = True
            # 计算滚动百分比
            maximum = self.horizontalScrollBar().maximum()
            if maximum == 0:
                percentage = 0
            else:
                percentage = value / maximum
                
            # 同步其他编辑器的滚动
            for edit in self.sync_scrolls:
                other_maximum = edit.horizontalScrollBar().maximum()
                edit.horizontalScrollBar().setValue(int(percentage * other_maximum))
            self.is_scrolling = False
            
    def wheelEvent(self, event):
        """处理鼠标滚轮事件"""
        super().wheelEvent(event)
        if not self.is_scrolling:
            self.is_scrolling = True
            # 同步其他编辑器的滚动
            for edit in self.sync_scrolls:
                edit.verticalScrollBar().setValue(self.verticalScrollBar().value())
            self.is_scrolling = False

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
        """当点击文件项时显示文件差异"""
        if not self.current_commit or not item:
            return
            
        # 如果点击的是目录（有子项），不显示差异
        if item.childCount() > 0:
            return
            
        try:
            file_path = self.get_full_path(item)
            parent = self.current_commit.parents[0] if self.current_commit.parents else None
            
            # 检查是否是合并提交
            is_merge = len(self.current_commit.parents) > 1
            
            # 在设置新内容前先清空并重置滚动条
            self.left_diff.clear()
            self.middle_diff.clear()
            self.right_diff.clear()
            self.left_diff.verticalScrollBar().setValue(0)
            self.middle_diff.verticalScrollBar().setValue(0)
            self.right_diff.verticalScrollBar().setValue(0)
            
            if is_merge:
                # 显示三方对比
                self.middle_diff.show()
                # 获取两个父提交的文件内容
                parent1_content = parent.tree[file_path].data_stream.read().decode('utf-8')
                parent2_content = self.current_commit.parents[1].tree[file_path].data_stream.read().decode('utf-8')
                current_content = self.current_commit.tree[file_path].data_stream.read().decode('utf-8')
                
                # 生成差异HTML
                old_html, _ = format_diff_content(parent1_content, current_content)
                middle_html, _ = format_diff_content(parent2_content, current_content)
                _, new_html = format_diff_content(parent1_content, current_content)
                
                self.left_diff.setHtml(old_html)
                self.middle_diff.setHtml(middle_html)
                self.right_diff.setHtml(new_html)
            else:
                # 隐藏中间文本框
                self.middle_diff.hide()
                if parent:
                    try:
                        # 获取旧版本内容
                        old_content = parent.tree[file_path].data_stream.read().decode('utf-8')
                        new_content = self.current_commit.tree[file_path].data_stream.read().decode('utf-8')
                        
                        # 生成差异HTML
                        old_html, new_html = format_diff_content(old_content, new_content)
                        
                        self.left_diff.setHtml(old_html)
                        self.right_diff.setHtml(new_html)
                    except KeyError:
                        # 文件在旧版本中不存在
                        self.left_diff.setPlainText("(文件不存在)")
                        new_content = self.current_commit.tree[file_path].data_stream.read().decode('utf-8')
                        self.right_diff.setHtml(format_diff_content("", new_content)[1])
                else:
                    # 第一个提交
                    self.left_diff.setPlainText("(新文件)")
                    new_content = self.current_commit.tree[file_path].data_stream.read().decode('utf-8')
                    self.right_diff.setHtml(format_diff_content("", new_content)[1])
                    
        except Exception as e:
            self.left_diff.setPlainText(f"获取文件差异失败: {str(e)}")
            self.middle_diff.clear()
            self.right_diff.clear()

def main():
    app = QApplication(sys.argv)
    window = GitManagerWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 