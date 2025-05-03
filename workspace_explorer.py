from PyQt6.QtWidgets import (QWidget, QSplitter, QTreeWidget, QTreeWidgetItem, 
                           QVBoxLayout, QTextEdit)
from PyQt6.QtCore import Qt
import os

class WorkspaceExplorer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        # 创建主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建水平分割器
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 创建文件树
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabels(["工作区文件"])
        self.file_tree.itemClicked.connect(self.on_file_clicked)
        
        # 创建文件编辑器
        self.file_editor = QTextEdit()
        self.file_editor.setReadOnly(True)  # 暂时设置为只读模式
        
        # 添加组件到分割器
        self.splitter.addWidget(self.file_tree)
        self.splitter.addWidget(self.file_editor)
        
        # 设置分割器的初始比例(1:2)
        self.splitter.setSizes([200, 400])
        
        # 添加分割器到布局
        layout.addWidget(self.splitter)
        
    def set_workspace_path(self, path):
        """设置并加载工作区路径"""
        self.workspace_path = path
        self.refresh_file_tree()
        
    def refresh_file_tree(self):
        """刷新文件树"""
        self.file_tree.clear()
        if hasattr(self, 'workspace_path'):
            self._add_directory_items(self.workspace_path, self.file_tree.invisibleRootItem())
            
    def _add_directory_items(self, path, parent):
        """递归添加目录内容到树形结构"""
        try:
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                tree_item = QTreeWidgetItem(parent)
                tree_item.setText(0, item)
                tree_item.setData(0, Qt.ItemDataRole.UserRole, item_path)
                
                if os.path.isdir(item_path):
                    self._add_directory_items(item_path, tree_item)
                    
        except Exception as e:
            print(f"Error loading directory {path}: {e}")
            
    def on_file_clicked(self, item):
        """处理文件点击事件"""
        file_path = item.data(0, Qt.ItemDataRole.UserRole)
        if os.path.isfile(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.file_editor.setText(content)
            except Exception as e:
                self.file_editor.setText(f"Error reading file: {e}") 