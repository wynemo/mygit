import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QFileDialog, QVBoxLayout, 
                           QWidget, QPushButton, QListWidget, QHBoxLayout, 
                           QLabel, QComboBox, QSplitter, QTextEdit)
from PyQt6.QtCore import Qt
from git_manager import GitManager

class GitManagerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Git Manager")
        self.setGeometry(100, 100, 1200, 800)
        self.git_manager = None
        
        # 创建主窗口部件
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        # 创建主布局
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)
        
        # 创建顶部控制区域
        top_layout = QHBoxLayout()
        main_layout.addLayout(top_layout)
        
        # 创建打开文件夹按钮
        self.open_button = QPushButton("打开文件夹")
        self.open_button.clicked.connect(self.open_folder)
        top_layout.addWidget(self.open_button)
        
        # 创建分支选择下拉框
        self.branch_label = QLabel("当前分支:")
        self.branch_combo = QComboBox()
        self.branch_combo.currentTextChanged.connect(self.on_branch_changed)
        top_layout.addWidget(self.branch_label)
        top_layout.addWidget(self.branch_combo)
        
        # 创建分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
        
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
        self.changes_text = QTextEdit()
        self.changes_text.setReadOnly(True)
        right_layout.addWidget(self.changes_text)
        
        # 添加左右部件到分割器
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        
        # 设置分割器初始大小
        splitter.setSizes([400, 800])
        
    def open_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "选择Git仓库")
        if folder_path:
            self.git_manager = GitManager(folder_path)
            if self.git_manager.initialize():
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
            
    def on_commit_clicked(self, item):
        """当点击提交历史项时显示文件变化"""
        if not self.git_manager or not self.git_manager.repo:
            return
            
        # 从item文本中提取commit hash
        commit_hash = item.text().split()[0]
        
        try:
            commit = self.git_manager.repo.commit(commit_hash)
            # 获取父提交
            parent = commit.parents[0] if commit.parents else None
            
            # 清空之前的显示
            self.changes_text.clear()
            
            if parent:
                # 获取与父提交的差异
                diff = parent.diff(commit)
                for change in diff:
                    self.changes_text.append(f"文件: {change.a_path}")
                    self.changes_text.append(f"状态: {change.change_type}")
                    self.changes_text.append("")
            else:
                # 如果是第一个提交,显示所有文件
                for item in commit.tree.traverse():
                    if item.type == 'blob':  # 只显示文件,不显示目录
                        self.changes_text.append(f"文件: {item.path}")
                        self.changes_text.append("状态: 新增")
                        self.changes_text.append("")
                        
        except Exception as e:
            self.changes_text.setText(f"获取文件变化失败: {str(e)}")

def main():
    app = QApplication(sys.argv)
    window = GitManagerWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 