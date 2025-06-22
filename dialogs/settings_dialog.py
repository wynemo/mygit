from typing import TYPE_CHECKING

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit

if TYPE_CHECKING:
    from settings import Settings

from pygments.styles import get_all_styles


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("设置")
        self.settings: Settings = parent.settings

        # 创建布局
        layout = QFormLayout(self)

        # 创建语言选择下拉框
        self.language_combo = QComboBox()
        self.language_combo.addItems(["中文", "English"])
        current_language = self.settings.settings.get("language", "中文")
        self.language_combo.setCurrentText(current_language)
        language_layout = QHBoxLayout()
        language_label = QLabel(self.tr("语言："))
        language_icon_label = QLabel()
        language_icon_label.setPixmap(QIcon("icons/globe.svg").pixmap(16, 16))
        language_layout.addWidget(language_icon_label)
        language_layout.addWidget(language_label)
        language_layout.addWidget(self.language_combo, 1)
        layout.addRow(language_layout)

        # 创建字体输入文本框（响应式布局）
        self.font_edit = QLineEdit()
        self.font_edit.setText(self.settings.get_font_family())
        font_layout = QHBoxLayout()
        font_layout.addWidget(QLabel(self.tr("字体：")))
        font_layout.addWidget(self.font_edit, 1)  # 设置拉伸因子
        layout.addRow(font_layout)

        # 创建字体大小输入框
        self.font_size_edit = QLineEdit()
        self.font_size_edit.setText(str(self.settings.get_font_size()))
        font_size_layout = QHBoxLayout()
        font_size_layout.addWidget(QLabel(self.tr("字体大小：")))
        font_size_layout.addWidget(self.font_size_edit, 1)
        layout.addRow(font_size_layout)

        # 创建代码风格下拉框
        self.code_style_combo = QComboBox()
        self.code_style_combo.addItems(get_all_styles())
        self.code_style_combo.setCurrentText(self.settings.get_code_style())
        code_style_layout = QHBoxLayout()
        code_style_layout.addWidget(QLabel(self.tr("代码风格：")))
        code_style_layout.addWidget(self.code_style_combo, 1)
        layout.addRow(code_style_layout)

        # 创建 API 设置输入框
        self.api_url_edit = QLineEdit()
        self.api_url_edit.setText(self.settings.settings.get("api_url", ""))
        api_url_layout = QHBoxLayout()
        api_url_layout.addWidget(QLabel(self.tr("API URL:")))
        api_url_layout.addWidget(self.api_url_edit, 1)
        layout.addRow(api_url_layout)

        self.api_secret_edit = QLineEdit()
        self.api_secret_edit.setText(self.settings.settings.get("api_secret", ""))
        self.api_secret_edit.setEchoMode(QLineEdit.EchoMode.Password)
        api_secret_layout = QHBoxLayout()
        api_secret_layout.addWidget(QLabel(self.tr("API Secret:")))
        api_secret_layout.addWidget(self.api_secret_edit, 1)
        layout.addRow(api_secret_layout)

        self.model_name_edit = QLineEdit()
        self.model_name_edit.setText(self.settings.settings.get("model_name", ""))
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel(self.tr("Model Name:")))
        model_layout.addWidget(self.model_name_edit, 1)
        layout.addRow(model_layout)

        self.prompt = QTextEdit()
        self.prompt.setText(
            self.settings.settings.get("prompt", "帮我生成 commit 信息，用中文，简洁，使用 Conventional Commits 格式")
        )
        prompt_layout = QHBoxLayout()
        prompt_layout.addWidget(QLabel(self.tr("Prompt:")))
        prompt_layout.addWidget(self.prompt, 1)
        layout.addRow(prompt_layout)

        # 添加确定和取消按钮
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def accept(self):
        """当点击确定按钮时保存设置"""
        # 保存字体设置
        self.settings.set_font_family(self.font_edit.text())
        # 保存字体大小设置
        try:
            font_size = int(self.font_size_edit.text())
            self.settings.set_font_size(font_size)
        except ValueError:
            # 如果输入无效，保持原大小
            pass

        # 保存代码风格设置
        self.settings.set_code_style(self.code_style_combo.currentText())

        # 保存 API 相关设置
        self.settings.settings["api_url"] = self.api_url_edit.text()
        self.settings.settings["api_secret"] = self.api_secret_edit.text()
        self.settings.settings["model_name"] = self.model_name_edit.text()
        self.settings.settings["prompt"] = self.prompt.toPlainText()

        # 保存语言设置
        self.settings.settings["language"] = self.language_combo.currentText()

        # 保存设置到文件
        self.settings.save_settings()

        super().accept()
