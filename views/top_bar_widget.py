import sys

from PyQt6.QtCore import QPoint, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap, QPolygon
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QToolButton,
    QWidget,
)

from components.new_branch_dialog import NewBranchDialog
from utils import get_main_window_by_parent


class RotatingIcon(QLabel):
    def __init__(self, png_path):
        super().__init__()
        self.target_size = 20  # 你想要的尺寸
        self.original_pixmap = QPixmap(png_path).scaled(
            self.target_size,
            self.target_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.angle = 0
        self.setPixmap(self.original_pixmap)

        # 定时器控制旋转
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.rotate)
        self.timer.start(16)  # 大约 60 FPS

    def rotate(self):
        self.angle = (self.angle + 3) % 360

        # 1. 创建画布
        canvas = QPixmap(self.target_size, self.target_size)
        canvas.fill(Qt.GlobalColor.transparent)

        # 2. 用 QPainter 在中心旋转并绘制
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # 3. 变换原点到中心，然后旋转
        center = self.target_size / 2
        painter.translate(center, center)
        painter.rotate(self.angle)
        painter.translate(-center, -center)

        # 4. 绘制原图
        painter.drawPixmap(0, 0, self.original_pixmap)
        painter.end()

        self.setPixmap(canvas)


class TopBarWidget(QWidget):
    open_folder_requested = pyqtSignal()
    recent_folder_selected = pyqtSignal(str)
    clear_recent_folders_requested = pyqtSignal()
    branch_changed = pyqtSignal(str)
    commit_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    toggle_bottom_panel_requested = pyqtSignal()
    toggle_left_panel_requested = pyqtSignal()  # 新增信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(50)  # As per requirement

        self._layout = QHBoxLayout()
        self._layout.setContentsMargins(10, 5, 10, 5)  # Adjusted margins for more elements
        self._layout.setSpacing(10)  # Added spacing between widgets
        self.setLayout(self._layout)

        # --- Open Folder Button ---
        self.open_button = QPushButton("📁 Open Folder")
        self.open_button.clicked.connect(self.open_folder_requested.emit)
        self._layout.addWidget(self.open_button)

        # --- Recent Folders Button and Menu ---
        self.recent_button = QPushButton("Recent")
        self.recent_menu = QMenu(self)
        self.recent_button.setMenu(self.recent_menu)
        self._layout.addWidget(self.recent_button)

        # --- Branch Label and Combo Box ---
        self.branch_label = QLabel("Branch:")
        self._layout.addWidget(self.branch_label)
        self.branch_combo = QComboBox()
        self.branch_combo.setMinimumWidth(150)
        self.branch_combo.currentTextChanged.connect(self.branch_changed.emit)
        self._layout.addWidget(self.branch_combo)

        # 新建分支按钮
        self.new_branch_button = QPushButton("+")
        self.new_branch_button.setToolTip("新建分支")
        self.new_branch_button.clicked.connect(self._on_new_branch_button_clicked)
        self._layout.addWidget(self.new_branch_button)

        # --- Spinner Label ---
        self.spinner_label = RotatingIcon("icons/spin.png")
        self.spinner_label.hide()
        self.layout().addWidget(self.spinner_label)

        self._layout.addStretch(1)  # Add stretch to push subsequent items to the right

        # --- Separator ---
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        self._layout.addWidget(separator)

        # --- Settings Button ---
        self.settings_button = QToolButton()
        self.settings_button.setIcon(QIcon("icons/settings.svg"))  # Assuming settings.svg
        self.settings_button.setText("Settings")  # Using text until icon is confirmed
        self.settings_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.settings_button.clicked.connect(self.settings_requested.emit)
        self._layout.addWidget(self.settings_button)

        # --- Toggle Bottom Panel Button ---
        self.toggle_bottom_button = QToolButton()
        self.toggle_bottom_button.setCheckable(True)
        self.toggle_bottom_button.clicked.connect(self._on_toggle_bottom_panel)
        self.update_toggle_button_icon(True)  # Initial state
        self._layout.addWidget(self.toggle_bottom_button)

        # --- Toggle Left Panel Button ---
        self.toggle_left_panel_button = QToolButton()
        self.toggle_left_panel_button.setCheckable(True)
        self.toggle_left_panel_button.setIcon(self._create_left_panel_icon(True))
        self.toggle_left_panel_button.setToolTip("隐藏左侧面板")
        self.toggle_left_panel_button.clicked.connect(self._on_toggle_left_panel)
        self._layout.addWidget(self.toggle_left_panel_button)

    def _on_toggle_bottom_panel(self):
        self.toggle_bottom_panel_requested.emit()
        # The actual icon update will be triggered by GitManagerWindow via update_toggle_button_icon

    def _on_toggle_left_panel(self):
        self.toggle_left_panel_requested.emit()
        # 图标和状态由主窗口控制

    def update_recent_menu(self, recent_folders):
        self.recent_menu.clear()
        for folder in recent_folders:
            action = QAction(folder, self)
            action.triggered.connect(lambda checked=False, f=folder: self.recent_folder_selected.emit(f))
            self.recent_menu.addAction(action)
        if recent_folders:
            self.recent_menu.addSeparator()
        clear_action = QAction("Clear Recent", self)
        clear_action.triggered.connect(self.clear_recent_folders_requested.emit)
        self.recent_menu.addAction(clear_action)
        self.recent_button.setEnabled(bool(recent_folders))

    def update_branches(self, branches, default_branch=None):
        self.branch_combo.blockSignals(True)
        self.branch_combo.clear()
        self.branch_combo.addItems(branches)
        if default_branch and default_branch in branches:
            self.branch_combo.setCurrentText(default_branch)
        elif branches:  # set to first branch if no default or default not in list
            self.branch_combo.setCurrentIndex(0)
        self.branch_combo.blockSignals(False)
        self.branch_combo.setEnabled(bool(branches))

    def _create_arrow_icon(self, down=True):
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor("black"))  # Icon color
        if down:
            points = QPolygon([QPoint(3, 6), QPoint(8, 11), QPoint(13, 6)])
        else:
            points = QPolygon([QPoint(3, 10), QPoint(8, 5), QPoint(13, 10)])
        painter.drawPolyline(points)
        painter.end()
        return QIcon(pixmap)

    def _create_left_panel_icon(self, visible=True):
        # 简单用左右箭头表示
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor("black"))
        if visible:
            # 显示时，画一个向左的箭头
            points = QPolygon([QPoint(11, 3), QPoint(5, 8), QPoint(11, 13)])
        else:
            # 隐藏时，画一个向右的箭头
            points = QPolygon([QPoint(5, 3), QPoint(11, 8), QPoint(5, 13)])
        painter.drawPolyline(points)
        painter.end()
        return QIcon(pixmap)

    def update_toggle_button_icon(self, is_panel_visible):
        # Using text for now, will switch to icons if provided
        # For example, using up/down arrows from a resource file or drawing them
        if is_panel_visible:
            self.toggle_bottom_button.setIcon(self._create_arrow_icon(down=True))
            self.toggle_bottom_button.setToolTip("Hide Bottom Panel")
            self.toggle_bottom_button.setChecked(True)
        else:
            self.toggle_bottom_button.setIcon(self._create_arrow_icon(down=False))
            self.toggle_bottom_button.setToolTip("Show Bottom Panel")
            self.toggle_bottom_button.setChecked(False)
        self.toggle_bottom_button.setIconSize(QSize(16, 16))

    def update_toggle_left_panel_icon(self, is_panel_visible):
        if is_panel_visible:
            self.toggle_left_panel_button.setIcon(self._create_left_panel_icon(True))
            self.toggle_left_panel_button.setToolTip("隐藏左侧面板")
            self.toggle_left_panel_button.setChecked(True)
        else:
            self.toggle_left_panel_button.setIcon(self._create_left_panel_icon(False))
            self.toggle_left_panel_button.setToolTip("显示左侧面板")
            self.toggle_left_panel_button.setChecked(False)
        self.toggle_left_panel_button.setIconSize(QSize(16, 16))

    def get_current_branch(self):
        return self.branch_combo.currentText()

    def set_buttons_enabled(self, enabled):
        """Enable or disable buttons that require an open repository."""
        self.branch_combo.setEnabled(enabled)
        # `recent_button` and `open_button` should always be enabled or handled separately.
        # `settings_button` and `toggle_bottom_button` usually always enabled.

    def start_spinning(self):
        self.spinner_label.show()

    def stop_spinning(self):
        self.spinner_label.hide()

    def _on_new_branch_button_clicked(self):
        """处理新建分支按钮点击事件"""
        dialog = NewBranchDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            branch_name = dialog.get_branch_name()
            main_window = get_main_window_by_parent(self)
            git_manager = main_window.git_manager
            git_manager.create_and_switch_branch(branch_name)
            main_window.update_branches_on_top_bar()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Create dummy icons for testing if they don't exist
    import os

    if not os.path.exists("icons"):
        os.makedirs("icons")
    for icon_name in ["fetch.svg", "pull.svg", "push.svg", "settings.svg"]:
        if not os.path.exists(f"icons/{icon_name}"):
            with open(f"icons/{icon_name}", "w") as f:
                f.write("<svg></svg>")  # Dummy SVG content

    main_window = QWidget()  # Dummy main window for testing
    main_window.setWindowTitle("TopBarWidget Test")
    main_layout = QHBoxLayout(main_window)

    top_bar = TopBarWidget(main_window)
    main_layout.addWidget(top_bar)

    # Example usage of methods
    top_bar.update_recent_menu(["/path/to/folder1", "/path/to/folder2"])
    top_bar.update_branches(["main", "develop", "feature/new-stuff"], default_branch="develop")
    top_bar.set_buttons_enabled(True)

    def handle_branch_change(branch):
        print(f"Branch changed to: {branch}")

    top_bar.branch_changed.connect(handle_branch_change)

    def handle_toggle(visible):
        print(f"Toggle bottom panel requested. Currently checked: {top_bar.toggle_bottom_button.isChecked()}")
        # In a real app, GitManagerWindow would call update_toggle_button_icon
        # For this test, we simulate it if the signal is just for request
        # top_bar.update_toggle_button_icon(not top_bar.toggle_bottom_button.isChecked()) # This might be confusing
        # as the button state changes, then this method is called.
        # GitManagerWindow is the source of truth for panel visibility.

    # Simulating GitManagerWindow's role in updating the toggle button icon
    # based on the emitted signal (which represents a *request* to toggle)
    def request_toggle_panel():
        print("Toggle panel requested by button click.")
        # Here, the main application would manage the panel's visibility
        # and then call `update_toggle_button_icon` on the top_bar.
        # For this test, let's assume the panel visibility flips and we update the icon.
        # This is a bit circular for a standalone test but demonstrates the connection.
        current_panel_visibility = top_bar.toggle_bottom_button.isChecked()  # This is post-click state
        print(
            f"Button is checked: {current_panel_visibility}. Simulating panel visibility to be {current_panel_visibility}."
        )
        top_bar.update_toggle_button_icon(current_panel_visibility)

    top_bar.toggle_bottom_panel_requested.connect(request_toggle_panel)

    main_window.resize(1000, 150)  # Resize window to better see the TopBarWidget
    main_window.show()
    sys.exit(app.exec())
