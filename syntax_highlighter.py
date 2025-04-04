from PyQt6.QtCore import Qt
from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
import re
import tempfile
import os
import subprocess

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

# New Highlighter for Diff View
class DiffCodeHighlighter(CodeHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Store diff info as a dictionary for quick lookup: {line_number: change_type}
        self.diff_line_info = {}
        # Define background formats for added/removed lines
        self.diff_formats = {
            'add': self.create_background_format('#e6ffe6'),  # Light green background
            'remove': self.create_background_format('#ffe6e6') # Light red background
        }

    def create_background_format(self, background_color):
        """Creates a QTextCharFormat with only background color."""
        fmt = QTextCharFormat()
        fmt.setBackground(QColor(background_color))
        return fmt

    def set_diff_info(self, line_info):
        """Receives diff info and stores it as a dictionary."""
        self.diff_line_info = {line_num: change_type for line_num, change_type in line_info}
        # Important: Trigger rehighlight after diff info changes
        # self.rehighlight() # Triggering rehighlight should be done from main.py after setting text AND diff info

    def highlightBlock(self, text):
        """Applies syntax highlighting first, then diff background."""
        # 1. Apply standard language syntax highlighting
        super().highlightBlock(text)
        
        # 2. Apply diff background highlighting
        current_block = self.currentBlock()
        line_number = current_block.blockNumber() + 1 # QTextBlock is 0-indexed
        
        if line_number in self.diff_line_info:
            change_type = self.diff_line_info[line_number]
            if change_type in self.diff_formats:
                background_format = self.diff_formats[change_type]
                # Apply background format to the entire block
                # This might override some syntax formats if they also set background,
                # but typically syntax highlighting only sets foreground color.
                self.setFormat(0, len(text), background_format)

def format_diff_content(old_content, new_content):
    """
    使用git diff获取结构化的差异信息。
    返回: (list_of_old_line_info, list_of_new_line_info)
    每个 list_of_x_line_info 是 [(line_number, change_type), ...] 列表
    change_type 可以是 'add', 'remove', 'normal'
    """
    
    old_line_info = []
    new_line_info = []

    # Handle empty content cases early
    if not old_content and not new_content:
        return [], []
        
    original_old_lines = old_content.splitlines()
    original_new_lines = new_content.splitlines()

    if not old_content:
         for i in range(len(original_new_lines)):
             new_line_info.append((i + 1, 'add'))
         return [], new_line_info
    if not new_content:
        for i in range(len(original_old_lines)):
            old_line_info.append((i + 1, 'remove'))
        return old_line_info, []

    # Create temporary files safely
    old_path, new_path = None, None # Initialize paths
    try:
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='_old', encoding='utf-8') as old_file:
            old_file.write(old_content)
            old_path = old_file.name
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='_new', encoding='utf-8') as new_file:
            new_file.write(new_content)
            new_path = new_file.name

        # --- Call git diff ---    
        cmd = ['git', 'diff', '--no-index', old_path, new_path]
        try:
            # Use a reasonable timeout
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', timeout=10, errors='replace')
            # Check return code: 0=no diff, 1=diff, >1=error
            if result.returncode > 1 and result.stderr:
                 diff_output = ""
                 print(f"Git diff error: {result.stderr}") 
            else:
                diff_output = result.stdout
        except subprocess.TimeoutExpired:
            print("Git diff command timed out")
            diff_output = ""
            result = None # Ensure result object exists for checks below
        except FileNotFoundError:
            print("Git command not found. Please ensure Git is installed and in the PATH.")
            diff_output = ""
            result = None
        except Exception as e:
            print(f"An unexpected error occurred during git diff: {e}")
            diff_output = ""
            result = None
            
        # If diff output is empty (files identical, error, or timeout), mark all lines as 'normal'
        if not diff_output or (result and result.returncode == 0):
            for i in range(len(original_old_lines)):
                old_line_info.append((i + 1, 'normal'))
            for i in range(len(original_new_lines)):
                new_line_info.append((i + 1, 'normal'))
            return old_line_info, new_line_info # Return early

        # --- Parse Git Diff Output --- 
        current_old_lineno = 1
        current_new_lineno = 1
        diff_lines = diff_output.splitlines()
        i = 0
        while i < len(diff_lines):
            line = diff_lines[i]
            
            # Skip header lines
            if line.startswith('diff --git') or line.startswith('index'):
                i += 1
                continue
            # Skip --- +++ lines carefully
            if line.startswith('--- ') or line.startswith('+++ '):
                i += 1
                continue
                
            # Process hunk headers
            if line.startswith('@@'):
                match = re.match(r'@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@', line)
                if match:
                    hunk_old_start = int(match.group(1))
                    hunk_new_start = int(match.group(2))
                    
                    # Add unchanged lines before the hunk
                    while current_old_lineno < hunk_old_start:
                        if current_old_lineno <= len(original_old_lines):
                            old_line_info.append((current_old_lineno, 'normal'))
                        if current_new_lineno <= len(original_new_lines):
                             new_line_info.append((current_new_lineno, 'normal')) 
                             current_new_lineno += 1 # Increment only if added
                        current_old_lineno += 1
                    
                    # Align line counters to the start of the hunk
                    current_old_lineno = hunk_old_start
                    current_new_lineno = hunk_new_start
                        
                i += 1
                continue # Move to the next line after processing hunk header
            
            # Process diff content lines
            if line.startswith('-'):
                if current_old_lineno <= len(original_old_lines):
                    old_line_info.append((current_old_lineno, 'remove'))
                    current_old_lineno += 1
                else: print(f"Warning: Tried to remove old line {current_old_lineno} beyond content length {len(original_old_lines)}")
            elif line.startswith('+'):
                if current_new_lineno <= len(original_new_lines):
                    new_line_info.append((current_new_lineno, 'add'))
                    current_new_lineno += 1
                else: print(f"Warning: Tried to add new line {current_new_lineno} beyond content length {len(original_new_lines)}")
            elif line.startswith(' '): 
                if current_old_lineno <= len(original_old_lines) and current_new_lineno <= len(original_new_lines):
                    old_line_info.append((current_old_lineno, 'normal'))
                    new_line_info.append((current_new_lineno, 'normal'))
                    current_old_lineno += 1
                    current_new_lineno += 1
                else: print(f"Warning: Mismatch in common line tracking at old:{current_old_lineno}, new:{current_new_lineno}")
            elif line.startswith('\\'): # Ignore "No newline at end of file"
                 pass
            else:
                # Should not happen with standard diff, but log if it does
                print(f"Warning: Unexpected diff line format: {line}")
                
            i += 1 # Move to the next line
        
        # Add unchanged lines after the last hunk
        while current_old_lineno <= len(original_old_lines):
            old_line_info.append((current_old_lineno, 'normal'))
            current_old_lineno += 1
        while current_new_lineno <= len(original_new_lines):
            new_line_info.append((current_new_lineno, 'normal'))
            current_new_lineno += 1
            
    finally:
        # Clean up temporary files safely
        for p in [old_path, new_path]:
            if p and os.path.exists(p):
                 try:
                     os.unlink(p)
                 except OSError as e:
                     print(f"Error deleting temp file {p}: {e}")

    return old_line_info, new_line_info 