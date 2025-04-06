import difflib
from dataclasses import dataclass

from PyQt6.QtCore import QPoint, QRect, QSize, Qt
from PyQt6.QtGui import (QColor, QFont, QPainter, QSyntaxHighlighter,
                         QTextCharFormat)
from PyQt6.QtWidgets import QHBoxLayout, QPlainTextEdit, QWidget


@dataclass
class DiffChunk:
    left_start: int
    left_end: int
    right_start: int
    right_end: int
    type: str  # 'equal', 'insert', 'delete', 'replace'

class DiffHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None, editor_type=''):
        super().__init__(parent)
        self.editor_type = editor_type
        self.diff_chunks = []
        print(f"\n=== 初始化DiffHighlighter ===")
        print(f"编辑器类型: {editor_type}")
        
        # 定义差异高亮的颜色
        self.diff_formats = {
            'delete': self.create_format('#ffcccc', '#cc0000'),  # 更深的红色
            'insert': self.create_format('#ccffcc', '#00cc00'),  # 更深的绿色
            'replace': self.create_format('#ffffcc', '#cccc00'),  # 更深的黄色
            'equal': None
        }
        print("差异格式已创建:", self.diff_formats)
        
    def create_format(self, background_color, text_color):
        """创建高亮格式，包含文字颜色和背景颜色"""
        print(f"\n创建格式 - 背景: {background_color}, 文字: {text_color}")
        fmt = QTextCharFormat()
        fmt.setBackground(QColor(background_color))
        fmt.setForeground(QColor(text_color))
        return fmt
        
    def set_diff_chunks(self, chunks):
        """设置差异块"""
        print(f"\n=== 设置差异块到高亮器 ===")
        print(f"高亮器类型: {self.editor_type}")
        print(f"块数量: {len(chunks)}")
        for i, chunk in enumerate(chunks):
            print(f"\n差异块 {i+1}:")
            print(f"类型: {chunk.type}")
            print(f"左侧范围: {chunk.left_start}-{chunk.left_end}")
            print(f"右侧范围: {chunk.right_start}-{chunk.right_end}")
        self.diff_chunks = chunks
        self.rehighlight()
        
    def highlightBlock(self, text):
        """高亮当前文本块"""
        block_number = self.currentBlock().blockNumber()
        print(f"\n=== 高亮块详细信息 ===")
        print(f"高亮器类型: {self.editor_type}")
        print(f"当前块号: {block_number}")
        print(f"文本内容: {text}")
        print(f"差异块数量: {len(self.diff_chunks)}")
        
        # 找到当前行所在的差异块
        current_chunk = None
        for chunk in self.diff_chunks:
            # 根据编辑器类型决定如何处理差异
            if self.editor_type in ['left', 'parent1_edit']:
                if chunk.left_start <= block_number < chunk.left_end:
                    current_chunk = chunk
                    print(f"找到左侧差异块: {chunk.type}")
                    break
            elif self.editor_type in ['right', 'parent2_edit']:
                if chunk.right_start <= block_number < chunk.right_end:
                    current_chunk = chunk
                    print(f"找到右侧差异块: {chunk.type}")
                    break
            elif self.editor_type == 'result_edit':
                # 对于三向合并中的结果编辑器，可能需要特殊处理
                # 这里可以根据需要添加特定的高亮逻辑
                pass
        
        # 如果找到差异块，应用相应的格式
        if current_chunk and current_chunk.type != 'equal':
            print(f"应用差异块格式: {current_chunk.type}")
            format_type = current_chunk.type
            
            if format_type in self.diff_formats:
                format = self.diff_formats[format_type]
                if format:
                    print(f"应用格式: {format_type}")
                    self.setFormat(0, len(text), format)
                    print("格式已应用")

class SyncedTextEdit(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setReadOnly(True)  # 设置为只读
        print(f"\n=== 初始化SyncedTextEdit ===")
        print(f"只读模式: {self.isReadOnly()}")
        
        # 添加行号区域
        self.line_number_area = LineNumberArea(self)
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.update_line_number_area_width()
        
        # 初始化差异信息
        self.diff_info = []
        # 从对象名称获取编辑器类型
        editor_type = self.objectName() or ''
        self.highlighter = DiffHighlighter(self.document(), editor_type)
        
    def set_diff_info(self, diff_info):
        """设置差异信息并更新高亮"""
        self.diff_info = diff_info
        self.highlighter.set_diff_chunks(diff_info)
        
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
        
        # 添加差异高亮器
        self.left_diff_highlighter = DiffHighlighter(self.left_edit.document(), 'left')
        self.right_diff_highlighter = DiffHighlighter(self.right_edit.document(), 'right')
        
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
        last_chunk = None
        
        print("\n差异块详情:")
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            print(f"\n当前块: {tag}")
            print(f"左侧范围: {i1}-{i2}")
            print(f"右侧范围: {j1}-{j2}")
            print("左侧内容:", left_lines[i1:i2] if i1 < len(left_lines) else "[]")
            print("右侧内容:", right_lines[j1:j2] if j1 < len(right_lines) else "[]")
            
            # 创建差异块
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
        print("\n=== 更新差异高亮 ===")
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
                            # 计算在差异块内的精确位置
                            block_progress = (current_line - source_start) / max(1, source_size)
                            # 调整目标行号，考虑差异块内的相对位置
                            target_line = target_start + int(block_progress * target_size)
                            print(f"在差异块内 [{source_start}, {source_end}] -> [{target_start}, {target_end}]")
                            print(f"块内进度: {block_progress:.2f}, 目标行: {target_line}")
                            break  # 找到当前所在的差异块后就停止
                        else:
                            # 如果已经过了这个差异块，直接累加差异
                            accumulated_diff += size_diff
                            print(f"经过差异块 [{source_start}, {source_end}] -> [{target_start}, {target_end}]")
                            print(f"累计调整: {accumulated_diff}")
            
            # 如果不在任何差异块内，应用累计的差异
            if target_line == current_line:
                target_line += accumulated_diff

            # 4. 计算目标文档中的滚动值
            target_bar = target_edit.verticalScrollBar()
            target_max = target_bar.maximum()
            
            # 根据目标行号计算滚动值
            target_doc_height = target_edit.document().size().height()
            target_line_count = target_edit.document().blockCount()
            avg_line_height = target_doc_height / target_line_count if target_line_count > 0 else 0
            
            # 直接使用目标行号计算滚动值
            target_scroll = int(target_line * avg_line_height)
            
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

class MergeDiffViewer(QWidget):
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
        
        # 创建三个编辑器：parent1, result, parent2
        self.parent1_edit = SyncedTextEdit()
        self.result_edit = SyncedTextEdit()
        self.parent2_edit = SyncedTextEdit()
        
        # 设置对象名称
        self.parent1_edit.setObjectName('parent1_edit')
        self.result_edit.setObjectName('result_edit')
        self.parent2_edit.setObjectName('parent2_edit')
        
        # 设置滚动事件处理
        self.parent1_edit.verticalScrollBar().valueChanged.connect(
            lambda val: self._on_scroll(val, 'parent1'))
        self.result_edit.verticalScrollBar().valueChanged.connect(
            lambda val: self._on_scroll(val, 'result'))
        self.parent2_edit.verticalScrollBar().valueChanged.connect(
            lambda val: self._on_scroll(val, 'parent2'))
        
        # 设置水平滚动同步
        self.parent1_edit.horizontalScrollBar().valueChanged.connect(
            lambda val: self._sync_hscroll(val, 'parent1'))
        self.result_edit.horizontalScrollBar().valueChanged.connect(
            lambda val: self._sync_hscroll(val, 'result'))
        self.parent2_edit.horizontalScrollBar().valueChanged.connect(
            lambda val: self._sync_hscroll(val, 'parent2'))
        
        # 添加到布局
        layout.addWidget(self.parent1_edit)
        layout.addWidget(self.result_edit)
        layout.addWidget(self.parent2_edit)
        self.setLayout(layout)
        
    def set_texts(self, parent1_text: str, result_text: str, parent2_text: str):
        """设置要比较的三个文本"""
        print("\n=== 设置新的三向文本进行比较 ===")
        # 设置文本
        self.parent1_edit.setPlainText(parent1_text)
        self.result_edit.setPlainText(result_text)
        self.parent2_edit.setPlainText(parent2_text)
        
        # 计算差异
        self._compute_diffs(parent1_text, result_text, parent2_text)
        
    def _compute_diffs(self, parent1_text: str, result_text: str, parent2_text: str):
        """计算三个文本之间的差异"""
        print("\n=== 开始计算三向差异 ===")
        
        # 预处理文本行
        parent1_lines = parent1_text.splitlines()
        result_lines = result_text.splitlines()
        parent2_lines = parent2_text.splitlines()
        
        print(f"Parent1行数: {len(parent1_lines)}")
        print(f"Result行数: {len(result_lines)}")
        print(f"Parent2行数: {len(parent2_lines)}")
        
        # 计算parent1和result之间的差异
        parent1_matcher = difflib.SequenceMatcher(None, parent1_lines, result_lines)
        parent1_chunks = []
        
        for tag, i1, i2, j1, j2 in parent1_matcher.get_opcodes():
            print(f"\nParent1差异块: {tag}, {i1}-{i2}, {j1}-{j2}")
            chunk = DiffChunk(
                left_start=i1,
                left_end=i2,
                right_start=j1,
                right_end=j2,
                type=tag
            )
            parent1_chunks.append(chunk)
                    
        # 计算parent2和result之间的差异
        parent2_matcher = difflib.SequenceMatcher(None, result_lines, parent2_lines)
        parent2_chunks = []
        
        for tag, i1, i2, j1, j2 in parent2_matcher.get_opcodes():
            print(f"\nParent2差异块: {tag}, {i1}-{i2}, {j1}-{j2}")
            chunk = DiffChunk(
                left_start=i1,
                left_end=i2,
                right_start=j1,
                right_end=j2,
                type=tag
            )
            parent2_chunks.append(chunk)
                    
        # 更新差异高亮
        self.parent1_edit.highlighter.set_diff_chunks(parent1_chunks)
        self.result_edit.highlighter.set_diff_chunks([])  # 中间不需要高亮
        self.parent2_edit.highlighter.set_diff_chunks(parent2_chunks)

    def _on_scroll(self, value, source: str):
        """处理滚动同步
        Args:
            value: 滚动条的值
            source: 滚动源('parent1', 'result', 'parent2')
        """
        if self._sync_vscroll_lock:
            return
            
        self._sync_vscroll_lock = True
        try:
            print(f"\n=== {source} 滚动事件开始 ===")
            
            # 获取所有编辑器
            editors = {
                'parent1': self.parent1_edit,
                'result': self.result_edit,
                'parent2': self.parent2_edit
            }
            
            source_edit = editors[source]
            
            # 获取当前视口中的行
            cursor = source_edit.cursorForPosition(QPoint(0, 0))
            current_line = cursor.blockNumber()
            
            # 同步其他编辑器的滚动
            for target_name, target_edit in editors.items():
                if target_name != source:
                    # 计算目标文档中的滚动值
                    target_doc_height = target_edit.document().size().height()
                    target_line_count = target_edit.document().blockCount()
                    avg_line_height = target_doc_height / target_line_count if target_line_count > 0 else 0
                    
                    # 使用当前行号计算目标滚动值
                    target_scroll = int(current_line * avg_line_height)
                    
                    # 确保滚动值在有效范围内
                    target_bar = target_edit.verticalScrollBar()
                    target_max = target_bar.maximum()
                    target_scroll = max(0, min(target_scroll, target_max))
                    
                    # 设置滚动条位置
                    target_edit.verticalScrollBar().setValue(target_scroll)
            
            print(f"=== {source} 滚动事件结束 ===\n")
                
        finally:
            self._sync_vscroll_lock = False
            
    def _sync_hscroll(self, value, source: str):
        """处理水平滚动同步"""
        if self._sync_hscroll_lock:
            return
            
        try:
            self._sync_hscroll_lock = True
            editors = {
                'parent1': self.parent1_edit,
                'result': self.result_edit,
                'parent2': self.parent2_edit
            }
            
            # 同步其他编辑器的水平滚动
            for name, editor in editors.items():
                if name != source:
                    editor.horizontalScrollBar().setValue(value)
        finally:
            self._sync_hscroll_lock = False
