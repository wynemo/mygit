# git_graph_view.py

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QPainter
from PyQt6.QtWidgets import QApplication, QGraphicsScene, QGraphicsView, QMenu

from git_graph_data import CommitNode
from git_graph_items import (
    COLOR_PALETTE,
    COMMIT_RADIUS,
    REF_PADDING_X,
    CommitCircle,
    CommitMessageItem,
    EdgeLine,
    ReferenceLabel,
)
from git_graph_layout import calculate_commit_positions
from git_log_parser import parse_git_log


class GitGraphView(QGraphicsView):
    commit_item_clicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)

        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)  # Enable panning
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)  # Zoom towards mouse

        self._commit_items: dict[str, CommitCircle] = {}
        self._edge_items: list[EdgeLine] = []
        self._ref_labels: list[ReferenceLabel] = []
        self._message_items: list[CommitMessageItem] = []

        self._zoom_factor_base = 1.1  # Base factor for zooming

        # Set context menu policy
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def clear_graph(self):
        self.scene.clear()
        self._commit_items.clear()
        self._edge_items.clear()
        self._ref_labels.clear()
        self._message_items.clear()

    def populate_graph(self, commits: list[CommitNode]):
        self.clear_graph()

        if not commits:
            # Handle case with no commits (e.g., empty repo or error)
            # Maybe display a message in the view or scene
            return

        # First pass: Create all commit circles and reference labels
        for commit_node in commits:
            # Determine the color index to use for the commit circle
            final_color_idx_for_circle = (
                commit_node.branch_color_idx if commit_node.branch_color_idx is not None else commit_node.color_idx
            )
            # color = COLOR_PALETTE[final_color_idx_for_circle % len(COLOR_PALETTE)] # This line is not directly used for CommitCircle constructor

            commit_item = CommitCircle(commit_node, color_idx=final_color_idx_for_circle)
            commit_item.setPos(commit_node.x, commit_node.y)
            self.scene.addItem(commit_item)
            self._commit_items[commit_node.sha] = commit_item

            # --- ReferenceLabel creation and positioning ---
            # Store reference labels for current commit to calculate their collective extent
            current_commit_ref_labels = []
            ref_y_offset = -COMMIT_RADIUS - 5

            # Determine the starting x-position for reference labels.
            # REF_PADDING_X is typically 4 or 5.
            base_x_for_labels_and_msg = commit_node.x + COMMIT_RADIUS + REF_PADDING_X

            max_ref_label_actual_width = 0  # The drawn width of the widest label

            for ref_text in commit_node.references:
                is_head = "HEAD" in ref_text
                is_tag = "tag:" in ref_text

                ref_label = ReferenceLabel(ref_text, commit_item, is_head=is_head, is_tag=is_tag)

                # Position the reference label. They stack vertically.
                # All ref labels for a commit will share the same X starting point.
                ref_label.setPos(base_x_for_labels_and_msg, commit_node.y + ref_y_offset)

                self.scene.addItem(ref_label)
                self._ref_labels.append(ref_label)  # Keep flat list as before for general management
                current_commit_ref_labels.append(ref_label)  # For positioning message item

                # Update max_ref_label_actual_width based on this label's drawn width
                # Note: boundingRect for ReferenceLabel includes its internal padding.
                max_ref_label_actual_width = max(max_ref_label_actual_width, ref_label.boundingRect().width())

                ref_y_offset -= ref_label.boundingRect().height() + 2  # Stack them upwards

            # --- CommitMessageItem creation and positioning ---
            # Position the message item to the right of all reference labels for this commit.
            # If there were reference labels, message_x_start is after them.
            # If no reference labels, message_x_start is just after the commit circle.

            message_x_start = base_x_for_labels_and_msg
            if max_ref_label_actual_width > 0:
                message_x_start += max_ref_label_actual_width + REF_PADDING_X  # Add padding after the widest label

            commit_msg_item = CommitMessageItem(commit_node, parent=None)  # Or parent=commit_item

            # Vertically center the message item with the commit circle
            msg_item_height = commit_msg_item.boundingRect().height()
            commit_msg_item.setPos(message_x_start, commit_node.y - msg_item_height / 2)
            self.scene.addItem(commit_msg_item)
            self._message_items.append(commit_msg_item)

        # Second pass: Create edges
        for commit_node in commits:
            if commit_node.sha not in self._commit_items:
                continue  # Should not happen if first pass was successful

            current_commit_item = self._commit_items[commit_node.sha]

            # Determine the color for edges leading to this commit_node
            final_color_idx_for_edge = (
                commit_node.branch_color_idx if commit_node.branch_color_idx is not None else commit_node.color_idx
            )
            edge_color_for_commit = COLOR_PALETTE[final_color_idx_for_edge % len(COLOR_PALETTE)]

            for parent_sha in commit_node.parents:
                if parent_sha in self._commit_items:
                    parent_commit_item = self._commit_items[parent_sha]

                    # Edge color can be from child (commit_node) or parent.
                    # Using child's color for the incoming edge is common.
                    edge = EdgeLine(parent_commit_item, current_commit_item, color=edge_color_for_commit)
                    self.scene.addItem(edge)
                    self._edge_items.append(edge)

        # Adjust scene rect after all items are added and positioned
        self.scene.setSceneRect(self.scene.itemsBoundingRect().adjusted(0, -50, 50, 50))  # Add some padding

    def load_repository(self, repo_path: str = "."):
        """High-level method to parse, layout, and display a repository's graph."""
        commits = parse_git_log(repo_path)
        if commits:
            calculate_commit_positions(commits)
            self.populate_graph(commits)
        else:
            self.clear_graph()  # Clear if parsing fails or no commits
            print(f"No commits found or error parsing repository at {repo_path}")

    def wheelEvent(self, event):
        """Handle mouse wheel events for zooming."""
        # Check if Ctrl is pressed for zooming, otherwise default scroll behavior
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.angleDelta().y() > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            event.accept()  # Indicate that the event has been handled
        else:
            super().wheelEvent(event)  # Default behavior (scrolling)

    def zoom_in(self):
        self.scale(self._zoom_factor_base, self._zoom_factor_base)

    def zoom_out(self):
        self.scale(1.0 / self._zoom_factor_base, 1.0 / self._zoom_factor_base)

    def keyPressEvent(self, event):
        """Handle key presses for zooming or other actions."""
        if event.key() == Qt.Key.Key_Plus or event.key() == Qt.Key.Key_Equal:
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:  # Ctrl + / Ctrl =
                self.zoom_in()
        elif event.key() == Qt.Key.Key_Minus:
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:  # Ctrl -
                self.zoom_out()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            item = self.itemAt(event.pos())
            if isinstance(item, CommitCircle):
                commit_sha = item.commit_node.sha
                self.commit_item_clicked.emit(commit_sha)
                # event.accept() # Optionally accept the event if it's fully handled
                # return # Return if you don't want further processing
        super().mousePressEvent(event)  # Call super for other event processing (like panning)

    def _show_context_menu(self, pos):
        """Show context menu for right-click on a commit circle."""
        scene_pos = self.mapToScene(pos)
        item = self.scene.itemAt(scene_pos, self.transform())

        if isinstance(item, CommitCircle):
            menu = QMenu(self)

            # Add "Copy Commit" action
            copy_action = QAction("Copy Commit", self)
            copy_action.triggered.connect(lambda: self._copy_commit_sha(item.commit_node.sha))
            menu.addAction(copy_action)

            # Show menu at cursor position
            menu.exec(self.viewport().mapToGlobal(pos))

    def _copy_commit_sha(self, sha):
        """Copy commit SHA to clipboard."""
        clipboard = QApplication.clipboard()
        clipboard.setText(sha)


if __name__ == "__main__":
    import os
    import sys

    app = QApplication(sys.argv)

    # --- Create a dummy repo for testing if not in one ---
    TEST_REPO_DIR = "temp_test_repo"

    def setup_dummy_repo(repo_dir):
        if os.path.exists(repo_dir):
            # Basic cleanup if exists (BE CAREFUL WITH THIS IN REAL SCENARIOS)
            # For a robust test, proper cleanup (like shutil.rmtree) would be needed.
            # Here, we'll just assume if it exists, it might be usable or we re-init.
            pass
        else:
            os.makedirs(repo_dir)

        original_cwd = os.getcwd()
        os.chdir(repo_dir)

        try:
            # Check if it's already a git repo
            is_git_repo = os.path.exists(".git")
            if not is_git_repo:
                subprocess.run(["git", "init"], check=True, capture_output=True)
                subprocess.run(["git", "config", "user.name", "Test User"], check=True)
                subprocess.run(["git", "config", "user.email", "test@example.com"], check=True)

                with open("file1.txt", "w") as f:
                    f.write("content1")
                subprocess.run(["git", "add", "file1.txt"], check=True)
                subprocess.run(["git", "commit", "-m", "Initial commit"], check=True)

                subprocess.run(["git", "checkout", "-b", "feature_branch"], check=True)
                with open("file2.txt", "w") as f:
                    f.write("content2")
                subprocess.run(["git", "add", "file2.txt"], check=True)
                subprocess.run(["git", "commit", "-m", "Add feature on branch"], check=True)

                subprocess.run(["git", "checkout", "main"], check=True)
                with open("file3.txt", "w") as f:
                    f.write("content3")
                subprocess.run(["git", "add", "file3.txt"], check=True)
                subprocess.run(["git", "commit", "-m", "Add another feature on main"], check=True)

                subprocess.run(["git", "merge", "feature_branch", "-m", "Merge feature_branch"], check=True)

                subprocess.run(["git", "tag", "v1.0"], check=True)

                with open("file4.txt", "w") as f:
                    f.write("content4")
                subprocess.run(["git", "add", "file4.txt"], check=True)
                subprocess.run(["git", "commit", "-m", "Commit after tag"], check=True)

                subprocess.run(["git", "checkout", "-b", "another_branch"], check=True)
                with open("file5.txt", "w") as f:
                    f.write("content5")
                subprocess.run(["git", "add", "file5.txt"], check=True)
                subprocess.run(["git", "commit", "-m", "Work on another branch"], check=True)
                subprocess.run(["git", "checkout", "main"], check=True)

        except Exception as e:
            print(f"Error setting up dummy repo: {e}")
        finally:
            os.chdir(original_cwd)

    # Check if current dir is a git repo, else use/create dummy
    current_path_is_repo = os.path.exists(".git") or os.path.exists("../.git")  # Simple check
    repo_to_load = "."

    if not QApplication.instance().topLevelWidgets():  # Check if running in an env where dummy setup is problematic
        if not current_path_is_repo:
            print(f"Not in a git repo. Setting up a dummy repo in ./{TEST_REPO_DIR}")
            import subprocess  # Make sure it's imported for dummy repo setup

            setup_dummy_repo(TEST_REPO_DIR)
            repo_to_load = TEST_REPO_DIR
        else:
            print(f"Running in current git repository: {os.getcwd()}")
    else:  # Likely in an environment like a dedicated test runner or IDE plugin
        print("Skipping dummy repo setup as other top-level widgets exist or specific environment detected.")
        if not current_path_is_repo:
            print("Warning: Not in a git repository, and dummy setup skipped. Graph may be empty.")

    view = GitGraphView()
    view.load_repository(repo_to_load)  # Load current dir or dummy

    view.setWindowTitle("Git Commit Graph Viewer")
    view.resize(800, 600)
    view.show()

    sys.exit(app.exec())
