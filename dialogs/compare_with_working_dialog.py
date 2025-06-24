from PyQt6.QtWidgets import QDialog, QVBoxLayout

from text_diff_viewer import DiffViewer

# todo 去掉这个，放到提交历史旁边的 tab


class CompareWithWorkingDialog(QDialog):
    def __init__(self, title, old_content, new_content, file_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(800, 600)

        layout = QVBoxLayout(self)
        self.diff_viewer = DiffViewer()
        layout.addWidget(self.diff_viewer)

        # todo, bug, hash is alwaysy head, none(workingdir)
        self.diff_viewer.set_texts(old_content, new_content, file_path, "HEAD", None)
        self.diff_viewer.right_edit.set_editable()

        # cursor 生成：设置可编辑后更新DiffViewer状态并创建还原按钮
        self.diff_viewer.right_edit_is_editable = True
        if self.diff_viewer.actual_diff_chunks:
            self.diff_viewer._create_restore_buttons()
