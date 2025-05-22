import logging

from PyQt6.QtCore import QRect, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QPlainTextEdit, QWidget

from diff_highlighter import DiffHighlighter
from settings import Settings


class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.editor.line_number_area_paint_event(event)


class SyncedTextEdit(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        settings = Settings()
        self.setFont(QFont(settings.get_font_family(), 10))
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setReadOnly(True)  # 设置为只读
        logging.debug("\n=== 初始化SyncedTextEdit ===")
        logging.debug("只读模式: %s", self.isReadOnly())

        # Blame data storage
        self.blame_data_full = []
        self.blame_annotations_per_line = []
        self.showing_blame = False
        self.file_path = None  # Initialize file_path, can be set externally

        # 添加行号区域
        self.line_number_area = LineNumberArea(self)
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.update_line_number_area_width()

        # 初始化差异信息
        self.highlighter = None

    def setObjectName(self, name: str) -> None:
        super().setObjectName(name)
        # 在设置对象名称后创建高亮器
        if self.highlighter is None:
            self.highlighter = DiffHighlighter(self.document(), name)
            logging.debug("创建高亮器，类型: %s", name)

    def line_number_area_width(self):
        digits = len(str(max(1, self.blockCount())))
        base_space = 3 + self.fontMetrics().horizontalAdvance("9") * digits

        if self.showing_blame:
            # Estimate width for blame annotations. This is a rough estimate.
            # A more accurate way would be to calculate max width of current annotations.
            # For now, let's assume an average annotation string length.
            # Example: "abcdef0 Author 2023-01-01"
            # This needs to be adjusted based on actual formatting and font.
            # Let's use a fixed addition or calculate from self.blame_annotations_per_line
            max_blame_width = 0
            if self.blame_annotations_per_line:
                for annotation in self.blame_annotations_per_line:
                    if annotation:  # Check if annotation is not None or empty
                        max_blame_width = max(
                            max_blame_width,
                            self.fontMetrics().horizontalAdvance(
                                annotation["author_name"]
                            ),
                        )
            # Add some padding if blame is shown
            blame_space = max_blame_width + 15 if max_blame_width > 0 else 0
            base_space += blame_space

        return base_space

    def update_line_number_area_width(self):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(
                0, rect.y(), self.line_number_area.width(), rect.height()
            )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(
            QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height())
        )

    def line_number_area_paint_event(self, event):
        """绘制行号区域"""
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor("#f0f0f0"))

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                display_string = ""
                if self.showing_blame:
                    if (
                        block_number < len(self.blame_annotations_per_line)
                        and self.blame_annotations_per_line[block_number]
                    ):
                        display_string = self.blame_annotations_per_line[block_number][
                            "author_name"
                        ]
                    else:
                        # Fallback if blame data is missing for this line (should ideally not happen for tracked lines)
                        display_string = " " * 20  # Placeholder for alignment
                    display_string += " | "  # Separator

                display_string += str(block_number + 1)  # Line number

                painter.setPen(QColor("#808080"))
                painter.drawText(
                    0,
                    int(top),
                    self.line_number_area.width() - 5,  # Adjust padding
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight,  # Line numbers still right-aligned after blame info
                    display_string,
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
                (
                    chunk.right_start == chunk.right_end
                    and self.objectName() == "right_edit"
                )
                or (
                    chunk.left_start == chunk.left_end
                    and self.objectName() == "left_edit"
                )
            ):
                pos = (
                    chunk.left_start
                    if chunk.left_start == chunk.left_end
                    else chunk.right_start
                ) - 1
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
