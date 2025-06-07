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
        self.project_btn.setCheckable(True)
        self.project_btn.setChecked(True)
        self.project_btn.setStyleSheet("""
            QToolButton {
                border: none;
                background-color: transparent;
            }
            QToolButton:hover {
                background-color: #e0e0e0;
            }
            QToolButton:checked {
                background-color: #2196F3;
            }
            QToolButton:checked:!active {
                background-color: #cccccc;
            }
        """)
        self.project_btn.clicked.connect(self.project_button_clicked.emit)
        self.project_btn.clicked.connect(self._on_project_clicked)
        layout.addWidget(self.project_btn)

        # 提交按钮
        self.commit_btn = QToolButton()
        self.commit_btn.setText("提交")
        self.commit_btn.setIcon(QIcon("icons/commit_icon.svg"))
        self.commit_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.commit_btn.setCheckable(True)
        self.commit_btn.setChecked(False)
        self.commit_btn.setStyleSheet("""
            QToolButton {
                border: none;
                background-color: transparent;
            }
            QToolButton:hover {
                background-color: #e0e0e0;
            }
            QToolButton:checked {
                background-color: #2196F3;
            }
            QToolButton:checked:!active {
                background-color: #cccccc;
            }
        """)
        self.commit_btn.clicked.connect(self.commit_button_clicked.emit)
        self.commit_btn.clicked.connect(self._on_commit_clicked)
        layout.addWidget(self.commit_btn)

        layout.addStretch()

    def focusOutEvent(self, event):
        """窗口失去焦点时更新按钮样式状态"""
        self.project_btn.setDown(False)
        self.commit_btn.setDown(False)
        super().focusOutEvent(event)

    def _on_project_clicked(self):
        """处理工程按钮点击事件"""
        self.project_btn.setChecked(True)
        self.commit_btn.setChecked(False)

    def _on_commit_clicked(self):
        """处理提交按钮点击事件"""
        self.commit_btn.setChecked(True)
        self.project_btn.setChecked(False)
