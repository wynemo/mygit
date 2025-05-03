from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem
from PyQt6.QtCore import pyqtSignal
from commit_graph import CommitGraphView

class CommitHistoryView(QWidget):
    commit_selected = pyqtSignal(str)  # 当选择提交时发出信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        self.setLayout(layout)
        
        self.history_label = QLabel("提交历史:")
        layout.addWidget(self.history_label)
        
        # 普通提交历史列表
        self.history_list = QTreeWidget()
        self.history_list.setHeaderLabels(["提交ID", "提交信息", "作者", "日期"])
        self.history_list.itemClicked.connect(self.on_commit_clicked)
        self.history_list.setColumnWidth(0, 80)  # Hash
        self.history_list.setColumnWidth(1, 200)  # Message
        self.history_list.setColumnWidth(2, 100)  # Author
        self.history_list.setColumnWidth(3, 150)  # Date
        layout.addWidget(self.history_list)
        
        # 图形化提交历史
        self.history_graph_list = CommitGraphView()
        self.history_graph_list.setHeaderLabels(["提交图", "提交ID", "提交信息", "作者", "日期"])
        self.history_graph_list.itemClicked.connect(self.on_commit_clicked)
        layout.addWidget(self.history_graph_list)
        
        self.history_graph_list.hide()  # 默认隐藏
        
    def update_history(self, git_manager, branch):
        """更新提交历史"""
        if branch == "all":
            self.history_graph_list.clear()
            self.history_list.hide()
            self.history_graph_list.show()
            graph_data = git_manager.get_commit_graph("main")
            self.history_graph_list.set_commit_data(graph_data)
        else:
            self.history_list.clear()
            self.history_graph_list.hide()
            self.history_list.show()
            commits = git_manager.get_commit_history(branch)
            for commit in commits:
                item = QTreeWidgetItem(self.history_list)
                item.setText(0, commit['hash'][:7])
                item.setText(1, commit['message'])
                item.setText(2, commit['author'])
                item.setText(3, commit['date'])
                
    def on_commit_clicked(self, item):
        """当点击提交时发出信号"""
        commit_hash = item.text(0) or item.text(1)
        self.commit_selected.emit(commit_hash) 