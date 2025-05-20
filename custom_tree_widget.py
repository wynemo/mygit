from PyQt6.QtCore import QRect, Qt, pyqtSignal
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


class CustomTreeWidget(QTreeWidget):
    # 定义一个信号，当需要隐藏浮动标签时发射
    hideOverlayRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._overlay_label = None

    def _ensure_overlay_label(self):
        if self._overlay_label is None:
            # 父对象设置为viewport，这样它的坐标和滚动能与树内容同步
            self._overlay_label = QLabel(self.viewport())
            self._overlay_label.setObjectName("overlayTextLabel")  # 便于用样式表控制
            self._overlay_label.setStyleSheet(
                """
                #overlayTextLabel {
                    background-color: white; /* 使用系统高亮背景色可能更好 */
                    color: black;           /* 使用系统高亮文字颜色可能更好 */
                    border: 1px solid black;
                    padding: 2px;
                    border-radius: 3px;
                }
            """
            )
            # 获取系统高亮颜色，使浮动标签看起来更原生
            palette = QApplication.palette()
            bg_color = palette.color(QPalette.ColorGroup.Active, QPalette.ColorRole.Highlight)
            text_color = palette.color(QPalette.ColorGroup.Active, QPalette.ColorRole.HighlightedText)
            self._overlay_label.setStyleSheet(
                f"#overlayTextLabel {{ background-color: {bg_color.name()}; color: {text_color.name()}; border: 1px solid gray; padding: 2px; border-radius: 3px; }}"
            )

            self._overlay_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)  # 让鼠标事件穿透
            self._overlay_label.hide()  # 默认隐藏
        return self._overlay_label

    def show_full_text_for_item(self, item: QTreeWidgetItem, column: int):
        if not item:
            if self._overlay_label:
                self._overlay_label.hide()
            return

        full_text = item.text(column)
        if not full_text:
            if self._overlay_label:
                self._overlay_label.hide()
            return

        label = self._ensure_overlay_label()
        label.setText(full_text)
        label.adjustSize()  # 根据文本调整大小

        # 获取单元格在viewport中的几何位置
        item_rect = self.visualRect(self.indexFromItem(item, column))

        if item_rect.isValid():
            # 计算理想的宽度，但不超过treeWidget本身的宽度
            preferred_width = label.width() + 5  # 加一点padding
            max_width = self.viewport().width() - item_rect.left() - 5
            display_width = min(preferred_width, max_width)

            # 定位 QLabel
            # x坐标与单元格对齐，y坐标也与单元格对齐
            # 高度是标签自适应的高度，宽度是计算后的宽度
            # 我们希望它能覆盖其他列，所以宽度就是标签根据文本内容自适应的宽度
            label_rect = QRect(item_rect.topLeft(), label.sizeHint())  # 使用标签的推荐大小
            label_rect.setWidth(min(label.sizeHint().width(), self.viewport().width() - item_rect.left()))

            # 如果文本很长，确保标签不会超出视口太多
            # x, y 是相对于 viewport 的
            new_x = item_rect.left()
            new_y = item_rect.top()

            # 简单的调整，防止完全遮盖当前行（如果需要，可以调整y使其在下方或有偏移）
            # label.setGeometry(new_x, new_y, label.width(), label.height())
            # 为了确保它在顶部并且不会被其他单元格的绘制覆盖（理论上，因为它是viewport的子控件且后创建）
            # 并且，确保它的宽度是它所需要的宽度
            label.setGeometry(new_x, new_y, label.fontMetrics().horizontalAdvance(full_text) + 6, item_rect.height())

            # 如果原始单元格文本已经被省略，我们才显示overlay
            font_metrics = self.fontMetrics()  # 或者 item.font(column) 的 fontMetrics
            text_width_in_cell = font_metrics.horizontalAdvance(full_text)

            if text_width_in_cell > self.columnWidth(column) - self.indentation() - 4:  # 减去可能的边距和缩进
                label.show()
                label.raise_()  # 确保它在最上层
            else:
                label.hide()  # 如果单元格能完整显示，则不显示浮层

        else:
            label.hide()

    def hide_overlay(self):
        if self._overlay_label:
            self._overlay_label.hide()
        self.hideOverlayRequested.emit()  # 发射信号

    # 如果树本身滚动，我们也需要更新浮动标签的位置或隐藏它
    def scrollContentsBy(self, dx, dy):
        super().scrollContentsBy(dx, dy)
        if self._overlay_label and self._overlay_label.isVisible():
            # 简单处理：滚动时先隐藏，选中项改变时会重新计算显示
            # 更复杂的：根据dx, dy移动overlay_label
            self._overlay_label.hide()
            # 或者，如果当前有选中项，重新定位
            current = self.currentItem()
            if current:
                self.show_full_text_for_item(current, 0)

    # 当焦点改变时，也隐藏浮动标签
    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.hide_overlay()

    # (可选) 点击树的其他地方也隐藏
    # def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
    #     item = self.itemAt(event.pos())
    #     if not item or self.indexFromItem(item, 0) != self.currentIndex():
    #         self.hide_overlay()
    #     super().mousePressEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QTreeWidget Overlay Text Example")
        self.setGeometry(100, 100, 700, 400)

        self.treeWidget = CustomTreeWidget()
        self.treeWidget.setColumnCount(3)
        self.treeWidget.setHeaderLabels(["Column 1 (Long Text)", "Column 2", "Column 3"])

        # 调整列宽，让第一列的文本更容易被截断
        self.treeWidget.setColumnWidth(0, 200)
        self.treeWidget.setColumnWidth(1, 150)
        self.treeWidget.setColumnWidth(2, 150)

        # 示例数据
        data = [
            (
                "这是一段非常非常非常非常长的文本，它肯定无法在第一列中完全显示出来，我们希望选中时能看到全部。",
                "Item A2",
                "Item A3",
            ),
            ("短文本1", "Item B2", "Item B3"),
            ("这是另一段也比较长的文本内容，用于测试当它被选中时的浮动显示效果。", "Item C2", "Item C3"),
            ("正常长度文本", "Item D2", "Item D3"),
            (
                "这是一个超级无敌究极旋风霹雳长长长长长长长长长长长长长长长长长长长长长长长长长长长长长长长长的文本串串串串串",
                "Item E2",
                "Item E3",
            ),
        ]

        for d in data:
            item = QTreeWidgetItem(self.treeWidget)
            item.setText(0, d[0])
            item.setText(1, d[1])
            item.setText(2, d[2])
            # 可选：仍然设置ToolTip作为备用
            item.setToolTip(0, d[0])

        self.treeWidget.currentItemChanged.connect(self.on_current_item_changed)

        # 如果希望鼠标悬停时也显示（更复杂，需要事件过滤器或mouseMoveEvent）
        # self.treeWidget.setMouseTracking(True)
        # self.treeWidget.viewport().installEventFilter(self)

        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        layout.addWidget(self.treeWidget)
        self.setCentralWidget(central_widget)

    def on_current_item_changed(self, current: QTreeWidgetItem, previous: QTreeWidgetItem):
        if previous:  # 隐藏之前可能显示的浮层（如果逻辑放在这里）
            pass
        if current:
            self.treeWidget.show_full_text_for_item(current, 0)
        else:
            self.treeWidget.hide_overlay()

    # --- 如果想用事件过滤器实现悬停（更复杂） ---
    # def eventFilter(self, source, event):
    #     if source == self.treeWidget.viewport():
    #         if event.type() == QEvent.Type.MouseMove:
    #             index = self.treeWidget.indexAt(event.pos())
    #             if index.isValid() and index.column() == 0:
    #                 item = self.treeWidget.itemFromIndex(index)
    #                 self.treeWidget.show_full_text_for_item(item, 0, hover=True, pos=event.globalPos()) # 需要修改show_full_text_for_item
    #             else:
    #                 self.treeWidget.hide_overlay() # 鼠标移出有效区域
    #         elif event.type() == QEvent.Type.Leave: # 鼠标离开viewport
    #             self.treeWidget.hide_overlay()
    #
    #     return super().eventFilter(source, event)


if __name__ == "__main__":
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()
