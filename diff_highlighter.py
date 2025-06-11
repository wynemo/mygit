import difflib
import logging

import diff_match_patch
from PyQt6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat

from diff_calculator import DiffChunk
from syntax_highlighter import PygmentsHighlighterEngine


class DiffHighlighterEngine:
    SIMILARITY_THRESHOLD_FOR_DETAILED_DIFF = 0.8

    def __init__(self, highlighter: QSyntaxHighlighter, editor_type=""):
        self.highlighter = highlighter
        self.editor_type = editor_type
        self.diff_chunks: list[DiffChunk] = []
        logging.debug("\n=== 初始化 DiffHighlighter ===")
        logging.debug("编辑器类型：%s", editor_type)

        # 定义差异高亮的颜色
        self.diff_formats = {
            "delete": self.create_format("#ffcccc", "#cc0000"),  # 更深的红色
            "insert": self.create_format("#ccffcc", "#00cc00"),  # 更深的绿色
            "replace": self.create_format("#ffffcc", "#cccc00"),  # 更深的黄色
            "equal": None,
        }
        # 新增：互相包含差异的高亮格式
        self.inline_contained_insert_format = self.create_format("#ccffcc", "#cccc00")
        self.inline_contained_delete_format = self.create_format("#800080", "#cccc00")

        logging.debug("差异格式已创建：%s", self.diff_formats)

    def create_format(self, background_color, text_color):
        """创建高亮格式，包含文字颜色和背景颜色"""
        logging.debug("\n创建格式 - 背景：%s, 文字：%s", background_color, text_color)
        fmt = QTextCharFormat()
        if background_color is not None:
            fmt.setBackground(QColor(background_color))
        if text_color is not None:
            fmt.setForeground(QColor(text_color))
        return fmt

    def set_diff_chunks(self, chunks):
        """设置差异块"""
        logging.debug("\n=== 设置差异块到高亮器 ===")
        logging.debug("高亮器类型：%s", self.editor_type)
        logging.debug("块数量：%d", len(chunks))
        for i, chunk in enumerate(chunks):
            logging.debug("\n差异块 %d:", i + 1)
            logging.debug("类型：%s", chunk.type)
            logging.debug("左侧范围：%d-%d", chunk.left_start, chunk.left_end)
            logging.debug("右侧范围：%d-%d", chunk.right_start, chunk.right_end)
        self.diff_chunks = chunks
        self.highlighter.rehighlight()

    def highlightBlock(self, text):
        """高亮当前文本块"""
        block_number = self.highlighter.currentBlock().blockNumber()
        logging.debug("\n=== 高亮块详细信息 ===")
        logging.debug("高亮器类型：%s", self.editor_type)
        logging.debug("当前块号：%d", block_number)
        logging.debug("文本内容：%s", text)
        logging.debug("差异块数量：%d", len(self.diff_chunks))

        # 找到当前行所在的差异块
        current_chunk = None
        for chunk in self.diff_chunks:
            # 根据编辑器类型决定如何处理差异
            if self.editor_type in ["left", "parent1_edit"]:
                if chunk.left_start <= block_number < chunk.left_end:
                    current_chunk = chunk
                    logging.debug("找到左侧差异块：%s", chunk.type)
                    break
            elif self.editor_type in ["right", "parent2_edit"]:
                if chunk.right_start <= block_number < chunk.right_end:
                    current_chunk = chunk
                    logging.debug("找到右侧差异块：%s", chunk.type)
                    break
            elif self.editor_type == "result_edit":
                # 对于三向合并中的结果编辑器，需要同时检查与两个父版本的差异
                parent1_chunk = None
                parent2_chunk = None

                # 查找与 parent1 的差异
                for chunk in self.diff_chunks:
                    if chunk.right_start <= block_number < chunk.right_end:
                        parent1_chunk = chunk
                        break

                # 查找与 parent2 的差异
                for chunk in self.diff_chunks:
                    if chunk.left_start <= block_number < chunk.left_end:
                        parent2_chunk = chunk
                        break

                # 根据差异情况设置不同的高亮
                if parent1_chunk and parent2_chunk:
                    # 与两个父版本都不同
                    if parent1_chunk.type != "equal" and parent2_chunk.type != "equal":
                        current_chunk = parent1_chunk
                        # 使用特殊的冲突颜色
                        conflict_format = self.create_format("#ffccff", "#cc00cc")  # 紫色
                        self.highlighter.setFormat(0, len(text), conflict_format)
                        return
                    elif parent1_chunk.type != "equal":
                        current_chunk = parent1_chunk
                    else:
                        current_chunk = parent2_chunk
                elif parent1_chunk:
                    current_chunk = parent1_chunk
                elif parent2_chunk:
                    current_chunk = parent2_chunk

        # 如果找到差异块，应用相应的格式
        if current_chunk and current_chunk.type != "equal":
            logging.debug("应用差异块格式：%s", current_chunk.type)
            format_type = current_chunk.type

            if format_type in self.diff_formats:
                format = self.diff_formats[format_type]
                if format:
                    logging.debug("应用格式：%s", format_type)
                    self.highlighter.setFormat(0, len(text), format)
                    logging.debug("格式已应用")

                # 新增：处理互相包含的情况
                if current_chunk.type == "replace":
                    try:
                        # 获取当前行的左右文本
                        if self.editor_type in ["left", "parent1_edit"]:
                            left_line_text = self.highlighter.document().findBlockByNumber(block_number).text()
                            right_line_text = self.highlighter.other_document.findBlockByNumber(
                                current_chunk.right_start + (block_number - current_chunk.left_start)
                            ).text()
                        elif self.editor_type in ["right", "parent2_edit"]:
                            right_line_text = self.highlighter.document().findBlockByNumber(block_number).text()
                            left_line_text = self.highlighter.other_document.findBlockByNumber(
                                current_chunk.left_start + (block_number - current_chunk.right_start)
                            ).text()
                        else:
                            return

                        # === BEGIN NEW DETAILED DIFF LOGIC ===
                        if (
                            left_line_text != right_line_text
                        ):  # Ensure they are actually different before calculating ratio
                            s = difflib.SequenceMatcher(None, left_line_text, right_line_text)
                            similarity_ratio = s.ratio()

                            if similarity_ratio > self.SIMILARITY_THRESHOLD_FOR_DETAILED_DIFF:
                                # The base "replace" format for the line is applied by the code just before this 'replace' handling.
                                # Now, apply character-level highlights on top.

                                if self.editor_type in ["left", "parent1_edit"]:
                                    # We are in the left editor, text is left_line_text.
                                    # Highlight parts of left_line_text that are changed or deleted compared to right_line_text.
                                    for tag, i1, i2, j1, j2 in s.get_opcodes():
                                        if (
                                            tag == "replace"
                                        ):  # Characters in left_line_text[i1:i2] are replaced by right_line_text[j1:j2]
                                            self.highlighter.setFormat(
                                                i1, i2 - i1, self.inline_contained_delete_format
                                            )  # Style for text being replaced in left view
                                        elif (
                                            tag == "delete"
                                        ):  # Characters in left_line_text[i1:i2] are not in right_line_text
                                            self.highlighter.setFormat(i1, i2 - i1, self.inline_contained_delete_format)
                                        # 'insert' (char in right but not left) means a gap in left, nothing to format in left_line_text itself.

                                elif self.editor_type in ["right", "parent2_edit"]:
                                    # We are in the right editor, text is right_line_text.
                                    # Highlight parts of right_line_text that are changed or inserted compared to left_line_text.
                                    for tag, i1, i2, j1, j2 in s.get_opcodes():
                                        if (
                                            tag == "replace"
                                        ):  # Characters in right_line_text[j1:j2] replace left_line_text[i1:i2]
                                            self.highlighter.setFormat(
                                                j1, j2 - j1, self.inline_contained_insert_format
                                            )  # Style for text that is replacing in right view
                                        elif (
                                            tag == "insert"
                                        ):  # Characters in right_line_text[j1:j2] are not in left_line_text
                                            self.highlighter.setFormat(j1, j2 - j1, self.inline_contained_insert_format)
                                        # 'delete' (char in left but not right) means a gap in right, nothing to format in right_line_text itself.

                                # If detailed diff was applied, we 'return' from highlightBlock for this line to skip old logic.
                                return
                        # === END NEW DETAILED DIFF LOGIC ===

                    except IndexError:
                        logging.warning("获取行文本时发生索引错误")


class DiffHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None, editor_type=""):
        super().__init__(parent)
        self.engine = DiffHighlighterEngine(self, editor_type=editor_type)

    def set_diff_chunks(self, chunks):
        self.engine.set_diff_chunks(chunks)
        self.rehighlight()

    def highlightBlock(self, text):
        self.engine.highlightBlock(text)


# -------- 总高亮器 --------
class MultiHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None, editor_type="", other_document=None):
        super().__init__(parent)
        self.diff_engine = NewDiffHighlighterEngine(self, editor_type=editor_type)
        self.pygments_engine = PygmentsHighlighterEngine(self)
        self.other_document = other_document

    def set_language(self, language_name):
        self.pygments_engine.set_language(language_name)
        self.rehighlight()

    def set_diff_chunks(self, chunks):
        self.diff_engine.set_diff_chunks(chunks)
        self.rehighlight()

    def set_texts(self, left_text: str, right_text: str):
        if hasattr(self.diff_engine, "set_texts"):
            self.diff_engine.set_texts(left_text, right_text)
            self.rehighlight()

    def highlightBlock(self, text):
        self.pygments_engine.highlightBlock(text)
        self.diff_engine.highlightBlock(text)


# new DiffHighlighterEngine
class NewDiffHighlighterEngine:
    def __init__(self, highlighter: QSyntaxHighlighter, editor_type=""):
        self.highlighter = highlighter
        self.editor_type = editor_type
        self.diff_chunks: list[DiffChunk] = []
        self.diff_list = []
        logging.debug("\n=== 初始化 DiffHighlighter ===")
        logging.debug("编辑器类型：%s", editor_type)

        self.dmp = diff_match_patch.diff_match_patch()

        # 定义不同类型差异的格式
        self.deleted_format = QTextCharFormat()
        self.deleted_format.setBackground(QColor(255, 200, 200))  # 浅红色背景
        self.deleted_format.setForeground(QColor(150, 0, 0))  # 深红色文字

        self.inserted_format = QTextCharFormat()
        self.inserted_format.setBackground(QColor(200, 255, 200))  # 浅绿色背景
        self.inserted_format.setForeground(QColor(0, 150, 0))  # 深绿色文字

        self.equal_format = QTextCharFormat()
        self.equal_format.setBackground(QColor(255, 255, 255))  # 白色背景
        self.equal_format.setForeground(QColor(0, 0, 0))  # 黑色文字

    def set_diff_chunks(self, chunks):
        self.diff_chunks = chunks

    def set_texts(self, left_text: str, right_text: str):
        """设置要对比的文本"""
        # 计算差异
        self.diff_list = self.dmp.diff_main(left_text, right_text)
        self.dmp.diff_cleanupSemantic(self.diff_list)

        # 触发重新高亮
        # self.highlighter.rehighlight()

    # left side property
    @property
    def is_left_side(self):
        return self.editor_type in ["left", "parent1_edit"]

    # right side property
    @property
    def is_right_side(self):
        return self.editor_type in ["right", "parent2_edit"]

    def highlightBlock(self, text: str):
        """重写高亮方法"""
        # if not self.diff_list:
        #     return

        # 构建完整文档文本用于定位
        document = self.highlighter.document()
        full_text = document.toPlainText()

        # 获取当前块在整个文档中的位置
        current_block = self.highlighter.currentBlock()
        block_start = current_block.position()
        block_length = len(text)

        # 根据差异列表应用格式
        current_pos = 0

        for op, data in self.diff_list:
            data_length = len(data)

            # 检查这个差异是否与当前块重叠
            if current_pos + data_length > block_start and current_pos < block_start + block_length:
                # 计算在当前块中的相对位置
                start_in_block = max(0, current_pos - block_start)
                end_in_block = min(block_length, current_pos + data_length - block_start)

                if end_in_block > start_in_block:
                    format_to_apply = None

                    if op == diff_match_patch.diff_match_patch.DIFF_DELETE:
                        if self.is_left_side:
                            format_to_apply = self.deleted_format
                    elif op == diff_match_patch.diff_match_patch.DIFF_INSERT:
                        if not self.is_left_side:
                            format_to_apply = self.inserted_format
                    # else:  # DIFF_EQUAL
                    # format_to_apply = self.equal_format

                    if format_to_apply:
                        self.highlighter.setFormat(start_in_block, end_in_block - start_in_block, format_to_apply)

            # 只有在 DELETE 和 EQUAL 时才移动左侧位置，INSERT 和 EQUAL 时才移动右侧位置
            if self.is_left_side:
                if op != diff_match_patch.diff_match_patch.DIFF_INSERT:
                    current_pos += data_length
            elif op != diff_match_patch.diff_match_patch.DIFF_DELETE:
                current_pos += data_length
