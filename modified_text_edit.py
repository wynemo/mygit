import typing

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QSizePolicy, QWidget

from text_edit import SyncedTextEdit


# <new_class>
# Not yet perfect, especially for modified lines
class ModifiedTextEdit(SyncedTextEdit):
    """Inherits from SyncedTextEdit, supports displaying line modification status next to line numbers"""

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
        self.overview_bar = OverViewBar(self, parent=self)
        self.overview_bar.setParent(self)
        self._update_overview_bar_geometry()
        self.verticalScrollBar().valueChanged.connect(self.overview_bar.update_overview)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_overview_bar_geometry()

    def _update_overview_bar_geometry(self):
        # Place the overview bar at the right edge of the widget, overlapping the scrollbar area
        if hasattr(self, "viewport"):
            viewport = self.viewport()
            bar_width = self.overview_bar.BAR_WIDTH
            # Move the bar到widget最右侧，和滚动条重叠
            x = self.width() - bar_width  # self.width() 包含滚动条宽度
            # self.overview_bar.setGeometry(x, 0, bar_width, viewport.height())
            self.overview_bar.setGeometry(
                viewport.width() + self.line_number_area_width() - bar_width, 0, bar_width, viewport.height()
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
                        print(f"mod_status: {mod_status}, color: {color}", block_line_number)
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
