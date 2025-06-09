import logging

from PyQt6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat

from diff_calculator import DiffChunk
from syntax_highlighter import PygmentsHighlighterEngine


class DiffHighlighterEngine:
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
        # 注意，颜色是叠加的， #ffffcc #800080 叠加后是 紫色
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

                        # 检查互相包含情况并高亮
                        if self.editor_type in ["left", "parent1_edit"]:
                            if right_line_text in left_line_text:  # 左行包含右行（删除情况）
                                start_index = left_line_text.find(right_line_text)
                                if start_index > 0:  # 左侧有前缀被删除
                                    self.highlighter.setFormat(0, start_index, self.inline_contained_delete_format)
                                if start_index + len(right_line_text) < len(left_line_text):  # 左侧有后缀被删除
                                    self.highlighter.setFormat(
                                        start_index + len(right_line_text),
                                        len(left_line_text) - (start_index + len(right_line_text)),
                                        self.inline_contained_delete_format,
                                    )
                        elif self.editor_type in ["right", "parent2_edit"]:
                            if left_line_text in right_line_text:  # 右行包含左行（新增情况）
                                start_index = right_line_text.find(left_line_text)
                                if start_index > 0:  # 右侧有前缀被新增
                                    self.highlighter.setFormat(0, start_index, self.inline_contained_insert_format)
                                if start_index + len(left_line_text) < len(right_line_text):  # 右侧有后缀被新增
                                    self.highlighter.setFormat(
                                        start_index + len(left_line_text),
                                        len(right_line_text) - (start_index + len(left_line_text)),
                                        self.inline_contained_insert_format,
                                    )
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
        self.diff_engine = DiffHighlighterEngine(self, editor_type=editor_type)
        self.pygments_engine = PygmentsHighlighterEngine(self)
        self.engines = [DiffHighlighterEngine(self, editor_type=editor_type), PygmentsHighlighterEngine(self)]
        self.other_document = other_document

    def set_language(self, language_name):
        self.pygments_engine.set_language(language_name)
        self.rehighlight()

    def set_diff_chunks(self, chunks):
        self.diff_engine.set_diff_chunks(chunks)
        self.rehighlight()

    def highlightBlock(self, text):
        self.pygments_engine.highlightBlock(text)
        self.diff_engine.highlightBlock(text)
