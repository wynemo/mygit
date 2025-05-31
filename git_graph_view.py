# git_graph_view.py

from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene, QApplication, QGraphicsItem
from PyQt5.QtGui import QPainter, QTransform, QColor
from PyQt5.QtCore import Qt, QRectF

from git_graph_data import CommitNode
from git_graph_items import CommitCircle, EdgeLine, ReferenceLabel, COLOR_PALETTE, COMMIT_RADIUS
from git_log_parser import parse_git_log
from git_graph_layout import calculate_commit_positions

class GitGraphView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)

        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag) # Enable panning
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse) # Zoom towards mouse

        self._commit_items: dict[str, CommitCircle] = {}
        self._edge_items: list[EdgeLine] = []
        self._ref_labels: list[ReferenceLabel] = []

        self._zoom_factor_base = 1.1 # Base factor for zooming

    def clear_graph(self):
        self.scene.clear()
        self._commit_items.clear()
        self._edge_items.clear()
        self._ref_labels.clear()

    def populate_graph(self, commits: list[CommitNode]):
        self.clear_graph()

        if not commits:
            # Handle case with no commits (e.g., empty repo or error)
            # Maybe display a message in the view or scene
            return

        # First pass: Create all commit circles and reference labels
        for commit_node in commits:
            # Create CommitCircle
            # Use commit_node.color_idx for the color palette index
            color = COLOR_PALETTE[commit_node.color_idx % len(COLOR_PALETTE)]
            commit_item = CommitCircle(commit_node, color_idx=commit_node.color_idx)
            commit_item.setPos(commit_node.x, commit_node.y)
            self.scene.addItem(commit_item)
            self._commit_items[commit_node.sha] = commit_item

            # Create ReferenceLabels (basic positioning, might overlap if many)
            ref_y_offset = -COMMIT_RADIUS - 5 # Start above the commit circle
            for ref_text in commit_node.references:
                is_head = "HEAD" in ref_text
                is_tag = "tag:" in ref_text # Simple check

                ref_label = ReferenceLabel(ref_text, commit_item, is_head=is_head, is_tag=is_tag)

                # Adjust position of ReferenceLabel relative to its CommitCircle item
                # This uses the CommitCircle's current scene position
                label_x = commit_node.x + COMMIT_RADIUS + 5 # To the right
                label_y = commit_node.y + ref_y_offset
                ref_label.setPos(label_x, label_y)

                self.scene.addItem(ref_label)
                self._ref_labels.append(ref_label)
                ref_y_offset -= ref_label.boundingRect().height() # Stack them upwards

        # Second pass: Create edges
        for commit_node in commits:
            if commit_node.sha not in self._commit_items:
                continue # Should not happen if first pass was successful

            current_commit_item = self._commit_items[commit_node.sha]
            edge_color = COLOR_PALETTE[commit_node.color_idx % len(COLOR_PALETTE)]

            for parent_sha in commit_node.parents:
                if parent_sha in self._commit_items:
                    parent_commit_item = self._commit_items[parent_sha]

                    # Edge color can be from child (commit_node) or parent.
                    # Using child's color for the incoming edge is common.
                    edge = EdgeLine(parent_commit_item, current_commit_item, color=edge_color)
                    self.scene.addItem(edge)
                    self._edge_items.append(edge)

        # Adjust scene rect after all items are added and positioned
        self.scene.setSceneRect(self.scene.itemsBoundingRect().adjusted(-50, -50, 50, 50)) # Add some padding

    def load_repository(self, repo_path: str = "."):
        """High-level method to parse, layout, and display a repository's graph."""
        commits = parse_git_log(repo_path)
        if commits:
            calculate_commit_positions(commits)
            self.populate_graph(commits)
        else:
            self.clear_graph() # Clear if parsing fails or no commits
            print(f"No commits found or error parsing repository at {repo_path}")


    def wheelEvent(self, event):
        """Handle mouse wheel events for zooming."""
        # Check if Ctrl is pressed for zooming, otherwise default scroll behavior
        if event.modifiers() & Qt.ControlModifier:
            if event.angleDelta().y() > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            event.accept() # Indicate that the event has been handled
        else:
            super().wheelEvent(event) # Default behavior (scrolling)

    def zoom_in(self):
        self.scale(self._zoom_factor_base, self._zoom_factor_base)

    def zoom_out(self):
        self.scale(1.0 / self._zoom_factor_base, 1.0 / self._zoom_factor_base)

    def keyPressEvent(self, event):
        """Handle key presses for zooming or other actions."""
        if event.key() == Qt.Key_Plus or event.key() == Qt.Key_Equal:
            if event.modifiers() & Qt.ControlModifier: # Ctrl + / Ctrl =
                 self.zoom_in()
        elif event.key() == Qt.Key_Minus:
            if event.modifiers() & Qt.ControlModifier: # Ctrl -
                self.zoom_out()
        else:
            super().keyPressEvent(event)


if __name__ == '__main__':
    import sys
    import os

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

                 with open("file1.txt", "w") as f: f.write("content1")
                 subprocess.run(["git", "add", "file1.txt"], check=True)
                 subprocess.run(["git", "commit", "-m", "Initial commit"], check=True)

                 subprocess.run(["git", "checkout", "-b", "feature_branch"], check=True)
                 with open("file2.txt", "w") as f: f.write("content2")
                 subprocess.run(["git", "add", "file2.txt"], check=True)
                 subprocess.run(["git", "commit", "-m", "Add feature on branch"], check=True)

                 subprocess.run(["git", "checkout", "main"], check=True)
                 with open("file3.txt", "w") as f: f.write("content3")
                 subprocess.run(["git", "add", "file3.txt"], check=True)
                 subprocess.run(["git", "commit", "-m", "Add another feature on main"], check=True)

                 subprocess.run(["git", "merge", "feature_branch", "-m", "Merge feature_branch"], check=True)

                 subprocess.run(["git", "tag", "v1.0"], check=True)

                 with open("file4.txt", "w") as f: f.write("content4")
                 subprocess.run(["git", "add", "file4.txt"], check=True)
                 subprocess.run(["git", "commit", "-m", "Commit after tag"], check=True)

                 subprocess.run(["git", "checkout", "-b", "another_branch"], check=True)
                 with open("file5.txt", "w") as f: f.write("content5")
                 subprocess.run(["git", "add", "file5.txt"], check=True)
                 subprocess.run(["git", "commit", "-m", "Work on another branch"], check=True)
                 subprocess.run(["git", "checkout", "main"], check=True)


        except Exception as e:
            print(f"Error setting up dummy repo: {e}")
        finally:
            os.chdir(original_cwd)

    # Check if current dir is a git repo, else use/create dummy
    current_path_is_repo = os.path.exists(".git") or os.path.exists("../.git") # Simple check
    repo_to_load = "."

    if not QApplication.instance().topLevelWidgets(): # Check if running in an env where dummy setup is problematic
        if not current_path_is_repo:
            print(f"Not in a git repo. Setting up a dummy repo in ./{TEST_REPO_DIR}")
            import subprocess # Make sure it's imported for dummy repo setup
            setup_dummy_repo(TEST_REPO_DIR)
            repo_to_load = TEST_REPO_DIR
        else:
            print(f"Running in current git repository: {os.getcwd()}")
    else: # Likely in an environment like a dedicated test runner or IDE plugin
        print("Skipping dummy repo setup as other top-level widgets exist or specific environment detected.")
        if not current_path_is_repo:
            print("Warning: Not in a git repository, and dummy setup skipped. Graph may be empty.")


    view = GitGraphView()
    view.load_repository(repo_to_load) # Load current dir or dummy

    view.setWindowTitle("Git Commit Graph Viewer")
    view.resize(800, 600)
    view.show()

    sys.exit(app.exec_())
