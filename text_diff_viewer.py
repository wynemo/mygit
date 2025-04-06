import difflib
from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import List

from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QHBoxLayout, QWidget

from diff_highlighter import DiffHighlighter
from text_edit import SyncedTextEdit


@dataclass
class DiffChunk:
    left_start: int
    left_end: int
    right_start: int
    right_end: int
    type: str  # 'equal', 'insert', 'delete', 'replace'


class DiffCalculator(ABC):
    """差异计算器基类"""
    
    @abstractmethod
    def compute_diff(self, left_text: str, right_text: str) -> List[DiffChunk]:
        """计算两个文本之间的差异
        
        Args:
            left_text: 左侧文本
            right_text: 右侧文本
            
        Returns:
            差异块列表
        """
        pass


class DifflibCalculator(DiffCalculator):
    """基于 difflib 的差异计算器"""
    
    def compute_diff(self, left_text: str, right_text: str) -> List[DiffChunk]:
        """使用 difflib 计算文本差异"""
        left_lines = left_text.splitlines()
        right_lines = right_text.splitlines()
        
        matcher = difflib.SequenceMatcher(None, left_lines, right_lines)
        chunks = []
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            chunk = DiffChunk(
                left_start=i1,
                left_end=i2,
                right_start=j1,
                right_end=j2,
                type=tag
            )
            chunks.append(chunk)
            
        return chunks


class GitDiffCalculator(DiffCalculator):
    """基于 git diff 输出的差异计算器"""
    
    def compute_diff(self, left_text: str, right_text: str) -> List[DiffChunk]:
        """解析 git diff 输出并转换为差异块列表
        
        注意：这个实现需要 git diff 的输出作为输入，而不是直接比较文本。
        实际使用时需要修改接口以接受 git diff 输出。
        """
        # TODO: 实现 git diff 解析逻辑
        raise NotImplementedError("Git diff calculator not implemented yet")


class DiffViewer(QWidget):
    def __init__(self, diff_calculator: DiffCalculator = None):
        super().__init__()
        self.setup_ui()
        self.diff_chunks = []
        self._sync_vscroll_lock = False
        self._sync_hscroll_lock = False
        
        # 设置差异计算器，默认为 DifflibCalculator
        self.diff_calculator = diff_calculator or DifflibCalculator()

    def setup_ui(self):
        layout = QHBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # 左侧文本编辑器
        self.left_edit = SyncedTextEdit()
        self.left_edit.setObjectName("left_edit")

        # 右侧文本编辑器
        self.right_edit = SyncedTextEdit()
        self.right_edit.setObjectName("right_edit")

        # 设置滚动事件处理
        self.left_edit.verticalScrollBar().valueChanged.connect(
            lambda val: self._on_scroll(val, True)
        )  # True 表示左侧滚动
        self.right_edit.verticalScrollBar().valueChanged.connect(
            lambda val: self._on_scroll(val, False)
        )  # False 表示右侧滚动

        self.left_edit.horizontalScrollBar().valueChanged.connect(
            lambda val: self._sync_hscroll(val, 0)
        )
        self.right_edit.horizontalScrollBar().valueChanged.connect(
            lambda val: self._sync_hscroll(val, 1)
        )

        # 添加差异高亮器
        self.left_diff_highlighter = DiffHighlighter(self.left_edit.document(), "left")
        self.right_diff_highlighter = DiffHighlighter(
            self.right_edit.document(), "right"
        )

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
        """计算文本差异，使用配置的差异计算器"""
        print("\n=== 开始计算差异 ===")
        print("左侧文本示例:")
        print(left_text[:200] + "..." if len(left_text) > 200 else left_text)
        print("\n右侧文本示例:")
        print(right_text[:200] + "..." if len(right_text) > 200 else right_text)

        # 使用差异计算器计算差异
        self.diff_chunks = self.diff_calculator.compute_diff(left_text, right_text)
        
        print(f"\n=== 差异计算完成 ===")
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
                if chunk.type != "equal":
                    source_start = (
                        chunk.left_start if is_left_scroll else chunk.right_start
                    )
                    source_end = chunk.left_end if is_left_scroll else chunk.right_end
                    target_start = (
                        chunk.right_start if is_left_scroll else chunk.left_start
                    )
                    target_end = chunk.right_end if is_left_scroll else chunk.left_end

                    if source_start <= current_line:
                        # 计算差异块的大小差异
                        source_size = source_end - source_start
                        target_size = target_end - target_start
                        size_diff = target_size - source_size

                        # 如果在差异块内，根据相对位置调整
                        if current_line < source_end:
                            # 计算在差异块内的精确位置
                            block_progress = (current_line - source_start) / max(
                                1, source_size
                            )
                            # 调整目标行号，考虑差异块内的相对位置
                            target_line = target_start + int(
                                block_progress * target_size
                            )
                            print(
                                f"在差异块内 [{source_start}, {source_end}] -> [{target_start}, {target_end}]"
                            )
                            print(
                                f"块内进度: {block_progress:.2f}, 目标行: {target_line}"
                            )
                            break  # 找到当前所在的差异块后就停止
                        else:
                            # 如果已经过了这个差异块，直接累加差异
                            accumulated_diff += size_diff
                            print(
                                f"经过差异块 [{source_start}, {source_end}] -> [{target_start}, {target_end}]"
                            )
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
            avg_line_height = (
                target_doc_height / target_line_count if target_line_count > 0 else 0
            )

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
        self.parent1_edit.setObjectName("parent1_edit")
        self.result_edit.setObjectName("result_edit")
        self.parent2_edit.setObjectName("parent2_edit")

        # 设置滚动事件处理
        self.parent1_edit.verticalScrollBar().valueChanged.connect(
            lambda val: self._on_scroll(val, "parent1")
        )
        self.result_edit.verticalScrollBar().valueChanged.connect(
            lambda val: self._on_scroll(val, "result")
        )
        self.parent2_edit.verticalScrollBar().valueChanged.connect(
            lambda val: self._on_scroll(val, "parent2")
        )

        # 设置水平滚动同步
        self.parent1_edit.horizontalScrollBar().valueChanged.connect(
            lambda val: self._sync_hscroll(val, "parent1")
        )
        self.result_edit.horizontalScrollBar().valueChanged.connect(
            lambda val: self._sync_hscroll(val, "result")
        )
        self.parent2_edit.horizontalScrollBar().valueChanged.connect(
            lambda val: self._sync_hscroll(val, "parent2")
        )

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
                left_start=i1, left_end=i2, right_start=j1, right_end=j2, type=tag
            )
            parent1_chunks.append(chunk)

        # 计算parent2和result之间的差异
        parent2_matcher = difflib.SequenceMatcher(None, result_lines, parent2_lines)
        parent2_chunks = []

        for tag, i1, i2, j1, j2 in parent2_matcher.get_opcodes():
            print(f"\nParent2差异块: {tag}, {i1}-{i2}, {j1}-{j2}")
            chunk = DiffChunk(
                left_start=i1, left_end=i2, right_start=j1, right_end=j2, type=tag
            )
            parent2_chunks.append(chunk)

        # 更新差异高亮
        print("\n=== 更新差异高亮 ===")
        print(f"Parent1差异块数量: {len(parent1_chunks)}")
        print(f"Parent2差异块数量: {len(parent2_chunks)}")

        self.parent1_edit.highlighter.set_diff_chunks(parent1_chunks)
        self.result_edit.highlighter.set_diff_chunks(parent1_chunks + parent2_chunks)
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
                "parent1": self.parent1_edit,
                "result": self.result_edit,
                "parent2": self.parent2_edit,
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
                    avg_line_height = (
                        target_doc_height / target_line_count
                        if target_line_count > 0
                        else 0
                    )

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
                "parent1": self.parent1_edit,
                "result": self.result_edit,
                "parent2": self.parent2_edit,
            }

            # 同步其他编辑器的水平滚动
            for name, editor in editors.items():
                if name != source:
                    editor.horizontalScrollBar().setValue(value)
        finally:
            self._sync_hscroll_lock = False
