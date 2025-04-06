from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QPlainTextEdit, QScrollBar, QFrame, QApplication)
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QSize, QPoint
from PyQt6.QtGui import (QPainter, QColor, QFont, QSyntaxHighlighter, 
                        QTextCharFormat, QTextCursor)
from text_diff_viewer import MergeDiffViewer, DiffViewer
import sys

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Text Diff Viewer")
        self.resize(1200, 800)
        
        # 创建主布局
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # 创建三向对比视图
        self.merge_viewer = MergeDiffViewer()
        layout.addWidget(self.merge_viewer)
        
        # 创建双向对比视图
        self.diff_viewer = DiffViewer()
        layout.addWidget(self.diff_viewer)
        
        # 加载测试数据
        self.load_test_data()
        
    def load_test_data(self):
        # 创建测试数据
        parent1_text = []
        result_text = []
        parent2_text = []
        
        # 生成100行测试数据
        for i in range(1, 101):
            base_line = f"Line {i}"
            
            if i == 15:
                parent1_text.append(base_line)
                parent1_text.append("This line only exists in parent1")
                result_text.append(base_line)
                parent2_text.append(base_line)
            elif i == 25:
                parent1_text.append(base_line)
                result_text.append(base_line)
                result_text.append("This line exists in result and parent2")
                parent2_text.append(base_line)
                parent2_text.append("This line exists in result and parent2")
            elif i == 35:
                parent1_text.append("Parent1 version")
                result_text.append("Result version")
                parent2_text.append("Parent2 version")
            else:
                parent1_text.append(base_line)
                result_text.append(base_line)
                parent2_text.append(base_line)
        
        # 转换为文本
        parent1_text = "\n".join(parent1_text)
        result_text = "\n".join(result_text)
        parent2_text = "\n".join(parent2_text)
        
        # 设置三向对比视图的文本
        self.merge_viewer.set_texts(parent1_text, result_text, parent2_text)
        
        # 设置双向对比视图的文本（比较parent1和parent2）
        self.diff_viewer.set_texts(parent1_text, parent2_text)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())