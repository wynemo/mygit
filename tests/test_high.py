import sys

import diff_match_patch
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat, QTextDocument
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class DiffSyntaxHighlighter(QSyntaxHighlighter):
    """基于 QSyntaxHighlighter 的差异高亮类"""

    def __init__(self, parent: QTextDocument = None):
        super().__init__(parent)
        self.dmp = diff_match_patch.diff_match_patch()
        self.diff_list = []
        self.is_left_side = True  # 标识是左侧还是右侧文本

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

    def set_texts(self, left_text: str, right_text: str, is_left: bool = True):
        """设置要对比的文本"""
        self.is_left_side = is_left
        # 计算差异
        self.diff_list = self.dmp.diff_main(left_text, right_text)
        self.dmp.diff_cleanupSemantic(self.diff_list)

        # 触发重新高亮
        self.rehighlight()

    def highlightBlock(self, text: str):
        """重写高亮方法"""
        if not self.diff_list:
            return

        # 构建完整文档文本用于定位
        document = self.document()
        full_text = document.toPlainText()

        # 获取当前块在整个文档中的位置
        current_block = self.currentBlock()
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
                    else:  # DIFF_EQUAL
                        format_to_apply = self.equal_format

                    if format_to_apply:
                        self.setFormat(start_in_block, end_in_block - start_in_block, format_to_apply)

            # 只有在 DELETE 和 EQUAL 时才移动左侧位置，INSERT 和 EQUAL 时才移动右侧位置
            if self.is_left_side:
                if op != diff_match_patch.diff_match_patch.DIFF_INSERT:
                    current_pos += data_length
            elif op != diff_match_patch.diff_match_patch.DIFF_DELETE:
                current_pos += data_length


class DiffViewerMainWindow(QMainWindow):
    """主窗口类"""

    def __init__(self):
        super().__init__()
        self.left_highlighter = None
        self.right_highlighter = None
        self.init_ui()

    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("文件差异对比工具")
        self.setGeometry(100, 100, 1200, 800)

        # 创建中央 widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 创建主布局
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        # 创建按钮布局
        button_layout = QHBoxLayout()

        # 创建按钮
        self.load_left_btn = QPushButton("加载左侧文件")
        self.load_right_btn = QPushButton("加载右侧文件")
        self.compare_btn = QPushButton("开始对比")
        self.clear_btn = QPushButton("清除内容")

        button_layout.addWidget(self.load_left_btn)
        button_layout.addWidget(self.load_right_btn)
        button_layout.addWidget(self.compare_btn)
        button_layout.addWidget(self.clear_btn)
        button_layout.addStretch()

        main_layout.addLayout(button_layout)

        # 创建标签布局
        label_layout = QHBoxLayout()
        self.left_label = QLabel("左侧文件 (原始)")
        self.right_label = QLabel("右侧文件 (修改后)")

        label_layout.addWidget(self.left_label)
        label_layout.addWidget(self.right_label)

        main_layout.addLayout(label_layout)

        # 创建分割器和文本编辑器
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.left_text_edit = QTextEdit()
        self.right_text_edit = QTextEdit()

        # 设置字体
        font = QFont("Consolas", 10)
        self.left_text_edit.setFont(font)
        self.right_text_edit.setFont(font)

        splitter.addWidget(self.left_text_edit)
        splitter.addWidget(self.right_text_edit)
        splitter.setSizes([600, 600])

        main_layout.addWidget(splitter)

        # 创建状态标签
        self.status_label = QLabel("准备就绪")
        main_layout.addWidget(self.status_label)

        # 连接信号
        self.load_left_btn.clicked.connect(self.load_left_file)
        self.load_right_btn.clicked.connect(self.load_right_file)
        self.compare_btn.clicked.connect(self.compare_texts)
        self.clear_btn.clicked.connect(self.clear_texts)

        # 创建语法高亮器
        self.left_highlighter = DiffSyntaxHighlighter(self.left_text_edit.document())
        self.right_highlighter = DiffSyntaxHighlighter(self.right_text_edit.document())

        # 添加一些示例文本
        self.add_sample_text()

    def add_sample_text(self):
        """添加示例文本用于演示"""
        left_sample = """这是第一行文本
这是第二行文本
这是第三行需要修改的文本
这是第四行文本
这是第五行文本"""

        right_sample = """这是第一行文本
这是第二行文本
这是第三行已经修改的文本
这是新增的一行
这是第四行文本
这是第五行文本"""

        self.left_text_edit.setPlainText(left_sample)
        self.right_text_edit.setPlainText(right_sample)

    def load_left_file(self):
        """加载左侧文件"""
        file_path, _ = QFileDialog.getOpenFileName(self, "选择左侧文件", "", "文本文件 (*.txt);;所有文件 (*)")

        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as file:
                    content = file.read()
                    self.left_text_edit.setPlainText(content)
                    self.left_label.setText(f"左侧文件：{file_path}")
                    self.status_label.setText(f"已加载左侧文件：{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"无法加载文件：{e!s}")

    def load_right_file(self):
        """加载右侧文件"""
        file_path, _ = QFileDialog.getOpenFileName(self, "选择右侧文件", "", "文本文件 (*.txt);;所有文件 (*)")

        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as file:
                    content = file.read()
                    self.right_text_edit.setPlainText(content)
                    self.right_label.setText(f"右侧文件：{file_path}")
                    self.status_label.setText(f"已加载右侧文件：{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"无法加载文件：{e!s}")

    def compare_texts(self):
        """执行文本对比并应用高亮"""
        left_content = self.left_text_edit.toPlainText()
        right_content = self.right_text_edit.toPlainText()

        if not left_content and not right_content:
            QMessageBox.information(self, "提示", "请先输入或加载要对比的文本")
            return

        try:
            # 设置高亮器的文本并指定左右侧
            self.left_highlighter.set_texts(left_content, right_content, is_left=True)
            self.right_highlighter.set_texts(left_content, right_content, is_left=False)

            self.status_label.setText("对比完成！红色表示删除，绿色表示新增")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"对比过程中出现错误：{e!s}")

    def clear_texts(self):
        """清除文本内容"""
        self.left_text_edit.clear()
        self.right_text_edit.clear()
        self.left_label.setText("左侧文件 (原始)")
        self.right_label.setText("右侧文件 (修改后)")
        self.status_label.setText("已清除所有内容")


def main():
    """主函数"""
    app = QApplication(sys.argv)

    # 检查 diff_match_patch 是否可用
    try:
        import diff_match_patch
    except ImportError:
        from PyQt6.QtWidgets import QMessageBox

        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle("缺少依赖")
        msg.setText("缺少 diff-match-patch 库")
        msg.setInformativeText("请运行：pip install diff-match-patch")
        msg.exec()
        sys.exit(1)

    window = DiffViewerMainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    pass
    # main()
