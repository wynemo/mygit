import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QFileDialog, QVBoxLayout, QWidget, QPushButton, QListWidget
from PyQt6.QtCore import Qt

class GitManagerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Git Manager")
        self.setGeometry(100, 100, 800, 600)
        
        # 创建主窗口部件
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        # 创建布局
        layout = QVBoxLayout()
        main_widget.setLayout(layout)
        
        # 创建打开文件夹按钮
        self.open_button = QPushButton("打开文件夹")
        self.open_button.clicked.connect(self.open_folder)
        layout.addWidget(self.open_button)
        
        # 创建列表显示区域
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)
        
    def open_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "选择Git仓库")
        if folder_path:
            # TODO: 在这里添加获取Git信息的逻辑
            self.list_widget.addItem(f"已选择文件夹: {folder_path}")

def main():
    app = QApplication(sys.argv)
    window = GitManagerWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 