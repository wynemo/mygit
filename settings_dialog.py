from PyQt6.QtWidgets import (QDialog, QFormLayout, QLineEdit, 
                           QDialogButtonBox)

# from git_manager_window import GitManagerWindow

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
        
        # 创建API设置输入框
        self.api_url_edit = QLineEdit()
        self.api_url_edit.setText(self.settings.settings.get("api_url", ""))
        layout.addRow("API URL:", self.api_url_edit)
        
        self.api_secret_edit = QLineEdit()
        self.api_secret_edit.setText(self.settings.settings.get("api_secret", ""))
        self.api_secret_edit.setEchoMode(QLineEdit.EchoMode.Password)  # 密码模式显示
        layout.addRow("API Secret:", self.api_secret_edit)
        
        self.model_name_edit = QLineEdit()
        self.model_name_edit.setText(self.settings.settings.get("model_name", ""))
        layout.addRow("Model Name:", self.model_name_edit)

        self.prompt = QLineEdit()
        self.prompt.setText(self.settings.settings.get("prompt", ""))
        layout.addRow("Prompt:", self.prompt)
        
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
        
        # 保存API相关设置
        self.settings.settings["api_url"] = self.api_url_edit.text()
        self.settings.settings["api_secret"] = self.api_secret_edit.text()
        self.settings.settings["model_name"] = self.model_name_edit.text()
        self.settings.settings["prompt"] = self.prompt.text()
        
        # 保存设置到文件
        self.settings.save_settings()
        
        super().accept()
