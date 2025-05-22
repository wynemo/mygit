import logging

from PyQt6.QtCore import QRect, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
import os # 导入os模块 (Import os module)
from PyQt6.QtWidgets import QPlainTextEdit, QWidget

from diff_highlighter import DiffHighlighter # 导入差异高亮器 (Import diff highlighter)
# from syntax_highlighter import SyntaxHighlighter # 注释掉旧的语法高亮器导入 (Comment out old syntax highlighter import)
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
        logging.debug("只读模式: {}", self.isReadOnly())

        # 添加行号区域
        self.line_number_area = LineNumberArea(self)
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.update_line_number_area_width()

        # 初始化差异信息及语法高亮器 (Initialize diff information and syntax highlighter)
        # DiffHighlighter 将在 setObjectName 中基于编辑器类型被创建 (DiffHighlighter will be created in setObjectName based on editor type)
        self.highlighter = None # DiffHighlighter 实例 (DiffHighlighter instance)
        # self.syntax_highlighter = None # 旧的语法高亮器成员，不再需要 (Old syntax highlighter member, no longer needed)
        # logging.debug("DiffHighlighter 将在 setObjectName 中创建。(DiffHighlighter will be created in setObjectName.)")

    def setObjectName(self, name: str) -> None:
        super().setObjectName(name)
        # 在设置对象名称后创建高亮器 (Create highlighter after setting object name)
        if self.highlighter is None: # 如果高亮器尚未创建 (If highlighter is not yet created)
            self.highlighter = DiffHighlighter(self.document(), name) # 创建DiffHighlighter实例 (Create DiffHighlighter instance)
            # logging.debug("创建高亮器 (DiffHighlighter)，类型: %s", name)

    def set_language(self, language_name):
        # 设置编辑器语言 (Set editor language)
        if self.highlighter: # 使用 self.highlighter (Use self.highlighter)
            self.highlighter.set_language(language_name) # 调用DiffHighlighter的set_language方法 (Call DiffHighlighter's set_language method)
            # logging.debug(f"编辑器语言已设置为: {language_name} (Editor language set to: {language_name})")
        # else:
            # logging.warning("尝试在 highlighter 未初始化时设置语言。(Attempted to set language when highlighter is not initialized.)")

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

        # 遍历所有差异块 (Iterate over all diff chunks) - DiffHighlighter暂时禁用 (DiffHighlighter temporarily disabled)
        # if not self.highlighter: # DiffHighlighter 相关的代码暂时注释掉 (DiffHighlighter related code temporarily commented out)
        #     return
        # for chunk in self.highlighter.diff_chunks:
        #     if chunk.type == "delete" and (
        #         (
        #             chunk.right_start == chunk.right_end
        #             and self.objectName() == "right_edit"
        #         )
        #         or (
        #             chunk.left_start == chunk.left_end
        #             and self.objectName() == "left_edit"
        #         )
        #     ):
        #         pos = (
        #             chunk.left_start
        #             if chunk.left_start == chunk.left_end
        #             else chunk.right_start
        #         ) - 1
        #         block = self.document().findBlockByLineNumber(pos)
        #         if block.isValid():
        #             # 获取这一行的几何信息 (Get geometry information for this line)
        #             block_geometry = self.blockBoundingGeometry(block)
        #             block_rect = block_geometry.translated(self.contentOffset())
        #             block_top = block_rect.top()
        #             block_bottom = block_rect.bottom()

        #             # 只绘制在可见区域内的行 (Only draw lines within the visible area)
        #             if block_bottom >= viewport_top and block_top <= viewport_bottom:
        #                 painter.drawLine(
        #                     0,
        #                     int(block_bottom),
        #                     self.viewport().width(),
        #                     int(block_bottom),
        #                 )
        #                 logging.debug(
        #                     "{} 删除块: {} - {} {}",
        #                     self.objectName(),
        #                     chunk.right_start,
        #                     chunk.right_end,
        #                     chunk,
        #                 )
