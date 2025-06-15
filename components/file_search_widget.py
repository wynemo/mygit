"""cursor 生成
文件搜索组件界面实现
"""

import logging
import os

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
)
from ripgrepy import Ripgrepy


class FileSearchWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        if hasattr(parent, "file_tree"):
            self.setMinimumWidth(parent.file_tree.width())
            self.setMinimumHeight(parent.file_tree.height())
        self.connect_signals()

    def setup_ui(self):
        """初始化 UI 界面"""
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
        search_input_container = QFrame()
        search_input_container.setStyleSheet("""
            QFrame {
                border: 1px solid #ccc;
                border-radius: 3px;
                background-color: white;
            }
        """)
        search_input_layout = QHBoxLayout(search_input_container)
        search_input_layout.setContentsMargins(0, 0, 0, 0)
        search_input_layout.setSpacing(0)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                padding: 5px;
                border: none;
            }
        """)
        search_input_layout.addWidget(self.search_input)

        # 工具按钮区域
        self.case_button = QPushButton("Aa")
        self.regex_button = QPushButton(".*")
        self.word_button = QPushButton("ab")

        # 设置按钮为可切换状态
        self.case_button.setCheckable(True)
        self.regex_button.setCheckable(True)
        self.word_button.setCheckable(True)

        # 按钮样式
        button_style = """
            QPushButton {
                padding: 5px 8px;
                min-width: 24px;
                border: none;
                background-color: transparent;
            }
            QPushButton:checked {
                background-color: #e0e0e0;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
            }
        """
        self.case_button.setStyleSheet(button_style)
        self.regex_button.setStyleSheet(button_style)
        self.word_button.setStyleSheet(button_style)

        search_input_layout.addWidget(self.case_button)
        search_input_layout.addWidget(self.regex_button)
        search_input_layout.addWidget(self.word_button)

        main_layout.addWidget(search_input_container)

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

    def connect_signals(self):
        """连接信号与槽"""
        self.search_input.textChanged.connect(self.perform_search)
        self.case_button.toggled.connect(self.perform_search)
        self.regex_button.toggled.connect(self.perform_search)
        self.word_button.toggled.connect(self.perform_search)
        self.include_input.textChanged.connect(self.perform_search)
        self.exclude_input.textChanged.connect(self.perform_search)
        self.result_tree.itemDoubleClicked.connect(self.open_file_from_tree)
        self.open_link.linkActivated.connect(self.open_file_from_tree_current_selection)

    def perform_search(self):
        """执行搜索并更新结果"""
        self.result_tree.clear()
        self.result_label.setText("0 results")

        query_text = self.search_input.text().strip()
        if not query_text:
            return

        try:
            rg = Ripgrepy(query_text, path=os.getcwd())
            if self.case_button.isChecked():
                rg.ignore_case()
            if not self.regex_button.isChecked():
                rg.fixed_strings()
            if self.word_button.isChecked():
                rg.word_regexp()

            include_pattern = self.include_input.text().strip()
            if include_pattern:
                rg.glob(include_pattern)

            exclude_pattern = self.exclude_input.text().strip()
            if exclude_pattern:
                rg.glob(f"!{exclude_pattern}")

            results = rg.json().run()
            file_matches = {}
            total_matches = 0

            for item in results.as_dict:
                if item["type"] == "match":
                    file_path = item["data"]["path"]["text"]
                    line_number = item["data"]["line_number"]
                    line_text = item["data"]["lines"]["text"]
                    file_matches.setdefault(file_path, []).append((line_number, line_text))
                    total_matches += 1

            for file_path, matches in file_matches.items():
                file_item = QTreeWidgetItem([f"{file_path} ({len(matches)})"])
                for line_number, line_text in matches:
                    line_item = QTreeWidgetItem([f"{line_number}: {line_text}"])
                    file_item.addChild(line_item)
                self.result_tree.addTopLevelItem(file_item)

            self.result_label.setText(f"{len(file_matches)} files, {total_matches} results")

        except Exception as e:
            logging.error(f"Search failed: {e}")
            self.result_label.setText("Search failed")

    def open_file_from_tree(self, item):
        """双击打开文件"""
        if item.parent() is None:  # 顶层项（文件）
            file_path = item.text(0).split(" (")[0]
            logging.info(f"Opening file: {file_path}")
        else:  # 子项（行）
            file_path = item.parent().text(0).split(" (")[0]
            line_number = int(item.text(0).split(":")[0])
            logging.info(f"Opening file: {file_path} at line {line_number}")

    def open_file_from_tree_current_selection(self):
        """点击链接打开当前选中文件"""
        current_item = self.result_tree.currentItem()
        if current_item:
            self.open_file_from_tree(current_item)
