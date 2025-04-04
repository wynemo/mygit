from PyQt6.QtWidgets import QPlainTextEdit, QWidget
from PyQt6.QtCore import Qt, QRect, QSize
from PyQt6.QtGui import QFont, QPainter, QColor, QTextBlock
from syntax_highlighter import DiffCodeHighlighter

class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.editor.line_number_area_paint_event(event)

class DiffTextEdit(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont('Courier New', 10))
        self.highlighter = DiffCodeHighlighter(self.document())
        self.sync_scrolls = []  # 同步滚动的其他编辑器列表
        self.is_scrolling = False  # 防止递归滚动
        
        # 创建行号区域
        self.line_number_area = LineNumberArea(self)
        
        # 监听滚动条变化
        self.verticalScrollBar().valueChanged.connect(self.on_scroll_changed)
        self.horizontalScrollBar().valueChanged.connect(self.on_horizontal_scroll_changed)
        
        # 连接更新行号区域的信号
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        
        # 初始化行号区域宽度
        self.update_line_number_area_width()
        
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

    def line_number_area_width(self):
        """计算行号区域的宽度"""
        digits = len(str(max(1, self.blockCount())))
        space = 3 + self.fontMetrics().horizontalAdvance('9') * digits
        return space

    def update_line_number_area_width(self):
        """更新编辑器的视口边距以适应行号"""
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        """更新行号区域"""
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width()

    def resizeEvent(self, event):
        """处理调整大小事件"""
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(),
                                              self.line_number_area_width(), cr.height()))

    def line_number_area_paint_event(self, event):
        """绘制行号区域"""
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor('#f0f0f0'))  # 浅灰色背景

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(QColor('#808080'))  # 灰色文字
                painter.drawText(0, int(top), self.line_number_area.width() - 2,
                               self.fontMetrics().height(),
                               Qt.AlignmentFlag.AlignRight, number)

            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1 