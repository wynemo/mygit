import contextlib

from PyQt6.QtWidgets import QVBoxLayout, QWidget

from text_diff_viewer import DiffViewer, MergeDiffViewer
from git_manager_window import GitManagerWindow

# SyncedTextEdit is used within DiffViewer and MergeDiffViewer,
# its blame_annotation_clicked signal will be connected from instances of these viewers.


class CompareView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    # _on_blame_annotation_clicked method is removed as its functionality is now centralized
    # in GitManagerWindow.handle_blame_click_from_editor

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self.diff_viewer = DiffViewer()
        self.merge_diff_viewer = MergeDiffViewer()
        self.merge_diff_viewer.hide()

        layout.addWidget(self.diff_viewer)
        layout.addWidget(self.merge_diff_viewer)

        # Find GitManagerWindow instance to connect the signal
        parent_widget = self.parent()
        git_manager_window_instance = None
        while parent_widget:
            if isinstance(parent_widget, GitManagerWindow):
                git_manager_window_instance = parent_widget
                break
            parent_widget = parent_widget.parent()

        if git_manager_window_instance:
            # Connect signals for DiffViewer
            self.diff_viewer.left_edit.blame_annotation_clicked.connect(
                git_manager_window_instance.handle_blame_click_from_editor
            )
            self.diff_viewer.right_edit.blame_annotation_clicked.connect(
                git_manager_window_instance.handle_blame_click_from_editor
            )

            # Connect signals for MergeDiffViewer
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
            # Optionally, log a warning if the main window instance isn't found
            print("Warning: GitManagerWindow instance not found for CompareView signal connections.")

        # Signal connections for blame_annotation_clicked from SyncedTextEdit instances
        # are removed from here. The connection is now established in WorkspaceExplorer.open_file_in_tab
        # directly to GitManagerWindow.handle_blame_click_from_editor when SyncedTextEdit
        # instances are created for files opened via WorkspaceExplorer.
        # For SyncedTextEdit instances within DiffViewer/MergeDiffViewer (part of CompareView),
        # if they are also opened via a mechanism that uses WorkspaceExplorer.open_file_in_tab,
        # they would be covered. If they are created and managed solely by CompareView/DiffViewer
        # without going through WorkspaceExplorer's file opening logic, their blame clicks
        # would not be handled by the new centralized handler unless explicitly connected.
        # The current task is to remove the CompareView-specific handler and its connections.

    def show_diff(self, git_manager, commit, file_path):
        """显示文件差异"""
        try:
            parents = commit.parents

            # 获取当前提交的文件内容
            try:
                current_content = commit.tree[file_path].data_stream.read().decode("utf-8", errors="replace")
            except KeyError:
                current_content = ""

            # 获取父提交的文件内容
            parent_content = ""
            if parents:
                with contextlib.suppress(KeyError):
                    parent_content = parents[0].tree[file_path].data_stream.read().decode("utf-8", errors="replace")

            # 根据父提交数量选择显示模式
            if len(parents) <= 1:
                self.diff_viewer.show()
                self.merge_diff_viewer.hide()
                parent_commit_hash = parents[0].hexsha if parents else None
                self.diff_viewer.set_texts(
                    parent_content, current_content, file_path, parent_commit_hash, commit.hexsha
                )
            else:
                self.diff_viewer.hide()
                self.merge_diff_viewer.show()

                # 获取第二个父提交的内容
                parent2_content = ""
                with contextlib.suppress(KeyError):
                    parent2_content = parents[1].tree[file_path].data_stream.read().decode("utf-8", errors="replace")

                parent1_commit_hash = parents[0].hexsha  # Assuming parents[0] exists for merge
                parent2_commit_hash = parents[1].hexsha  # Assuming parents[1] exists for merge
                self.merge_diff_viewer.set_texts(
                    parent_content,
                    current_content,
                    parent2_content,
                    file_path,
                    parent1_commit_hash,
                    commit.hexsha,
                    parent2_commit_hash,
                )

        except Exception as e:
            print(f"Error displaying file diff: {e}")
