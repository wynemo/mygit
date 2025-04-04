from PyQt6.QtCore import Qt
from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
import re
class DiffHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.diff_formats = {
            'add': self.create_format('#97f295', '#e6ffe6'),  # 绿色
            'remove': self.create_format('#ff9999', '#ffe6e6'),  # 红色
            'header': self.create_format('#0000ff', '#f0f0ff'),  # 蓝色
        }

    def create_format(self, color, background=None):
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        if background:
            fmt.setBackground(QColor(background))
        return fmt

    def highlightBlock(self, text):
        # 根据行首字符判断差异类型
        if text.startswith('+'):
            self.setFormat(0, len(text), self.diff_formats['add'])
        elif text.startswith('-'):
            self.setFormat(0, len(text), self.diff_formats['remove'])
        elif text.startswith('@'):
            self.setFormat(0, len(text), self.diff_formats['header'])

class CodeHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighting_rules = []
        
        # 基本的语法高亮规则
        keyword_format = self.create_format('#0000ff')  # 蓝色关键字
        keywords = [
            'def', 'class', 'import', 'from', 'as', 'return', 'if', 'else', 'elif',
            'try', 'except', 'finally', 'for', 'while', 'break', 'continue',
            'pass', 'raise', 'True', 'False', 'None', 'and', 'or', 'not', 'is',
            'in', 'with', 'async', 'await', 'lambda'
        ]
        for word in keywords:
            self.highlighting_rules.append((
                f'\\b{word}\\b',
                keyword_format
            ))
            
        # 字符串
        string_format = self.create_format('#008000')  # 绿色字符串
        self.highlighting_rules.append((
            r'"[^"\\]*(\\.[^"\\]*)*"',
            string_format
        ))
        self.highlighting_rules.append((
            r"'[^'\\]*(\\.[^'\\]*)*'",
            string_format
        ))
        
        # 注释
        comment_format = self.create_format('#808080')  # 灰色注释
        self.highlighting_rules.append((
            r'#[^\n]*',
            comment_format
        ))
        
        # 数字
        number_format = self.create_format('#800000')  # 褐色数字
        self.highlighting_rules.append((
            r'\b\d+\b',
            number_format
        ))
        
        # 函数调用
        function_format = self.create_format('#800080')  # 紫色函数
        self.highlighting_rules.append((
            r'\b[A-Za-z0-9_]+(?=\()',
            function_format
        ))

    def create_format(self, color):
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        return fmt

    def highlightBlock(self, text):
        for pattern, format in self.highlighting_rules:
            #for match in Qt.re.finditer(pattern, text):
            for match in re.finditer(pattern, text):
                start = match.start()
                length = match.end() - start
                self.setFormat(start, length, format)

def format_diff_content(old_content, new_content):
    """生成带有行号和差异标记的HTML内容"""
    import difflib
    
    differ = difflib.Differ()
    diff = list(differ.compare(old_content.splitlines(True), new_content.splitlines(True)))
    
    old_html = []
    new_html = []
    line_num_old = 1
    line_num_new = 1
    
    for line in diff:
        if line.startswith('  '):  # 未改变的行
            old_html.append(f'<span class="line-number">{line_num_old}</span><span class="normal">{line[2:]}</span>')
            new_html.append(f'<span class="line-number">{line_num_new}</span><span class="normal">{line[2:]}</span>')
            line_num_old += 1
            line_num_new += 1
        elif line.startswith('- '):  # 删除的行
            old_html.append(f'<span class="line-number">{line_num_old}</span><span class="remove">{line[2:]}</span>')
            line_num_old += 1
        elif line.startswith('+ '):  # 添加的行
            new_html.append(f'<span class="line-number">{line_num_new}</span><span class="add">{line[2:]}</span>')
            line_num_new += 1
            
    old_html = ''.join(old_html)
    new_html = ''.join(new_html)
    
    css = """
    <style>
        .line-number {
            display: inline-block;
            width: 3em;
            color: #666;
            background-color: #f0f0f0;
            padding-right: 0.5em;
            text-align: right;
            user-select: none;
        }
        .normal {
            display: inline-block;
            white-space: pre;
            width: calc(100% - 3.5em);
        }
        .add {
            display: inline-block;
            white-space: pre;
            width: calc(100% - 3.5em);
            background-color: #e6ffe6;
        }
        .remove {
            display: inline-block;
            white-space: pre;
            width: calc(100% - 3.5em);
            background-color: #ffe6e6;
        }
    </style>
    """
    
    return f"{css}<pre>{old_html}</pre>", f"{css}<pre>{new_html}</pre>" 