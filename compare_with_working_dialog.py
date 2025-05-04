from PyQt6.QtWidgets import QDialog, QVBoxLayout
from text_diff_viewer import DiffViewer

#todo 去掉这个，放到提交历史旁边的tab

class CompareWithWorkingDialog(QDialog):
    def __init__(self, title, old_content, new_content, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(800, 600)

        layout = QVBoxLayout(self)
        self.diff_viewer = DiffViewer()
        layout.addWidget(self.diff_viewer)

        self.diff_viewer.set_texts(old_content, new_content)
