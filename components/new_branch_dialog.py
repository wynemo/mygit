"""cursor 生成"""

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)


class NewBranchDialog(QDialog):
    """新建分支对话框"""

    def __init__(self, parent=None, branches: Optional[list[str]] = None):
        super().__init__(parent)
        self.setWindowTitle("Create New Branch")
        self.setMinimumWidth(350)

        # 主布局
        layout = QVBoxLayout(self)

        # 分支名称选择
        branch_layout = QHBoxLayout()
        branch_layout.addWidget(QLabel("Branch Name:"))
        self.branch_combo = QLineEdit()
        if branches and len(branches) > 0:
            self.branch_combo.setText(branches[0])
        else:
            self.branch_combo.setText("main")
        self.branch_combo.setPlaceholderText("Enter new branch name")

        branch_layout.addWidget(self.branch_combo)
        layout.addLayout(branch_layout)

        # 复选框
        self.checkout_checkbox = QCheckBox("Checkout branch")
        self.checkout_checkbox.setChecked(True)
        layout.addWidget(self.checkout_checkbox)

        self.overwrite_checkbox = QCheckBox("Overwrite existing branch")
        self.overwrite_checkbox.setChecked(False)
        layout.addWidget(self.overwrite_checkbox)

        # 按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok,
            Qt.Orientation.Horizontal,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def get_branch_name(self) -> str:
        """获取输入的分支名称"""
        return self.branch_combo.text().strip()

    def should_checkout(self) -> bool:
        """是否应该检出分支"""
        return self.checkout_checkbox.isChecked()

    def should_overwrite(self) -> bool:
        """是否应该覆盖现有分支"""
        return self.overwrite_checkbox.isChecked()
