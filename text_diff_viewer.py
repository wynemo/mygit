from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QPlainTextEdit, QScrollBar, QFrame, QApplication)
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QSize, QPoint
from PyQt6.QtGui import (QPainter, QColor, QFont, QSyntaxHighlighter, 
                        QTextCharFormat, QTextCursor)
from dataclasses import dataclass
from typing import List, Tuple, Optional
import difflib
import re
import time
import sys

@dataclass
class DiffChunk:
    left_start: int
    left_end: int
    right_start: int
    right_end: int
    type: str  # 'equal', 'insert', 'delete', 'replace'

class GoHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighting_rules = []
        self.debug_count = 0  # 添加调试计数器
        
        # 关键字 - 使用更深的蓝色
        keywords = [
            'package', 'import', 'func', 'type', 'struct', 'interface',
            'if', 'else', 'for', 'range', 'switch', 'case', 'default',
            'return', 'break', 'continue', 'goto', 'fallthrough',
            'defer', 'go', 'select', 'chan', 'map', 'var', 'const',
            'true', 'false', 'nil', 'iota'
        ]
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor('#1E90FF'))  # 更深的蓝色
        self.highlighting_rules.extend(
            [(f'\\b{word}\\b', keyword_format) for word in keywords]
        )
        
        # 字符串 - 使用更深的橙色
        string_format = QTextCharFormat()
        string_format.setForeground(QColor('#FF8C00'))  # 更深的橙色
        self.highlighting_rules.append(('".*?"', string_format))
        self.highlighting_rules.append(("`.*?`", string_format))
        
        # 注释 - 使用更深的绿色
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor('#228B22'))  # 更深的绿色
        self.highlighting_rules.append(('//.*$', comment_format))
        self.highlighting_rules.append(('/\\*.*?\\*/', comment_format))
        
        # 函数调用 - 使用更深的黄色
        function_format = QTextCharFormat()
        function_format.setForeground(QColor('#DAA520'))  # 更深的黄色
        self.highlighting_rules.append(('\\b\\w+(?=\\()', function_format))
        
        # 数字 - 使用更深的绿色
        number_format = QTextCharFormat()
        number_format.setForeground(QColor('#2E8B57'))  # 更深的绿色
        self.highlighting_rules.append(('\\b\\d+\\b', number_format))
        
        # 类型 - 使用更深的青色
        type_format = QTextCharFormat()
        type_format.setForeground(QColor('#008B8B'))  # 更深的青色
        self.highlighting_rules.append(('\\b(int|string|bool|float64|float32|byte|rune|error)\\b', type_format))

    def highlightBlock(self, text):
        self.debug_count += 1
        if self.debug_count <= 3:  # 只打印前三次调用的信息
            print(f"\n=== Go语法高亮 #{self.debug_count} ===")
            print(f"高亮器: {self.parent().objectName()}")
            print(f"当前行: {self.currentBlock().blockNumber() + 1}")
            print(f"文本内容: {text}")
        
        for pattern, format in self.highlighting_rules:
            for match in re.finditer(pattern, text):
                start, end = match.span()
                if self.debug_count <= 3:
                    print(f"匹配规则: {pattern}")
                    print(f"匹配范围: {start}-{end}")
                    print(f"匹配文本: {text[start:end]}")
                self.setFormat(start, end - start, format)

class DiffHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.diff_chunks = []
        
        # 定义差异高亮的颜色
        self.diff_formats = {
            'delete': self.create_format('#ffeef0', '#ff0000'),  # 浅红色背景，红色文字
            'insert': self.create_format('#e6ffed', '#28a745'),  # 浅绿色背景，绿色文字
            'replace': self.create_format('#fff5b1', '#735c0f'),  # 浅黄色背景，深黄色文字
            'equal': None
        }
        
    def create_format(self, background_color, text_color):
        """创建高亮格式，包含文字颜色和背景颜色"""
        fmt = QTextCharFormat()
        fmt.setBackground(QColor(background_color))
        fmt.setForeground(QColor(text_color))
        return fmt
        
    def set_diff_chunks(self, chunks):
        print(f"设置差异块到高亮器: {self.parent().objectName()}, 块数量: {len(chunks)}")
        self.diff_chunks = chunks
        self.rehighlight()
        
    def highlightBlock(self, text):
        block_number = self.currentBlock().blockNumber()
        
        # 找到当前行所在的差异块
        current_chunk = None
        for chunk in self.diff_chunks:
            # 检查是否是左侧编辑器
            if self.parent().objectName() == 'left_edit':
                if chunk.left_start <= block_number < chunk.left_end:
                    current_chunk = chunk
                    break
            # 检查是否是右侧编辑器
            elif self.parent().objectName() == 'right_edit':
                if chunk.right_start <= block_number < chunk.right_end:
                    current_chunk = chunk
                    break
        
        # 如果找到差异块，应用相应的格式
        if current_chunk and current_chunk.type != 'equal':
            print(f"找到差异块: {current_chunk.type}")
            # 根据编辑器和差异类型选择格式
            format_type = None
            if self.parent().objectName() == 'left_edit':
                if current_chunk.type == 'delete':
                    format_type = 'delete'
                elif current_chunk.type == 'replace':
                    format_type = 'replace'
            else:  # right_edit
                if current_chunk.type == 'insert':
                    format_type = 'insert'
                elif current_chunk.type == 'replace':
                    format_type = 'replace'
            
            # 应用格式
            if format_type and format_type in self.diff_formats:
                format = self.diff_formats[format_type]
                if format:
                    print(f"应用格式: {format_type}")
                    self.setFormat(0, len(text), format)

class SyncedTextEdit(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setFont(QFont('Courier New', 10))
        
        # 添加行号区域
        self.line_number_area = LineNumberArea(self)
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.update_line_number_area_width()
        
    def line_number_area_width(self):
        digits = len(str(max(1, self.blockCount())))
        space = 3 + self.fontMetrics().horizontalAdvance('9') * digits
        return space
        
    def update_line_number_area_width(self):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)
        
    def update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
            
    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(),
                                              self.line_number_area_width(), cr.height()))
                                              
    def line_number_area_paint_event(self, event):
        """绘制行号区域"""
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor('#f0f0f0'))
        
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()
        
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(QColor('#808080'))
                painter.drawText(0, int(top), self.line_number_area.width() - 2,
                               self.fontMetrics().height(),
                               Qt.AlignmentFlag.AlignRight, number)
                               
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1

class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        
    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)
        
    def paintEvent(self, event):
        self.editor.line_number_area_paint_event(event)

class DiffViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.diff_chunks = []
        self._sync_vscroll_lock = False
        self._sync_hscroll_lock = False
        
    def setup_ui(self):
        layout = QHBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 左侧文本编辑器
        self.left_edit = SyncedTextEdit()
        self.left_edit.setObjectName('left_edit')
        
        # 右侧文本编辑器
        self.right_edit = SyncedTextEdit()
        self.right_edit.setObjectName('right_edit')
        
        # 设置滚动事件处理
        self.left_edit.verticalScrollBar().valueChanged.connect(
            lambda val: self._on_scroll(val, True))  # True 表示左侧滚动
        self.right_edit.verticalScrollBar().valueChanged.connect(
            lambda val: self._on_scroll(val, False))  # False 表示右侧滚动
        
        self.left_edit.horizontalScrollBar().valueChanged.connect(
            lambda val: self._sync_hscroll(val, 0))
        self.right_edit.horizontalScrollBar().valueChanged.connect(
            lambda val: self._sync_hscroll(val, 1))
        
        # 添加语法高亮器
        self.left_highlighter = GoHighlighter(self.left_edit.document())
        self.right_highlighter = GoHighlighter(self.right_edit.document())
        
        # 添加差异高亮器
        self.left_diff_highlighter = DiffHighlighter(self.left_edit.document())
        self.right_diff_highlighter = DiffHighlighter(self.right_edit.document())
        
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
        
        # 预处理文本行，去除行尾空白和行首空白
        left_lines = [line.strip() for line in left_text.splitlines()]
        right_lines = [line.strip() for line in right_text.splitlines()]
        
        print(f"左侧文本行数: {len(left_lines)}")
        print(f"右侧文本行数: {len(right_lines)}")
        
        # 使用 junk 参数忽略空白字符的差异
        matcher = difflib.SequenceMatcher(
            lambda x: x.isspace() or not x.strip(),  # 忽略空白行
            left_lines,
            right_lines,
            autojunk=False  # 禁用自动junk检测
        )
        
        self.diff_chunks = []
        last_chunk = None
        
        print("\n差异块详情:")
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            print(f"\n当前块: {tag}")
            print(f"左侧范围: {i1}-{i2}")
            print(f"右侧范围: {j1}-{j2}")
            
            # 尝试合并相邻的差异块
            if last_chunk and tag != 'equal':
                if (last_chunk.left_end == i1 and 
                    last_chunk.right_end == j1 and 
                    last_chunk.type != 'equal'):
                    last_chunk.left_end = i2
                    last_chunk.right_end = j2
                    continue
            
            # 对于相等的块，检查是否真的完全相等
            if tag == 'equal':
                # 打印相等块的内容进行比对
                print("相等块内容比对:")
                is_really_equal = True
                for i, j in zip(range(i1, i2), range(j1, j2)):
                    left_line = left_lines[i]
                    right_line = right_lines[j]
                    if left_line != right_line:
                        print(f"发现不相等的行:")
                        print(f"左侧第{i+1}行: {left_line}")
                        print(f"右侧第{j+1}行: {right_line}")
                        is_really_equal = False
                        break
                
                if not is_really_equal:
                    tag = 'replace'
            
            chunk = DiffChunk(
                left_start=i1,
                left_end=i2,
                right_start=j1,
                right_end=j2,
                type=tag
            )
            self.diff_chunks.append(chunk)
            last_chunk = chunk
            
        print("\n=== 差异计算完成 ===")
        print(f"总共发现 {len(self.diff_chunks)} 个差异块")
        
        # 更新差异高亮
        self.left_diff_highlighter.set_diff_chunks(self.diff_chunks)
        self.right_diff_highlighter.set_diff_chunks(self.diff_chunks)
        
        # 不再需要更新编辑器的差异块信息，因为这个功能已被移除
        # self.left_edit.set_diff_chunks(self.diff_chunks)
        # self.right_edit.set_diff_chunks(self.diff_chunks)

    def _on_scroll(self, value, is_left_scroll: bool):
        """统一处理滚动事件
        Args:
            value: 滚动条的值
            is_left_scroll: 是否是左侧编辑器的滚动
        """
        if self._sync_vscroll_lock:
            return
        
        self._sync_vscroll_lock = True
        try:
            print(f"\n=== {'左' if is_left_scroll else '右'}侧滚动事件开始 ===")
            
            # 获取源编辑器和目标编辑器
            source_edit = self.left_edit if is_left_scroll else self.right_edit
            target_edit = self.right_edit if is_left_scroll else self.left_edit
            
            # 1. 获取当前滚动位置的相对值
            source_bar = source_edit.verticalScrollBar()
            max_value = source_bar.maximum()
            relative_pos = value / max_value if max_value > 0 else 0
            print(f"当前滚动相对位置: {relative_pos:.3f}")
            
            # 2. 获取当前视口中的行
            cursor = source_edit.cursorForPosition(QPoint(0, 0))
            current_line = cursor.blockNumber()
            print(f"当前视口起始行: {current_line}")
            
            # 3. 根据差异块调整目标位置
            target_line = current_line
            accumulated_diff = 0
            for chunk in self.diff_chunks:
                if chunk.type != 'equal':
                    source_start = chunk.left_start if is_left_scroll else chunk.right_start
                    source_end = chunk.left_end if is_left_scroll else chunk.right_end
                    target_start = chunk.right_start if is_left_scroll else chunk.left_start
                    target_end = chunk.right_end if is_left_scroll else chunk.left_end
                    
                    if source_start <= current_line:
                        # 计算差异块的大小差异
                        source_size = source_end - source_start
                        target_size = target_end - target_start
                        size_diff = target_size - source_size
                        
                        # 如果在差异块内，根据相对位置调整
                        if current_line < source_end:
                            block_progress = (current_line - source_start) / max(1, source_size)
                            accumulated_diff += int(size_diff * block_progress)
                            print(f"在差异块内 [{source_start}, {source_end}] -> [{target_start}, {target_end}]")
                            print(f"块内进度: {block_progress:.2f}, 累计调整: {accumulated_diff}")
                        else:
                            accumulated_diff += size_diff
                            print(f"经过差异块 [{source_start}, {source_end}] -> [{target_start}, {target_end}]")
                            print(f"累计调整: {accumulated_diff}")
            
            target_line += accumulated_diff
            
            # 4. 计算目标文档中的滚动值
            target_bar = target_edit.verticalScrollBar()
            target_max = target_bar.maximum()
            
            # 使用相对位置计算目标滚动值
            target_scroll = int(relative_pos * target_max)
            
            # 根据差异块调整滚动值
            if accumulated_diff != 0:
                # 计算每行的平均高度
                target_doc_height = target_edit.document().size().height()
                target_line_count = target_edit.document().blockCount()
                avg_line_height = target_doc_height / target_line_count if target_line_count > 0 else 0
                
                # 根据累计差异调整滚动值
                adjustment = accumulated_diff * avg_line_height
                target_scroll = int(target_scroll + adjustment)
            
            # 确保滚动值在有效范围内
            target_scroll = max(0, min(target_scroll, target_max))
            print(f"目标行: {target_line}, 目标滚动值: {target_scroll}")
            
            # 设置滚动条位置
            target_edit.verticalScrollBar().setValue(target_scroll)
            
            print(f"=== {'左' if is_left_scroll else '右'}侧滚动事件结束 ===\n")
                
        finally:
            self._sync_vscroll_lock = False

    def _sync_hscroll(self, value, master_idx):
        """处理水平滚动同步"""
        if self._sync_hscroll_lock:
            return
            
        try:
            self._sync_hscroll_lock = True
            editors = [self.left_edit, self.right_edit]
            target = editors[1 - master_idx]  # 另一个编辑器
            target.horizontalScrollBar().setValue(value)
        finally:
            self._sync_hscroll_lock = False

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Text Diff Viewer")
        self.resize(1200, 800)
        
        # Create diff viewer
        self.diff_viewer = DiffViewer()
        self.setCentralWidget(self.diff_viewer)
        
        # Load test data
        self.load_test_data()
        
    def load_test_data(self):
        # 创建简单的测试数据
        left_text = ""
        right_text = ""
        
        # 生成左边50行
        for i in range(1, 101):
            left_text += f"Line {i}\n"
            right_text += f"Line {i}\n"
            if i == 25:
                right_text += "Inserted line\n"
            
        self.diff_viewer.set_texts(left_text, right_text)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())