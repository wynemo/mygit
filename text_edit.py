from PyQt6.QtCore import QRect, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QPainter
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
        print("\n=== 初始化SyncedTextEdit ===")
        print(f"只读模式: {self.isReadOnly()}")

        # 添加行号区域
        self.line_number_area = LineNumberArea(self)
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.update_line_number_area_width()

        # 初始化差异信息
        self.diff_info = []
        self.highlighter = None

    def setObjectName(self, name: str) -> None:
        super().setObjectName(name)
        # 在设置对象名称后创建高亮器
        if self.highlighter is None:
            self.highlighter = DiffHighlighter(self.document(), name)
            print(f"创建高亮器，类型: {name}")

    def set_diff_info(self, diff_info):
        """设置差异信息并更新高亮"""
        self.diff_info = diff_info
        self.highlighter.set_diff_chunks(diff_info)

    def line_number_area_width(self):
        digits = len(str(max(1, self.blockCount())))
        space = 3 + self.fontMetrics().horizontalAdvance("9") * digits
        return space

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
                number = str(block_number + 1)
                painter.setPen(QColor("#808080"))
                painter.drawText(
                    0,
                    int(top),
                    self.line_number_area.width() - 2,
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight,
                    number,
                )

            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1
