from PyQt6.QtWidgets import QPlainTextEdit, QWidget, QHBoxLayout
from PyQt6.QtCore import Qt, QRect, QSize, QPoint
from PyQt6.QtGui import QFont, QPainter, QColor, QTextBlock, QTextCursor
from syntax_highlighter import DiffCodeHighlighter
from dataclasses import dataclass
from typing import List, Optional
import difflib

@dataclass
class DiffChunk:
    left_start: int
    left_end: int
    right_start: int
    right_end: int
    type: str  # 'equal', 'insert', 'delete', 'replace'

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
        self.diff_info = []  # 差异信息列表
        
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
            try:
                print(f"\n=== {self.objectName()} 滚动事件开始 ===")
                
                # 获取当前视口中的第一行
                cursor = self.cursorForPosition(QPoint(0, 0))
                current_line = cursor.blockNumber()
                print(f"当前视口起始行: {current_line}")
                
                # 获取当前滚动位置的相对值
                source_bar = self.verticalScrollBar()
                max_value = source_bar.maximum()
                relative_pos = value / max_value if max_value > 0 else 0
                print(f"当前滚动相对位置: {relative_pos:.3f}")
                
                # 同步其他编辑器的滚动
                for edit in self.sync_scrolls:
                    # 根据差异信息调整目标行
                    target_line = self._map_line_number(current_line, edit)
                    print(f"映射到目标行: {target_line}")
                    
                    # 计算目标文档中的滚动值
                    target_doc_height = edit.document().size().height()
                    target_line_count = edit.document().blockCount()
                    if target_line_count > 0:
                        # 计算平均行高
                        avg_line_height = target_doc_height / target_line_count
                        # 根据目标行号计算滚动值
                        target_scroll = int(target_line * avg_line_height)
                        
                        # 确保值在有效范围内
                        target_maximum = edit.verticalScrollBar().maximum()
                        target_scroll = max(0, min(target_scroll, target_maximum))
                        print(f"目标滚动值: {target_scroll}")
                        
                        # 设置滚动值
                        edit.verticalScrollBar().setValue(target_scroll)
                
                print(f"=== {self.objectName()} 滚动事件结束 ===\n")
                
            finally:
                self.is_scrolling = False
                
    def _map_line_number(self, line: int, target_edit) -> int:
        """将当前编辑器的行号映射到目标编辑器的行号"""
        # 获取父窗口
        parent = self.parent()
        if not parent or not hasattr(parent, 'diff_chunks'):
            return line
            
        # 确定源和目标
        is_source_left = self.objectName() == 'left_edit'
        
        # 遍历差异块
        accumulated_diff = 0
        for chunk in parent.diff_chunks:
            if chunk.type != 'equal':
                source_start = chunk.left_start if is_source_left else chunk.right_start
                source_end = chunk.left_end if is_source_left else chunk.right_end
                target_start = chunk.right_start if is_source_left else chunk.left_start
                target_end = chunk.right_end if is_source_left else chunk.left_end
                
                if source_start <= line:
                    # 计算差异块的大小差异
                    source_size = source_end - source_start
                    target_size = target_end - target_start
                    size_diff = target_size - source_size
                    
                    # 如果在差异块内，根据相对位置调整
                    if line < source_end:
                        # 计算在差异块内的精确位置
                        block_progress = (line - source_start) / max(1, source_size)
                        # 调整目标行号，考虑差异块内的相对位置
                        return target_start + int(block_progress * target_size)
                    else:
                        # 如果已经过了这个差异块，直接累加差异
                        accumulated_diff += size_diff
        
        # 如果不在任何差异块内，应用累计的差异
        return line + accumulated_diff
            
    def on_horizontal_scroll_changed(self, value):
        """水平滚动条值改变时的处理"""
        if not self.is_scrolling:
            self.is_scrolling = True
            try:
                # 计算滚动百分比
                maximum = self.horizontalScrollBar().maximum()
                if maximum > 0:
                    percentage = value / maximum
                    # 同步其他编辑器的滚动
                    for edit in self.sync_scrolls:
                        other_maximum = edit.horizontalScrollBar().maximum()
                        target_value = int(percentage * other_maximum)
                        target_value = max(0, min(target_value, other_maximum))
                        edit.horizontalScrollBar().setValue(target_value)
            finally:
                self.is_scrolling = False
            
    def set_diff_info(self, line_info):
        """设置差异信息"""
        self.diff_info = line_info
        if isinstance(self.highlighter, DiffCodeHighlighter):
            self.highlighter.set_diff_info(line_info)
        else:
            print("Warning: Highlighter is not DiffCodeHighlighter")

    def rehighlight(self):
        """触发重新高亮"""
        self.highlighter.rehighlight()

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

class DiffViewer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.diff_chunks = []
        self.setup_ui()
        
    def setup_ui(self):
        layout = QHBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建左右两个编辑器
        self.left_edit = DiffTextEdit()
        self.right_edit = DiffTextEdit()
        
        # 设置对象名称以便识别
        self.left_edit.setObjectName('left_edit')
        self.right_edit.setObjectName('right_edit')
        
        # 设置同步滚动
        self.left_edit.add_sync_scroll(self.right_edit)
        self.right_edit.add_sync_scroll(self.left_edit)
        
        # 添加到布局
        layout.addWidget(self.left_edit)
        layout.addWidget(self.right_edit)
        self.setLayout(layout)
        
    def set_texts(self, left_text: str, right_text: str):
        """设置要比较的文本"""
        print("\n=== 设置新的文本进行比较 ===")
        # 先设置文本
        self.left_edit.setPlainText(left_text)
        self.right_edit.setPlainText(right_text)
        
        # 计算差异
        self._compute_diff(left_text, right_text)
        
    def _compute_diff(self, left_text: str, right_text: str):
        """计算文本差异，忽略行尾空白字符的差异"""
        print("\n=== 开始计算差异 ===")
        print("左侧文本示例:")
        print(left_text[:200] + "..." if len(left_text) > 200 else left_text)
        print("\n右侧文本示例:")
        print(right_text[:200] + "..." if len(right_text) > 200 else right_text)
        
        # 预处理文本行
        left_lines = left_text.splitlines()
        right_lines = right_text.splitlines()
        
        print(f"\n左侧文本行数: {len(left_lines)}")
        print(f"右侧文本行数: {len(right_lines)}")
        
        # 使用 difflib 计算差异
        matcher = difflib.SequenceMatcher(None, left_lines, right_lines)
        
        self.diff_chunks = []
        
        print("\n差异块详情:")
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            print(f"\n当前块: {tag}")
            print(f"左侧范围: {i1}-{i2}")
            print(f"右侧范围: {j1}-{j2}")
            print("左侧内容:", left_lines[i1:i2] if i1 < len(left_lines) else "[]")
            print("右侧内容:", right_lines[j1:j2] if j1 < len(right_lines) else "[]")
            
            chunk = DiffChunk(
                left_start=i1,
                left_end=i2,
                right_start=j1,
                right_end=j2,
                type=tag
            )
            self.diff_chunks.append(chunk)
            
        print("\n=== 差异计算完成 ===")
        print(f"总共发现 {len(self.diff_chunks)} 个差异块")
        
        # 更新差异高亮
        self._update_diff_highlights()
        
    def _update_diff_highlights(self):
        """更新两个编辑器的差异高亮"""
        left_info = []
        right_info = []
        
        print("\n=== 更新差异高亮 ===")
        for chunk in self.diff_chunks:
            print(f"\n处理差异块: {chunk.type}")
            print(f"左侧范围: {chunk.left_start}-{chunk.left_end}")
            print(f"右侧范围: {chunk.right_start}-{chunk.right_end}")
            
            if chunk.type == 'replace':
                # 替换：两侧都标记
                for line in range(chunk.left_start + 1, chunk.left_end + 1):
                    left_info.append((line, 'remove'))
                for line in range(chunk.right_start + 1, chunk.right_end + 1):
                    right_info.append((line, 'add'))
            elif chunk.type == 'delete':
                # 删除：左侧标记
                for line in range(chunk.left_start + 1, chunk.left_end + 1):
                    left_info.append((line, 'remove'))
            elif chunk.type == 'insert':
                # 插入：右侧标记
                for line in range(chunk.right_start + 1, chunk.right_end + 1):
                    right_info.append((line, 'add'))
            
        print(f"\n最终差异信息:")
        print(f"左侧: {left_info}")
        print(f"右侧: {right_info}")
        
        # 设置高亮信息
        self.left_edit.set_diff_info(left_info)
        self.right_edit.set_diff_info(right_info)
        
        # 触发重新高亮
        self.left_edit.rehighlight()
        self.right_edit.rehighlight() 