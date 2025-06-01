from PyQt6.QtCore import Qt
from PyQt6.QtGui import (
    QColor,
    QPainter,
    QPen,
)

from text_edit import SyncedTextEdit


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
                if mod_status:  # 仅当有状态时处理
                    color = self.LINE_STATUS_COLORS.get(mod_status)
                    if color:  # 确保颜色存在
                        print(f"mod_status: {mod_status}, color: {color}", block_line_number)
                        painter.setBrush(color)
                        painter.setPen(Qt.PenStyle.NoPen)

                        # 计算标记的垂直中心位置
                        mark_y = int(top + (current_block_height - self.MODIFICATION_MARK_SIZE) / 2)

                        if mod_status == "deleted":
                            last_mod_status = self.line_modifications.get(block_line_number - 1)
                            if not last_mod_status or not last_mod_status == "deleted":
                                # 绘制红点表示删除
                                # 计算圆心的x位置（在标记区域的中心）
                                dot_center_x = modification_mark_x + self.MODIFICATION_MARK_SIZE // 2
                                # 绘制圆点
                                painter.drawEllipse(
                                    int(dot_center_x - self.MODIFICATION_MARK_SIZE / 2),
                                    int(top),
                                    int(self.MODIFICATION_MARK_SIZE),
                                    int(self.MODIFICATION_MARK_SIZE),
                                )
                        elif mod_status in ("added", "modified"):
                            # 绘制竖线表示新增或修改
                            # 设置画笔，用于画线
                            painter.setPen(QPen(color, 2))  # 线宽设为2像素
                            # 计算竖线的x位置（在标记区域的中心）
                            line_x = modification_mark_x + self.MODIFICATION_MARK_SIZE // 2
                            # 绘制竖线，从当前行的顶部到底部
                            # 确保坐标值为整数
                            painter.drawLine(int(line_x), int(top), int(line_x), int(top + current_block_height))

            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1


# </new_class>
