import contextlib
import logging
import os

from PyQt6.QtWidgets import QPushButton, QStackedWidget, QVBoxLayout, QWidget

from text_diff_viewer import DiffViewer, MergeDiffViewer
from unified_diff_viewer import UnifiedDiffViewer


class CompareView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.left_text = ""
        self.right_text = ""
        self.file_path = ""
        self.setup_ui()

    def setup_ui(self):
        from git_manager_window import GitManagerWindow

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self.view_mode_button = QPushButton("切换到统一视图")
        self.view_mode_button.clicked.connect(self.toggle_view_mode)
        layout.addWidget(self.view_mode_button)

        self.stacked_widget = QStackedWidget()
        layout.addWidget(self.stacked_widget)

        self.diff_viewer = DiffViewer()
        self.unified_diff_viewer = UnifiedDiffViewer()
        self.merge_diff_viewer = MergeDiffViewer()

        self.stacked_widget.addWidget(self.diff_viewer)
        self.stacked_widget.addWidget(self.unified_diff_viewer)
        self.stacked_widget.addWidget(self.merge_diff_viewer)

        parent_widget = self.parent()
        git_manager_window_instance = None
        while parent_widget:
            if isinstance(parent_widget, GitManagerWindow):
                git_manager_window_instance = parent_widget
                break
            parent_widget = parent_widget.parent()

        if git_manager_window_instance:
            self.diff_viewer.left_edit.blame_annotation_clicked.connect(
                git_manager_window_instance.handle_blame_click_from_editor
            )
            self.diff_viewer.right_edit.blame_annotation_clicked.connect(
                git_manager_window_instance.handle_blame_click_from_editor
            )
            self.merge_diff_viewer.parent1_edit.blame_annotation_clicked.connect(
                git_manager_window_instance.handle_blame_click_from_editor
            )
            self.merge_diff_viewer.result_edit.blame_annotation_clicked.connect(
                git_manager_window_instance.handle_blame_click_from_editor
            )
            self.merge_diff_viewer.parent2_edit.blame_annotation_clicked.connect(
                git_manager_window_instance.handle_blame_click_from_editor
            )
        else:
            logging.warning("GitManagerWindow instance not found for CompareView signal connections.")

    def toggle_view_mode(self):
        current_index = self.stacked_widget.currentIndex()
        if current_index == 0:
            self.stacked_widget.setCurrentIndex(1)
            self.view_mode_button.setText("切换到并排视图")
            self.unified_diff_viewer.set_texts(self.left_text, self.right_text, self.file_path)
        elif current_index == 1:
            self.stacked_widget.setCurrentIndex(0)
            self.view_mode_button.setText("切换到统一视图")
            self.diff_viewer.set_texts(self.left_text, self.right_text, self.file_path)

    def show_diff(self, git_manager, commit, file_path, other_commit=None, is_comparing_with_workspace=False):
        """显示文件差异"""
        try:
            self.file_path = file_path
            if is_comparing_with_workspace:
                try:
                    self.left_text = commit.tree[file_path].data_stream.read().decode("utf-8", errors="replace")
                except KeyError:
                    self.left_text = ""
                working_file_path = os.path.join(git_manager.repo.working_dir, file_path)
                if os.path.exists(working_file_path):
                    with open(working_file_path, "r", encoding="utf-8", errors="replace") as f:
                        self.right_text = f.read()
                else:
                    self.right_text = ""
                self.diff_viewer.set_texts(
                    self.left_text,
                    self.right_text,
                    file_path,
                    right_file_path=file_path,
                    left_commit_hash=commit.hexsha,
                    right_commit_hash=None,
                )
                self.diff_viewer.right_edit.set_editable()
                self.stacked_widget.setCurrentWidget(self.diff_viewer)
                self.view_mode_button.setVisible(True)
                return

            parents = commit.parents
            try:
                content = commit.tree[file_path].data_stream.read().decode("utf-8", errors="replace")
            except KeyError:
                content = ""

            if other_commit:
                other_commit_content = other_commit.tree[file_path].data_stream.read().decode("utf-8", errors="replace")
                self.left_text = content
                self.right_text = other_commit_content
                self.diff_viewer.set_texts(
                    self.left_text,
                    self.right_text,
                    file_path,
                    right_file_path=None,
                    left_commit_hash=commit.hexsha,
                    right_commit_hash=other_commit.hexsha,
                )
                self.stacked_widget.setCurrentWidget(self.diff_viewer)
                self.view_mode_button.setVisible(True)
                return

            parent_content = ""
            if parents:
                with contextlib.suppress(KeyError):
                    parent_content = parents[0].tree[file_path].data_stream.read().decode("utf-8", errors="replace")

            if len(parents) <= 1:
                self.left_text = parent_content
                self.right_text = content
                parent_commit_hash = parents[0].hexsha if parents else None
                self.diff_viewer.set_texts(
                    self.left_text, self.right_text, file_path, file_path, parent_commit_hash, commit.hexsha
                )
                self.stacked_widget.setCurrentWidget(self.diff_viewer)
                self.view_mode_button.setVisible(True)
            else:
                self.stacked_widget.setCurrentWidget(self.merge_diff_viewer)
                self.view_mode_button.setVisible(False)
                parent2_content = ""
                with contextlib.suppress(KeyError):
                    parent2_content = parents[1].tree[file_path].data_stream.read().decode("utf-8", errors="replace")
                parent1_commit_hash = parents[0].hexsha
                parent2_commit_hash = parents[1].hexsha
                self.merge_diff_viewer.set_texts(
                    parent_content,
                    content,
                    parent2_content,
                    file_path,
                    parent1_commit_hash,
                    commit.hexsha,
                    parent2_commit_hash,
                )
        except Exception:
            logging.exception("显示文件差异时出错")
