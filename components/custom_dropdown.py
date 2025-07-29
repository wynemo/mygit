import os

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QCursor, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

"""
  使用方法：
  
  ## 基本用法
  # 创建下拉框
  dropdown = CustomDropdown("选择用户", ["张三", "李四", "王五"])

  # 设置选中项
  dropdown.set_selected_item("张三")

  # 清除选中项
  dropdown.clear_selected_item()

  # 监听清除信号
  dropdown.clear_selection.connect(your_handler)
  
  ## 联想输入功能
  # 使用列表作为联想数据源
  dropdown = CustomDropdown(
      "选择用户", 
      ["张三", "李四", "王五"],
      suggestion_provider=["张三", "李四", "王五", "赵六", "孙七"]
  )
  
  # 使用函数作为联想数据源（支持动态获取）
  def get_user_suggestions(query):
      # 根据查询返回用户列表
      return [user for user in all_users if query.lower() in user.lower()]
  
  dropdown = CustomDropdown(
      "选择用户",
      [],
      suggestion_provider=get_user_suggestions
  )
  
  # 分支名联想示例
  def get_branch_suggestions(query):
      # 获取 Git 分支列表
      import subprocess
      result = subprocess.run(['git', 'branch', '-a'], capture_output=True, text=True)
      branches = [line.strip().replace('* ', '').replace('origin/', '') 
                 for line in result.stdout.split('\n') if line.strip()]
      return [branch for branch in branches if query.lower() in branch.lower()]
  
  branch_dropdown = CustomDropdown(
      "选择分支",
      [],
      suggestion_provider=get_branch_suggestions
  )
  
  ## 联想功能特性
  - 实时搜索：输入时自动显示匹配项
  - 键盘导航：上下箭头选择，回车/Tab 确认，ESC 取消
  - 鼠标操作：点击选择联想项
  - 智能插入：自动处理分隔符（|）和换行
  - 配置选项：
    * max_suggestions: 最大显示数量（默认 10）
    * case_sensitive: 是否大小写敏感（默认 False）
    * min_chars: 触发联想的最小字符数（默认 1）
"""


class SuggestionListWidget(QListWidget):
    """联想建议列表组件"""

    item_selected = pyqtSignal(str)  # 选中项信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedHeight(200)  # 最大高度
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # 设置样式
        self.setStyleSheet("""
            QListWidget {
                background-color: white;
                border: 1px solid #e9ecef;
                border-radius: 6px;
                outline: none;
                selection-background-color: #f8f9fa;
            }
            QListWidget::item {
                padding: 8px 12px;
                border: none;
                color: #495057;
                font-size: 13px;
            }
            QListWidget::item:hover {
                background-color: #f8f9fa;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
                color: #1976d2;
            }
        """)

        # 连接信号
        self.itemClicked.connect(self._on_item_clicked)

    def _on_item_clicked(self, item):
        """处理项目点击"""
        if item:
            self.item_selected.emit(item.text())
            self.hide()

    def show_suggestions(self, suggestions, position):
        """显示建议列表"""
        self.clear()

        if not suggestions:
            self.hide()
            return

        # 添加建议项
        for suggestion in suggestions:
            item = QListWidgetItem(suggestion)
            self.addItem(item)

        # 调整大小和位置
        self.setFixedWidth(300)  # 与输入框宽度一致
        item_height = 32  # 每项高度
        visible_items = min(len(suggestions), 6)  # 最多显示 6 项
        self.setFixedHeight(visible_items * item_height + 4)  # +4 为边框

        self.move(position)
        self.show()

        # 默认选中第一项
        if self.count() > 0:
            self.setCurrentRow(0)

    def select_next(self):
        """选择下一项"""
        current = self.currentRow()
        if current < self.count() - 1:
            self.setCurrentRow(current + 1)

    def select_previous(self):
        """选择上一项"""
        current = self.currentRow()
        if current > 0:
            self.setCurrentRow(current - 1)

    def get_selected_text(self):
        """获取当前选中项的文本"""
        current_item = self.currentItem()
        return current_item.text() if current_item else None


class EditableInputPopup(QFrame):
    """可编辑输入的弹出窗口"""

    values_submitted = pyqtSignal(list)  # 提交多个值

    def __init__(self, parent=None, suggestion_provider=None, max_suggestions=10, case_sensitive=False, min_chars=1):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 联想功能配置
        self.suggestion_provider = suggestion_provider
        self.max_suggestions = max_suggestions
        self.case_sensitive = case_sensitive
        self.min_chars = min_chars

        # 创建联想列表组件
        self.suggestion_list = None
        if suggestion_provider is not None:
            self.suggestion_list = SuggestionListWidget(parent)
            self.suggestion_list.item_selected.connect(self._on_suggestion_selected)
            self.suggestion_list.hide()

        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 创建主容器
        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #e9ecef;
                border-radius: 6px;
            }
        """)

        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(12, 12, 12, 12)
        container_layout.setSpacing(8)

        # 提示标签
        hint_label = QLabel("Select one or more values separated with | or new lines, use ⌘↵ to finish")
        hint_label.setStyleSheet("""
            QLabel {
                color: #6c757d;
                font-size: 12px;
                background: transparent;
                border: none;
                padding: 4px 0;
            }
        """)
        hint_label.setWordWrap(True)
        container_layout.addWidget(hint_label)

        # 文本输入框
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("输入值，用 | 或换行分隔...")
        self.text_edit.setStyleSheet("""
            QTextEdit {
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
                background-color: white;
                min-height: 80px;
                max-height: 120px;
            }
            QTextEdit:focus {
                border-color: #007bff;
                outline: none;
            }
        """)

        # 监听快捷键 Cmd+Enter (macOS) 或 Ctrl+Enter (其他系统)
        self.text_edit.installEventFilter(self)

        # 如果启用了联想功能，监听文本变化
        if self.suggestion_list is not None:
            self.text_edit.textChanged.connect(self._on_text_changed)

        container_layout.addWidget(self.text_edit)

        # 按钮行
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(8)

        # 取消按钮
        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 6px 16px;
                font-size: 13px;
                color: #495057;
            }
            QPushButton:hover {
                background-color: #e9ecef;
            }
        """)
        cancel_btn.clicked.connect(self.hide)
        button_layout.addWidget(cancel_btn)

        # 弹性空间
        button_layout.addStretch()

        # 确认按钮
        confirm_btn = QPushButton("确认 (⌘↵)")
        confirm_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                border: 1px solid #007bff;
                border-radius: 4px;
                padding: 6px 16px;
                font-size: 13px;
                color: white;
            }
            QPushButton:hover {
                background-color: #0056b3;
                border-color: #0056b3;
            }
        """)
        confirm_btn.clicked.connect(self._submit_values)
        button_layout.addWidget(confirm_btn)

        container_layout.addLayout(button_layout)
        layout.addWidget(container)

        # 设置焦点到文本编辑框
        QTimer.singleShot(100, self.text_edit.setFocus)

    def eventFilter(self, obj, event):
        """事件过滤器，处理快捷键和联想导航"""
        if obj == self.text_edit and event.type() == event.Type.KeyPress:
            key = event.key()

            # 检查 Cmd+Enter (macOS) 或 Ctrl+Enter
            if key == Qt.Key.Key_Return and (
                event.modifiers() & Qt.KeyboardModifier.ControlModifier
                or event.modifiers() & Qt.KeyboardModifier.MetaModifier
            ):
                self._submit_values()
                return True

            # 处理联想列表导航
            if self.suggestion_list is not None and self.suggestion_list.isVisible():
                if key == Qt.Key.Key_Down:
                    # 下箭头 - 选择下一项
                    self.suggestion_list.select_next()
                    return True
                elif key == Qt.Key.Key_Up:
                    # 上箭头 - 选择上一项
                    self.suggestion_list.select_previous()
                    return True
                elif key in [Qt.Key.Key_Return, Qt.Key.Key_Tab]:
                    # 回车或 Tab - 确认选择
                    selected_text = self.suggestion_list.get_selected_text()
                    if selected_text:
                        self._on_suggestion_selected(selected_text)
                        return True
                elif key == Qt.Key.Key_Escape:
                    # ESC - 隐藏建议列表
                    self.suggestion_list.hide()
                    return True

        return super().eventFilter(obj, event)

    def _submit_values(self):
        """提交输入的值"""
        text = self.text_edit.toPlainText().strip()
        if not text:
            self.hide()
            return

        # 解析多个值：先按换行分割，再按 | 分割
        values = []
        lines = text.split("\n")
        for line in lines:
            line = line.strip()
            if "|" in line:
                # 按 | 分割
                parts = [part.strip() for part in line.split("|") if part.strip()]
                values.extend(parts)
            elif line:
                values.append(line)

        # 去重并保持顺序
        unique_values = []
        for value in values:
            if value not in unique_values:
                unique_values.append(value)

        if unique_values:
            self.values_submitted.emit(unique_values)

        self.hide()

    def _on_text_changed(self):
        """处理文本变化事件"""
        if self.suggestion_list is None:
            return

        # 获取当前光标位置的词汇
        current_word = self._get_current_word()

        if len(current_word) >= self.min_chars:
            # 获取联想建议
            suggestions = self._get_suggestions(current_word)
            if suggestions:
                self._show_suggestions(suggestions)
            else:
                self.suggestion_list.hide()
        else:
            self.suggestion_list.hide()

    def _get_current_word(self):
        """获取当前光标位置的词汇"""
        cursor = self.text_edit.textCursor()
        text = self.text_edit.toPlainText()
        position = cursor.position()

        # 找到当前词汇的开始和结束位置
        start = position
        end = position

        # 向前查找词汇开始位置（遇到空格、换行、|停止）
        while start > 0 and text[start - 1] not in [" ", "\n", "|"]:
            start -= 1

        # 向后查找词汇结束位置（遇到空格、换行、|停止）
        while end < len(text) and text[end] not in [" ", "\n", "|"]:
            end += 1

        return text[start:position].strip()

    def _get_suggestions(self, query):
        """根据查询获取联想建议"""
        if not query or self.suggestion_provider is None:
            return []

        # 处理不同类型的建议提供者
        if callable(self.suggestion_provider):
            try:
                # 如果是函数，调用函数获取建议
                all_suggestions = self.suggestion_provider(query)
            except Exception:
                return []
        elif isinstance(self.suggestion_provider, (list, tuple)):
            # 如果是列表，直接过滤
            all_suggestions = self.suggestion_provider
        else:
            return []

        # 根据查询过滤建议
        filtered_suggestions = []
        for suggestion in all_suggestions:
            if not self.case_sensitive:
                if query.lower() in suggestion.lower():
                    filtered_suggestions.append(suggestion)
            elif query in suggestion:
                filtered_suggestions.append(suggestion)

        # 限制数量并返回
        return filtered_suggestions[: self.max_suggestions]

    def _show_suggestions(self, suggestions):
        """显示联想建议列表"""
        if not suggestions or self.suggestion_list is None:
            return

        # 计算建议列表的位置（在输入框下方）
        global_pos = self.mapToGlobal(self.text_edit.geometry().bottomLeft())
        global_pos.setY(global_pos.y() + 5)  # 稍微向下偏移

        self.suggestion_list.show_suggestions(suggestions, global_pos)

    def _on_suggestion_selected(self, suggestion):
        """处理联想项选择"""
        cursor = self.text_edit.textCursor()
        text = self.text_edit.toPlainText()
        position = cursor.position()

        # 找到当前词汇的开始位置
        start = position
        while start > 0 and text[start - 1] not in [" ", "\n", "|"]:
            start -= 1

        # 替换当前词汇
        cursor.setPosition(start)
        cursor.setPosition(position, cursor.MoveMode.KeepAnchor)
        cursor.insertText(suggestion)

        # 隐藏建议列表
        self.suggestion_list.hide()

    def show_at_position(self, position):
        """在指定位置显示弹出框"""
        self.setMinimumWidth(300)
        self.setFixedWidth(300)
        self.move(position)
        self.show()
        self.text_edit.clear()
        self.text_edit.setFocus()

        # 隐藏联想列表
        if self.suggestion_list is not None:
            self.suggestion_list.hide()

    def hide(self):
        """隐藏弹出框"""
        super().hide()
        # 同时隐藏联想列表
        if self.suggestion_list is not None:
            self.suggestion_list.hide()


class DropdownPopup(QFrame):
    """下拉框弹出窗口"""

    item_selected = pyqtSignal(str)
    custom_values_selected = pyqtSignal(list)  # 新增：自定义值选择信号

    def __init__(self, parent=None, suggestion_provider=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.editable_popup = None
        self.suggestion_provider = suggestion_provider
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 创建主容器
        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #e9ecef;
                border-radius: 6px;
            }
        """)

        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # 添加 "Select..." 选项
        select_item = QLabel("Select...")
        select_item.setStyleSheet("""
            QLabel {
                color: #6c757d;
                font-size: 13px;
                padding: 8px 12px;
                background: transparent;
                border: none;
            }
            QLabel:hover {
                background-color: #f8f9fa;
            }
        """)
        select_item.setMinimumHeight(32)
        select_item.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        select_item.mousePressEvent = lambda _: self._on_select_clicked()
        container_layout.addWidget(select_item)

        # 添加示例用户项（可以根据需要动态添加）
        for item in self.parent().items:
            _item = QLabel(item)
            _item.setStyleSheet("""
                QLabel {
                    color: #495057;
                    font-size: 13px;
                    padding: 8px 12px;
                    background: transparent;
                    border: none;
                }
                QLabel:hover {
                    background-color: #f8f9fa;
                }
            """)
            _item.setMinimumHeight(32)
            _item.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            _item.mousePressEvent = lambda _, u=item: self._on_item_clicked(u)
            container_layout.addWidget(_item)

        layout.addWidget(container)

    def _on_item_clicked(self, item_text):
        """处理选项点击"""
        self.item_selected.emit(item_text)
        self.hide()

    def _on_select_clicked(self):
        """处理 Select... 选项点击，弹出可编辑输入框"""
        self.hide()  # 先隐藏下拉框

        if not self.editable_popup:
            self.editable_popup = EditableInputPopup(self.parent(), suggestion_provider=self.suggestion_provider)
            self.editable_popup.values_submitted.connect(self._on_custom_values_submitted)

        # 计算弹出框位置（相对于父组件）
        if self.parent():
            parent_widget = self.parent()
            global_pos = parent_widget.mapToGlobal(parent_widget.rect().bottomLeft())
            self.editable_popup.show_at_position(global_pos)

    def _on_custom_values_submitted(self, values):
        """处理自定义值提交"""
        self.custom_values_selected.emit(values)

    def show_at_position(self, position):
        """在指定位置显示弹出框"""
        # 设置最小宽度，确保与下拉框宽度一致
        self.setMinimumWidth(150)
        self.move(position)
        self.show()


class CustomDropdown(QWidget):
    clicked = pyqtSignal()
    clear_selection = pyqtSignal()
    values_changed = pyqtSignal(list)  # 新增：多值变化信号

    def __init__(self, text=None, items=None, parent=None, suggestion_provider=None):
        super().__init__(parent)
        self.text = text
        self.items = items or []
        self.selected_item = None
        self.selected_values = []  # 新增：存储多个选中的值
        self.dropdown_popup = None
        self.suggestion_provider = suggestion_provider  # 联想数据提供者
        self.setup_ui()
        self.setFixedHeight(32)
        self.setStyleSheet("""
            CustomDropdown {
                background-color: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 6px;
                padding: 6px 12px;
            }
            CustomDropdown:hover {
                background-color: #e9ecef;
                border-color: #dee2e6;
            }
        """)

    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        # 左侧文字标签
        self.text_label = QLabel(self.text or "")
        self.text_label.setStyleSheet("""
            QLabel {
                color: #495057;
                font-size: 13px;
                font-weight: 500;
                background: transparent;
                border: none;
            }
        """)
        layout.addWidget(self.text_label)

        # 选中项标签（初始隐藏）
        self.selected_label = QLabel()
        self.selected_label.setStyleSheet("""
            QLabel {
                color: #007bff;
                font-size: 13px;
                font-weight: 500;
                background: transparent;
                border: none;
                margin-left: 8px;
            }
        """)
        self.selected_label.hide()
        layout.addWidget(self.selected_label)

        # X 按钮（初始隐藏）
        self.clear_button = QLabel()
        self.clear_button.setText("×")
        self.clear_button.setStyleSheet("""
            QLabel {
                color: #6c757d;
                font-size: 16px;
                font-weight: bold;
                background: transparent;
                border: none;
                padding: 0 4px;
                margin-left: 4px;
            }
            QLabel:hover {
                color: #dc3545;
            }
        """)
        self.clear_button.hide()
        self.clear_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.clear_button.mousePressEvent = self._on_clear_clicked
        layout.addWidget(self.clear_button)

        # 右侧箭头图标
        self.arrow_label = QLabel()
        self.load_arrow_icon()
        layout.addWidget(self.arrow_label)

    def load_arrow_icon(self):
        """加载 SVG 箭头图标"""
        svg_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "icons", "chevron-down.svg")

        if os.path.exists(svg_path):
            # 使用 QSvgRenderer 渲染 SVG
            renderer = QSvgRenderer(svg_path)

            # 创建一个 16x16 的像素图
            pixmap = QPixmap(16, 16)
            pixmap.fill(Qt.GlobalColor.transparent)

            # 渲染 SVG 到像素图
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()

            self.arrow_label.setPixmap(pixmap)
        else:
            # 如果 SVG 文件不存在，使用文本箭头作为后备
            self.arrow_label.setText("▼")
            self.arrow_label.setStyleSheet("""
                QLabel {
                    color: #6c757d;
                    font-size: 12px;
                    background: transparent;
                    border: none;
                }
            """)

    def mousePressEvent(self, event):
        """处理鼠标点击事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._show_dropdown()
            self.clicked.emit()
        super().mousePressEvent(event)

    def _show_dropdown(self):
        """显示下拉框"""
        if not self.dropdown_popup:
            self.dropdown_popup = DropdownPopup(self, suggestion_provider=self.suggestion_provider)
            self.dropdown_popup.item_selected.connect(self._on_item_selected)
            self.dropdown_popup.custom_values_selected.connect(self._on_custom_values_selected)

        # 计算弹出框位置
        global_pos = self.mapToGlobal(self.rect().bottomLeft())
        self.dropdown_popup.show_at_position(global_pos)

    def _on_item_selected(self, item_text):
        """处理选项选择"""
        if item_text != "Select...":
            self.set_selected_item(item_text)

    def _on_custom_values_selected(self, values):
        """处理自定义值选择"""
        self.set_selected_values(values)
        self.values_changed.emit(values)

    def set_text(self, text):
        """设置显示文字"""
        self.text = text
        self.text_label.setText(text)

    def set_selected_item(self, item_text):
        """设置选中项"""
        self.selected_item = item_text
        if item_text:
            self.selected_values = [item_text]  # 同步到多值列表
        else:
            self.selected_values = []
        self._update_display()
        self.values_changed.emit(self.selected_values)

    def set_selected_values(self, values):
        """设置多个选中的值"""
        self.selected_values = values[:]  # 复制列表
        self.selected_item = values[0] if values else None  # 兼容性：设置第一个值为单选值
        self._update_display()

    def get_selected_values(self):
        """获取所有选中的值"""
        return self.selected_values[:]

    def _update_display(self):
        """更新显示"""
        if self.selected_values:
            # 显示选中的值，如果太多则省略
            display_text = " | ".join(self.selected_values)
            if len(display_text) > 30:  # 如果显示文本太长
                display_text = f"{self.selected_values[0]}... ({len(self.selected_values)} items)"

            self.selected_label.setText(display_text)
            self.selected_label.show()
            self.clear_button.show()
        else:
            self.selected_label.hide()
            self.clear_button.hide()

    def clear_selected_item(self):
        """清除选中项"""
        self.selected_item = None
        self.selected_values = []
        self.selected_label.hide()
        self.clear_button.hide()

    def _on_clear_clicked(self, event):
        """处理清除按钮点击事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clear_selected_item()
            self.clear_selection.emit()
            self.values_changed.emit([])
        # 阻止事件传播，避免触发组件的 clicked 信号
        event.accept()
