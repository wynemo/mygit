from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QTextEdit, 
                           QPushButton, QLabel, QDialogButtonBox)

class CommitDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("提交更改")
        self.setMinimumWidth(400)
        self.setMinimumHeight(250)
        
        # 创建布局
        layout = QVBoxLayout(self)
        
        # 提交信息输入区域
        message_label = QLabel("提交信息:")
        layout.addWidget(message_label)
        
        self.message_edit = QTextEdit()
        layout.addWidget(self.message_edit)
        
        # 按钮区域
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def get_commit_message(self):
        return self.message_edit.toPlainText()
