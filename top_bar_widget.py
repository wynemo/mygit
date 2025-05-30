import sys

from PyQt6.QtCore import QPoint, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QToolButton,
    QWidget,
)


class TopBarWidget(QWidget):
    open_folder_requested = pyqtSignal()
    recent_folder_selected = pyqtSignal(str)
    clear_recent_folders_requested = pyqtSignal()
    branch_changed = pyqtSignal(str)
    commit_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    fetch_requested = pyqtSignal()
    pull_requested = pyqtSignal()
    push_requested = pyqtSignal()
    toggle_bottom_panel_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(100)  # As per requirement

        self._layout = QHBoxLayout()
        self._layout.setContentsMargins(10, 5, 10, 5)  # Adjusted margins for more elements
        self._layout.setSpacing(10)  # Added spacing between widgets
        self.setLayout(self._layout)

        # --- Open Folder Button ---
        self.open_button = QPushButton("Open Folder")
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

        # --- Commit Button ---
        self.commit_button = QPushButton("Commit")
        self.commit_button.clicked.connect(self.commit_requested.emit)
        self._layout.addWidget(self.commit_button)

        self._layout.addStretch(1)  # Add stretch to push subsequent items to the right

        # --- Fetch, Pull, Push Buttons ---
        self.fetch_button = QToolButton()
        self.fetch_button.setIcon(QIcon("icons/fetch.svg"))
        self.fetch_button.setText("Fetch")
        self.fetch_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.fetch_button.clicked.connect(self.fetch_requested.emit)
        self._layout.addWidget(self.fetch_button)

        self.pull_button = QToolButton()
        self.pull_button.setIcon(QIcon("icons/pull.svg"))  # Placeholder, assuming pull.svg
        self.pull_button.setText("Pull")
        self.pull_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.pull_button.clicked.connect(self.pull_requested.emit)
        self._layout.addWidget(self.pull_button)

        self.push_button = QToolButton()
        self.push_button.setIcon(QIcon("icons/push.svg"))  # Placeholder, assuming push.svg
        self.push_button.setText("Push")
        self.push_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.push_button.clicked.connect(self.push_requested.emit)
        self._layout.addWidget(self.push_button)

        # --- Separator ---
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        self._layout.addWidget(separator)

        # --- Settings Button ---
        self.settings_button = QToolButton()
        # self.settings_button.setIcon(QIcon("icons/settings.svg")) # Assuming settings.svg
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

    def _on_toggle_bottom_panel(self):
        self.toggle_bottom_panel_requested.emit()
        # The actual icon update will be triggered by GitManagerWindow via update_toggle_button_icon

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
            points = [QPoint(3, 6), QPoint(8, 11), QPoint(13, 6)]
        else:
            points = [QPoint(3, 10), QPoint(8, 5), QPoint(13, 10)]
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

    def get_current_branch(self):
        return self.branch_combo.currentText()

    def set_buttons_enabled(self, enabled):
        """Enable or disable buttons that require an open repository."""
        self.commit_button.setEnabled(enabled)
        self.branch_combo.setEnabled(enabled)
        self.fetch_button.setEnabled(enabled)
        self.pull_button.setEnabled(enabled)
        self.push_button.setEnabled(enabled)
        # `recent_button` and `open_button` should always be enabled or handled separately.
        # `settings_button` and `toggle_bottom_button` usually always enabled.


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
