from PyQt6.QtWidgets import (QWidget, QSplitter, QTreeWidget, QTreeWidgetItem, 
                           QVBoxLayout, QTextEdit, QTabWidget)
from PyQt6.QtCore import Qt, QMimeData
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QDrag
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
        self.file_tree = FileTreeWidget(self)  # 传入self作为父部件
        self.file_tree.setHeaderLabels(["工作区文件"])
        
        # 创建标签页组件
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.setAcceptDrops(True)
        self.tab_widget.dragEnterEvent = self.tab_drag_enter_event
        self.tab_widget.dropEvent = self.tab_drop_event
        
        # 添加组件到分割器
        self.splitter.addWidget(self.file_tree)
        self.splitter.addWidget(self.tab_widget)
        
        # 设置分割器的初始比例(1:2)
        self.splitter.setSizes([200, 400])
        
        # 添加分割器到布局
        layout.addWidget(self.splitter)
        
    def tab_drag_enter_event(self, event: QDragEnterEvent):
        """处理拖拽进入事件"""
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def tab_drop_event(self, event: QDropEvent):
        """处理拖放事件"""
        file_path = event.mimeData().text()
        if os.path.isfile(file_path):
            self.open_file_in_tab(file_path)

    def open_file_in_tab(self, file_path: str):
        """在新标签页中打开文件"""
        try:
            # 检查文件是否已经打开
            for i in range(self.tab_widget.count()):
                if self.tab_widget.widget(i).property("file_path") == file_path:
                    self.tab_widget.setCurrentIndex(i)
                    return

            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 创建新的文本编辑器
            text_edit = QTextEdit()
            text_edit.setProperty("file_path", file_path)
            text_edit.setText(content)
            
            # 添加新标签页
            file_name = os.path.basename(file_path)
            self.tab_widget.addTab(text_edit, file_name)
            self.tab_widget.setCurrentWidget(text_edit)
            
        except Exception as e:
            print(f"Error opening file: {e}")

    def close_tab(self, index: int):
        """关闭标签页"""
        self.tab_widget.removeTab(index)

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
            
class FileTreeWidget(QTreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.itemDoubleClicked.connect(self._handle_double_click)
        
    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            item = self.itemAt(event.pos())
            if item and os.path.isfile(item.data(0, Qt.ItemDataRole.UserRole)):
                drag = QDrag(self)
                mime_data = QMimeData()
                mime_data.setText(item.data(0, Qt.ItemDataRole.UserRole))
                drag.setMimeData(mime_data)
                drag.exec()
                
    def _handle_double_click(self, item):
        """处理双击事件"""
        file_path = item.data(0, Qt.ItemDataRole.UserRole)
        if os.path.isfile(file_path):
            # 获取父部件(WorkspaceExplorer)的引用
            workspace_explorer = self.parent()
            while workspace_explorer and not isinstance(workspace_explorer, WorkspaceExplorer):
                workspace_explorer = workspace_explorer.parent()
            
            if workspace_explorer:
                workspace_explorer.open_file_in_tab(file_path) 