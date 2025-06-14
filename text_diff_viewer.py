import logging
from typing import Optional

from PyQt6.QtCore import QPoint
from PyQt6.QtGui import QColor, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QTextEdit, QVBoxLayout, QWidget

from diff_calculator import DiffCalculator, DiffChunk, DifflibCalculator
from diff_highlighter import MultiHighlighter
from editors.text_edit import SyncedTextEdit
from utils.language_map import LANGUAGE_MAP


class DiffViewer(QWidget):
    def __init__(self, diff_calculator: DiffCalculator | None = None):
        super().__init__()
        self.actual_diff_chunks = []
        self.current_diff_index = -1
        self.setup_ui()
        self._sync_vscroll_lock = False
        self._sync_hscroll_lock = False

        # 设置差异计算器，默认为 DifflibCalculator
        self.diff_calculator = diff_calculator or DifflibCalculator()

    def _scroll_to_current_diff(self):
        if 0 <= self.current_diff_index < len(self.actual_diff_chunks):
            chunk = self.actual_diff_chunks[self.current_diff_index]
            logging.info(
                f"Scrolling to diff chunk index {self.current_diff_index}: "
                f"Type: {chunk.type}, "
                f"Left: {chunk.left_start}-{chunk.left_end}, "
                f"Right: {chunk.right_start}-{chunk.right_end}"
            )

            # Scroll left editor to the start of the diff chunk
            # We assume chunk line numbers are 0-indexed as per typical difflib usage
            # and findBlockByNumber expectation.
            # If a chunk indicates no lines on one side (e.g., pure insertion/deletion),
            # we scroll to the line *before* where the change is indicated, or line 0.

            left_target_line = chunk.left_start
            if chunk.left_start == chunk.left_end and chunk.type == "insert":  # Insertion in right, so left has a "gap"
                # Try to scroll to the line before the insertion point on the left
                left_target_line = max(0, chunk.left_start - 1) if chunk.left_start > 0 else 0

            right_target_line = chunk.right_start
            if (
                chunk.right_start == chunk.right_end and chunk.type == "delete"
            ):  # Deletion in right, so right has a "gap"
                # Try to scroll to the line before the deletion point on the right
                right_target_line = max(0, chunk.right_start - 1) if chunk.right_start > 0 else 0

            # For "modify" or "equal" (though "equal" is filtered out for actual_diff_chunks),
            # left_start and right_start are the lines to go to.
            # For "delete" (text removed from left, shown as gap in right), scroll left_edit to left_start, right_edit to right_start (which is the line before deletion).
            # For "insert" (text added to right, shown as gap in left), scroll left_edit to left_start (line before insertion), right_edit to right_start.

            # Clear previous highlights
            self.left_edit.clear_highlighted_line()
            self.right_edit.clear_highlighted_line()

            # Set new highlights based on the chunk type
            # left_target_line and right_target_line are what the view will be scrolled to.
            # Highlighting these lines provides a consistent UX with the scroll position.
            # For the side that has the actual content of the change (e.g., right side for "insert", left side for "delete"),
            # we highlight the start of that content block.

            if chunk.type == "insert":
                # Content added to right. Right editor highlights start of new block (chunk.right_start).
                # Left editor highlights the line it's scrolled to (left_target_line, typically line before insertion).
                if chunk.right_start < self.right_edit.document().blockCount():  # Check line validity
                    self.right_edit.set_highlighted_line(chunk.right_start)
                if left_target_line < self.left_edit.document().blockCount():  # Check line validity
                    self.left_edit.set_highlighted_line(left_target_line)
            elif chunk.type == "delete":
                # Content removed from left. Left editor highlights start of removed block (chunk.left_start).
                # Right editor highlights the line it's scrolled to (right_target_line, typically line before deletion).
                if chunk.left_start < self.left_edit.document().blockCount():  # Check line validity
                    self.left_edit.set_highlighted_line(chunk.left_start)
                if right_target_line < self.right_edit.document().blockCount():  # Check line validity
                    self.right_edit.set_highlighted_line(right_target_line)
            elif chunk.type == "replace":  # <--- This line is changed
                # Content modified in both. Both editors highlight start of modified block.
                if chunk.left_start < self.left_edit.document().blockCount():  # Check line validity
                    self.left_edit.set_highlighted_line(chunk.left_start)
                if chunk.right_start < self.right_edit.document().blockCount():  # Check line validity
                    self.right_edit.set_highlighted_line(chunk.right_start)

            self.left_edit.scroll_to_line(left_target_line)
            self.right_edit.scroll_to_line(right_target_line)

            logging.info(
                f"Called scroll_to_line for left editor to line {left_target_line}, right editor to line {right_target_line}"
            )
        else:
            logging.warning(
                f"Skipping scroll: current_diff_index={self.current_diff_index}, num_actual_diffs={len(self.actual_diff_chunks)}"
            )

    def _update_button_states(self):
        num_actual_diffs = len(self.actual_diff_chunks)
        prev_enabled = self.current_diff_index > 0
        next_enabled = self.current_diff_index < num_actual_diffs - 1

        # Special case for initial load when diffs exist, current_diff_index is -1
        if self.current_diff_index == -1 and num_actual_diffs > 0:
            next_enabled = True  # Allow "Next" to reach the first diff

        self.prev_diff_button.setEnabled(prev_enabled)
        self.next_diff_button.setEnabled(next_enabled)

        logging.info(
            f"Updating button states: num_actual_diffs={num_actual_diffs}, current_diff_index={self.current_diff_index} -> "
            f"Prev button enabled: {prev_enabled}, Next button enabled: {next_enabled}"
        )
        # Log the special handling for the next button if current_diff_index is -1 and diffs exist
        if (
            self.current_diff_index == -1 and num_actual_diffs > 0 and not next_enabled
        ):  # This case should not happen due to logic above, but good to log
            logging.info("Initial state with diffs: Next button forced to enabled to reach first diff.")

    def setup_ui(self):
        # Button layout
        button_layout = QHBoxLayout()
        self.prev_diff_button = QPushButton("Previous Change")
        self.next_diff_button = QPushButton("Next Change")
        self.prev_diff_button.setEnabled(False)
        self.next_diff_button.setEnabled(False)
        self.prev_diff_button.clicked.connect(self.navigate_to_previous_diff)
        self.next_diff_button.clicked.connect(self.navigate_to_next_diff)
        button_layout.addWidget(self.prev_diff_button)
        button_layout.addWidget(self.next_diff_button)

        # Text editor layout
        editor_layout = QHBoxLayout()
        editor_layout.setSpacing(0)
        editor_layout.setContentsMargins(0, 0, 0, 0)

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

        self.left_edit.horizontalScrollBar().valueChanged.connect(lambda val: self._sync_hscroll(val, 0))
        self.right_edit.horizontalScrollBar().valueChanged.connect(lambda val: self._sync_hscroll(val, 1))

        # 添加差异高亮器
        self.left_edit.highlighter = MultiHighlighter(self.left_edit.document(), "left", self.right_edit.document())
        self.right_edit.highlighter = MultiHighlighter(self.right_edit.document(), "right", self.left_edit.document())

        # 添加到布局
        editor_layout.addWidget(self.left_edit)
        editor_layout.addWidget(self.right_edit)

        # Main layout
        main_layout = QVBoxLayout()
        main_layout.addLayout(button_layout)
        main_layout.addLayout(editor_layout)
        self.setLayout(main_layout)

        # Clear any initial highlights
        self.left_edit.clear_highlighted_line()
        self.right_edit.clear_highlighted_line()

    def set_texts(
        self,
        left_text: str,
        right_text: str,
        file_path: str,
        left_commit_hash: Optional[str],
        right_commit_hash: Optional[str],
    ):
        """设置要比较的文本"""
        self.left_edit.clear_highlighted_line()
        self.right_edit.clear_highlighted_line()
        # self.current_diff_index = -1 # This is already handled in _compute_diff, which is called shortly after.
        # Keeping it here can be redundant but harmless.
        # For clarity, let _compute_diff manage current_diff_index.
        logging.debug("\n=== 设置新的文本进行比较 ===")
        # 先设置文本
        self.left_edit.setPlainText(left_text)
        self.right_edit.setPlainText(right_text)

        # Set file_path and commit_hash for blame functionality
        self.left_edit.file_path = file_path
        self.left_edit.current_commit_hash = left_commit_hash
        self.right_edit.file_path = file_path
        self.right_edit.current_commit_hash = right_commit_hash

        # 计算差异
        self._compute_diff(left_text, right_text)

        language = LANGUAGE_MAP.get(file_path.split(".")[-1], "text")
        self.left_edit.highlighter.set_language(language)
        self.right_edit.highlighter.set_language(language)

        if hasattr(self.left_edit.highlighter, "empty_block_numbers"):
            selections = []
            for block_number in self.left_edit.highlighter.empty_block_numbers:
                selection = QTextEdit.ExtraSelection()
                char_format = QTextCharFormat()
                char_format.setBackground(QColor(255, 200, 200))  # 浅红色背景
                char_format.setProperty(QTextCharFormat.Property.FullWidthSelection, True)  # 关键
                selection.format = char_format

                block = self.left_edit.document().findBlockByNumber(block_number)
                cursor = QTextCursor(block)
                cursor.select(QTextCursor.SelectionType.BlockUnderCursor)

                selection.cursor = cursor
                selections.append(selection)
            if selections:
                self.left_edit.setExtraSelections(selections)

    def _compute_diff(self, left_text: str, right_text: str):
        self.diff_chunks = self.diff_calculator.compute_diff(left_text, right_text)

        self.left_edit.highlighter.set_diff_chunks(self.diff_chunks)
        self.right_edit.highlighter.set_diff_chunks(self.diff_chunks)

        self.left_edit.highlighter.set_texts(left_text, right_text)
        self.right_edit.highlighter.set_texts(left_text, right_text)

        logging.info(f"Total diff chunks from algorithm: {len(self.diff_chunks)}")
        self.actual_diff_chunks = [chunk for chunk in self.diff_chunks if chunk.type != "equal"]
        logging.info(f"Number of actual (non-equal) diff chunks: {len(self.actual_diff_chunks)}")
        self.current_diff_index = -1  # Start before the first diff
        self._update_button_states()  # Initial state for buttons
        # Special handling for enabling "Next" is now within _update_button_states

    def navigate_to_previous_diff(self):
        logging.info(f"Attempting to navigate to previous diff. Current index: {self.current_diff_index}")
        if not self.actual_diff_chunks:
            self.left_edit.clear_highlighted_line()
            self.right_edit.clear_highlighted_line()
            logging.info("No actual diffs to navigate. Cleared highlights.")
            return
        if self.current_diff_index > 0:
            self.current_diff_index -= 1
            logging.info(f"Navigating to previous diff. New index: {self.current_diff_index}")
            self._scroll_to_current_diff()
            # Log chunk details after scroll
            if 0 <= self.current_diff_index < len(self.actual_diff_chunks):
                chunk = self.actual_diff_chunks[self.current_diff_index]
                logging.info(
                    f"Navigated to chunk: Type: {chunk.type}, "
                    f"Left: {chunk.left_start}-{chunk.left_end}, "
                    f"Right: {chunk.right_start}-{chunk.right_end}"
                )
        else:
            logging.info("Already at the first diff or no diffs to navigate back to.")
        self._update_button_states()

    def navigate_to_next_diff(self):
        logging.info(f"Attempting to navigate to next diff. Current index: {self.current_diff_index}")
        if not self.actual_diff_chunks:
            self.left_edit.clear_highlighted_line()
            self.right_edit.clear_highlighted_line()
            logging.info("No actual diffs to navigate. Cleared highlights.")
            return
        if self.current_diff_index < len(self.actual_diff_chunks) - 1:
            self.current_diff_index += 1
            logging.info(f"Navigating to next diff. New index: {self.current_diff_index}")
            self._scroll_to_current_diff()
            # Log chunk details after scroll
            if 0 <= self.current_diff_index < len(self.actual_diff_chunks):
                chunk = self.actual_diff_chunks[self.current_diff_index]
                logging.info(
                    f"Navigated to chunk: Type: {chunk.type}, "
                    f"Left: {chunk.left_start}-{chunk.left_end}, "
                    f"Right: {chunk.right_start}-{chunk.right_end}"
                )
        else:
            logging.info("Already at the last diff or no diffs to navigate forward to.")
        self._update_button_states()

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
                        if target_size == 0 and chunk.type == "delete":
                            # 对于删除块，使用当前行号减去删除的行数
                            logging.debug(
                                "current_line: %d, source_end: %d, source_start: %d, chunk type %s",
                                current_line,
                                source_end,
                                source_start,
                                chunk.type,
                            )
                            target_line = current_line - (source_end - source_start)
                        else:
                            # 对于其他类型的块，使用相对位置计算
                            logging.debug(
                                "block_progress: %f, target_size: %d, target_start: %d",
                                block_progress,
                                target_size,
                                target_start,
                            )
                            target_line = target_start + int(block_progress * target_size)
                        logging.debug(
                            "在差异块内 [%d, %d] -> [%d, %d]",
                            source_start,
                            source_end,
                            target_start,
                            target_end,
                        )
                        print(chunk)
                        logging.debug("块内进度：%.2f, 目标行：%d", block_progress, target_line)
                        break
                    else:
                        # 如果已经过了这个差异块，直接累加差异
                        accumulated_diff += size_diff
                        logging.debug(
                            "经过差异块 [%d, %d] -> [%d, %d]",
                            source_start,
                            source_end,
                            target_start,
                            target_end,
                        )
                        logging.debug("累计调整：%d", accumulated_diff)

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
            logging.debug("\n=== %s 滚动事件开始 ===", "左侧" if is_left_scroll else "右侧")

            # 获取源编辑器和目标编辑器
            source_edit = self.left_edit if is_left_scroll else self.right_edit
            target_edit = self.right_edit if is_left_scroll else self.left_edit

            # 获取当前视口中的行
            cursor = source_edit.cursorForPosition(QPoint(0, 0))
            current_line = cursor.blockNumber()
            logging.debug("当前视口起始行：%d", current_line)

            # 计算目标行号
            target_line = self._calculate_target_line(current_line, self.diff_chunks, is_left_scroll)

            # 计算滚动值
            target_scroll = self._calculate_scroll_value(target_edit, target_line)
            logging.debug(
                "目标编辑器：%s, 目标行：%d, 目标滚动值：%d",
                target_edit.objectName(),
                target_line,
                target_scroll,
            )

            # 设置滚动条位置
            target_edit.verticalScrollBar().setValue(target_scroll)

            logging.debug("=== %s 滚动事件结束 ===\n", "左侧" if is_left_scroll else "右侧")

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
    def __init__(self, diff_calculator: DiffCalculator | None = None):
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
        self.parent1_edit.verticalScrollBar().valueChanged.connect(lambda val: self._on_scroll(val, "parent1"))
        self.result_edit.verticalScrollBar().valueChanged.connect(lambda val: self._on_scroll(val, "result"))
        self.parent2_edit.verticalScrollBar().valueChanged.connect(lambda val: self._on_scroll(val, "parent2"))

        # 设置水平滚动同步
        self.parent1_edit.horizontalScrollBar().valueChanged.connect(lambda val: self._sync_hscroll(val, "parent1"))
        self.result_edit.horizontalScrollBar().valueChanged.connect(lambda val: self._sync_hscroll(val, "result"))
        self.parent2_edit.horizontalScrollBar().valueChanged.connect(lambda val: self._sync_hscroll(val, "parent2"))

        # 添加到布局
        layout.addWidget(self.parent1_edit)
        layout.addWidget(self.result_edit)
        layout.addWidget(self.parent2_edit)
        self.setLayout(layout)

    def set_texts(
        self,
        parent1_text: str,
        result_text: str,
        parent2_text: str,
        file_path: str,
        parent1_commit_hash: Optional[str],
        result_commit_hash: Optional[str],
        parent2_commit_hash: Optional[str],
    ):
        """设置要比较的三个文本"""
        logging.debug("\n=== 设置新的三向文本进行比较 ===")
        # 设置文本
        self.parent1_edit.setPlainText(parent1_text)
        self.result_edit.setPlainText(result_text)
        self.parent2_edit.setPlainText(parent2_text)

        # Set file_path and commit_hash for blame functionality
        self.parent1_edit.file_path = file_path
        self.parent1_edit.current_commit_hash = parent1_commit_hash
        self.result_edit.file_path = file_path
        self.result_edit.current_commit_hash = result_commit_hash
        self.parent2_edit.file_path = file_path
        self.parent2_edit.current_commit_hash = parent2_commit_hash

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
                        type=chunk_type,
                    )
                else:
                    current_chunk.left_end = line_num + 1
                    current_chunk.right_end = line_num + 1
            elif current_chunk:
                result_chunks.append(current_chunk)
                current_chunk = None

        if current_chunk:
            result_chunks.append(current_chunk)

        self.result_edit.highlighter.set_diff_chunks(result_chunks)

    def _on_scroll(self, value, source: str):
        """处理滚动同步
        Args:
            value: 滚动条的值
            source: 滚动源 ('parent1', 'result', 'parent2')
        """
        if self._sync_vscroll_lock:
            return

        self._sync_vscroll_lock = True
        try:
            logging.debug("\n=== %s 滚动事件开始 ===", source)

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
            logging.debug("当前视口起始行：%d", current_line)

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
                    logging.debug("目标行：%d, 目标滚动值：%d", target_line, target_scroll)

                    # 设置滚动条位置
                    target_edit.verticalScrollBar().setValue(target_scroll)

            logging.debug("=== %s 滚动事件结束 ===\n", source)

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
