import logging

from pygments import lexers, styles  # 导入 Pygments 模块 (Import Pygments modules)
from pygments.util import (
    ClassNotFound,  # 导入 Pygments 异常类 (Import Pygments exception class)
)
from PyQt6.QtGui import (  # 导入 QFont (Import QFont)
    QColor,
    QFont,
    QSyntaxHighlighter,
    QTextCharFormat,
)

from settings import settings


class PygmentsHighlighterEngine:
    def __init__(self, highlighter: QSyntaxHighlighter):
        self.highlighter = highlighter

        # Pygments 语法高亮相关初始化 (Pygments syntax highlighting related initialization)
        self.lexer = None  # Pygments 词法分析器 (Pygments lexer)
        self.style_formats = {}  # 存储词法标记对应的 QTextCharFormat (Stores QTextCharFormat for tokens)
        self.default_text_format = QTextCharFormat()  # 默认文本格式 (Default text format)
        self.default_text_format.setForeground(
            QColor("#000000")
        )  # 设置默认前景色为黑色 (Set default foreground to black)

    def _initialize_language_styling(self, language_name):
        # 根据语言名称初始化词法分析器和样式 (Initialize lexer and styles based on language name)
        try:
            self.lexer = lexers.get_lexer_by_name(language_name)
            logging.info("词法分析器已设置为：%s", language_name)
        except ClassNotFound:
            logging.warning("未找到语言 '%s' 的词法分析器，将使用纯文本模式。", language_name)
            self.lexer = lexers.get_lexer_by_name("text")  # Fallback to plain text

        try:
            # 您可以选择一个 Pygments 样式 (You can choose a Pygments style)
            # 例如 'default', 'monokai', 'emacs', 'friendly' 等 (e.g., 'default', 'monokai', 'emacs', 'friendly', etc.)
            style_name = settings.get_code_style()  # 从设置中获取代码风格 (Get code style from settings)
            if not style_name:
                style_name = "friendly"  # 如果未设置，则使用默认样式 (Use default style if not set)
            style = styles.get_style_by_name(style_name)
            self.style_formats = {}
            for token_type, style_definition in style:
                qt_format = QTextCharFormat()
                if style_definition["color"]:
                    qt_format.setForeground(QColor(f"#{style_definition['color']}"))
                if style_definition[
                    "bgcolor"
                ]:  # 语法高亮也可能定义背景色 (Syntax highlighting might also define background color)
                    qt_format.setBackground(QColor(f"#{style_definition['bgcolor']}"))
                if style_definition["bold"]:
                    qt_format.setFontWeight(QFont.Weight.Bold)
                if style_definition["italic"]:
                    qt_format.setFontItalic(True)
                if style_definition["underline"]:
                    qt_format.setFontUnderline(True)
                self.style_formats[token_type] = qt_format
        except ClassNotFound:
            self.style_formats = {}  # 出错时清空样式 (Clear styles on error)

    def set_language(self, language_name):
        # 设置高亮的语言 (Set the language for highlighting)
        self._initialize_language_styling(language_name)

    def highlightBlock(self, text):
        # 高亮当前文本块 (Highlight the current text block)

        if self.lexer:
            try:
                for index, token_type, token_text in self.lexer.get_tokens_unprocessed(text):
                    if token_type in self.style_formats:
                        # 获取语法高亮格式 (Get syntax highlighting format)
                        syntax_format = self.style_formats[token_type]
                        # 应用格式 (Apply format)
                        self.highlighter.setFormat(index, len(token_text), syntax_format)
            except Exception:
                # Fallback: 确保在出错时至少应用默认格式 (Fallback: ensure default format is applied if error)
                self.highlighter.setFormat(0, len(text), self.default_text_format)


class CodeHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.engine = PygmentsHighlighterEngine(self)

    def set_language(self, language_name):
        self.engine.set_language(language_name)
        self.rehighlight()

    def highlightBlock(self, text):
        self.engine.highlightBlock(text)
