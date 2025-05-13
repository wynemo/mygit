import os
from datetime import datetime
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QLabel, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget


class FileHistoryView(QWidget):
    commit_selected = pyqtSignal(str)  # 发送提交哈希的信号
    
    def __init__(self, file_path, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.git_manager = None
        self.setup_ui()
        
        # 尝试从父窗口获取git_manager
        main_window = self.window()
        if hasattr(main_window, 'git_manager') and main_window.git_manager:
            self.git_manager = main_window.git_manager
            self.update_history()

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        self.setLayout(layout)

        self.history_label = QLabel(f"文件历史: {self.file_path}")
        layout.addWidget(self.history_label)

        self.history_list = QTreeWidget()
        self.history_list.setHeaderLabels(["提交ID", "提交信息", "作者", "日期"])
        self.history_list.itemClicked.connect(self.on_commit_clicked)
        self.history_list.setColumnWidth(0, 80)  # Hash
        self.history_list.setColumnWidth(1, 200)  # Message
        self.history_list.setColumnWidth(2, 100)  # Author
        self.history_list.setColumnWidth(3, 150)  # Date
        layout.addWidget(self.history_list)
        
    def update_history(self):
        """更新文件的提交历史"""
        if not self.git_manager:
            return
            
        self.history_list.clear()
        try:
            # 获取相对于git仓库根目录的文件路径
            repo_path = self.git_manager.repo.working_dir
            relative_path = os.path.relpath(self.file_path, repo_path)
            
            # 使用git log命令获取文件的提交历史
            commits = []
            for commit in self.git_manager.repo.iter_commits(paths=relative_path):
                commits.append(commit)
                
            # 添加到历史列表
            for commit in commits:
                item = QTreeWidgetItem()
                # 提交ID (短哈希)
                item.setText(0, commit.hexsha[:7])
                # 提交信息
                item.setText(1, commit.summary)
                # 作者
                item.setText(2, commit.author.name)
                # 日期
                commit_date = datetime.fromtimestamp(commit.committed_date)
                item.setText(3, commit_date.strftime("%Y-%m-%d %H:%M:%S"))
                # 存储完整哈希值用于后续操作
                item.setData(0, 256, commit.hexsha)  # Qt.ItemDataRole.UserRole = 256
                
                self.history_list.addTopLevelItem(item)
        except Exception as e:
            item = QTreeWidgetItem()
            item.setText(0, f"获取历史失败: {str(e)}")
            self.history_list.addTopLevelItem(item)
            
    def on_commit_clicked(self, item):
        """当用户点击提交记录时触发"""
        commit_hash = item.data(0, 256)  # Qt.ItemDataRole.UserRole = 256
        if commit_hash:
            self.commit_selected.emit(commit_hash)
            
            # 尝试在主窗口的标签页中打开比较视图
            main_window = self.window()
            if hasattr(main_window, 'on_file_selected'):
                # 获取相对于git仓库根目录的文件路径
                repo_path = self.git_manager.repo.working_dir
                relative_path = os.path.relpath(self.file_path, repo_path)
                main_window.on_file_selected(relative_path)
