from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QTextEdit, 
                           QPushButton, QLabel, QDialogButtonBox,
                           QTreeWidget, QTreeWidgetItem, QHBoxLayout,
                           QSplitter, QWidget)
from PyQt6.QtCore import Qt

class CommitDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("提交更改")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)
        self.git_manager = parent.git_manager
        
        # 创建主布局
        layout = QVBoxLayout(self)
        
        # 创建分割器
        splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(splitter)
        
        # 上半部分：文件列表
        files_widget = QWidget()
        files_layout = QVBoxLayout(files_widget)
        
        # 创建文件列表区域
        files_label = QLabel("Changed Files:")
        files_layout.addWidget(files_label)
        
        # 暂存和未暂存文件的树形控件
        self.staged_tree = QTreeWidget()
        self.staged_tree.setHeaderLabels(["Staged Files", "Status"])
        self.staged_tree.itemDoubleClicked.connect(self.unstage_file)
        
        self.unstaged_tree = QTreeWidget()
        self.unstaged_tree.setHeaderLabels(["Unstaged Files", "Status"])
        self.unstaged_tree.itemDoubleClicked.connect(self.stage_file)
        
        files_layout.addWidget(self.staged_tree)
        files_layout.addWidget(self.unstaged_tree)
        
        splitter.addWidget(files_widget)
        
        # 下半部分：提交信息
        commit_widget = QWidget()
        commit_layout = QVBoxLayout(commit_widget)
        
        message_label = QLabel("Commit Message:")
        commit_layout.addWidget(message_label)
        
        self.message_edit = QTextEdit()
        commit_layout.addWidget(self.message_edit)
        
        splitter.addWidget(commit_widget)
        
        # 按钮区域
        button_box = QDialogButtonBox()
        self.commit_button = button_box.addButton("Commit", 
                                                QDialogButtonBox.ButtonRole.AcceptRole)
        self.cancel_button = button_box.addButton("Cancel", 
                                                QDialogButtonBox.ButtonRole.RejectRole)
        
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        # 初始化显示文件状态
        self.refresh_file_status()
        
    def refresh_file_status(self):
        """刷新文件状态显示"""
        self.staged_tree.clear()
        self.unstaged_tree.clear()
        
        if not self.git_manager:
            return
            
        repo = self.git_manager.repo
        
        # 获取暂存的文件
        staged = repo.index.diff('HEAD')
        for diff in staged:
            item = QTreeWidgetItem(self.staged_tree)
            item.setText(0, diff.a_path)
            item.setText(1, 'Modified')
            
        # 获取未暂存的文件
        unstaged = repo.index.diff(None)
        for diff in unstaged:
            item = QTreeWidgetItem(self.unstaged_tree)
            item.setText(0, diff.a_path)
            item.setText(1, 'Modified')
            
        # 获取未跟踪的文件
        untracked = repo.untracked_files
        for file_path in untracked:
            item = QTreeWidgetItem(self.unstaged_tree)
            item.setText(0, file_path)
            item.setText(1, 'Untracked')
    
    def stage_file(self, item):
        """暂存选中的文件"""
        file_path = item.text(0)
        try:
            self.git_manager.repo.index.add([file_path])
            self.refresh_file_status()
        except Exception as e:
            print(f"无法暂存文件: {str(e)}")
    
    def unstage_file(self, item):
        """取消暂存选中的文件"""
        file_path = item.text(0)
        try:
            # 使用 git reset 来取消暂存，而不是 remove
            self.git_manager.repo.git.reset('HEAD', file_path)
            self.refresh_file_status()
        except Exception as e:
            print(f"无法取消暂存文件: {str(e)}")
    
    def get_commit_message(self):
        return self.message_edit.toPlainText()