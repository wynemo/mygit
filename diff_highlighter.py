import logging
from PyQt6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat, QFont # 导入 QFont (Import QFont)
from pygments import lexers, styles # 导入Pygments模块 (Import Pygments modules)
from pygments.util import ClassNotFound # 导入Pygments异常类 (Import Pygments exception class)


class DiffHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None, editor_type=""):
        super().__init__(parent)
        self.editor_type = editor_type  # 编辑器类型 (Editor type)
        self.diff_chunks = []  # 差异块列表 (List of diff chunks)
        # logging.debug("\n=== 初始化DiffHighlighter ===")
        # logging.debug("编辑器类型: %s", editor_type)

        # Pygments 语法高亮相关初始化 (Pygments syntax highlighting related initialization)
        self.lexer = None # Pygments 词法分析器 (Pygments lexer)
        self.style_formats = {} # 存储词法标记对应的 QTextCharFormat (Stores QTextCharFormat for tokens)
        self.default_text_format = QTextCharFormat() # 默认文本格式 (Default text format)
        self.default_text_format.setForeground(QColor("#000000")) # 设置默认前景色为黑色 (Set default foreground to black)
        self._initialize_language_styling("python") # 初始化默认语言为Python (Initialize default language to Python)

        # 定义差异高亮的颜色 (Define diff highlight colors)
        # 修改: 现在只改变背景色，文字颜色由语法高亮控制 (Modification: Now only changes background color, text color controlled by syntax highlighting)
        self.diff_formats = {
            "delete": self.create_format("#ffcccc"),  # 删除操作的背景色 (Background color for delete operation)
            "insert": self.create_format("#ccffcc"),  # 插入操作的背景色 (Background color for insert operation)
            "replace": self.create_format("#ffffcc"), # 替换操作的背景色 (Background color for replace operation)
            "equal": None, # 无变化的块不需要特殊格式 (No special format needed for unchanged blocks)
        }
        # logging.debug("差异格式已创建: %s", self.diff_formats)

    def create_format(self, background_color, text_color_for_diff_only=None): # text_color is now optional
        # 创建高亮格式 (Create highlight format)
        # logging.debug(f"创建差异格式 - 背景: {background_color}, 文字: {text_color_for_diff_only}")
        fmt = QTextCharFormat()
        fmt.setBackground(QColor(background_color)) # 设置背景色 (Set background color)
        if text_color_for_diff_only: # 如果指定了差异文本颜色，则设置 (If diff text color is specified, set it)
            fmt.setForeground(QColor(text_color_for_diff_only))
        return fmt

    def _initialize_language_styling(self, language_name):
        # 根据语言名称初始化词法分析器和样式 (Initialize lexer and styles based on language name)
        try:
            self.lexer = lexers.get_lexer_by_name(language_name)
            # logging.debug(f"词法分析器已设置为: {language_name}")
        except ClassNotFound:
            # logging.warning(f"未找到语言 '{language_name}' 的词法分析器，将使用纯文本模式。(Lexer for language '{language_name}' not found, using plain text mode.)")
            self.lexer = lexers.get_lexer_by_name("text") # Fallback to plain text

        try:
            # 您可以选择一个Pygments样式 (You can choose a Pygments style)
            # 例如 'default', 'monokai', 'emacs', 'friendly' 等 (e.g., 'default', 'monokai', 'emacs', 'friendly', etc.)
            style = styles.get_style_by_name('default') 
            self.style_formats = {}
            for token_type, style_definition in style:
                qt_format = QTextCharFormat()
                if style_definition['color']:
                    qt_format.setForeground(QColor(f"#{style_definition['color']}"))
                if style_definition['bgcolor']: # 语法高亮也可能定义背景色 (Syntax highlighting might also define background color)
                    qt_format.setBackground(QColor(f"#{style_definition['bgcolor']}"))
                if style_definition['bold']:
                    qt_format.setFontWeight(QFont.Weight.Bold)
                if style_definition['italic']:
                    qt_format.setFontItalic(True)
                if style_definition['underline']:
                    qt_format.setFontUnderline(True)
                self.style_formats[token_type] = qt_format
            # logging.debug(f"语法高亮样式已从 '{style.name}' 加载。(Syntax highlighting style loaded from '{style.name}'.)")
        except ClassNotFound:
            # logging.error(f"未找到Pygments样式。(Pygments style not found.)")
            self.style_formats = {} # 出错时清空样式 (Clear styles on error)

    def set_language(self, language_name):
        # 设置高亮的语言 (Set the language for highlighting)
        self._initialize_language_styling(language_name)
        self.rehighlight() # 重新高亮整个文档 (Rehighlight the entire document)

    def set_diff_chunks(self, chunks):
        """设置差异块"""
        logging.debug("\n=== 设置差异块到高亮器 ===")
        logging.debug("高亮器类型: %s", self.editor_type)
        logging.debug("块数量: %d", len(chunks))
        for i, chunk in enumerate(chunks):
            logging.debug("\n差异块 %d:", i + 1)
            logging.debug("类型: %s", chunk.type)
            logging.debug("左侧范围: %d-%d", chunk.left_start, chunk.left_end)
            logging.debug("右侧范围: %d-%d", chunk.right_start, chunk.right_end)
        self.diff_chunks = chunks
        self.rehighlight()

    def highlightBlock(self, text):
        # 高亮当前文本块 (Highlight the current text block)

        # 1. 应用Pygments语法高亮 (Apply Pygments syntax highlighting)
        # 默认情况下，将整个块的格式设置为默认文本格式 (By default, set format for the whole block to default text format)
        self.setFormat(0, len(text), self.default_text_format)

        if self.lexer:
            # logging.debug(f"Pygments 语法高亮: 应用于文本 '{text[:30]}...' (Pygments syntax highlighting: Applying to text '{text[:30]}...')")
            try:
                for index, token_type, token_text in self.lexer.get_tokens_unprocessed(text):
                    if token_type in self.style_formats:
                        # 获取语法高亮格式 (Get syntax highlighting format)
                        syntax_format = self.style_formats[token_type]
                        # 应用格式 (Apply format)
                        self.setFormat(index, len(token_text), syntax_format)
            except Exception as e:
                # logging.error(f"Pygments 词法分析时出错 (Error during Pygments tokenization): {e}")
                # Fallback: 确保在出错时至少应用默认格式 (Fallback: ensure default format is applied if error)
                self.setFormat(0, len(text), self.default_text_format)
        
        # 2. 应用差异高亮 (Apply diff highlighting)
        block_number = self.currentBlock().blockNumber() # 当前块号 (Current block number)
        # logging.debug("\n=== 高亮块详细信息 ===")
        # logging.debug("高亮器类型: %s", self.editor_type)
        # logging.debug("当前块号: %d", block_number)
        # logging.debug("文本内容: %s", text)
        # logging.debug("差异块数量: %d", len(self.diff_chunks))

        current_chunk = None # 当前差异块 (Current diff chunk)
        for chunk in self.diff_chunks:
            # 根据编辑器类型决定如何处理差异 (Determine how to handle diffs based on editor type)
            if self.editor_type in ["left", "parent1_edit"]:
                if chunk.left_start <= block_number < chunk.left_end:
                    current_chunk = chunk
                    # logging.debug("找到左侧差异块: %s", chunk.type)
                    break
            elif self.editor_type in ["right", "parent2_edit"]:
                if chunk.right_start <= block_number < chunk.right_end:
                    current_chunk = chunk
                    # logging.debug("找到右侧差异块: %s", chunk.type)
                    break
            elif self.editor_type == "result_edit": # 三向合并的结果编辑器 (Result editor for three-way merge)
                parent1_chunk = None
                parent2_chunk = None
                for c in self.diff_chunks: # 确保从原始chunks查找 (Ensure lookup from original chunks)
                    if c.right_start <= block_number < c.right_end: # 与parent1比较 (Compare with parent1)
                        parent1_chunk = c
                        break 
                for c in self.diff_chunks: # 确保从原始chunks查找 (Ensure lookup from original chunks)
                    if c.left_start <= block_number < c.left_end: # 与parent2比较 (Compare with parent2)
                        parent2_chunk = c
                        break

                if parent1_chunk and parent2_chunk:
                    if parent1_chunk.type != "equal" and parent2_chunk.type != "equal":
                        # logging.debug("冲突块: 同时与 parent1 和 parent2 不同 (Conflict block: different from both parent1 and parent2)")
                        # 特殊冲突高亮，覆盖语法高亮 (Special conflict highlighting, overrides syntax highlighting)
                        conflict_format = self.create_format("#ffccff", "#cc00cc")  # 紫色背景和文字 (Purple background and text)
                        self.setFormat(0, len(text), conflict_format)
                        return # 冲突块不应用后续的普通差异高亮 (Conflict blocks do not apply subsequent normal diff highlighting)
                    elif parent1_chunk.type != "equal":
                        current_chunk = parent1_chunk
                    else: # parent2_chunk.type != "equal" or both are equal (but that case is handled by current_chunk remaining None or being "equal")
                        current_chunk = parent2_chunk
                elif parent1_chunk:
                    current_chunk = parent1_chunk
                elif parent2_chunk:
                    current_chunk = parent2_chunk
        
        if current_chunk and current_chunk.type != "equal":
            # logging.debug("应用差异块格式: %s", current_chunk.type)
            format_type = current_chunk.type
            if format_type in self.diff_formats:
                diff_specific_format = self.diff_formats[format_type]
                if diff_specific_format:
                    # logging.debug("应用差异特定格式: %s", format_type)
                    # diff格式主要修改背景色，语法高亮的前景色应该保留 (Diff format primarily changes background, syntax foreground should be preserved)
                    # Qt的setFormat会合并格式，如果diff_specific_format只设置了背景，则前景不变 (Qt's setFormat merges formats, if diff_specific_format only sets background, foreground remains)
                    self.setFormat(0, len(text), diff_specific_format)
                    # logging.debug("差异格式已应用")
