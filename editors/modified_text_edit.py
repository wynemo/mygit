import logging
import os
import typing

from PyQt6.QtCore import Qt, pyqtSignal  # 引入 pyqtSignal
from PyQt6.QtGui import QColor, QFocusEvent, QPainter, QPen
from PyQt6.QtWidgets import QSizePolicy, QWidget

from diff_calculator import DifflibCalculator
from editors.text_edit import SyncedTextEdit

if typing.TYPE_CHECKING:
    from git_manager import GitManager


# <new_class>
# 普通编辑器 主要专注于修改的文字部分
class ModifiedTextEdit(SyncedTextEdit):
    """Inherits from SyncedTextEdit, supports displaying line modification status next to line numbers"""

    # 文件脏状态改变信号 (文件路径，是否变脏)
    dirty_status_changed = pyqtSignal(str, bool)

    LINE_STATUS_COLORS: typing.ClassVar[dict] = {
        "added": QColor("#4CAF50"),  # green for added
        "modified": QColor("#FFC107"),  # yellow for modified
        "deleted": QColor("#F44336"),  # red for deleted
    }
    MODIFICATION_MARK_WIDTH: typing.ClassVar[int] = 10
    MODIFICATION_MARK_SIZE: typing.ClassVar[int] = 6

    def __init__(self, parent=None):
        super().__init__(parent)
        self.line_modifications = {}  # Store modification status for each line
        self.overview_bar = OverViewBar(self, parent=self)  # 绘制在最右边
        self.overview_bar.setParent(self)
        # 连接文档内容修改信号
        self.document().modificationChanged.connect(self._on_modification_changed)
        self._update_overview_bar_geometry()
        self.verticalScrollBar().valueChanged.connect(self.overview_bar.update_overview)

        # 设置滚动条为半透明 这样 overview_bar 能与滚动条绘制在一起
        # 但样式不是很好看 以后看看怎么弄
        scrollbar = self.verticalScrollBar()
        scrollbar.setStyleSheet("""
QPlainTextEdit QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 0px 0px 0px 0px;
}
QPlainTextEdit QScrollBar::handle:vertical {
    background: rgba(0, 0, 0, 100);  /* 半透明黑色 */
    min-height: 20px;
    border-radius: 5px;
}
QPlainTextEdit QScrollBar::add-page:vertical,
QPlainTextEdit QScrollBar::sub-page:vertical {
    background: transparent;
}
QPlainTextEdit QScrollBar::add-line:vertical,
QPlainTextEdit QScrollBar::sub-line:vertical {
    height: 0px;
}
QPlainTextEdit QScrollBar::up-arrow:vertical,
QPlainTextEdit QScrollBar::down-arrow:vertical {
    background: none;
    height: 0px;
    width: 0px;
}
QPlainTextEdit QScrollBar::handle:vertical:hover {
    background: rgba(0, 0, 0, 140);
}
QPlainTextEdit QScrollBar::handle:vertical:pressed {
    background: rgba(0, 0, 0, 180);
}
        """)

    def focusInEvent(self, event: QFocusEvent):
        """Handle the event when the widget gains focus."""
        super().focusInEvent(event)
        if self.document().isModified():
            logging.debug("文档有未保存的修改，不刷新")
            return

        # 高亮文件树中的对应文件
        parent = self.parent()
        while parent and not hasattr(parent, "file_tree"):
            parent = parent.parent()
        if parent and hasattr(parent, "file_tree"):
            logging.debug("in focusInEvent highlight_file_item: %s", self.file_path)
            parent.file_tree.highlight_file_item(self.file_path)

        current_content = self.toPlainText()
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                new_content = f.read()
        except Exception:
            logging.exception("Error reading file")
            return

        # 仅当文件实际内容与编辑器当前内容不同时才更新文本，以避免不必要的刷新和光标位置丢失
        if new_content != current_content:
            scrollbar = self.verticalScrollBar()
            # 保存当前滚动条的位置，以便在刷新内容后恢复
            stored_value = scrollbar.value()
            # 设置 document 的文本
            self.setPlainText(new_content)
            # 恢复滚动条位置，避免不必要的滚动到顶部
            scrollbar.setValue(stored_value)

        parent = self.parent()
        while parent and not hasattr(parent, "git_manager"):  # Check parent exists
            parent = parent.parent()
        if parent and hasattr(parent, "git_manager"):
            # todo should check if it's under git version
            # 获取仓库路径
            diffs = self.get_diffs(parent.git_manager, self.toPlainText())
            # print(f"focusInEvent diffs: {diffs}") # TODO remove this print
            self.set_line_modifications(diffs)

    # <new_method>
    # 当文档内容修改状态改变时调用
    def _on_modification_changed(self, modified: bool):
        """当文档内容修改状态改变时调用，发出 dirty_status_changed 信号。"""
        if self.file_path:
            self.dirty_status_changed.emit(self.file_path, modified)
            logging.debug("Emitted dirty_status_changed for %s: %s", self.file_path, modified)

    # </new_method>

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_overview_bar_geometry()

    def _update_overview_bar_geometry(self):
        # Place the overview bar at the right edge of the widget, overlapping the scrollbar area
        if hasattr(self, "viewport"):
            viewport = self.viewport()
            bar_width = self.overview_bar.BAR_WIDTH
            self.overview_bar.setGeometry(
                viewport.width() + self.line_number_area_width(), 0, bar_width, viewport.height()
            )
            self.overview_bar.raise_()

    def set_line_modifications(self, modifications: dict):
        self.line_modifications = modifications
        self.update_line_number_area_width()
        self.line_number_area.update()
        self.overview_bar.update_overview()

    def line_number_area_width(self):
        """Reimplement the line number area width calculation method, including modification mark space"""
        base_width = super().line_number_area_width()
        return base_width + self.MODIFICATION_MARK_WIDTH

    def line_number_area_paint_event(self, event):
        """Reimplement the line number area paint event, add modification mark handling"""
        # First, call the parent class to draw the basic background, line numbers, and blame comments
        super().line_number_area_paint_event(event)

        # If there are no modification marks, return directly
        if not self.line_modifications:
            return

        painter = QPainter(self.line_number_area)

        # Calculate the position of the modification mark (to the left of the line number)
        line_digits = len(str(max(1, self.blockCount())))
        line_num_text_width = self.fontMetrics().horizontalAdvance("9" * line_digits)
        modification_mark_x = int(
            self.line_number_area.width()
            - line_num_text_width
            - self.PADDING_RIGHT_OF_LINENUM
            - self.MODIFICATION_MARK_WIDTH
            + 2  # left margin
        )

        # Traverse all visible blocks to draw modification marks
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                current_block_height = self.blockBoundingRect(block).height()
                block_line_number = block_number + 1

                # Draw modification status mark
                mod_status = self.line_modifications.get(block_line_number)
                if mod_status:  # Process only when there is a status
                    color = self.LINE_STATUS_COLORS.get(mod_status)
                    if color:  # Ensure the color exists
                        # logging.debug(
                        #     "block_line_number %d, mod_status: %s, color: %s", block_line_number, mod_status, color
                        # )
                        painter.setBrush(color)
                        painter.setPen(Qt.PenStyle.NoPen)

                        # Calculate the vertical center position of the mark
                        mark_y = int(top + (current_block_height - self.MODIFICATION_MARK_SIZE) / 2)

                        if mod_status == "deleted":
                            last_mod_status = self.line_modifications.get(block_line_number - 1)
                            if not last_mod_status or not last_mod_status == "deleted":
                                # Draw a red dot to indicate deletion
                                # Calculate the x position of the circle center (in the center of the mark area)
                                dot_center_x = modification_mark_x + self.MODIFICATION_MARK_SIZE // 2
                                # Draw the dot
                                painter.drawEllipse(
                                    int(dot_center_x - self.MODIFICATION_MARK_SIZE / 2),
                                    int(top),
                                    int(self.MODIFICATION_MARK_SIZE),
                                    int(self.MODIFICATION_MARK_SIZE),
                                )
                        elif mod_status in ("added", "modified"):
                            # Draw a vertical line to indicate addition or modification
                            # Set the pen for drawing the line
                            painter.setPen(QPen(color, 2))  # Set the line width to 2 pixels
                            # Calculate the x position of the vertical line (in the center of the mark area)
                            line_x = modification_mark_x + self.MODIFICATION_MARK_SIZE // 2
                            # Draw the line, from the top to the bottom of the current line
                            # Ensure the coordinate values are integers
                            painter.drawLine(int(line_x), int(top), int(line_x), int(top + current_block_height))

            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1

    def save_content(self):
        super().save_content()
        # 文件已保存，状态变为未修改
        if self.file_path:  # Ensure file_path is set
            self.dirty_status_changed.emit(self.file_path, False)
            logging.debug("Emitted dirty_status_changed for %s (saved): False", self.file_path)
        self.document().setModified(False)
        parent = self.parent()
        while parent and not hasattr(parent, "git_manager"):  # Check parent exists
            parent = parent.parent()
        if parent and hasattr(parent, "git_manager"):
            # todo should check if it's under git version
            # 获取仓库路径
            diffs = self.get_diffs(parent.git_manager)
            # print(f"diffs: {diffs}") # TODO remove this print
            self.set_line_modifications(diffs)
        else:
            # print("cant get git manager") # TODO remove this print
            pass  # No git manager found, nothing to do for diffs

    def get_diffs(self, git_manager: "GitManager", new_content: str | None = None) -> dict:
        repo_path = git_manager.repo.working_dir
        relative_path = os.path.relpath(self.file_path, repo_path)
        repo = git_manager.repo
        is_untracked = relative_path in repo.untracked_files
        if is_untracked:
            diffs = {}
        else:
            try:
                old_content = repo.git.show(f":{relative_path}")  # 暂存区内容
            except Exception:
                old_content = ""
                logging.exception("Error getting old content")
            if new_content is None:
                try:
                    with open(self.file_path, "r", encoding="utf-8") as f:
                        new_content = f.read()
                except Exception:
                    logging.exception("Error reading file")
                    new_content = "Error reading file"

            # 编辑器可能会在文件末尾添加一个多余的换行符
            # 如果新内容只是旧内容加上一个换行符，我们视它们为相同，以避免误报
            if new_content == old_content + "\n":
                new_content = old_content

            diffs = DifflibCalculator().get_diff(old_content, new_content)
        return diffs


class OverViewBar(QWidget):
    """Overview bar widget for showing file modification summary on the right side of the editor."""

    BAR_WIDTH: typing.ClassVar[int] = 10
    LINE_MARK_WIDTH: typing.ClassVar[int] = 6
    LINE_MARK_COLOR: typing.ClassVar[dict] = {
        "added": QColor("#4CAF50"),
        "modified": QColor("#FFC107"),
        "deleted": QColor("#F44336"),
    }

    def __init__(self, text_edit: "ModifiedTextEdit", parent=None):
        super().__init__(parent)
        self.text_edit = text_edit
        self.setFixedWidth(self.BAR_WIDTH)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

    def paintEvent(self, event):
        painter = QPainter(self)
        modifications = self.text_edit.line_modifications
        total_lines = max(1, self.text_edit.blockCount())
        height = self.height()
        for line_num, status in modifications.items():
            if status not in self.LINE_MARK_COLOR:
                continue
            y = int((line_num - 1) / total_lines * height)
            color = self.LINE_MARK_COLOR[status]
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRect(
                (self.BAR_WIDTH - self.LINE_MARK_WIDTH) // 2, y, self.LINE_MARK_WIDTH, max(3, int(height / total_lines))
            )

    def update_overview(self):
        self.update()
