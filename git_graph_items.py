# git_graph_items.py

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainterPath, QPen
from PyQt6.QtWidgets import QGraphicsEllipseItem, QGraphicsItem, QGraphicsPathItem, QGraphicsTextItem

from git_graph_data import CommitNode  # Assuming git_graph_data.py is available

# --- Configuration for items ---
COMMIT_RADIUS = 10
HORIZONTAL_SPACING = 40
VERTICAL_SPACING = 40

# Colors (can be expanded and made configurable)
COLOR_PALETTE = [
    QColor("#1f77b4"),
    QColor("#ff7f0e"),
    QColor("#2ca02c"),
    QColor("#d62728"),
    QColor("#9467bd"),
    QColor("#8c564b"),
    QColor("#e377c2"),
    QColor("#7f7f7f"),
    QColor("#bcbd22"),
    QColor("#17becf"),
]
DEFAULT_COMMIT_COLOR = QColor(Qt.GlobalColor.gray)
SELECTED_COMMIT_COLOR = QColor(Qt.GlobalColor.yellow)
HOVER_COMMIT_COLOR = QColor(Qt.GlobalColor.lightGray)

DEFAULT_EDGE_COLOR = QColor(Qt.GlobalColor.darkGray)
EDGE_THICKNESS = 1.5

REF_PADDING_X = 4
REF_PADDING_Y = 2
REF_BACKGROUND_COLOR_BRANCH = QColor("#e6f7ff")  # Light blue
REF_BORDER_COLOR_BRANCH = QColor("#91d5ff")
REF_TEXT_COLOR_BRANCH = QColor(Qt.GlobalColor.black)

REF_BACKGROUND_COLOR_TAG = QColor("#fffbe6")  # Light yellow
REF_BORDER_COLOR_TAG = QColor("#ffe58f")
REF_TEXT_COLOR_TAG = QColor(Qt.GlobalColor.black)

REF_BACKGROUND_COLOR_HEAD = QColor("#f6ffed")  # Light green
REF_BORDER_COLOR_HEAD = QColor("#b7eb8f")
REF_TEXT_COLOR_HEAD = QColor(Qt.GlobalColor.black)

# Configuration for CommitMessageItem
COMMIT_MSG_MAX_LENGTH = 60
COMMIT_MSG_COLOR = QColor("#444444")  # Dark gray for commit messages
COMMIT_MSG_FONT_FAMILY = "Arial"
COMMIT_MSG_FONT_SIZE = 9


class CommitCircle(QGraphicsEllipseItem):
    def __init__(self, commit_node: CommitNode, color_idx: int = 0, parent: QGraphicsItem = None):
        super().__init__(-COMMIT_RADIUS, -COMMIT_RADIUS, 2 * COMMIT_RADIUS, 2 * COMMIT_RADIUS, parent)
        self.commit_node = commit_node
        self.base_color = COLOR_PALETTE[color_idx % len(COLOR_PALETTE)]
        self.current_brush_color = self.base_color

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)  # For updates if needed
        self.setAcceptHoverEvents(True)

        self.setBrush(QBrush(self.base_color))
        self.setPen(QPen(Qt.GlobalColor.black, 1))

        tooltip_text = (
            f"SHA: {self.commit_node.sha}\n"
            f"Author: {self.commit_node.author_name} <{self.commit_node.author_email}>\n"
            f"Date: {self.commit_node.author_date}\n"
            f"Message: {self.commit_node.message}"
        )
        self.setToolTip(tooltip_text)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedChange:
            if value:  # Selected
                self.current_brush_color = SELECTED_COMMIT_COLOR
            else:  # Deselected
                self.current_brush_color = self.base_color
            self.setBrush(QBrush(self.current_brush_color))
        return super().itemChange(change, value)

    def hoverEnterEvent(self, event):
        if not self.isSelected():
            self.setBrush(QBrush(HOVER_COMMIT_COLOR))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        if not self.isSelected():
            self.setBrush(QBrush(self.current_brush_color))  # Revert to current selected or base color
        super().hoverLeaveEvent(event)

    # Potentially add paint method for more custom drawing if needed


class EdgeLine(QGraphicsPathItem):
    def __init__(
        self,
        start_item: CommitCircle,
        end_item: CommitCircle,
        color: QColor = DEFAULT_EDGE_COLOR,
        parent: QGraphicsItem = None,
    ):
        super().__init__(parent)
        self.start_item = start_item
        self.end_item = end_item
        self.line_color = color

        self.setPen(
            QPen(
                self.line_color,
                EDGE_THICKNESS,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        self.setZValue(-1)  # Draw edges behind commits

        self.update_path()

    def update_path(self):
        path = QPainterPath()
        # For now, simple straight line. Curves can be added later.
        # Points are relative to the scene, items might be transformed.
        # We use scenePos() for robustness.
        start_pos = self.start_item.scenePos()
        end_pos = self.end_item.scenePos()

        path.moveTo(start_pos)
        path.lineTo(end_pos)
        self.setPath(path)

    # If CommitCircles move, their scenePos changes, and edges might need to be updated.
    # This can be handled by the view/scene by calling update_path on relevant edges
    # when commit positions change.


class ReferenceLabel(QGraphicsTextItem):
    def __init__(self, text: str, commit_item: CommitCircle, is_head=False, is_tag=False, parent: QGraphicsItem = None):
        super().__init__(text, parent)
        self.commit_item = commit_item
        self.text = text

        font = QFont("Arial", 8)
        self.setFont(font)

        if is_head:
            self.bg_color = REF_BACKGROUND_COLOR_HEAD
            self.border_color = REF_BORDER_COLOR_HEAD
            self.text_color = REF_TEXT_COLOR_HEAD
        elif is_tag:
            self.bg_color = REF_BACKGROUND_COLOR_TAG
            self.border_color = REF_BORDER_COLOR_TAG
            self.text_color = REF_TEXT_COLOR_TAG
        else:  # Branch
            self.bg_color = REF_BACKGROUND_COLOR_BRANCH
            self.border_color = REF_BORDER_COLOR_BRANCH
            self.text_color = REF_TEXT_COLOR_BRANCH

        self.setDefaultTextColor(self.text_color)

        # Adjust position relative to the commit circle
        # This might need refinement based on how many labels a commit has
        # For now, place it to the right of the commit circle
        self.setPos(
            commit_item.pos().x() + COMMIT_RADIUS + REF_PADDING_X,
            commit_item.pos().y() - self.boundingRect().height() / 2,
        )

    def paint(self, painter, option, widget=None):
        # Draw background and border
        painter.setPen(QPen(self.border_color, 1))
        painter.setBrush(QBrush(self.bg_color))
        # Add padding to the bounding rect for drawing
        bg_rect = self.boundingRect().adjusted(-REF_PADDING_X, -REF_PADDING_Y, REF_PADDING_X, REF_PADDING_Y)
        painter.drawRoundedRect(bg_rect, 3, 3)

        # Call superclass paint for the text itself
        super().paint(painter, option, widget)

    def boundingRect(self) -> QRectF:
        # Adjust bounding rect to include padding for background drawing
        rect = super().boundingRect()
        rect.adjust(-REF_PADDING_X, -REF_PADDING_Y, REF_PADDING_X, REF_PADDING_Y)
        return rect


class CommitMessageItem(QGraphicsTextItem):
    def __init__(self, full_message: str, parent: QGraphicsItem = None):
        super().__init__(parent)

        self.full_message = full_message  # Store original for potential future use

        # Truncate message for display
        if len(full_message) > COMMIT_MSG_MAX_LENGTH:
            display_text = full_message[: COMMIT_MSG_MAX_LENGTH - 3] + "..."
        else:
            display_text = full_message

        self.setPlainText(display_text)

        font = QFont(COMMIT_MSG_FONT_FAMILY, COMMIT_MSG_FONT_SIZE)
        self.setFont(font)
        self.setDefaultTextColor(COMMIT_MSG_COLOR)

        # Basic tooltip showing the full message if it was truncated
        if display_text != full_message:
            self.setToolTip(f"Full message: {full_message}")


if __name__ == "__main__":
    # This file is intended to be imported, not run directly.
    # Basic test code could be added here if using a QApplication,
    # but it's better to test these items within a QGraphicsScene in the main view.
    print("git_graph_items.py defines QGraphicsItem subclasses for Git graph visualization.")
    print("Run the main application to see them in action.")
