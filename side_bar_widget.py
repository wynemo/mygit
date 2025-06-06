from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QToolButton, QVBoxLayout, QWidget


class SideBarWidget(QWidget):
    project_button_clicked = pyqtSignal()
    commit_button_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(30)
        self.setStyleSheet("background-color: #f0f0f0;")

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 10, 0, 10)
        layout.setSpacing(10)
        self.setLayout(layout)

        # 工程按钮
        self.project_btn = QToolButton()
        self.project_btn.setText("工程")
        self.project_btn.setIcon(QIcon("icons/project.svg"))
        self.project_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.project_btn.clicked.connect(self.project_button_clicked.emit)
        layout.addWidget(self.project_btn)

        # 提交按钮
        self.commit_btn = QToolButton()
        self.commit_btn.setText("提交")
        self.commit_btn.setIcon(QIcon("icons/commit_icon.svg"))
        self.commit_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.commit_btn.clicked.connect(self.commit_button_clicked.emit)
        layout.addWidget(self.commit_btn)

        layout.addStretch()
