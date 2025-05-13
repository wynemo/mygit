from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem


class CommitGraphView(QTreeWidget):
    COMMIT_DOT_RADIUS = 5
    COLUMN_WIDTH = 20
    ROW_HEIGHT = 30

    def __init__(self, parent=None):
        super().__init__(parent)
        self.commits = []
        self.branch_colors = {}
        self.commit_positions = {}  # 存储每个提交的位置

    def set_commit_data(self, graph_data):
        """设置提交数据"""
        self.commits = graph_data["commits"]
        self.branch_colors = graph_data["branch_colors"]
        self.calculate_positions()
        self.update()

    def calculate_positions(self):
        """计算每个提交的位置"""
        self.commit_positions.clear()

        for idx, commit in enumerate(self.commits):
            # 计算垂直位置
            y = idx * self.ROW_HEIGHT + self.ROW_HEIGHT // 2

            # 根据分支计算水平位置
            branch_idx = 0
            if commit["branches"]:
                branch_name = commit["branches"][0]
                branch_idx = list(self.branch_colors.keys()).index(branch_name)

            x = branch_idx * self.COLUMN_WIDTH + self.COLUMN_WIDTH

            self.commit_positions[commit["hash"]] = QPoint(x, y)

    def calculate_positions(self):
        """计算每个提交的位置"""
        self.commit_positions.clear()

        for idx, commit in enumerate(self.commits):
            # 计算垂直位置 (不需要考虑滚动偏移，在绘制时处理)
            y = idx * self.ROW_HEIGHT + self.ROW_HEIGHT // 2

            # 根据分支计算水平位置
            branch_idx = 0
            if commit["branches"]:
                branch_name = commit["branches"][0]
                branch_idx = list(self.branch_colors.keys()).index(branch_name)

            x = branch_idx * self.COLUMN_WIDTH + self.COLUMN_WIDTH

            self.commit_positions[commit["hash"]] = QPoint(x, y)

    def paintEvent(self, event):
        """重写绘制事件"""
        super().paintEvent(event)

        if not self.commits:
            return

        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 获取滚动条位置
        v_scroll = self.verticalScrollBar().value()
        h_scroll = self.horizontalScrollBar().value()

        # 绘制连线和提交点
        for commit in self.commits:
            # 应用滚动偏移
            current_pos = QPoint(
                self.commit_positions[commit["hash"]].x() - h_scroll,
                self.commit_positions[commit["hash"]].y() - v_scroll,
            )

            # 检查是否在可见区域内
            if not (0 <= current_pos.y() <= self.viewport().height()):
                continue

            # 绘制到父提交的连线
            for parent_hash in commit["parents"]:
                if parent_hash in self.commit_positions:
                    # 应用滚动偏移到父节点位置
                    parent_pos = QPoint(
                        self.commit_positions[parent_hash].x() - h_scroll,
                        self.commit_positions[parent_hash].y() - v_scroll,
                    )

                    # 确定连线颜色
                    line_color = QColor("#cccccc")
                    if commit["branches"]:
                        branch_name = commit["branches"][0]
                        line_color = QColor(self.branch_colors[branch_name])

                    # 绘制连线
                    pen = QPen(line_color, 2)
                    painter.setPen(pen)
                    painter.drawLine(current_pos, parent_pos)

            # 绘制提交点
            for branch_name in commit["branches"]:
                color = QColor(self.branch_colors[branch_name])
                painter.setBrush(color)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(
                    current_pos.x() - self.COMMIT_DOT_RADIUS,
                    current_pos.y() - self.COMMIT_DOT_RADIUS,
                    self.COMMIT_DOT_RADIUS * 2,
                    self.COMMIT_DOT_RADIUS * 2,
                )
