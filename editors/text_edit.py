import logging
import os
from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import QRect, QSize, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QContextMenuEvent,
    QFont,
    QKeyEvent,  # Added QKeyEvent
    QMouseEvent,
    QPainter,
    QPen,
    QTextCursor,
    QTextDocument,
)
from PyQt6.QtWidgets import (
    QApplication,
    QMenu,
    QMessageBox,  # Added for save confirmation
    QPlainTextEdit,
    QTextEdit,  # Added QTextEdit
    QToolTip,
    QWidget,
)

from diff_highlighter import DiffHighlighter
from find_dialog import FindDialog
from settings import BLAME_COLOR_PALETTE, Settings

if TYPE_CHECKING:
    from git_manager import GitManager


class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        self.setMouseTracking(True)  # 启用鼠标跟踪以支持悬停事件

    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.editor.line_number_area_paint_event(event)

    def contextMenuEvent(self, event: QContextMenuEvent):
        """Handle right-click context menu event for line number area"""
        menu = QMenu(self)
        copy_action = menu.addAction("Copy Revision Number")
        copy_action.triggered.connect(lambda: self.copy_revision_number(event.pos()))
        menu.exec(event.globalPos())

    def copy_revision_number(self, pos):
        """Copy commit hash of the line at given position to clipboard"""
        y_pos = pos.y()
        block = self.editor.firstVisibleBlock()
        block_number = block.blockNumber()
        block_top = self.editor.blockBoundingGeometry(block).translated(self.editor.contentOffset()).top()
        block_height = self.editor.blockBoundingRect(block).height()

        if block_height == 0:
            return

        line_index = block_number + int((y_pos - block_top) / block_height)

        if 0 <= line_index < len(self.editor.blame_annotations_per_line):
            annotation = self.editor.blame_annotations_per_line[line_index]
            if annotation and "commit_hash" in annotation:
                # get clipboard pyqt6
                clipboard = QApplication.clipboard()
                clipboard.setText(annotation["commit_hash"])

    def mouseMoveEvent(self, event: QMouseEvent):
        """处理鼠标移动事件，显示 blame 信息的工具提示"""
        if self.editor.showing_blame and self.editor.blame_annotations_per_line:
            # 检查鼠标是否在 blame 注释区域内
            blame_area_width = self.editor.PADDING_LEFT_OF_BLAME + getattr(self.editor, "max_blame_display_width", 0)
            if event.pos().x() < blame_area_width:
                # 获取鼠标所在行号
                y_pos = event.pos().y()
                block = self.editor.firstVisibleBlock()
                block_number = block.blockNumber()
                block_top = self.editor.blockBoundingGeometry(block).translated(self.editor.contentOffset()).top()
                block_height = self.editor.blockBoundingRect(block).height()

                if block_height > 0:  # 避免除以零
                    line_index = block_number + int((y_pos - block_top) / block_height)

                    # 获取该行的 blame 数据
                    if 0 <= line_index < len(self.editor.blame_annotations_per_line):
                        annotation = self.editor.blame_annotations_per_line[line_index]
                        if annotation and "commit_hash" in annotation:
                            # 从 blame_data_full 获取完整数据
                            if line_index < len(self.editor.blame_data_full):
                                full_data = self.editor.blame_data_full[line_index]
                                # 格式化工具提示文本
                                tooltip_text = (
                                    f"commit {full_data['commit_hash']}\n"
                                    f"Author: {full_data['author_name']}\n"
                                    f"Date: {full_data['committed_date']}\n\n"
                                    f"{full_data.get('summary', 'No commit message')}"
                                )
                                QToolTip.showText(event.globalPosition().toPoint(), tooltip_text)
                                return
            # 鼠标不在 blame 区域或没有数据时隐藏工具提示
            QToolTip.hideText()

        super().mouseMoveEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        # 如果是左键点击，定位到对应的 commit
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.editor.showing_blame
            and self.editor.blame_annotations_per_line
        ):
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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighted_line_number = -1

        # Initialize blame color palette and commit hash color store
        self.blame_color_palette = BLAME_COLOR_PALETTE
        self.assigned_commit_base_colors = {}
        self.line_final_color_indices = []
        # self.commit_hash_colors removed

        settings = Settings()
        self.setFont(QFont(settings.get_font_family(), settings.get_font_size()))
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setReadOnly(True)  # 默认设置为只读
        self.original_content = ""  # 保存原始内容，用于取消编辑时恢复
        logging.debug("\n=== 初始化 SyncedTextEdit ===")
        logging.debug("默认只读模式：%s", self.isReadOnly())

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

        # 初始化差异信息
        self.highlighter = None

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.find_dialog_instance = None  # Initialize find_dialog_instance
        self.search_highlights = []  # Initialize search_highlights

    # get_blame_color method removed

    def set_highlighted_line(self, line_number: int):
        """Sets the line number to be highlighted in the line number area."""
        # Convert to 0-indexed if it's not already clear from usage context
        # Assuming line_number is passed as 0-indexed from DiffViewer
        self.highlighted_line_number = line_number
        if hasattr(self, "line_number_area") and self.line_number_area:
            self.line_number_area.update()

    def clear_highlighted_line(self):
        """Clears any highlighted line number."""
        self.highlighted_line_number = -1
        if hasattr(self, "line_number_area") and self.line_number_area:
            self.line_number_area.update()

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
        # 全选快捷键 (Ctrl+A 或 Cmd+A)
        elif event.key() == Qt.Key.Key_A and (
            event.modifiers() == Qt.KeyboardModifier.ControlModifier
            or event.modifiers() == Qt.KeyboardModifier.MetaModifier
        ):
            self.select_all_text()
            event.accept()
        # 复制快捷键 (Ctrl+C 或 Cmd+C)
        elif event.key() == Qt.Key.Key_C and (
            event.modifiers() == Qt.KeyboardModifier.ControlModifier
            or event.modifiers() == Qt.KeyboardModifier.MetaModifier
        ):
            self.copy_text()
            event.accept()
        # 粘贴快捷键 (Ctrl+V 或 Cmd+V)
        elif event.key() == Qt.Key.Key_V and (
            event.modifiers() == Qt.KeyboardModifier.ControlModifier
            or event.modifiers() == Qt.KeyboardModifier.MetaModifier
        ):
            if not self.isReadOnly():
                self.paste_text()
                event.accept()
            else:
                super().keyPressEvent(event)  # Allow paste to work in read-only mode if underlying widget supports it
        else:
            super().keyPressEvent(event)  # Call base class implementation for other keys

    def find_text(self, search_text: str, direction: str = "next", case_sensitive: bool = False) -> bool:
        """Finds text in the editor and highlights it if found, with wrap-around functionality."""
        # Clear previous highlights
        self.search_highlights.clear()
        self.setExtraSelections([])

        flags = QTextDocument.FindFlag(0)
        if direction == "previous":
            flags |= QTextDocument.FindFlag.FindBackward
        if case_sensitive:
            flags |= QTextDocument.FindFlag.FindCaseSensitively

        # 第一次查找
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
            return True

        logging.info(f"'{search_text}' not found in {self.objectName()} at initial position. Attempting wrap-around.")

        # 未找到匹配项，尝试换行查找
        cursor = self.textCursor()
        if direction == "next":
            # 如果向下查找未找到，移动到开头再次查找
            cursor.movePosition(QTextCursor.MoveOperation.Start)
        else:  # direction == "previous"
            # 如果向上查找未找到，移动到结尾再次查找
            cursor.movePosition(QTextCursor.MoveOperation.End)

        self.setTextCursor(cursor)
        found_after_wrap = super().find(search_text, flags)

        if found_after_wrap:
            logging.info(f"Found '{search_text}' after wrap-around in {self.objectName()}")
            self.ensureCursorVisible()
            selection = QTextEdit.ExtraSelection()
            selection.cursor = self.textCursor()
            selection.format.setBackground(QColor("#ADD8E6"))
            self.search_highlights.append(selection)
            self.setExtraSelections(self.search_highlights)
            return True

        # 完全未找到
        logging.info(f"'{search_text}' not found anywhere in {self.objectName()}.")
        return False

    def clear_search_highlights(self):
        """Clears all search-related highlights from the editor."""
        self.search_highlights.clear()
        self.setExtraSelections([])
        logging.debug(f"Search highlights cleared for {self.objectName()}")

    def scroll_to_line(self, line_number: int):
        """Scrolls the text edit to make the specified line number (0-indexed) appear at the top."""
        document = self.document()
        if 0 <= line_number < document.blockCount():
            block = document.findBlockByNumber(line_number)
            if block.isValid():
                cursor = QTextCursor(block)
                self.setTextCursor(cursor)  # Place the cursor at the start of the block

                # Scroll to make this cursor appear at the top of the viewport
                # Get the rectangle of the cursor in viewport coordinates
                cursor_rect_in_viewport = self.cursorRect(cursor)
                # Get the current value of the vertical scrollbar (document Y-coordinate at the top of viewport)
                current_scroll_bar_value = self.verticalScrollBar().value()

                # Calculate the new scrollbar value.
                # new_scroll_bar_value is the document Y-coordinate that should be at the top of the viewport
                # to make the current cursor_rect_in_viewport.top() become 0.
                new_scroll_bar_value = current_scroll_bar_value + cursor_rect_in_viewport.top()

                self.verticalScrollBar().setValue(new_scroll_bar_value)

                # Call ensureCursorVisible as a safeguard, especially for lines taller than the viewport
                # or to ensure the cursor has focus.
                self.ensureCursorVisible()

                logging.info(
                    f"Scrolled {self.objectName()} to bring line {line_number + 1} (0-indexed: {line_number}) to the top. "
                    f"Cursor viewport top: {cursor_rect_in_viewport.top()}, Current scroll val: {current_scroll_bar_value}, New scroll val: {new_scroll_bar_value}"
                )
            else:
                logging.warning(f"Block for line {line_number} (0-indexed) not found in {self.objectName()}.")
        else:
            logging.warning(
                f"Invalid line number {line_number} (0-indexed) for {self.objectName()}. Total lines: {document.blockCount()}"
            )

    def show_context_menu(self, position):
        menu = QMenu(self)

        select_all_action = menu.addAction("Select All")
        select_all_action.triggered.connect(self.select_all_text)

        copy_action = menu.addAction("Copy")
        copy_action.triggered.connect(self.copy_text)

        paste_action = menu.addAction("Paste")
        paste_action.triggered.connect(self.paste_text)
        if self.isReadOnly():
            paste_action.setEnabled(False)

        menu.addSeparator()

        # if self.isReadOnly() or not self.blame_annotations_per_line:
        blame_action = menu.addAction("Show Blame")
        blame_action.triggered.connect(self.show_blame)
        clear_blame_action = menu.addAction("Clear Blame")
        clear_blame_action.triggered.connect(self.clear_blame_data)

        # Fix for menu position when blame info is shown
        # Convert position from viewport coordinates to global coordinates
        global_pos = self.viewport().mapToGlobal(position)
        menu.exec(global_pos)

    # Renamed from _show_context_menu to show_context_menu for consistency
    # No other change in this method, just ensuring the diff picks up the rename if any confusion.

    def select_all_text(self):
        # Placeholder for select all functionality
        logging.debug("Select All action triggered")
        self.selectAll()

    def copy_text(self):
        # Placeholder for copy functionality
        logging.debug("Copy action triggered")
        self.copy()

    def paste_text(self):
        # Placeholder for paste functionality
        logging.debug("Paste action triggered")
        self.paste()

    def set_editable(self):
        """将文本编辑设置为可编辑模式并保存原始内容"""
        if self.isReadOnly():
            self.edit_mode = True
            # 保存原始内容
            self.original_content = self.toPlainText()
            self.setReadOnly(False)
            logging.info("进入编辑模式，文件路径：%s", self.file_path)
            self.viewport().setCursor(Qt.CursorShape.IBeamCursor)  # 显示可编辑光标

    def save_content(self):
        """保存更改到文件"""
        if self.isReadOnly() or not self.file_path:
            return

        try:
            current_content = self.toPlainText()

            with open(self.file_path, "w", encoding="utf-8") as f:
                f.write(current_content)

            logging.info("文件保存成功：%s", self.file_path)
            self.original_content = current_content

            self.viewport().setCursor(Qt.CursorShape.ArrowCursor)  # 恢复箭头光标

        except Exception as e:
            logging.error("文件保存失败：%s", str(e))
            QMessageBox.critical(self, "保存错误", f"无法保存文件：{e!s}", QMessageBox.StandardButton.Ok)

    def set_blame_data(self, blame_data_list: list):
        self.assigned_commit_base_colors = {}
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
        # self.commit_hash_colors removed

        # Clear and prepare for pre-calculating line colors
        self.line_final_color_indices = []
        # self.assigned_commit_base_colors is already initialized above - good.

        num_colors = len(self.blame_color_palette)
        loop_previous_hash = None
        loop_previous_color_index = -1

        for line_idx in range(len(self.blame_annotations_per_line)):
            annotation_data = self.blame_annotations_per_line[line_idx]
            current_commit_hash = None
            final_color_index_for_line = -1  # Default for lines with no blame or if coloring fails

            if annotation_data and isinstance(annotation_data, dict):  # Ensure annotation_data is a dict
                current_commit_hash = annotation_data.get("commit_hash")

            if num_colors > 0 and current_commit_hash:
                # 1. Determine base color for the current hash
                current_hash_base_color_index = self.assigned_commit_base_colors.get(current_commit_hash)
                if current_hash_base_color_index is None:
                    current_hash_base_color_index = abs(hash(current_commit_hash)) % num_colors
                    self.assigned_commit_base_colors[current_commit_hash] = current_hash_base_color_index

                calculated_color_index = current_hash_base_color_index

                # 2. Adjacency Rule for Different Hashes
                if (
                    loop_previous_hash
                    and current_commit_hash != loop_previous_hash
                    and calculated_color_index == loop_previous_color_index
                ):
                    for i in range(1, num_colors):
                        candidate_color_index = (calculated_color_index + i) % num_colors
                        if candidate_color_index != loop_previous_color_index:
                            calculated_color_index = candidate_color_index
                            break

                # 3. Consistency Rule for Same Hashes
                elif (
                    loop_previous_hash and current_commit_hash == loop_previous_hash and loop_previous_color_index != -1
                ):
                    calculated_color_index = loop_previous_color_index

                final_color_index_for_line = calculated_color_index

                # Update trackers for the next iteration of this loop
                loop_previous_hash = current_commit_hash
                loop_previous_color_index = final_color_index_for_line
            else:
                # Line has no blame data, or no hash, or no colors defined. Reset for next valid line.
                loop_previous_hash = None
                loop_previous_color_index = -1

            self.line_final_color_indices.append(final_color_index_for_line)

        # Ensure viewport updates after colors are calculated, if not already done by subsequent calls.
        # The existing self.viewport().update() at the end of the original set_blame_data might be sufficient.
        self.update_line_number_area_width()
        self.viewport().update()

    def clear_blame_data(self):
        self.blame_annotations_per_line = []
        self.blame_data_full = []  # Also clear the full data
        self.max_blame_display_width = 0  # Reset max width when clearing blame
        self.showing_blame = False
        self.assigned_commit_base_colors = {}
        self.line_final_color_indices = []
        # self.commit_hash_colors removed
        self.update_line_number_area_width()
        self.viewport().update()

    def show_blame(self):
        main_window = self.parent()
        while main_window and not hasattr(main_window, "git_manager"):
            main_window = main_window.parent()

        if not main_window or not hasattr(main_window, "git_manager") or not main_window.git_manager:
            logging.error("Git manager not found or accessible from SyncedTextEdit.")
            return

        git_manager: "GitManager" = main_window.git_manager
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
            logging.debug("创建高亮器，类型：%s", name)

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

        # previous_blamed_commit_hash and previous_drawn_color_index removed as color calculation is now pre-done.

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

                # Highlight background for the current line number if it's the highlighted one
                if block_number == self.highlighted_line_number:
                    highlight_color = QColor(Qt.GlobalColor.yellow).lighter(120)  # A light yellow
                    # Define the rectangle for the line number highlight more precisely
                    # It should cover the area for this specific line number.
                    # line_num_rect is already calculated for drawing text, so we can reuse its geometry.
                    painter.fillRect(line_num_rect, highlight_color)

                # Line Number Drawing (existing code)
                line_number_string = str(block_number + 1)
                # x_start_for_linenum and line_num_text_width are defined above
                painter.setPen(QColor("#808080"))  # Color for line numbers
                painter.drawText(
                    line_num_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, line_number_string
                )

                # Blame Annotation Drawing
                if self.showing_blame:
                    annotation_data = None
                    if block_number < len(self.blame_annotations_per_line):
                        annotation_data = self.blame_annotations_per_line[block_number]

                    # Default color for the blame rectangle background
                    blame_qcolor = QColor(Qt.GlobalColor.lightGray)  # Or your desired default/non-blamed line color

                    if annotation_data and isinstance(annotation_data, dict) and "_display_string" in annotation_data:
                        # Retrieve the pre-calculated color index for this line
                        # An index of -1 (or other chosen default) means "no specific blame color"
                        color_idx_for_line = -1
                        if block_number < len(self.line_final_color_indices):
                            color_idx_for_line = self.line_final_color_indices[block_number]

                        if color_idx_for_line != -1 and 0 <= color_idx_for_line < len(self.blame_color_palette):
                            blame_qcolor = self.blame_color_palette[color_idx_for_line]
                        # else: line will use the default blame_qcolor (e.g., lightGray or transparent)

                        # The rest of the drawing logic for the annotation text and rectangle fill remains
                        annotation_display_string = annotation_data["_display_string"]
                        max_width_for_blame_area = getattr(self, "max_blame_display_width", 0)
                        if not isinstance(max_width_for_blame_area, (int, float)):
                            max_width_for_blame_area = 0

                        blame_text_rect = QRect(
                            int(self.PADDING_LEFT_OF_BLAME),
                            int(top),
                            int(max_width_for_blame_area),
                            int(current_block_height),
                        )

                        blame_fill_rect = QRect(
                            0,
                            int(top),
                            int(self.PADDING_LEFT_OF_BLAME + max_width_for_blame_area + self.PADDING_AFTER_BLAME),
                            int(current_block_height),
                        )
                        painter.fillRect(blame_fill_rect, blame_qcolor)

                        painter.setPen(QColor("#333333"))  # Color for annotation text
                        painter.drawText(
                            blame_text_rect,
                            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                            annotation_display_string,
                        )
                    # The 'else' case for 'if annotation_data and ...' (where no valid annotation for this line)
                    # implicitly means the default background of the line number area will show,
                    # or if you want a specific fill for non-annotated lines within the blame area,
                    # that could be added here. For now, it will just not draw a specific blame colored box.

                    # Note: The old 'else' that reset previous_blamed_commit_hash and previous_drawn_color_index
                    # is no longer needed here because these variables are entirely removed from this method's scope
                    # for color calculation.

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
                            "%s 删除块：%s - %s %s",
                            self.objectName(),
                            chunk.right_start,
                            chunk.right_end,
                            chunk,
                        )
