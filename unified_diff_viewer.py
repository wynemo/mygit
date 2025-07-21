import os
from typing import Dict, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon, QTextCharFormat
from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from diff_calculator import DiffCalculator, DifflibCalculator
from diff_highlighter import MultiHighlighter
from editors.text_edit import SyncedTextEdit


class UnifiedHighlighter(MultiHighlighter):
    """
    为统一差异视图提供高亮功能的类。
    """

    def __init__(self, document, unified_line_mapping: Dict[int, Tuple[str, any, int]]):
        super().__init__(document, "unified", None)
        self.unified_line_mapping = unified_line_mapping
        self.insert_format = QTextCharFormat()
        self.insert_format.setBackground(QColor(200, 255, 200))  # 浅绿色
        self.delete_format = QTextCharFormat()
        self.delete_format.setBackground(QColor(255, 200, 200))  # 浅红色

    def highlightBlock(self, text):
        # 首先应用语法高亮
        super().highlightBlock(text)

        # 然后应用差异高亮
        block_number = self.currentBlock().blockNumber()
        if block_number in self.unified_line_mapping:
            line_type, chunk, original_line = self.unified_line_mapping[block_number]

            if line_type == "insert":
                self.setFormat(0, len(text), self.insert_format)
            elif line_type == "delete":
                self.setFormat(0, len(text), self.delete_format)
            elif line_type == "omitted":
                # 为省略行设置特殊格式
                omitted_format = QTextCharFormat()
                omitted_format.setForeground(QColor(128, 128, 128))  # 灰色文字
                self.setFormat(0, len(text), omitted_format)


class UnifiedDiffViewer(QWidget):
    """
    一个统一的差异查看器，将左右两侧的内容合并在单个编辑器中显示。
    """

    def __init__(self, diff_calculator: DiffCalculator | None = None):
        super().__init__()
        self.actual_diff_chunks = []
        self.current_diff_index = -1
        self.unified_line_mapping = {}  # 映射统一行号到原始行号
        self.setup_ui()
        self.diff_calculator = diff_calculator or DifflibCalculator()

    def _create_icon_button(self, icon_path: str, tooltip: str) -> QPushButton:
        """创建带SVG图标的按钮"""
        button = QPushButton()
        button.setIcon(QIcon(icon_path))
        button.setIconSize(button.sizeHint())  # 设置图标大小
        button.setFixedSize(30, 30)  # 设置固定大小
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
                border-radius: 12px;
            }
            QPushButton:pressed {
                background: rgba(0, 0, 0, 0.2);
                border-radius: 12px;
            }
            QPushButton:disabled {
                background: transparent;
                opacity: 0.3;
            }
        """)
        return button

    def setup_ui(self):
        # 按钮布局
        button_layout = QHBoxLayout()
        button_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)  # 左对齐

        # 使用SVG图标替换文本按钮
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

        # 统一编辑器
        self.unified_edit = SyncedTextEdit()
        self.unified_edit.setObjectName("unified_edit")
        self.unified_edit.setReadOnly(True)

        # 主布局
        main_layout = QVBoxLayout()
        main_layout.addLayout(button_layout)
        main_layout.addWidget(self.unified_edit)
        self.setLayout(main_layout)

    def set_texts(
        self,
        left_text: str,
        right_text: str,
        file_path: str,
    ):
        """
        设置要比较的文本，并生成统一的差异视图。
        """
        self.diff_chunks = self.diff_calculator.compute_diff(left_text, right_text)
        self.actual_diff_chunks = [chunk for chunk in self.diff_chunks if chunk.type != "equal"]
        self.current_diff_index = -1

        unified_text = self._format_unified_text(left_text, right_text)
        self.unified_edit.setPlainText(unified_text)

        self.unified_edit.highlighter = UnifiedHighlighter(self.unified_edit.document(), self.unified_line_mapping)
        # self.unified_edit.highlighter.set_language(LANGUAGE_MAP.get(file_path.split(".")[-1], "text"))

        self._update_button_states()

    def _format_unified_text(self, left_text: str, right_text: str) -> str:
        """
        将左右文本格式化为统一的差异格式。
        """
        left_lines = left_text.splitlines()
        right_lines = right_text.splitlines()
        unified_lines = []
        self.unified_line_mapping.clear()
        unified_line_num = 0
        context_lines = 3  # 在变更前后显示的上下文行数

        for chunk_idx, chunk in enumerate(self.diff_chunks):
            if chunk.type == "equal":
                chunk_size = chunk.left_end - chunk.left_start

                # 如果是第一个或最后一个chunk，或者chunk很小，就完全显示
                if chunk_idx == 0 or chunk_idx == len(self.diff_chunks) - 1 or chunk_size <= 2 * context_lines:
                    for i in range(chunk.left_start, chunk.left_end):
                        left_line_num = i + 1
                        right_line_num = chunk.right_start + (i - chunk.left_start) + 1
                        line_content = left_lines[i]
                        formatted_line = f"{left_line_num:>4} {right_line_num:>4}  {line_content}"
                        unified_lines.append(formatted_line)
                        self.unified_line_mapping[unified_line_num] = ("equal", chunk, i)
                        unified_line_num += 1
                else:
                    # 显示开头的几行
                    for i in range(chunk.left_start, min(chunk.left_start + context_lines, chunk.left_end)):
                        left_line_num = i + 1
                        right_line_num = chunk.right_start + (i - chunk.left_start) + 1
                        line_content = left_lines[i]
                        formatted_line = f"{left_line_num:>4} {right_line_num:>4}  {line_content}"
                        unified_lines.append(formatted_line)
                        self.unified_line_mapping[unified_line_num] = ("equal", chunk, i)
                        unified_line_num += 1

                    # 添加省略号
                    omitted_count = chunk_size - 2 * context_lines
                    if omitted_count > 0:
                        formatted_line = f"{'':>4} {'':>4}  ... ({omitted_count} lines omitted) ..."
                        unified_lines.append(formatted_line)
                        self.unified_line_mapping[unified_line_num] = ("omitted", chunk, -1)
                        unified_line_num += 1

                    # 显示结尾的几行
                    for i in range(
                        max(chunk.left_end - context_lines, chunk.left_start + context_lines), chunk.left_end
                    ):
                        left_line_num = i + 1
                        right_line_num = chunk.right_start + (i - chunk.left_start) + 1
                        line_content = left_lines[i]
                        formatted_line = f"{left_line_num:>4} {right_line_num:>4}  {line_content}"
                        unified_lines.append(formatted_line)
                        self.unified_line_mapping[unified_line_num] = ("equal", chunk, i)
                        unified_line_num += 1
            elif chunk.type == "delete":
                for i in range(chunk.left_start, chunk.left_end):
                    left_line_num = i + 1
                    line_content = left_lines[i]
                    formatted_line = f"{left_line_num:>4}       {line_content}"
                    unified_lines.append(formatted_line)
                    self.unified_line_mapping[unified_line_num] = ("delete", chunk, i)
                    unified_line_num += 1
            elif chunk.type == "insert":
                for i in range(chunk.right_start, chunk.right_end):
                    right_line_num = i + 1
                    line_content = right_lines[i]
                    formatted_line = f"     {right_line_num:>4}  {line_content}"
                    unified_lines.append(formatted_line)
                    self.unified_line_mapping[unified_line_num] = ("insert", chunk, i)
                    unified_line_num += 1
            elif chunk.type == "replace":
                for i in range(chunk.left_start, chunk.left_end):
                    left_line_num = i + 1
                    line_content = left_lines[i]
                    formatted_line = f"{left_line_num:>4}       {line_content}"
                    unified_lines.append(formatted_line)
                    self.unified_line_mapping[unified_line_num] = ("delete", chunk, i)
                    unified_line_num += 1
                for i in range(chunk.right_start, chunk.right_end):
                    right_line_num = i + 1
                    line_content = right_lines[i]
                    formatted_line = f"     {right_line_num:>4}  {line_content}"
                    unified_lines.append(formatted_line)
                    self.unified_line_mapping[unified_line_num] = ("insert", chunk, i)
                    unified_line_num += 1

        return "\n".join(unified_lines)

    def _update_button_states(self):
        num_actual_diffs = len(self.actual_diff_chunks)
        prev_enabled = self.current_diff_index > 0
        next_enabled = self.current_diff_index < num_actual_diffs - 1

        if self.current_diff_index == -1 and num_actual_diffs > 0:
            next_enabled = True

        self.prev_diff_button.setEnabled(prev_enabled)
        self.next_diff_button.setEnabled(next_enabled)

    def navigate_to_previous_diff(self):
        if self.current_diff_index > 0:
            self.current_diff_index -= 1
            self._scroll_to_current_diff()
        self._update_button_states()

    def navigate_to_next_diff(self):
        if self.current_diff_index < len(self.actual_diff_chunks) - 1:
            self.current_diff_index += 1
            self._scroll_to_current_diff()
        self._update_button_states()

    def _scroll_to_current_diff(self):
        """
        滚动到当前差异块的位置。
        """
        if 0 <= self.current_diff_index < len(self.actual_diff_chunks):
            chunk = self.actual_diff_chunks[self.current_diff_index]

            # 找到该差异块在统一视图中的第一行
            target_line = -1
            for unified_line, (line_type, mapped_chunk, original_line) in self.unified_line_mapping.items():
                if mapped_chunk == chunk:
                    target_line = unified_line
                    break

            if target_line != -1:
                self.unified_edit.scroll_to_line(target_line)
                self.unified_edit.set_highlighted_line(target_line)
