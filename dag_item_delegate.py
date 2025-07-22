from PyQt6.QtWidgets import QStyledItemDelegate
from PyQt6.QtCore import Qt, QPoint
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
        current_col = dag_info['column']
        current_x = current_col * self.column_width + self.column_width / 2

        # Draw line from center to bottom, if it has children
        if dag_info.get('has_children'):
            pen = QPen(QColor(self.colors[dag_info['color_index'] % len(self.colors)]), 2)
            painter.setPen(pen)
            painter.drawLine(int(current_x), int(center_y), int(current_x), rect.bottom())

        # Draw lines from parents
        for conn in dag_info.get('connections', []):
            parent_col = conn['from_col']
            color_index = conn['color_index']

            pen = QPen(QColor(self.colors[color_index % len(self.colors)]), 2)
            painter.setPen(pen)

            parent_x = parent_col * self.column_width + self.column_width / 2

            # Draw a line from the parent's column at the top to the current node's center
            if parent_col == current_col:
                painter.drawLine(int(current_x), rect.top(), int(current_x), int(center_y))
            else:
                # branch/merge line
                painter.drawLine(int(parent_x), rect.top(), int(parent_x), int(center_y))
                painter.drawLine(int(parent_x), int(center_y), int(current_x), int(center_y))


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
                poly.append(QPoint(int(p[0]), int(p[1])))
            painter.drawPolygon(poly)
        else:
            # Circle for regular commits
            painter.drawEllipse(int(node_x - self.node_radius), int(node_y - self.node_radius), int(self.node_radius * 2), int(self.node_radius * 2))
