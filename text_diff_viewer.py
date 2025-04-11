from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QHBoxLayout, QWidget

from diff_calculator import DiffCalculator, DiffChunk, DifflibCalculator
from diff_highlighter import DiffHighlighter
from text_edit import SyncedTextEdit


class DiffViewer(QWidget):
    def __init__(self, diff_calculator: DiffCalculator = None):
        super().__init__()
        self.setup_ui()
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
        self.diff_chunks = self.diff_calculator.compute_diff(left_text, right_text)

        self.left_diff_highlighter.set_diff_chunks(self.diff_chunks)
        self.right_diff_highlighter.set_diff_chunks(self.diff_chunks)

    def _calculate_target_line(self, current_line: int, diff_chunks: list, is_left_scroll: bool) -> int:
        """计算目标行号
        Args:
            current_line: 当前行号
            diff_chunks: 差异块列表
            is_left_scroll: 是否是左侧滚动
        Returns:
            int: 目标行号
        """
        target_line = current_line
        accumulated_diff = 0
        for chunk in diff_chunks:
            if chunk.type != "equal":
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
                        if target_size == 0:
                            # 对于删除块，使用当前行号减去删除的行数
                            target_line = current_line - (source_end - source_start)
                        else:
                            # 对于其他类型的块，使用相对位置计算
                            target_line = target_start + int(block_progress * target_size)
                        print(f"在差异块内 [{source_start}, {source_end}] -> [{target_start}, {target_end}]")
                        print(f"块内进度: {block_progress:.2f}, 目标行: {target_line}")
                        break
                    else:
                        # 如果已经过了这个差异块，直接累加差异
                        accumulated_diff += size_diff
                        print(f"经过差异块 [{source_start}, {source_end}] -> [{target_start}, {target_end}]")
                        print(f"累计调整: {accumulated_diff}")

        # 如果不在任何差异块内，应用累计的差异
        if target_line == current_line:
            target_line += accumulated_diff
        return target_line

    def _calculate_scroll_value(self, target_edit: SyncedTextEdit, target_line: int) -> int:
        """计算滚动值
        Args:
            target_edit: 目标编辑器
            target_line: 目标行号
        Returns:
            int: 滚动值
        """
        # 计算目标文档中的滚动值
        target_bar = target_edit.verticalScrollBar()
        target_max = target_bar.maximum()

        # 根据目标行号计算滚动值
        target_doc_height = target_edit.document().size().height()
        target_line_count = target_edit.document().blockCount()
        avg_line_height = target_doc_height / target_line_count if target_line_count > 0 else 0

        # 直接使用目标行号计算滚动值
        target_scroll = int(target_line * avg_line_height)

        # 确保滚动值在有效范围内
        return max(0, min(target_scroll, target_max))

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
            print(f"\n=== {'左侧' if is_left_scroll else '右侧'} 滚动事件开始 ===")

            # 获取源编辑器和目标编辑器
            source_edit = self.left_edit if is_left_scroll else self.right_edit
            target_edit = self.right_edit if is_left_scroll else self.left_edit

            # 获取当前视口中的行
            cursor = source_edit.cursorForPosition(QPoint(0, 0))
            current_line = cursor.blockNumber()
            print(f"当前视口起始行: {current_line}")

            # 计算目标行号
            target_line = self._calculate_target_line(current_line, self.diff_chunks, is_left_scroll)

            # 计算滚动值
            target_scroll = self._calculate_scroll_value(target_edit, target_line)
            print(f"目标行: {target_line}, 目标滚动值: {target_scroll}")

            # 设置滚动条位置
            target_edit.verticalScrollBar().setValue(target_scroll)

            print(f"=== {'左侧' if is_left_scroll else '右侧'} 滚动事件结束 ===\n")

        finally:
            self._sync_vscroll_lock = False

    def _sync_hscroll(self, value, source: int):
        """处理水平滚动同步"""
        if self._sync_hscroll_lock:
            return

        try:
            self._sync_hscroll_lock = True
            # 同步另一个编辑器的水平滚动
            target_edit = self.right_edit if source == 0 else self.left_edit
            target_edit.horizontalScrollBar().setValue(value)
        finally:
            self._sync_hscroll_lock = False


class MergeDiffViewer(DiffViewer):
    def __init__(self, diff_calculator: DiffCalculator = None):
        super().__init__(diff_calculator)
        self.parent1_chunks = []
        self.parent2_chunks = []

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
        # 计算 parent1 和 result 的差异
        self.parent1_chunks = self.diff_calculator.compute_diff(parent1_text, result_text)
        # 计算 result 和 parent2 的差异
        self.parent2_chunks = self.diff_calculator.compute_diff(result_text, parent2_text)

        # 设置高亮
        self.parent1_edit.highlighter.set_diff_chunks(self.parent1_chunks)
        self.parent2_edit.highlighter.set_diff_chunks(self.parent2_chunks)
        
        # 为 result 编辑器创建转换后的差异块
        result_chunks = []
        
        # 获取 result 中的所有行
        result_lines = result_text.splitlines()
        
        # 创建一个映射来标记每一行的状态
        line_status = {}  # key: line_number, value: (in_parent1, in_parent2)
        
        # 初始化所有行的状态
        for i in range(len(result_lines)):
            line_status[i] = [True, True]  # 默认在两个父版本中都存在
            
        # 处理 parent1 的差异
        for chunk in self.parent1_chunks:
            if chunk.type != "equal":
                # 标记这些行与 parent1 不同
                for i in range(chunk.right_start, chunk.right_end):
                    line_status[i][0] = False
                    
        # 处理 parent2 的差异
        for chunk in self.parent2_chunks:
            if chunk.type != "equal":
                # 标记这些行与 parent2 不同
                for i in range(chunk.left_start, chunk.left_end):
                    line_status[i][1] = False
        
        # 根据行状态创建差异块
        current_chunk = None
        for line_num, (in_parent1, in_parent2) in line_status.items():
            chunk_type = None
            if not in_parent1 and not in_parent2:
                chunk_type = "conflict"  # 与两个父版本都不同
            elif not in_parent1:
                chunk_type = "parent1_diff"  # 只与 parent1 不同
            elif not in_parent2:
                chunk_type = "parent2_diff"  # 只与 parent2 不同
            
            if chunk_type:
                if current_chunk is None or current_chunk.type != chunk_type:
                    if current_chunk:
                        result_chunks.append(current_chunk)
                    current_chunk = DiffChunk(
                        left_start=line_num,
                        left_end=line_num + 1,
                        right_start=line_num,
                        right_end=line_num + 1,
                        type=chunk_type
                    )
                else:
                    current_chunk.left_end = line_num + 1
                    current_chunk.right_end = line_num + 1
            else:
                if current_chunk:
                    result_chunks.append(current_chunk)
                    current_chunk = None
        
        if current_chunk:
            result_chunks.append(current_chunk)
        
        self.result_edit.highlighter.set_diff_chunks(result_chunks)

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
            print(f"当前视口起始行: {current_line}")

            # 同步其他编辑器的滚动
            for target_name, target_edit in editors.items():
                if target_name != source:
                    # 根据源和目标确定使用哪个差异块
                    if source == "parent1" and target_name == "result":
                        diff_chunks = self.parent1_chunks
                        is_left_scroll = True
                    elif source == "result" and target_name == "parent1":
                        diff_chunks = self.parent1_chunks
                        is_left_scroll = False
                    elif source == "result" and target_name == "parent2":
                        diff_chunks = self.parent2_chunks
                        is_left_scroll = True
                    elif source == "parent2" and target_name == "result":
                        diff_chunks = self.parent2_chunks
                        is_left_scroll = False
                    elif source == "parent1" and target_name == "parent2":
                        # 通过 parent1->result 和 result->parent2 的差异推导出 parent1->parent2 的差异
                        diff_chunks = self.parent1_chunks + self.parent2_chunks
                        is_left_scroll = True
                    elif source == "parent2" and target_name == "parent1":
                        # 通过 parent2->result 和 result->parent1 的差异推导出 parent2->parent1 的差异
                        diff_chunks = self.parent2_chunks + self.parent1_chunks
                        is_left_scroll = False
                    else:
                        # 如果不需要考虑差异块，直接使用行号同步
                        diff_chunks = []
                        is_left_scroll = True

                    # 计算目标行号
                    target_line = self._calculate_target_line(current_line, diff_chunks, is_left_scroll)

                    # 计算滚动值
                    target_scroll = self._calculate_scroll_value(target_edit, target_line)
                    print(f"目标行: {target_line}, 目标滚动值: {target_scroll}")

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
