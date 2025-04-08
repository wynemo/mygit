from PyQt6.QtWidgets import (QDialog, QFormLayout, QLineEdit, 
                           QDialogButtonBox)

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("设置")
        self.settings = parent.settings
        
        # 创建布局
        layout = QFormLayout(self)
        
        # 创建字体输入文本框
        self.font_edit = QLineEdit()
        self.font_edit.setText(self.settings.get_font_family())
        layout.addRow("字体:", self.font_edit)
        
        # 添加确定和取消按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
    
    def accept(self):
        """当点击确定按钮时保存设置"""
        # 保存字体设置
        self.settings.set_font_family(self.font_edit.text())
        # 应用字体设置
        self.parent.apply_font_settings()
        super().accept()
