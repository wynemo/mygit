import unittest
from unittest.mock import MagicMock, patch, mock_open
import sys
import os

from PyQt6.QtWidgets import QApplication, QTreeWidgetItem
from PyQt6.QtCore import QPoint, Qt, QEvent
from PyQt6.QtGui import QMouseEvent

# Add project root to sys.path to allow importing project modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from main_window import GitManagerWindow
# CompareView is no longer the primary target for this test's SyncedTextEdit
# from compare_view import CompareView 
from commit_history_view import CommitHistoryView
from text_edit import SyncedTextEdit, LineNumberArea
from workspace_explorer import WorkspaceExplorer


# Ensure a QApplication instance exists for testing PyQt widgets
app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

class TestBlameAnnotationClickWorkspace(unittest.TestCase): # Renamed for clarity
    @classmethod
    def setUpClass(cls):
        cls.git_manager_patcher = patch('git_manager.GitManager')
        cls.MockGitManager = cls.git_manager_patcher.start()
        
        cls.mock_git_manager_instance = cls.MockGitManager.return_value
        cls.mock_git_manager_instance.repo_path = "/tmp/mockrepo"
        # Default blame data for get_blame_data, will be overridden in setUp
        cls.mock_git_manager_instance.get_blame_data.return_value = [] 

    @classmethod
    def tearDownClass(cls):
        cls.git_manager_patcher.stop()

    def setUp(self):
        """Set up the test environment before each test method."""
        self.main_window = GitManagerWindow(testing_mode=True)
        self.workspace_explorer = self.main_window.workspace_explorer
        self.commit_history_view = self.main_window.commit_history_view

        self.commit_history_view.history_list.clear()
        
        self.commit_hashes = {
            "abcdef0": "abcdef0123456789abcdef0123456789abcdef0",
            "1234567": "1234567890123456789012345678901234567890",
            "fedcba9": "fedcba9876543210fedcba9876543210fedcba9"
        }
        for short_hash in self.commit_hashes.keys():
            item = QTreeWidgetItem([short_hash, "Test Author", "Test Date", "Test Message"])
            self.commit_history_view.history_list.addTopLevelItem(item)

        self.sample_blame_data = [
            {'commit_hash': self.commit_hashes["abcdef0"], 'author_name': 'Author A', 'committed_date': '2023-01-01', 'line_no': 1}, # _display_string is added by set_blame_data
            {'commit_hash': self.commit_hashes["1234567"], 'author_name': 'Author B', 'committed_date': '2023-01-02', 'line_no': 2},
            {'commit_hash': self.commit_hashes["fedcba9"], 'author_name': 'Author C', 'committed_date': '2023-01-03', 'line_no': 3},
        ]
        
        # Patch GitManager's get_blame_data to return our sample data for the show_blame call
        self.mock_git_manager_instance.get_blame_data.return_value = self.sample_blame_data

        self.mock_file_path = os.path.join(self.mock_git_manager_instance.repo_path, "test_file.py")
        
        # Mock builtins.open for workspace_explorer.open_file_in_tab
        mock_file_content = "Line 1 content\nLine 2 content\nLine 3 content\nLine 4 content"
        with patch('builtins.open', new_callable=mock_open, read_data=mock_file_content):
            self.workspace_explorer.open_file_in_tab(self.mock_file_path)
        
        self.synced_text_edit = self.workspace_explorer.tab_widget.currentWidget()
        self.assertIsInstance(self.synced_text_edit, SyncedTextEdit, "WorkspaceExplorer did not open SyncedTextEdit.")
        
        # Call show_blame() on the SyncedTextEdit instance.
        # show_blame() internally calls git_manager.get_blame_data and then set_blame_data().
        # The SyncedTextEdit needs its file_path property set, which open_file_in_tab should do.
        self.assertEqual(self.synced_text_edit.property("file_path"), self.mock_file_path)
        self.synced_text_edit.show_blame() # This will use the patched get_blame_data

        # Ensure blame data is actually loaded for the test to be valid
        self.assertTrue(self.synced_text_edit.showing_blame, "Blame data not showing in SyncedTextEdit after show_blame().")
        self.assertEqual(len(self.synced_text_edit.blame_annotations_per_line), len(self.sample_blame_data))

        # Patch GitManagerWindow.handle_blame_click_from_editor
        self.main_window.handle_blame_click_from_editor = MagicMock(
            wraps=self.main_window.handle_blame_click_from_editor
        )
        
        # Mock the on_commit_clicked method of CommitHistoryView
        self.commit_history_view.on_commit_clicked = MagicMock(
            wraps=self.commit_history_view.on_commit_clicked
        )

    def test_blame_click_handled_by_gitmanagerwindow(self):
        """Test blame click in WorkspaceExplorer's editor is handled by GitManagerWindow."""
        target_line_index = 1 # Corresponds to sample_blame_data[1], short hash "1234567"
        target_commit_short_hash = "1234567"
        expected_full_hash = self.commit_hashes[target_commit_short_hash]

        line_number_area = self.synced_text_edit.line_number_area

        block = self.synced_text_edit.document().findBlockByNumber(target_line_index)
        if not block.isValid():
            self.fail(f"Block for line index {target_line_index} is not valid.")

        block_top = self.synced_text_edit.blockBoundingGeometry(block).translated(self.synced_text_edit.contentOffset()).top()
        block_height = self.synced_text_edit.blockBoundingRect(block).height()
        click_y = int(block_top + block_height / 2)
        click_x = self.synced_text_edit.PADDING_LEFT_OF_BLAME + 5 

        mouse_event = QMouseEvent(
            QEvent.Type.MouseButtonPress, QPoint(click_x, click_y),
            Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier
        )

        line_number_area.mousePressEvent(mouse_event)
        QApplication.processEvents()

        # Assert that GitManagerWindow.handle_blame_click_from_editor was called
        self.main_window.handle_blame_click_from_editor.assert_called_once_with(expected_full_hash)

        # Assert UI updates triggered by handle_blame_click_from_editor
        current_history_item = self.commit_history_view.history_list.currentItem()
        self.assertIsNotNone(current_history_item, "No item selected in commit history.")
        self.assertEqual(current_history_item.text(0), target_commit_short_hash, "Incorrect commit selected.")

        # Assert that CommitHistoryView.on_commit_clicked was called by the handler
        # The handler calls it with just the item.
        self.commit_history_view.on_commit_clicked.assert_called_once_with(current_history_item)

        self.assertEqual(self.main_window.tab_widget.currentIndex(), 0, "Commit history tab not selected.")

    def tearDown(self):
        """Clean up after each test method."""
        # Close any tabs opened in workspace_explorer
        if self.workspace_explorer and self.workspace_explorer.tab_widget:
            while self.workspace_explorer.tab_widget.count() > 0:
                self.workspace_explorer.tab_widget.removeTab(0)
        
        self.main_window.close()
        # QApplication.processEvents() # Process events from closing, if necessary

if __name__ == "__main__":
    unittest.main()
