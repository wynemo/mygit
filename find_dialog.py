import os
from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,  # Added
    QFrame,
    QHBoxLayout,  # Added
    QLabel,  # Added for completeness, though not strictly in initial req
    QLineEdit,  # Added
    QPushButton,  # Added
    QVBoxLayout,  # Added
)

if TYPE_CHECKING:
    from text_edit import SyncedTextEdit  # 仅在类型检查时导入


class FindDialog(QFrame):  # Changed from QDialog to QWidget
    def __init__(self, parent_editor: "SyncedTextEdit", initial_search_text: Optional[str] = None):
        super().__init__(parent_editor)  # Set SyncedTextEdit as parent for context
        self.editor = parent_editor
        self.setWindowTitle("Find")
        # check if on windows
        if os.name == "nt":
            self.setWindowFlags(Qt.WindowType.WindowDoesNotAcceptFocus | Qt.WindowType.Tool)
        self.setStyleSheet("""
            background-color: #f8f8f8;
            border: 1px solid #ccc;
            border-radius: 4px;
        """)
        self._drag_active = False
        self._drag_position = None

        # UI Elements
        self.search_input = QLineEdit(self)
        if initial_search_text:
            self.search_input.setText(initial_search_text)
            self.search_input.selectAll()  # Select the text for easy replacement or confirmation
        else:
            self.search_input.setPlaceholderText("Enter text to find...")
        self.case_sensitive_checkbox = QCheckBox("Case sensitive", self)
        self.find_next_button = QPushButton("Find Next", self)
        self.find_previous_button = QPushButton("Find Previous", self)
        self.close_button = QPushButton("Close", self)

        # Connections
        self.find_next_button.clicked.connect(self.on_find_next)
        self.find_previous_button.clicked.connect(self.on_find_previous)
        self.close_button.clicked.connect(self.custom_close)  # Changed from self.accept

        # Layout
        main_layout = QVBoxLayout(self)

        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("Find:", self))  # Optional label
        input_layout.addWidget(self.search_input)
        main_layout.addLayout(input_layout)

        options_layout = QHBoxLayout()
        options_layout.addWidget(self.case_sensitive_checkbox)
        options_layout.addStretch()  # Pushes checkbox to the left
        main_layout.addLayout(options_layout)

        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()  # Push buttons to the right
        buttons_layout.addWidget(self.find_previous_button)
        buttons_layout.addWidget(self.find_next_button)
        buttons_layout.addStretch()  # Spacer
        buttons_layout.addWidget(self.close_button)
        main_layout.addLayout(buttons_layout)

        self.setLayout(main_layout)
        self.setMinimumWidth(300)  # Adjust as needed

    def on_find_next(self):
        search_text = self.search_input.text()
        if not search_text:
            return
        if os.name == "nt":
            self.editor.activateWindow()
            self.editor.setFocus()
        case_sensitive = self.case_sensitive_checkbox.isChecked()
        self.editor.find_text(search_text, direction="next", case_sensitive=case_sensitive)

    def on_find_previous(self):
        search_text = self.search_input.text()
        if not search_text:
            return
        if os.name == "nt":
            self.editor.activateWindow()
            self.editor.setFocus()
        case_sensitive = self.case_sensitive_checkbox.isChecked()
        self.editor.find_text(search_text, direction="previous", case_sensitive=case_sensitive)

    def custom_close(self):
        """Handles the logic for closing the dialog."""
        self.editor.clear_search_highlights()
        self.editor.find_dialog_instance = None
        self.close()  # QWidget.close()

    def closeEvent(self, event):
        """Ensures cleanup when the dialog is closed via window controls."""
        self.custom_close()  # Call our custom close logic
        super().closeEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_active = True
            self._drag_position = event.position().toPoint()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_active and event.buttons() & Qt.MouseButton.LeftButton:
            offset = event.position().toPoint() - self._drag_position
            self.move(self.pos() + offset)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_active = False
        self._drag_position = None
        event.accept()
