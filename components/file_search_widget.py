"""cursor 生成
文件搜索组件界面实现
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


class FileSearchWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        if hasattr(parent, "file_tree"):
            self.setMinimumWidth(parent.file_tree.width())
            self.setMinimumHeight(parent.file_tree.height())

    def setup_ui(self):
        """初始化UI界面"""
        self.setWindowTitle("File Search")
        self.setStyleSheet("""
            QFrame {
                background-color: #f8f8f8;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
            QLineEdit {
                padding: 5px;
                border: 1px solid #ccc;
                border-radius: 3px;
            }
            QPushButton {
                padding: 5px 10px;
                min-width: 24px;
                border: 1px solid #ccc;
                border-radius: 3px;
                background-color: #f0f0f0;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QTreeWidget {
                border: 1px solid #ddd;
                border-radius: 3px;
                background-color: white;
            }
        """)

        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # 搜索输入区域
        search_input_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search...")
        search_input_layout.addWidget(self.search_input)

        # 工具按钮区域
        tool_buttons_layout = QHBoxLayout()
        tool_buttons_layout.setSpacing(4)

        self.refresh_button = QPushButton("↻")
        self.clear_button = QPushButton("×")
        self.settings_button = QPushButton("⚙")
        self.case_button = QPushButton("Aa")
        self.regex_button = QPushButton(".*")
        self.word_button = QPushButton("ab")

        tool_buttons_layout.addWidget(self.refresh_button)
        tool_buttons_layout.addWidget(self.clear_button)
        tool_buttons_layout.addWidget(self.settings_button)
        tool_buttons_layout.addWidget(self.case_button)
        tool_buttons_layout.addWidget(self.regex_button)
        tool_buttons_layout.addWidget(self.word_button)

        search_input_layout.addLayout(tool_buttons_layout)
        main_layout.addLayout(search_input_layout)

        # 文件过滤区域
        filter_layout = QHBoxLayout()
        self.include_input = QLineEdit()
        self.include_input.setPlaceholderText("files to include")
        self.exclude_input = QLineEdit()
        self.exclude_input.setPlaceholderText("files to exclude")

        filter_layout.addWidget(self.include_input)
        filter_layout.addWidget(self.exclude_input)
        main_layout.addLayout(filter_layout)

        # 结果统计
        self.result_label = QLabel("0 results")
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        main_layout.addWidget(self.result_label)

        # 搜索结果树
        self.result_tree = QTreeWidget()
        self.result_tree.setHeaderHidden(True)
        self.result_tree.setIndentation(15)

        # 添加示例数据用于界面展示
        file_item1 = QTreeWidgetItem(["src/main.py (3)"])
        file_item1.addChild(QTreeWidgetItem(["1: import os"]))
        file_item1.addChild(QTreeWidgetItem(["5: def main():"]))
        file_item1.addChild(QTreeWidgetItem(["10:     print('Hello')"]))

        file_item2 = QTreeWidgetItem(["utils/helper.py (1)"])
        file_item2.addChild(QTreeWidgetItem(["7: def helper_function():"]))

        self.result_tree.addTopLevelItem(file_item1)
        self.result_tree.addTopLevelItem(file_item2)

        main_layout.addWidget(self.result_tree)

        # Open in editor 链接
        self.open_link = QLabel("Open in editor")
        self.open_link.setStyleSheet("color: #0066cc; text-decoration: underline;")
        self.open_link.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_link.setAlignment(Qt.AlignmentFlag.AlignRight)
        main_layout.addWidget(self.open_link)

        self.setLayout(main_layout)
