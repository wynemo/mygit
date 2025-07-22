import logging
import os
from typing import Optional

from PyQt6.QtCore import QPoint, Qt, QTimer
from PyQt6.QtGui import QColor, QIcon, QKeyEvent, QTextCharFormat, QTextCursor
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

        # cursor 生成：添加反向还原按钮相关的属性
        self.restore_buttons = []  # 存储所有的还原按钮
        self.right_edit_is_editable = False  # 标记右侧编辑器是否可编辑

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
            self.left_edit.clear_block_background()
            self.right_edit.clear_block_background()

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
                    # 设置右侧代码块背景
                    self.right_edit.set_block_background(chunk.right_start, chunk.right_end)
                if left_target_line < self.left_edit.document().blockCount():  # Check line validity
                    self.left_edit.set_highlighted_line(left_target_line)
            elif chunk.type == "delete":
                # Content removed from left. Left editor highlights start of removed block (chunk.left_start).
                # Right editor highlights the line it's scrolled to (right_target_line, typically line before deletion).
                if chunk.left_start < self.left_edit.document().blockCount():  # Check line validity
                    self.left_edit.set_highlighted_line(chunk.left_start)
                    # 设置左侧代码块背景
                    self.left_edit.set_block_background(chunk.left_start, chunk.left_end)
                if right_target_line < self.right_edit.document().blockCount():  # Check line validity
                    self.right_edit.set_highlighted_line(right_target_line)
            elif chunk.type == "replace":  # <--- This line is changed
                # Content modified in both. Both editors highlight start of modified block.
                if chunk.left_start < self.left_edit.document().blockCount():  # Check line validity
                    self.left_edit.set_highlighted_line(chunk.left_start)
                    # 设置左侧代码块背景
                    self.left_edit.set_block_background(chunk.left_start, chunk.left_end)
                if chunk.right_start < self.right_edit.document().blockCount():  # Check line validity
                    self.right_edit.set_highlighted_line(chunk.right_start)
                    # 设置右侧代码块背景
                    self.right_edit.set_block_background(chunk.right_start, chunk.right_end)

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

    def _create_icon_button(self, icon_path: str, tooltip: str) -> QPushButton:
        """cursor 生成：创建带SVG图标的按钮"""
        button = QPushButton()
        button.setIcon(QIcon(icon_path))
        button.setIconSize(button.sizeHint().scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio))  # 设置更小的图标大小
        button.setFixedSize(24, 24)  # 设置更小的固定大小
        button.setToolTip(tooltip)
        # 设置按钮样式，移除边框和背景，只显示箭头
        button.setStyleSheet("""
            QPushButton {
                border: none;
                background: transparent;
                padding: 0px;
            }
            QPushButton:hover {
                background: rgba(0, 0, 0, 0.1);
                border-radius: 6px;
            }
            QPushButton:pressed {
                background: rgba(0, 0, 0, 0.2);
                border-radius: 6px;
            }
            QPushButton:disabled {
                background: transparent;
                opacity: 0.3;
            }
        """)
        return button

    def setup_ui(self):
        # Button layout
        button_layout = QHBoxLayout()
        button_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)  # 左对齐

        # cursor 生成：使用SVG图标替换文本按钮
        up_icon_path = os.path.join(os.path.dirname(__file__), "icons", "up.svg")
        down_icon_path = os.path.join(os.path.dirname(__file__), "icons", "down.svg")

        self.prev_diff_button = self._create_icon_button(up_icon_path, "Previous Change")
        self.next_diff_button = self._create_icon_button(down_icon_path, "Next Change")

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
        self.left_edit.clear_block_background()
        self.right_edit.clear_block_background()

    def set_texts(
        self,
        left_text: str,
        right_text: str,
        file_path: str,
        right_file_path: str | None = None,
        left_commit_hash: str | None = None,
        right_commit_hash: str | None = None,
    ):
        """设置要比较的文本"""
        self.left_edit.clear_highlighted_line()
        self.right_edit.clear_highlighted_line()
        self.left_edit.clear_block_background()
        self.right_edit.clear_block_background()
        # self.current_diff_index = -1 # This is already handled in _compute_diff, which is called shortly after.
        # Keeping it here can be redundant but harmless.
        # For clarity, let _compute_diff manage current_diff_index.
        logging.debug("\n=== 设置新的文本进行比较 ===")

        # cursor 生成：检查右侧编辑器是否可编辑
        self.right_edit_is_editable = not self.right_edit.isReadOnly()

        # 先设置文本
        self.left_edit.setPlainText(left_text)
        self.right_edit.setPlainText(right_text)

        # Set file_path and commit_hash for blame functionality
        self.left_edit.file_path = file_path
        self.left_edit.current_commit_hash = left_commit_hash
        self.right_edit.file_path = file_path if right_file_path is None else right_file_path
        self.right_edit.current_commit_hash = right_commit_hash

        # 计算差异
        self._compute_diff(left_text, right_text)

        language = LANGUAGE_MAP.get(file_path.split(".")[-1], "text")
        self.left_edit.highlighter.set_language(language)
        language = LANGUAGE_MAP.get(self.right_edit.file_path.split(".")[-1], "text")
        self.right_edit.highlighter.set_language(language)

        if hasattr(self.left_edit.highlighter, "empty_block_numbers"):
            selections = []
            for block_number in self.left_edit.highlighter.empty_block_numbers:
                selection = QTextEdit.ExtraSelection()
                char_format = QTextCharFormat()
                char_format.setBackground(QColor(220, 220, 220))  # 浅灰色背景
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

        # cursor 生成：如果右侧可编辑，创建还原按钮
        if self.right_edit_is_editable:
            self._create_restore_buttons()

    def _create_restore_buttons(self):
        """cursor 生成：为左侧的每个修改块创建还原按钮"""
        # 清除之前的按钮
        self._clear_restore_buttons()

        for chunk in self.actual_diff_chunks:
            # 为 delete、replace 和 insert 类型的 chunk 创建按钮
            if chunk.type in ["delete", "replace", "insert"]:
                button = QPushButton("→")
                button.setFixedSize(20, 20)
                button.setStyleSheet("""
                    QPushButton {
                        background-color: #4CAF50;
                        color: white;
                        border: none;
                        border-radius: 10px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #45a049;
                    }
                    QPushButton:pressed {
                        background-color: #3d8b40;
                    }
                """)
                button.setToolTip("点击将左侧内容还原到右侧")

                # 连接点击事件，传递 chunk 信息
                button.clicked.connect(lambda checked, c=chunk: self._restore_chunk_to_right(c))

                # 设置按钮为左侧编辑器的子 widget
                button.setParent(self.left_edit)
                button.show()

                self.restore_buttons.append(button)

        # 定位按钮
        self._position_restore_buttons()

    def _clear_restore_buttons(self):
        """cursor 生成：清除所有还原按钮"""
        for button in self.restore_buttons:
            button.deleteLater()
        self.restore_buttons.clear()

    def _position_restore_buttons(self):
        """cursor 生成：定位还原按钮到合适的位置"""
        for i, button in enumerate(self.restore_buttons):
            # 找到对应的 chunk
            chunk_index = 0
            for chunk in self.actual_diff_chunks:
                if chunk.type in ["delete", "replace", "insert"]:
                    if chunk_index == i:
                        # 计算按钮位置
                        line_number = chunk.left_start
                        if line_number <= self.left_edit.document().blockCount():
                            block = self.left_edit.document().findBlockByNumber(line_number - 1)
                            block_geometry = self.left_edit.blockBoundingGeometry(block)
                            block_top = block_geometry.translated(self.left_edit.contentOffset()).top()

                            # 将按钮放在左侧编辑器的右边边缘，避免被滚动条遮挡
                            x = self.left_edit.width() - 45  # 增加更多的边距避免滚动条
                            y = int(block_top) + 2

                            print(
                                f"-------------- chunk: {chunk}, line_number: {line_number}, block_top: {block_top}, x: {x}, y: {y}"
                            )
                            button.move(x, y)
                        break
                    chunk_index += 1

    def _restore_chunk_to_right(self, chunk: DiffChunk):
        """cursor 生成：将指定 chunk 的左侧内容还原到右侧"""
        if not self.right_edit_is_editable:
            return

        try:
            # cursor 生成：保存当前的滚动位置
            left_scroll_value = self.left_edit.verticalScrollBar().value()
            right_scroll_value = self.right_edit.verticalScrollBar().value()

            # 获取左侧的内容
            left_lines = self.left_edit.toPlainText().splitlines()
            right_lines = self.right_edit.toPlainText().splitlines()

            if chunk.type == "delete":
                # 删除类型：在右侧插入左侧被删除的内容
                deleted_lines = left_lines[chunk.left_start : chunk.left_end]
                # 在右侧的对应位置插入
                right_lines[chunk.right_start : chunk.right_start] = deleted_lines

            elif chunk.type == "replace":
                # 替换类型：用左侧的内容替换右侧的内容
                original_lines = left_lines[chunk.left_start : chunk.left_end]
                right_lines[chunk.right_start : chunk.right_end] = original_lines

            elif chunk.type == "insert":
                # 插入类型：移除右侧新增的内容
                del right_lines[chunk.right_start : chunk.right_end]

            # 更新右侧编辑器的内容
            new_content = "\n".join(right_lines)
            self.right_edit.setPlainText(new_content)

            # 保存到磁盘
            self.right_edit.save_content()

            # 重新计算 diff
            left_text = self.left_edit.toPlainText()
            right_text = self.right_edit.toPlainText()
            self._compute_diff(left_text, right_text)

            # cursor 生成：恢复滚动位置
            self.left_edit.verticalScrollBar().setValue(left_scroll_value)
            self.right_edit.verticalScrollBar().setValue(right_scroll_value)

            logging.info(f"已还原 chunk: {chunk.type}, 左侧行 {chunk.left_start}-{chunk.left_end}")

        except Exception:
            logging.exception("还原内容时发生错误")

    def navigate_to_previous_diff(self):
        logging.info("Attempting to navigate to previous diff. Current index: %d", self.current_diff_index)
        if not self.actual_diff_chunks:
            self.left_edit.clear_highlighted_line()
            self.right_edit.clear_highlighted_line()
            self.left_edit.clear_block_background()
            self.right_edit.clear_block_background()
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
        logging.info("Attempting to navigate to next diff. Current index: %d", self.current_diff_index)
        if not self.actual_diff_chunks:
            self.left_edit.clear_highlighted_line()
            self.right_edit.clear_highlighted_line()
            self.left_edit.clear_block_background()
            self.right_edit.clear_block_background()
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

            # cursor 生成：滚动后重新定位还原按钮
            if self.restore_buttons:
                self._position_restore_buttons()

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

    def resizeEvent(self, event):
        """cursor 生成：窗口大小改变时重新定位还原按钮"""
        super().resizeEvent(event)
        if self.restore_buttons:
            # 延迟执行以确保布局完成
            QTimer.singleShot(10, self._position_restore_buttons)


class MergeDiffViewer(DiffViewer):
    def __init__(self, diff_calculator: DiffCalculator | None = None):
        super().__init__(diff_calculator)
        self.parent1_chunks = []
        self.parent2_chunks = []
        self.merged_actual_diff_chunks = []  # For navigation across all 3 panes
        self.current_merged_diff_index = -1  # Index for merged navigation
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # Allow MergeDiffViewer to receive focus

    def setup_ui(self):
        # layout = QHBoxLayout() # Original layout variable, not used now for main structure
        # layout.setSpacing(0)
        # layout.setContentsMargins(0, 0, 0, 0)

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

        # 显式设置 MultiHighlighter
        self.parent1_edit.highlighter = MultiHighlighter(
            self.parent1_edit.document(), "parent1_edit", self.result_edit.document()
        )
        self.parent2_edit.highlighter = MultiHighlighter(
            self.parent2_edit.document(), "parent2_edit", self.result_edit.document()
        )
        self.result_edit.highlighter = MultiHighlighter(self.result_edit.document(), "result_edit", None)

        editor_layout = QHBoxLayout()
        editor_layout.setSpacing(0)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.addWidget(self.parent1_edit)
        editor_layout.addWidget(self.result_edit)
        editor_layout.addWidget(self.parent2_edit)

        # Button layout for navigation
        button_layout = QHBoxLayout()
        button_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)  # 左对齐
        # Ensure these buttons are created for MergeDiffViewer specifically
        up_icon_path = os.path.join(os.path.dirname(__file__), "icons", "up.svg")
        down_icon_path = os.path.join(os.path.dirname(__file__), "icons", "down.svg")

        self.prev_diff_button = self._create_icon_button(up_icon_path, "Previous Change")
        self.next_diff_button = self._create_icon_button(down_icon_path, "Next Change")
        self.prev_diff_button.setEnabled(False)
        self.next_diff_button.setEnabled(False)

        # Connect signals AFTER buttons are created
        # self.prev_diff_button.clicked.disconnect() # Not needed for new buttons
        # self.next_diff_button.clicked.disconnect() # Not needed for new buttons
        self.prev_diff_button.clicked.connect(self.navigate_to_previous_merged_diff)
        self.next_diff_button.clicked.connect(self.navigate_to_next_merged_diff)

        button_layout.addWidget(self.prev_diff_button)
        button_layout.addWidget(self.next_diff_button)

        # Main layout for MergeDiffViewer
        main_layout = QVBoxLayout()
        main_layout.addLayout(button_layout)
        main_layout.addLayout(editor_layout)
        self.setLayout(main_layout)

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

        # 设置语法高亮语言
        language = LANGUAGE_MAP.get(file_path.split(".")[-1], "text")
        if hasattr(self.parent1_edit.highlighter, "set_language"):
            self.parent1_edit.highlighter.set_language(language)
        if hasattr(self.parent2_edit.highlighter, "set_language"):
            self.parent2_edit.highlighter.set_language(language)
        if hasattr(self.result_edit.highlighter, "set_language"):
            self.result_edit.highlighter.set_language(language)

    def _compute_diffs(self, parent1_text: str, result_text: str, parent2_text: str):
        """计算三个文本之间的差异"""
        # 计算 parent1 和 result 的差异
        self.parent1_chunks = self.diff_calculator.compute_diff(parent1_text, result_text)
        # 计算 result 和 parent2 的差异
        self.parent2_chunks = self.diff_calculator.compute_diff(result_text, parent2_text)

        # 设置高亮
        self.parent1_edit.highlighter.set_diff_chunks(self.parent1_chunks)
        self.parent1_edit.highlighter.set_texts(parent1_text, result_text)

        self.parent2_edit.highlighter.set_diff_chunks(self.parent2_chunks)
        self.parent2_edit.highlighter.set_texts(result_text, parent2_text)

        # 为 result 编辑器创建转换后的差异块 (result_edit 仍使用 DiffHighlighter)
        # This logic seems to be for highlighting the result_edit pane, not for navigation.
        # We'll keep it for that purpose.
        result_chunks_for_highlighting = []
        result_lines = result_text.splitlines()
        line_status = {}
        for i in range(len(result_lines)):
            line_status[i] = [True, True]
        for chunk in self.parent1_chunks:
            if chunk.type != "equal":
                for i in range(chunk.right_start, chunk.right_end):
                    if i < len(result_lines):
                        line_status[i][0] = False
        for chunk in self.parent2_chunks:
            if chunk.type != "equal":
                for i in range(chunk.left_start, chunk.left_end):
                    if i < len(result_lines):
                        line_status[i][1] = False

        current_highlight_chunk = None
        for line_num, (in_parent1, in_parent2) in line_status.items():
            chunk_type = None
            if not in_parent1 and not in_parent2:
                chunk_type = "conflict"
            elif not in_parent1:
                chunk_type = "parent1_diff"
            elif not in_parent2:
                chunk_type = "parent2_diff"

            if chunk_type:
                if current_highlight_chunk is None or current_highlight_chunk.type != chunk_type:
                    if current_highlight_chunk:
                        result_chunks_for_highlighting.append(current_highlight_chunk)
                    current_highlight_chunk = DiffChunk(
                        type=chunk_type,
                        left_start=line_num,
                        left_end=line_num + 1,
                        right_start=line_num,
                        right_end=line_num + 1,
                    )
                else:
                    current_highlight_chunk.left_end = line_num + 1
                    current_highlight_chunk.right_end = line_num + 1
            elif current_highlight_chunk:
                result_chunks_for_highlighting.append(current_highlight_chunk)
                current_highlight_chunk = None
        if current_highlight_chunk:
            result_chunks_for_highlighting.append(current_highlight_chunk)

        self.result_edit.highlighter.set_diff_chunks(result_chunks_for_highlighting)
        self.result_edit.highlighter.set_merge_texts(parent1_text, parent2_text, result_text)

        # Prepare merged actual diff chunks for navigation
        self.merged_actual_diff_chunks = []
        # Tag chunks with their origin and original chunk data
        for chunk in self.parent1_chunks:
            if chunk.type != "equal":
                # For P1 vs R diffs, primary sort key is result_start (chunk.right_start)
                self.merged_actual_diff_chunks.append(
                    {"origin": "p1_result", "chunk": chunk, "sort_key": chunk.right_start}
                )

        for chunk in self.parent2_chunks:
            if chunk.type != "equal":
                # For R vs P2 diffs, primary sort key is result_start (chunk.left_start)
                self.merged_actual_diff_chunks.append(
                    {"origin": "result_p2", "chunk": chunk, "sort_key": chunk.left_start}
                )

        # Sort all diffs based on their starting line in the result pane
        self.merged_actual_diff_chunks.sort(key=lambda x: x["sort_key"])

        # Remove duplicate diffs that might occur if a change in Result affects both P1 and P2 identically
        # This is a simple deduplication. More sophisticated logic might be needed if chunks can overlap partially.
        unique_merged_chunks = []
        seen_keys = set()
        for item in self.merged_actual_diff_chunks:
            # Create a unique key for the chunk based on its position in the result pane and type
            # Chunks from p1_result: (type, p1_start, p1_end, result_start, result_end)
            # Chunks from result_p2: (type, result_start, result_end, p2_start, p2_end)
            # We need a canonical representation for deduplication.
            # Key: (result_start, result_end, type_of_change_in_result, content_implication)
            # This is complex. For now, let's use a simpler key based on result lines and origin for sorting,
            # and rely on visual non-duplication for now. True semantic deduplication is harder.
            # Simpler approach: if two consecutive chunks (after sorting) refer to the exact same
            # lines in the result view and have compatible types, consider merging or picking one.
            # For now, we'll keep them and let navigation step through them.
            # The sorting should already group related changes.
            pass  # No explicit deduplication for now, sorting is the primary organization

        self.current_merged_diff_index = -1
        self._update_merged_button_states()

    def _update_merged_button_states(self):
        num_actual_diffs = len(self.merged_actual_diff_chunks)
        prev_enabled = self.current_merged_diff_index > 0
        next_enabled = self.current_merged_diff_index < num_actual_diffs - 1

        if self.current_merged_diff_index == -1 and num_actual_diffs > 0:
            next_enabled = True

        self.prev_diff_button.setEnabled(prev_enabled)
        self.next_diff_button.setEnabled(next_enabled)
        logging.info(
            f"MergeDiffViewer: Updating button states: num_actual_diffs={num_actual_diffs}, current_merged_diff_index={self.current_merged_diff_index} -> "
            f"Prev button enabled: {prev_enabled}, Next button enabled: {next_enabled}"
        )

    def navigate_to_previous_merged_diff(self):
        logging.info(
            "MergeDiffViewer: Attempting to navigate to previous merged diff. Current index: %d",
            self.current_merged_diff_index,
        )
        if not self.merged_actual_diff_chunks:
            # Clear highlights on all three panes
            self.parent1_edit.clear_highlighted_line()
            self.result_edit.clear_highlighted_line()
            self.parent2_edit.clear_highlighted_line()
            self.parent1_edit.clear_block_background()
            self.result_edit.clear_block_background()
            self.parent2_edit.clear_block_background()
            logging.info("MergeDiffViewer: No actual merged diffs to navigate. Cleared highlights.")
            return

        if self.current_merged_diff_index > 0:
            self.current_merged_diff_index -= 1
            logging.info(
                f"MergeDiffViewer: Navigating to previous merged diff. New index: {self.current_merged_diff_index}"
            )
            self._scroll_to_current_merged_diff()
        else:
            logging.info("MergeDiffViewer: Already at the first merged diff or no diffs to navigate back to.")
        self._update_merged_button_states()

    def navigate_to_next_merged_diff(self):
        logging.info(
            "MergeDiffViewer: Attempting to navigate to next merged diff. Current index: %d",
            self.current_merged_diff_index,
        )
        if not self.merged_actual_diff_chunks:
            # Clear highlights on all three panes
            self.parent1_edit.clear_highlighted_line()
            self.result_edit.clear_highlighted_line()
            self.parent2_edit.clear_highlighted_line()
            self.parent1_edit.clear_block_background()
            self.result_edit.clear_block_background()
            self.parent2_edit.clear_block_background()
            logging.info("MergeDiffViewer: No actual merged diffs to navigate. Cleared highlights.")
            return

        if self.current_merged_diff_index < len(self.merged_actual_diff_chunks) - 1:
            self.current_merged_diff_index += 1
            logging.info(
                f"MergeDiffViewer: Navigating to next merged diff. New index: {self.current_merged_diff_index}"
            )
            self._scroll_to_current_merged_diff()
        else:
            logging.info("MergeDiffViewer: Already at the last merged diff or no diffs to navigate forward to.")
        self._update_merged_button_states()

    def _scroll_to_current_merged_diff(self):
        if not (0 <= self.current_merged_diff_index < len(self.merged_actual_diff_chunks)):
            logging.warning(f"MergeDiffViewer: Invalid current_merged_diff_index: {self.current_merged_diff_index}")
            return

        merged_chunk_item = self.merged_actual_diff_chunks[self.current_merged_diff_index]
        origin = merged_chunk_item["origin"]
        chunk = merged_chunk_item["chunk"]  # This is the original DiffChunk

        logging.info(
            f"MergeDiffViewer: Scrolling to diff chunk index {self.current_merged_diff_index}: "
            f"Origin: {origin}, Type: {chunk.type}, "
            f"P1/Res_L: {chunk.left_start}-{chunk.left_end}, Res_R/P2: {chunk.right_start}-{chunk.right_end}"
        )

        # Clear previous highlights on all panes
        for editor in [self.parent1_edit, self.result_edit, self.parent2_edit]:
            editor.clear_highlighted_line()
            editor.clear_block_background()

        # Determine target lines for scrolling and highlighting
        # These are 0-indexed
        p1_target_line, res_target_line, p2_target_line = -1, -1, -1

        if origin == "p1_result":  # Parent1 vs Result
            p1_scroll_to = chunk.left_start
            res_scroll_to = chunk.right_start
            # p2_scroll_to will be synced by _on_scroll based on result_edit's scroll

            # Highlighting for P1 vs Result
            if chunk.type == "insert":  # Insert in Result (right side of p1_result diff)
                self.result_edit.set_highlighted_line(chunk.right_start)
                self.result_edit.set_block_background(chunk.right_start, chunk.right_end)
                # Left (P1) has a "gap", scroll to line before insertion if possible
                p1_scroll_to = max(0, chunk.left_start - 1) if chunk.left_start > 0 else 0
                self.parent1_edit.set_highlighted_line(p1_scroll_to)
            elif chunk.type == "delete":  # Delete in Result (means content present in P1 is missing in Result)
                self.parent1_edit.set_highlighted_line(chunk.left_start)
                self.parent1_edit.set_block_background(chunk.left_start, chunk.left_end)
                # Right (Result) has a "gap", scroll to line before deletion
                res_scroll_to = max(0, chunk.right_start - 1) if chunk.right_start > 0 else 0
                self.result_edit.set_highlighted_line(res_scroll_to)
            elif chunk.type == "replace":
                self.parent1_edit.set_highlighted_line(chunk.left_start)
                self.parent1_edit.set_block_background(chunk.left_start, chunk.left_end)
                self.result_edit.set_highlighted_line(chunk.right_start)
                self.result_edit.set_block_background(chunk.right_start, chunk.right_end)

            self.parent1_edit.scroll_to_line(p1_scroll_to)
            self.result_edit.scroll_to_line(res_scroll_to)
            # self.parent2_edit will be synced via _on_scroll triggered by result_edit

        elif origin == "result_p2":  # Result vs Parent2
            res_scroll_to = chunk.left_start  # Result is left side of result_p2 diff
            p2_scroll_to = chunk.right_start  # Parent2 is right side of result_p2 diff
            # p1_scroll_to will be synced by _on_scroll based on result_edit's scroll

            # Highlighting for Result vs Parent2
            if chunk.type == "insert":  # Insert in Parent2 (right side of result_p2 diff)
                self.parent2_edit.set_highlighted_line(chunk.right_start)
                self.parent2_edit.set_block_background(chunk.right_start, chunk.right_end)
                # Left (Result) has a "gap"
                res_scroll_to = max(0, chunk.left_start - 1) if chunk.left_start > 0 else 0
                self.result_edit.set_highlighted_line(res_scroll_to)
            elif chunk.type == "delete":  # Delete in Parent2 (means content present in Result is missing in P2)
                self.result_edit.set_highlighted_line(chunk.left_start)
                self.result_edit.set_block_background(chunk.left_start, chunk.left_end)
                # Right (P2) has a "gap"
                p2_scroll_to = max(0, chunk.right_start - 1) if chunk.right_start > 0 else 0
                self.parent2_edit.set_highlighted_line(p2_scroll_to)
            elif chunk.type == "replace":
                self.result_edit.set_highlighted_line(chunk.left_start)
                self.result_edit.set_block_background(chunk.left_start, chunk.left_end)
                self.parent2_edit.set_highlighted_line(chunk.right_start)
                self.parent2_edit.set_block_background(chunk.right_start, chunk.right_end)

            self.result_edit.scroll_to_line(res_scroll_to)
            self.parent2_edit.scroll_to_line(p2_scroll_to)
            # self.parent1_edit will be synced via _on_scroll triggered by result_edit

        # The _on_scroll mechanism should handle syncing the third pane.
        # We explicitly scroll two panes involved in the direct diff.
        # For example, if result_edit is scrolled, its _on_scroll handler
        # will try to sync parent1_edit and parent2_edit.
        # We need to ensure this doesn't cause infinite loops or fight with explicit scrolls.
        # The _sync_vscroll_lock in _on_scroll should prevent this.
        # One of the explicit scrolls (e.g. self.result_edit.scroll_to_line) will trigger
        # the _on_scroll logic which will then sync the other panes.

        logging.info("MergeDiffViewer: Called scroll_to_line for relevant editors.")

    def keyPressEvent(self, event: QKeyEvent):
        """Handle key presses for navigation."""
        key = event.key()
        if key == Qt.Key.Key_Down:
            self.navigate_to_next_merged_diff()
            event.accept()
        elif key == Qt.Key.Key_Up:
            self.navigate_to_previous_merged_diff()
            event.accept()
        else:
            # Important: Pass the event to the superclass if not handled here.
            # This ensures that standard text editing keys (if the editors were editable)
            # or other base class key events are still processed.
            # However, MergeDiffViewer itself is a QWidget, not a QTextEdit.
            # The actual text editing key events are handled by the SyncedTextEdit instances.
            # So, we call QWidget's keyPressEvent.
            super().keyPressEvent(event)

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
