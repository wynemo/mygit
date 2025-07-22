from PyQt6.QtWidgets import QStyledItemDelegate
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush, QPolygon, QPainterPath

class DAGItemDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.colors = [
            '#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A',
            '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9'
        ]
        self.node_radius = 4
        self.column_width = 20

    def paint(self, painter, option, index):
        if index.column() == 0:  # Assuming DAG is in the first column
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            dag_info = index.data(Qt.ItemDataRole.UserRole + 1)
            if not dag_info:
                painter.restore()
                return

            self.draw_connections(painter, option.rect, dag_info)
            self.draw_commit_node(painter, option.rect, dag_info)

            painter.restore()
        else:
            super().paint(painter, option, index)

    def draw_connections(self, painter, rect, dag_info):
        center_y = rect.center().y()

        for conn in dag_info.get('connections', []):
            from_col = conn['from_col']
            to_col = conn['to_col']
            color_index = conn['color_index']

            pen = QPen(QColor(self.colors[color_index % len(self.colors)]), 2)
            painter.setPen(pen)

            start_x = from_col * self.column_width + self.column_width / 2
            end_x = to_col * self.column_width + self.column_width / 2

            if from_col == to_col:
                # Straight line
                painter.drawLine(int(start_x), rect.top(), int(end_x), rect.bottom())
            else:
                # Curved line for branching/merging
                path = QPainterPath()
                path.moveTo(start_x, rect.top())
                path.cubicTo(start_x, center_y, end_x, center_y, end_x, rect.bottom())
                painter.drawPath(path)


    def draw_commit_node(self, painter, rect, dag_info):
        column = dag_info['column']
        color_index = dag_info['color_index']

        node_x = column * self.column_width + self.column_width / 2
        node_y = rect.center().y()

        color = QColor(self.colors[color_index % len(self.colors)])
        painter.setBrush(QBrush(color))

        pen_color = QColor(Qt.GlobalColor.black)
        if dag_info.get('is_merge'):
            pen_color = QColor(Qt.GlobalColor.darkGreen)

        painter.setPen(QPen(pen_color, 1.5))

        if dag_info.get('is_merge'):
            # Diamond for merge commits
            points = [
                (node_x, node_y - self.node_radius * 1.5),
                (node_x + self.node_radius * 1.5, node_y),
                (node_x, node_y + self.node_radius * 1.5),
                (node_x - self.node_radius * 1.5, node_y)
            ]
            poly = QPolygon()
            for p in points:
                poly.append(p)
            painter.drawPolygon(poly)
        else:
            # Circle for regular commits
            painter.drawEllipse(int(node_x - self.node_radius), int(node_y - self.node_radius), int(self.node_radius * 2), int(self.node_radius * 2))
