"""
cursor 生成
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QGroupBox, QHBoxLayout, QLabel, QMessageBox, QPushButton, QRadioButton, QVBoxLayout


class GitResetDialog(QDialog):
    def __init__(self, current_branch: str, commit_hash: str, commit_message: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Git Reset")
        self.setFixedSize(500, 350)

        self.main_layout = QVBoxLayout(self)

        self.top_info_label = QLabel(f'<b>{current_branch}</b> -> <b>{commit_hash}</b> "{commit_message}"')
        self.top_info_label.setTextFormat(Qt.TextFormat.RichText)
        self.top_info_label.setWordWrap(True)
        self.main_layout.addWidget(self.top_info_label)

        self.description_label = QLabel(
            "This will reset the current branch head to the selected commit, and update the working tree and the index according to the selected mode:"
        )
        self.description_label.setWordWrap(True)
        self.main_layout.addWidget(self.description_label)

        self.reset_mode_group_box = QGroupBox("")
        self.reset_mode_layout = QVBoxLayout(self.reset_mode_group_box)

        self.soft_radio = QRadioButton("Soft")
        self.soft_description = QLabel("Files won't change, differences will be staged for commit.")
        self.soft_radio.setChecked(False)  # Default to Mixed as per image
        self.reset_mode_layout.addWidget(self.soft_radio)
        self.reset_mode_layout.addWidget(self.soft_description)

        self.mixed_radio = QRadioButton("Mixed")
        self.mixed_description = QLabel("Files won't change, differences won't be staged.")
        self.mixed_radio.setChecked(True)  # Default to Mixed as per image
        self.reset_mode_layout.addWidget(self.mixed_radio)
        self.reset_mode_layout.addWidget(self.mixed_description)

        self.hard_radio = QRadioButton("Hard")
        self.hard_description = QLabel(
            "Files will be reverted to the state of the selected commit.\nWarning: any local changes will be lost."
        )
        self.hard_description.setWordWrap(True)
        self.reset_mode_layout.addWidget(self.hard_radio)
        self.reset_mode_layout.addWidget(self.hard_description)

        self.keep_radio = QRadioButton("Keep")
        self.keep_description = QLabel(
            "Files will be reverted to the state of the selected commit, but local changes will be kept intact."
        )
        self.keep_description.setWordWrap(True)
        self.reset_mode_layout.addWidget(self.keep_radio)
        self.reset_mode_layout.addWidget(self.keep_description)

        self.main_layout.addWidget(self.reset_mode_group_box)

        self.button_layout = QHBoxLayout()
        self.help_button = QPushButton("?")
        self.help_button.setFixedSize(30, 30)
        self.button_layout.addWidget(self.help_button)
        self.button_layout.addStretch()

        self.cancel_button = QPushButton("Cancel")
        self.button_layout.addWidget(self.cancel_button)

        self.reset_button = QPushButton("Reset")
        self.reset_button.setDefault(True)
        self.button_layout.addWidget(self.reset_button)

        self.main_layout.addLayout(self.button_layout)

        # Connect signals
        self.cancel_button.clicked.connect(self.reject)
        self.reset_button.clicked.connect(self.accept)
        self.help_button.clicked.connect(self._show_help)

    def get_selected_mode(self) -> str:
        if self.soft_radio.isChecked():
            return "soft"
        elif self.mixed_radio.isChecked():
            return "mixed"
        elif self.hard_radio.isChecked():
            return "hard"
        elif self.keep_radio.isChecked():
            return "keep"
        return "mixed"  # Default to mixed if none selected, though one should always be selected

    def _show_help(self):
        QMessageBox.information(
            self,
            "Git Reset Help",
            """
Soft: Files won't change, differences will be staged for commit.

Mixed: Files won't change, differences won't be staged. This is the default mode.

Hard: Files will be reverted to the state of the selected commit. Warning: any local changes will be lost.

Keep: Files will be reverted to the state of the selected commit, but local changes will be kept intact.
""",
        )
