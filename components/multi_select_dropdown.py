"""
多选下拉框组件
支持多项选择和搜索过滤
"""

from PyQt6.QtCore import Qt, pyqtSignal, QEvent
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, 
    QListWidget, QListWidgetItem, QCheckBox, QLabel, QFrame
)


class MultiSelectDropdown(QWidget):
    """多选下拉框组件"""
    
    selectionChanged = pyqtSignal(list)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.options = []
        self.selected_items = []
        self.is_dropdown_open = False
        self.setup_ui()
        self.connect_signals()
    
    def setup_ui(self):
        """设置UI"""
        self.setFixedWidth(300)
        
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(2)
        
        # 输入框容器
        self.input_container = QFrame()
        self.input_container.setStyleSheet("""
            QFrame {
                background-color: #2d3748;
                border: 1px solid #4a5568;
                border-radius: 4px;
            }
        """)
        input_layout = QHBoxLayout(self.input_container)
        input_layout.setContentsMargins(8, 8, 8, 8)
        
        # 搜索输入框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("")
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: transparent;
                border: none;
                color: white;
                font-size: 14px;
            }
            QLineEdit::placeholder {
                color: #a0aec0;
            }
        """)
        
        # 下拉箭头按钮
        self.dropdown_button = QPushButton("▼")
        self.dropdown_button.setFixedSize(20, 20)
        self.dropdown_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: white;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #4a5568;
                border-radius: 2px;
            }
        """)
        
        input_layout.addWidget(self.search_input)
        input_layout.addWidget(self.dropdown_button)
        
        main_layout.addWidget(self.input_container)
        
        # 下拉列表
        self.dropdown_list = QListWidget()
        self.dropdown_list.setStyleSheet("""
            QListWidget {
                background-color: #2d3748;
                border: 1px solid #4a5568;
                border-radius: 4px;
                color: white;
                outline: none;
            }
            QListWidget::item {
                padding: 8px;
                border: none;
            }
            QListWidget::item:hover {
                background-color: #4a5568;
            }
        """)
        self.dropdown_list.hide()
        main_layout.addWidget(self.dropdown_list)
        
        # 底部提示文本
        self.help_label = QLabel("Select one or more values separated with | or new lines, use ⌘↵ to finish")
        self.help_label.setStyleSheet("""
            QLabel {
                color: #a0aec0;
                font-size: 12px;
                padding: 4px 0;
            }
        """)
        self.help_label.setWordWrap(True)
        main_layout.addWidget(self.help_label)
        
        self.setLayout(main_layout)
    
    def connect_signals(self):
        """连接信号"""
        self.dropdown_button.clicked.connect(self.toggle_dropdown)
        self.search_input.textChanged.connect(self.filter_options)
        self.search_input.returnPressed.connect(self.handle_return_pressed)
    
    def toggle_dropdown(self):
        """切换下拉列表显示状态"""
        if self.is_dropdown_open:
            self.hide_dropdown()
        else:
            self.show_dropdown()
    
    def show_dropdown(self):
        """显示下拉列表"""
        self.is_dropdown_open = True
        self.dropdown_list.show()
        self.dropdown_button.setText("▲")
        self.update_list_items()
    
    def hide_dropdown(self):
        """隐藏下拉列表"""
        self.is_dropdown_open = False
        self.dropdown_list.hide()
        self.dropdown_button.setText("▼")
    
    def update_list_items(self):
        """更新列表项"""
        self.dropdown_list.clear()
        filter_text = self.search_input.text().lower()
        
        for option in self.options:
            if not filter_text or filter_text in option.lower():
                item = QListWidgetItem()
                checkbox = QCheckBox(option)
                checkbox.setChecked(option in self.selected_items)
                checkbox.stateChanged.connect(lambda state, opt=option: self.toggle_selection(opt, state))
                checkbox.setStyleSheet("""
                    QCheckBox {
                        color: white;
                        spacing: 8px;
                    }
                    QCheckBox::indicator {
                        width: 16px;
                        height: 16px;
                    }
                    QCheckBox::indicator:unchecked {
                        background-color: transparent;
                        border: 2px solid #4a5568;
                        border-radius: 2px;
                    }
                    QCheckBox::indicator:checked {
                        background-color: #4299e1;
                        border: 2px solid #4299e1;
                        border-radius: 2px;
                    }
                """)
                
                self.dropdown_list.addItem(item)
                self.dropdown_list.setItemWidget(item, checkbox)
    
    def filter_options(self, text):
        """过滤选项"""
        if self.is_dropdown_open:
            self.update_list_items()
    
    def toggle_selection(self, option, state):
        """切换选项选择状态"""
        if state == Qt.CheckState.Checked.value:
            if option not in self.selected_items:
                self.selected_items.append(option)
        else:
            if option in self.selected_items:
                self.selected_items.remove(option)
        
        self.update_display()
        self.selectionChanged.emit(self.selected_items)
    
    def update_display(self):
        """更新显示文本"""
        if self.selected_items:
            display_text = " | ".join(self.selected_items)
            self.search_input.setText(display_text)
        else:
            self.search_input.setText("")
    
    def handle_return_pressed(self):
        """处理回车键"""
        text = self.search_input.text().strip()
        if text and not self.is_dropdown_open:
            # 解析多个值（用 | 或换行分隔）
            values = [v.strip() for v in text.replace('\n', '|').split('|') if v.strip()]
            for value in values:
                if value not in self.selected_items and value in self.options:
                    self.selected_items.append(value)
            self.update_display()
            self.selectionChanged.emit(self.selected_items)
        
        if self.is_dropdown_open:
            self.hide_dropdown()
    
    def set_options(self, options):
        """设置选项列表"""
        self.options = options
        if self.is_dropdown_open:
            self.update_list_items()
    
    def get_selected_values(self):
        """获取选中的值列表"""
        return self.selected_items.copy()
    
    def set_selected_values(self, values):
        """设置选中的值"""
        self.selected_items = [v for v in values if v in self.options]
        self.update_display()
        if self.is_dropdown_open:
            self.update_list_items()
    
    def clear_selection(self):
        """清空选择"""
        self.selected_items.clear()
        self.update_display()
        if self.is_dropdown_open:
            self.update_list_items()
        self.selectionChanged.emit(self.selected_items)
    
    def keyPressEvent(self, event):
        """处理键盘事件"""
        if event.key() == Qt.Key.Key_Escape:
            self.hide_dropdown()
        elif event.key() == Qt.Key.Key_Return and event.modifiers() == Qt.KeyboardModifier.MetaModifier:
            # Cmd+Enter 完成选择
            self.hide_dropdown()
        else:
            super().keyPressEvent(event)
    
    def focusOutEvent(self, event):
        """失去焦点时隐藏下拉列表"""
        # 延迟隐藏，以便处理点击事件
        if self.is_dropdown_open:
            self.hide_dropdown()
        super().focusOutEvent(event)