import logging
import os
from typing import Optional

from PyQt6.QtCore import QRect, QSize, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QFont,
    QKeyEvent,  # Added QKeyEvent
    QMouseEvent,
    QPainter,
    QPen,
    QTextCursor,
    QTextDocument,
)
from PyQt6.QtWidgets import (
    QMenu,
    QMessageBox,  # Added for save confirmation
    QPlainTextEdit,
    QTextEdit,  # Added QTextEdit
    QWidget,
)

from diff_highlighter import DiffHighlighter
from find_dialog import FindDialog
from settings import Settings


class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.editor.line_number_area_paint_event(event)

    def mousePressEvent(self, event: QMouseEvent):
        if self.editor.showing_blame and self.editor.blame_annotations_per_line:
            y_pos = event.pos().y()
            block = self.editor.firstVisibleBlock()
            block_number = block.blockNumber()
            block_top = self.editor.blockBoundingGeometry(block).translated(self.editor.contentOffset()).top()
            block_height = self.editor.blockBoundingRect(block).height()

            if block_height == 0:  # Avoid division by zero if block height is zero
                super().mousePressEvent(event)
                return

            line_index = block_number + int((y_pos - block_top) / block_height)

            if 0 <= line_index < len(self.editor.blame_annotations_per_line):
                annotation = self.editor.blame_annotations_per_line[line_index]
                if annotation and "commit_hash" in annotation:
                    # Check if the click is within the blame annotation area
                    # This is a simplified check, assuming blame text starts from PADDING_LEFT_OF_BLAME
                    # and extends up to max_blame_display_width
                    blame_area_width = self.editor.PADDING_LEFT_OF_BLAME + getattr(
                        self.editor, "max_blame_display_width", 0
                    )
                    if event.pos().x() < blame_area_width:
                        full_hash = annotation.get("commit_hash", "")
                        if full_hash:
                            self.editor.blame_annotation_clicked.emit(full_hash)
                            return  # Event handled

        super().mousePressEvent(event)


class SyncedTextEdit(QPlainTextEdit):
    blame_annotation_clicked = pyqtSignal(str)
    # Padding constants
    PADDING_LEFT_OF_BLAME = 5
    PADDING_AFTER_BLAME = 10
    PADDING_RIGHT_OF_LINENUM = 5
    # 编辑状态
    edit_cancel_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        settings = Settings()
        self.setFont(QFont(settings.get_font_family(), 10))
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setReadOnly(True)  # 默认设置为只读
        self.original_content = ""  # 保存原始内容，用于取消编辑时恢复
        logging.debug("\n=== 初始化SyncedTextEdit ===")
        logging.debug("默认只读模式: %s", self.isReadOnly())

        # Blame data storage
        # self.blame_data_full will store the original dicts with full hashes
        self.blame_data_full = []
        self.blame_annotations_per_line = []  # Will store annotations with _display_string for painting
        self.showing_blame = False
        self.file_path = None  # Initialize file_path, can be set externally
        self.current_commit_hash: Optional[str] = None  # Ensured Optional[str]

        # 编辑状态变量
        self.edit_mode = False
        # 添加行号区域
        self.line_number_area = LineNumberArea(self)
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.update_line_number_area_width()

        # 连接编辑取消信号
        self.edit_cancel_requested.connect(self.cancel_edit)
        # 初始化差异信息
        self.highlighter = None

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.find_dialog_instance = None  # Initialize find_dialog_instance
        self.search_highlights = []  # Initialize search_highlights

    def open_find_dialog(self):
        cursor = self.textCursor()
        selected_text = cursor.selectedText()

        if self.find_dialog_instance is None or not self.find_dialog_instance.isVisible():
            self.find_dialog_instance = FindDialog(parent_editor=self, initial_search_text=selected_text)

            editor_global_pos = self.rect().topRight()

            dialog_width = self.find_dialog_instance.sizeHint().width()
            if dialog_width <= 0 and hasattr(self.find_dialog_instance, "minimumWidth"):
                dialog_width = self.find_dialog_instance.minimumWidth()  # Fallback to minimumWidth

            dialog_x = editor_global_pos.x() - dialog_width - 100
            dialog_y = editor_global_pos.y() + 50

            self.find_dialog_instance.move(dialog_x, dialog_y)

            self.find_dialog_instance.show()
        else:
            if selected_text and hasattr(self.find_dialog_instance, "search_input"):
                self.find_dialog_instance.search_input.setText(selected_text)
            self.find_dialog_instance.show()
            print("show again")

    def keyPressEvent(self, event: QKeyEvent):
        # 保存快捷键 (Ctrl+S 或 Cmd+S)
        if (
            not self.isReadOnly()
            and event.key() == Qt.Key.Key_S
            and (
                event.modifiers() == Qt.KeyboardModifier.ControlModifier
                or event.modifiers() == Qt.KeyboardModifier.MetaModifier
            )
        ):
            self.save_content()
            event.accept()
        # 查找快捷键 (Ctrl+F 或 Cmd+F)
        elif event.key() == Qt.Key.Key_F and (
            event.modifiers() == Qt.KeyboardModifier.ControlModifier
            or event.modifiers() == Qt.KeyboardModifier.MetaModifier
        ):
            self.open_find_dialog()
            event.accept()  # Indicate that the event has been handled
        else:
            super().keyPressEvent(event)  # Call base class implementation for other keys

    def find_text(self, search_text: str, direction: str = "next", case_sensitive: bool = False) -> bool:
        """Finds text in the editor and highlights it if found."""
        # Clear previous highlights
        self.search_highlights.clear()
        self.setExtraSelections([])

        flags = QTextDocument.FindFlag(0)
        if direction == "previous":
            flags |= QTextDocument.FindFlag.FindBackward
        if case_sensitive:
            flags |= QTextDocument.FindFlag.FindCaseSensitively

        # Call QPlainTextEdit's find method
        found = super().find(search_text, flags)

        if found:
            logging.info(f"Found '{search_text}' in {self.objectName()}")
            self.ensureCursorVisible()  # Make sure the found text is visible

            # Create and apply highlight for the found text
            selection = QTextEdit.ExtraSelection()
            selection.cursor = self.textCursor()  # Cursor is already at the found selection
            selection.format.setBackground(QColor("#ADD8E6"))  # Light blue
            self.search_highlights.append(selection)
            self.setExtraSelections(self.search_highlights)
        else:
            logging.info(f"'{search_text}' not found in {self.objectName()}")
            # Highlights are already cleared at the beginning of the method.
            # If not found while searching forward, move cursor to the beginning.
            # This allows the next search to start from the top.
            if direction == "next":
                cursor = self.textCursor()
                cursor.movePosition(QTextCursor.MoveOperation.Start)
                self.setTextCursor(cursor)
            # Optional: If searching backward and not found, could move to the end.
            # else: # direction == "previous"
            #     cursor = self.textCursor()
            #     cursor.movePosition(QTextCursor.MoveOperation.End)
            #     self.setTextCursor(cursor)
        return found

    def clear_search_highlights(self):
        """Clears all search-related highlights from the editor."""
        self.search_highlights.clear()
        self.setExtraSelections([])
        logging.debug(f"Search highlights cleared for {self.objectName()}")

    def scroll_to_line(self, line_number: int):
        """Scrolls the text edit to the specified line number (0-indexed)."""
        document = self.document()
        if 0 <= line_number < document.blockCount():
            block = document.findBlockByNumber(line_number)
            if block.isValid():
                cursor = QTextCursor(block)
                self.setTextCursor(cursor)
                self.ensureCursorVisible()
                logging.info(f"Scrolled {self.objectName()} to line {line_number + 1} (0-indexed: {line_number})")
            else:
                logging.warning(f"Block for line {line_number} (0-indexed) not found in {self.objectName()}.")
        else:
            logging.warning(
                f"Invalid line number {line_number} (0-indexed) for {self.objectName()}. Total lines: {document.blockCount()}"
            )

    def show_context_menu(self, position):
        menu = QMenu(self)
        if self.isReadOnly():
            edit_action = menu.addAction("编辑内容")
            edit_action.triggered.connect(self.set_editable)
        else:
            save_action = menu.addAction("保存更改")
            save_action.triggered.connect(self.save_content)
            cancel_edit_action = menu.addAction("取消编辑")
            cancel_edit_action.triggered.connect(self.cancel_edit)

        # 只在只读状态下显示blame相关菜单
        if self.isReadOnly() or not self.blame_annotations_per_line:
            blame_action = menu.addAction("Show Blame")
            blame_action.triggered.connect(self.show_blame)
            clear_blame_action = menu.addAction("Clear Blame")
            clear_blame_action.triggered.connect(self.clear_blame_data)
        menu.exec(self.mapToGlobal(position))

    # Renamed from _show_context_menu to show_context_menu for consistency
    # No other change in this method, just ensuring the diff picks up the rename if any confusion.

    def set_editable(self):
        """将文本编辑设置为可编辑模式并保存原始内容"""
        if self.isReadOnly():
            self.edit_mode = True
            # 保存原始内容
            self.original_content = self.toPlainText()
            self.setReadOnly(False)
            logging.info("进入编辑模式，文件路径: %s", self.file_path)
            self.viewport().setCursor(Qt.CursorShape.IBeamCursor)  # 显示可编辑光标

    def save_content(self):
        """保存更改到文件"""
        if self.isReadOnly() or not self.file_path:
            return

        try:
            current_content = self.toPlainText()
            # 显示保存确认对话框
            reply = QMessageBox.question(
                self,
                "确认保存",
                f"确定保存更改到文件 '{os.path.basename(self.file_path)}'?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save,
            )

            if reply == QMessageBox.StandardButton.Save:
                with open(self.file_path, "w", encoding="utf-8") as f:
                    f.write(current_content)

                logging.info("文件保存成功: %s", self.file_path)
                self.original_content = current_content

                # 保存后自动切换回只读模式
                self.setReadOnly(True)
                self.edit_mode = False
                self.viewport().setCursor(Qt.CursorShape.ArrowCursor)  # 恢复箭头光标

                # 显示保存成功信息
                QMessageBox.information(
                    self,
                    "保存成功",
                    f"文件 '{os.path.basename(self.file_path)}' 已成功保存",
                    QMessageBox.StandardButton.Ok,
                )
        except Exception as e:
            logging.error("文件保存失败: %s", str(e))
            QMessageBox.critical(self, "保存错误", f"无法保存文件: {e!s}", QMessageBox.StandardButton.Ok)

    def cancel_edit(self):
        """取消编辑并恢复原始内容"""
        if not self.isReadOnly() and self.edit_mode:
            self.setPlainText(self.original_content)
            self.setReadOnly(True)
            self.edit_mode = False
            logging.info("已取消编辑并恢复原始内容")
            self.viewport().setCursor(Qt.CursorShape.ArrowCursor)  # 恢复箭头光标

    def set_blame_data(self, blame_data_list: list):
        # 如果在编辑模式下，无法显示blame信息
        if not self.isReadOnly():
            logging.warning("当前处于编辑模式，无法显示blame信息")
            return

        self.max_blame_display_width = 0
        # Store the full data separately, ensuring original commit_hash is preserved.
        self.blame_data_full = list(blame_data_list)  # Make a copy

        processed_for_display = []
        if blame_data_list:
            for original_annotation in self.blame_data_full:
                if original_annotation:  # Ensure annotation is not None
                    # Create a copy for display purposes to avoid altering blame_data_full's dicts
                    display_annotation = dict(original_annotation)

                    commit_hash_full = display_annotation.get("commit_hash", "")
                    author_name = display_annotation.get("author_name", "Unknown Author")
                    committed_date = display_annotation.get("committed_date", "Unknown Date")

                    # Use short hash for display string
                    display_string = f"{commit_hash_full[:7]} {author_name} {committed_date}"
                    display_annotation["_display_string"] = display_string

                    calculated_width = self.fontMetrics().horizontalAdvance(display_string)
                    self.max_blame_display_width = max(self.max_blame_display_width, calculated_width)

                    processed_for_display.append(display_annotation)
                else:
                    # Handle cases where an annotation might be None in the list
                    processed_for_display.append(None)

        self.blame_annotations_per_line = processed_for_display  # This list is for display and click handling
        self.showing_blame = True
        self.update_line_number_area_width()
        self.viewport().update()

    def clear_blame_data(self):
        self.blame_annotations_per_line = []
        self.blame_data_full = []  # Also clear the full data
        self.max_blame_display_width = 0  # Reset max width when clearing blame
        self.showing_blame = False
        self.update_line_number_area_width()
        self.viewport().update()

    def show_blame(self):
        main_window = self.parent()
        while main_window and not hasattr(main_window, "git_manager"):
            main_window = main_window.parent()

        if not main_window or not hasattr(main_window, "git_manager") or not main_window.git_manager:
            logging.error("Git manager not found or accessible from SyncedTextEdit.")
            return

        git_manager = main_window.git_manager
        if not git_manager.repo:
            logging.error("Git repository not initialized in GitManager.")
            return

        file_path = self.file_path  # Changed from self.property("file_path")

        if not file_path:  # Check if file_path is None or empty
            logging.error("File path is not set in SyncedTextEdit. Cannot show blame.")
            return

        # Now that file_path is confirmed to be valid, proceed
        relative_file_path = os.path.relpath(file_path, git_manager.repo_path)
        commit_to_blame = self.current_commit_hash if self.current_commit_hash else None

        blame_data = git_manager.get_blame_data(relative_file_path, commit_to_blame)
        if blame_data:
            self.set_blame_data(blame_data)
        else:
            # Log specific to no blame data, file_path is known to be set here
            logging.error("No blame data found for %s at commit %s", relative_file_path, commit_to_blame)
            # Optionally, clear existing blame data if new data fetch fails or to indicate no data
            # self.clear_blame_data()

    def setObjectName(self, name: str) -> None:
        super().setObjectName(name)
        # 在设置对象名称后创建高亮器
        if self.highlighter is None:
            self.highlighter = DiffHighlighter(self.document(), name)
            logging.debug("创建高亮器，类型: %s", name)

    def line_number_area_width(self):
        line_digits = len(str(max(1, self.blockCount())))
        line_num_text_width = self.fontMetrics().horizontalAdvance("9" * line_digits)
        total_line_number_component_width = line_num_text_width + self.PADDING_RIGHT_OF_LINENUM

        if self.showing_blame and self.blame_annotations_per_line:
            # Ensure max_blame_display_width is available and is a number
            current_max_blame_width = getattr(self, "max_blame_display_width", 0)
            if not isinstance(current_max_blame_width, (int, float)):
                current_max_blame_width = 0

            width = (
                self.PADDING_LEFT_OF_BLAME
                + current_max_blame_width
                + self.PADDING_AFTER_BLAME
                + total_line_number_component_width
            )
        else:
            width = self.PADDING_LEFT_OF_BLAME + total_line_number_component_width

        return int(width)

    def update_line_number_area_width(self):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))

    def line_number_area_paint_event(self, event):
        """绘制行号区域"""
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor("#f0f0f0"))  # Paint background

        line_digits = len(str(max(1, self.blockCount())))
        line_num_text_width = self.fontMetrics().horizontalAdvance("9" * line_digits)

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                current_block_height = self.blockBoundingRect(block).height()

                # Line Number Drawing
                line_number_string = str(block_number + 1)
                x_start_for_linenum = (
                    self.line_number_area.width() - self.PADDING_RIGHT_OF_LINENUM - line_num_text_width
                )
                line_num_rect = QRect(
                    int(x_start_for_linenum), int(top), int(line_num_text_width), int(current_block_height)
                )
                painter.setPen(QColor("#808080"))  # Color for line numbers
                painter.drawText(
                    line_num_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, line_number_string
                )

                # Blame Annotation Drawing
                if self.showing_blame:
                    annotation_display_string = ""
                    if (
                        block_number < len(self.blame_annotations_per_line)
                        and self.blame_annotations_per_line[block_number]
                        and "_display_string" in self.blame_annotations_per_line[block_number]
                    ):
                        annotation_display_string = self.blame_annotations_per_line[block_number]["_display_string"]

                    if annotation_display_string:  # Only draw if there's something to show
                        max_width_for_blame_area = getattr(self, "max_blame_display_width", 0)
                        # Ensure max_width_for_blame_area is a number, otherwise default to 0
                        if not isinstance(max_width_for_blame_area, (int, float)):
                            max_width_for_blame_area = 0

                        blame_rect = QRect(
                            int(self.PADDING_LEFT_OF_BLAME),
                            int(top),
                            int(max_width_for_blame_area),
                            int(current_block_height),
                        )
                        painter.setPen(QColor("#333333"))  # Color for blame text
                        painter.drawText(
                            blame_rect,
                            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                            annotation_display_string,
                        )

            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self.viewport())
        pen = QPen(QColor("#666666"))
        pen.setWidth(2)
        painter.setPen(pen)

        # 获取当前视口的可见区域
        viewport_rect = self.viewport().rect()
        viewport_top = viewport_rect.top()
        viewport_bottom = viewport_rect.bottom()

        # 遍历所有差异块
        if not self.highlighter or not hasattr(self.highlighter, "diff_chunks"):
            return
        for chunk in self.highlighter.diff_chunks:
            if chunk.type == "delete" and (
                (chunk.right_start == chunk.right_end and self.objectName() == "right_edit")
                or (chunk.left_start == chunk.left_end and self.objectName() == "left_edit")
            ):
                pos = (chunk.left_start if chunk.left_start == chunk.left_end else chunk.right_start) - 1
                block = self.document().findBlockByLineNumber(pos)
                if block.isValid():
                    # 获取这一行的几何信息
                    block_geometry = self.blockBoundingGeometry(block)
                    block_rect = block_geometry.translated(self.contentOffset())
                    block_top = block_rect.top()
                    block_bottom = block_rect.bottom()

                    # 只绘制在可见区域内的行
                    if block_bottom >= viewport_top and block_top <= viewport_bottom:
                        painter.drawLine(
                            0,
                            int(block_bottom),
                            self.viewport().width(),
                            int(block_bottom),
                        )
                        logging.debug(
                            "%s 删除块: %s - %s %s",
                            self.objectName(),
                            chunk.right_start,
                            chunk.right_end,
                            chunk,
                        )


# <new_class>
# 还不是特别完善，特别是针对修改的行
class ModifiedTextEdit(SyncedTextEdit):
    """继承自SyncedTextEdit，支持在行号旁显示行修改状态"""

    LINE_STATUS_COLORS = {
        "added": QColor("#4CAF50"),  # 绿色表示新增
        "modified": QColor("#FFC107"),  # 黄色表示修改
        "deleted": QColor("#F44336"),  # 红色表示删除
    }
    MODIFICATION_MARK_WIDTH = 10  # 修改标记的宽度
    MODIFICATION_MARK_SIZE = 6  # 标记直径大小

    def __init__(self, parent=None):
        super().__init__(parent)
        self.line_modifications = {}  # 存储每行的修改状态
        # 确保行号区域宽度计算包含修改标记
        self.update_line_number_area_width()

    def set_line_modifications(self, modifications: dict):
        """设置每行的修改状态

        Args:
            modifications: 包含每行修改状态的列表，元素可以是:
                "added" - 新增行
                "modified" - 修改行
                "deleted" - 删除行
                None - 未修改
        """
        self.line_modifications = modifications
        self.update_line_number_area_width()
        self.line_number_area.update()

    def line_number_area_width(self):
        """重写行号区域宽度计算方法，包含修改标记空间"""
        base_width = super().line_number_area_width()
        return base_width + self.MODIFICATION_MARK_WIDTH

    def line_number_area_paint_event(self, event):
        """重写行号区域绘制事件，新增修改标记处理"""
        # 首先调用父类绘制基础的背景、行号和blame注释
        super().line_number_area_paint_event(event)

        # 如果没有修改标记，直接返回
        if not self.line_modifications:
            return

        painter = QPainter(self.line_number_area)

        # 计算修改标记的位置 (在行号的左侧)
        line_digits = len(str(max(1, self.blockCount())))
        line_num_text_width = self.fontMetrics().horizontalAdvance("9" * line_digits)
        modification_mark_x = int(
            self.line_number_area.width()
            - line_num_text_width
            - self.PADDING_RIGHT_OF_LINENUM
            - self.MODIFICATION_MARK_WIDTH
            + 2  # 左边距
        )

        # 遍历所有可见块绘制修改标记
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                current_block_height = self.blockBoundingRect(block).height()
                block_line_number = block_number + 1

                # 绘制修改状态标记
                mod_status = self.line_modifications.get(block_line_number)
                if mod_status and mod_status in self.LINE_STATUS_COLORS:
                    color = self.LINE_STATUS_COLORS[mod_status]
                    painter.setBrush(color)
                    painter.setPen(Qt.PenStyle.NoPen)

                    # 计算标记的垂直中心位置
                    mark_y = int(top + (current_block_height - self.MODIFICATION_MARK_SIZE) / 2)

                    # 绘制圆点表示修改状态
                    mark_rect = QRect(
                        modification_mark_x, mark_y, self.MODIFICATION_MARK_SIZE, self.MODIFICATION_MARK_SIZE
                    )
                    painter.drawEllipse(mark_rect)

            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1


# </new_class>
