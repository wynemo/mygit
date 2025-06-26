import contextlib
import logging
import os

from PyQt6.QtWidgets import QVBoxLayout, QWidget

from text_diff_viewer import DiffViewer, MergeDiffViewer

# SyncedTextEdit is used within DiffViewer and MergeDiffViewer,
# its blame_annotation_clicked signal will be connected from instances of these viewers.


class CompareView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    # _on_blame_annotation_clicked method is removed as its functionality is now centralized
    # in GitManagerWindow.handle_blame_click_from_editor

    def setup_ui(self):
        from git_manager_window import GitManagerWindow

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

    def show_diff(self, git_manager, commit, file_path, other_commit=None, is_comparing_with_workspace=False):
        """显示文件差异"""
        try:
            # Get content of the primary commit (left side for two-way diff, or result for merge diff)
            try:
                # This is 'current_content' if comparing with parent, or 'left_content' if comparing with other_commit/workspace
                main_content = commit.tree[file_path].data_stream.read().decode("utf-8", errors="replace")
            except KeyError:
                main_content = ""  # File might not exist in this commit

            if is_comparing_with_workspace:
                # Case: Compare 'commit' (left) with Working Directory (right)
                working_file_path = os.path.join(git_manager.repo.working_dir, file_path)
                right_content = ""
                if os.path.exists(working_file_path):
                    with open(working_file_path, "r", encoding="utf-8", errors="replace") as f:
                        right_content = f.read()
                else:
                    # File might be deleted in working dir, or path_in_commit was from a rename
                    # and file_path is the new name not yet existing or different.
                    # For "compare with working", file_path is the current path in the working dir.
                    pass # right_content remains ""

                self.diff_viewer.show()
                self.merge_diff_viewer.hide()
                self.diff_viewer.set_texts(
                    left_text=main_content, # Content from the commit
                    right_text=right_content, # Content from the working directory
                    left_file_path=file_path, # Path in commit (can be old_file_path if renamed)
                    right_file_path=file_path, # Path in working directory
                    left_commit_hash=commit.hexsha,
                    right_commit_hash=None,  # Indicates working directory
                )

            elif other_commit:
                # Case: Compare 'commit' (left) with 'other_commit' (right)
                try:
                    right_content = other_commit.tree[file_path].data_stream.read().decode("utf-8", errors="replace")
                except KeyError:
                    right_content = ""  # File might not exist in other_commit

                self.diff_viewer.show()
                self.merge_diff_viewer.hide()
                self.diff_viewer.set_texts(
                    left_text=main_content,
                    right_text=right_content,
                    left_file_path=file_path,
                    right_file_path=file_path, # Assuming path is the same for both commits
                    left_commit_hash=commit.hexsha,
                    right_commit_hash=other_commit.hexsha,
                )
            else:
                # Case: Compare 'commit' (right for 2-way, result for 3-way) with its parent(s)
                parents = commit.parents
                if len(parents) <= 1:  # Single parent or initial commit
                    parent_content = ""
                    parent_commit_hash = None
                    if parents: # Has at least one parent
                        try:
                            # Path in parent could be different if file was renamed in 'commit'
                            # For simplicity, this usually assumes file_path is the path in 'commit'
                            # and tries to find it in parent. A more robust solution handles renames.
                            parent_content = parents[0].tree[file_path].data_stream.read().decode("utf-8", errors="replace")
                        except KeyError:
                            parent_content = "" # File didn't exist in parent or path was different
                        parent_commit_hash = parents[0].hexsha

                    self.diff_viewer.show()
                    self.merge_diff_viewer.hide()
                    # Left side is parent, Right side is the selected commit's content
                    self.diff_viewer.set_texts(
                        left_text=parent_content,
                        right_text=main_content, # main_content is from 'commit'
                        left_file_path=file_path, # Path in parent (ideally, could be different if renamed)
                        right_file_path=file_path, # Path in current commit
                        left_commit_hash=parent_commit_hash,
                        right_commit_hash=commit.hexsha,
                    )
                else:  # Merge commit, show 3-way diff (parent1, result, parent2)
                    self.diff_viewer.hide()
                    self.merge_diff_viewer.show()

                    parent1_content = ""
                    try:
                        parent1_content = parents[0].tree[file_path].data_stream.read().decode("utf-8", errors="replace")
                    except KeyError:
                        parent1_content = ""

                    parent2_content = ""
                    try:
                        parent2_content = parents[1].tree[file_path].data_stream.read().decode("utf-8", errors="replace")
                    except KeyError:
                        parent2_content = ""

                    self.merge_diff_viewer.set_texts(
                        parent1_text=parent1_content,
                        result_text=main_content,  # main_content is from 'commit' (the merge result)
                        parent2_text=parent2_content,
                        file_path=file_path, # Assuming file_path is consistent across merge
                        parent1_commit_hash=parents[0].hexsha,
                        result_commit_hash=commit.hexsha,
                        parent2_commit_hash=parents[1].hexsha,
                    )
        except Exception:
            logging.exception("Error displaying file diff")
