import unittest
import tempfile
import shutil
import os
import git # GitPython
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt # For Qt.GlobalColor if needed

# Adjust import paths if necessary
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from git_manager import GitManager
from workspace_explorer import WorkspaceExplorer # This contains FileTreeWidget

# It's good practice to have a QApplication instance for widget tests
app = None

def setUpModule():
    global app
    app = QApplication.instance()
    if app is None:
        # Pass sys.argv or [] if no arguments are needed by QApplication
        app = QApplication(sys.argv if hasattr(sys, 'argv') else [])

def tearDownModule():
    global app
    # QApplication uses atexit to clean up, explicitly calling quit/exit might be problematic
    # Depending on test runner, app might be None or already cleaned up
    if app is not None:
        # app.exit() # This can sometimes hang in test environments
        app.quit() # Prefer quit for event loop termination
    app = None


class TestFileTreeStatusColors(unittest.TestCase):
    def setUp(self):
        self.repo_path = tempfile.mkdtemp()
        self.repo = git.Repo.init(self.repo_path)
        
        # Initial commit for a normal file
        self.normal_file_rel = "normal_file.txt"
        self.normal_file_abs = os.path.join(self.repo_path, self.normal_file_rel)
        with open(self.normal_file_abs, "w") as f:
            f.write("Normal content")
        self.repo.index.add([self.normal_file_abs])
        self.repo.index.commit("Initial commit with normal_file.txt")

        self.git_manager = GitManager(self.repo_path)
        self.git_manager.initialize()
        
        # WorkspaceExplorer now takes git_manager in its constructor
        self.workspace_explorer = WorkspaceExplorer(git_manager=self.git_manager)
        # No need to call set_workspace_path here if we do it per test or if setup should reflect an empty state first


    def tearDown(self):
        # Explicitly close any open tabs in workspace_explorer to free resources if necessary
        if hasattr(self.workspace_explorer, 'tab_widget'):
            for i in range(self.workspace_explorer.tab_widget.count()):
                self.workspace_explorer.tab_widget.removeTab(0) # Remove always the first one
        
        # If WorkspaceExplorer or its children create persistent resources, clean them here
        # self.workspace_explorer.deleteLater() # Example if it were a QObject needing cleanup
        
        shutil.rmtree(self.repo_path)

    def find_item_in_tree(self, file_tree, item_name):
        root = file_tree.invisibleRootItem()
        for i in range(root.childCount()):
            child_item = root.child(i)
            if child_item.text(0) == item_name:
                return child_item
        return None

    def test_modified_file_is_brown(self):
        modified_file_rel = "modified_file.txt"
        modified_file_abs = os.path.join(self.repo_path, modified_file_rel)
        
        # Create and commit the file first so it's tracked
        with open(modified_file_abs, "w") as f:
            f.write("Original content for modification")
        self.repo.index.add([modified_file_abs])
        self.repo.index.commit("Add file to be modified")

        # Now modify it in the working directory
        with open(modified_file_abs, "w") as f:
            f.write("This content is modified")

        # Refresh the file tree to reflect changes
        self.workspace_explorer.set_workspace_path(self.repo_path) 

        file_tree = self.workspace_explorer.file_tree
        item_found = self.find_item_in_tree(file_tree, modified_file_rel)
        
        self.assertIsNotNone(item_found, f"Modified file '{modified_file_rel}' not found in tree")
        expected_color = QColor(165, 42, 42) # Brown color used in implementation
        # Item's foreground is a QBrush, get its color.
        self.assertEqual(item_found.foreground(0).color().rgb(), expected_color.rgb(), "Modified file color is not brown")

    def test_normal_file_default_color(self):
        # Refresh the file tree
        self.workspace_explorer.set_workspace_path(self.repo_path)

        file_tree = self.workspace_explorer.file_tree
        item_found = self.find_item_in_tree(file_tree, self.normal_file_rel)
        
        self.assertIsNotNone(item_found, f"Normal file '{self.normal_file_rel}' not found in tree")
        
        # Check it's NOT brown. The actual default color can vary (system theme, Qt styling).
        # We check if a color was explicitly set by our logic. If not, it's default.
        # foreground(0) returns a QBrush. If no explicit color set, it might be a default brush.
        # A more direct check is to see if the color is the one we set for modified files.
        brown_color = QColor(165, 42, 42)
        
        # If item.foreground(0) was never set, its .color() might be black by default or theme-dependent.
        # The key is that it should not be the "modified" color.
        current_color = item_found.foreground(0).color()
        self.assertNotEqual(current_color.rgb(), brown_color.rgb(), "Normal file color should not be brown")

        # Optional: More specific check if you know the default (e.g. black)
        # default_text_color = QColor(Qt.GlobalColor.black) # Or another default
        # self.assertEqual(current_color.rgb(), default_text_color.rgb(), "Normal file color is not the expected default.")


if __name__ == "__main__":
    unittest.main()
