from PyQt6.QtWidgets import QTextEdit
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from syntax_highlighter import DiffCodeHighlighter

class DiffTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont('Courier New', 10))
        self.highlighter = DiffCodeHighlighter(self.document())
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
            
    def set_diff_info(self, line_info):
        """Passes diff info to the highlighter."""
        if isinstance(self.highlighter, DiffCodeHighlighter):
            self.highlighter.set_diff_info(line_info)
        else:
             # Fallback or error handling if highlighter is not the expected type
             print("Warning: Highlighter is not DiffCodeHighlighter, cannot set diff info.")

    def rehighlight(self):
        """Triggers rehighlighting."""
        self.highlighter.rehighlight()
        
    def wheelEvent(self, event):
        """处理鼠标滚轮事件"""
        super().wheelEvent(event)
        if not self.is_scrolling:
            self.is_scrolling = True
            # 同步其他编辑器的滚动
            for edit in self.sync_scrolls:
                edit.verticalScrollBar().setValue(self.verticalScrollBar().value())
            self.is_scrolling = False 