import unittest
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QApplication, QComboBox, QTreeWidget, QWidget

# CommitHistoryView is used by GitManagerWindow, but we directly interact with window.commit_history_view
# from commit_history_view import CommitHistoryView 
from git_manager import GitManager

# Application imports
from git_manager_window import GitManagerWindow


class TestBlameAnnotationClick(unittest.TestCase):

    app = None

    @classmethod
    def setUpClass(cls):
        # Ensure a QApplication instance exists for testing Qt widgets
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication([])
            # Store a flag if we created it, to clean up if necessary
            cls._created_qapplication = True


    @classmethod
    def tearDownClass(cls):
        # Clean up QApplication if it was created by this test class
        if hasattr(cls, '_created_qapplication') and cls._created_qapplication:
            if QApplication.instance() is not None: # Check if it still exists
                QApplication.instance().quit() 
        cls.app = None


    def generate_mock_commits(self, count):
        commits = []
        # Generate hashes where the first 7 characters are unique
        base_alphabet = "abcdef0123456789"
        for i in range(count):
            # Create a unique 7-char prefix, then fill the rest
            unique_prefix = f"{i:07d}" # e.g., "0000000", "0000001"
            remaining_chars = "".join(base_alphabet[(i + j) % len(base_alphabet)] for j in range(40 - 7))
            full_hash = unique_prefix + remaining_chars
            commits.append({
                "hash": full_hash,
                "message": f"Commit message {i}",
                "author": "Test Author",
                "date": "2023-01-01 10:00:00"
            })
        return commits

    def test_blame_click_loads_older_commit(self):
        # 1. Mock GitManager
        mock_git_manager = MagicMock(spec=GitManager)
        total_commits = 15 
        mock_commits_data = self.generate_mock_commits(total_commits)
        
        def mock_get_commit_history(branch, limit, skip):
            return mock_commits_data[skip : skip + limit]

        mock_git_manager.get_commit_history.side_effect = mock_get_commit_history
        
        mock_git_manager.repo = MagicMock()
        mocked_commit_obj_for_selection = MagicMock() 
        mock_git_manager.repo.commit = MagicMock(return_value=mocked_commit_obj_for_selection)
        mock_git_manager.get_branches = MagicMock(return_value=["main", "test_branch"])
        mock_git_manager.get_default_branch = MagicMock(return_value="main")
        mock_git_manager.initialize = MagicMock(return_value=True) 


        # 2. Instantiate GitManagerWindow
        with patch('git_manager_window.Settings', MagicMock()) as mock_settings_constructor:
            mock_settings_instance = mock_settings_constructor.return_value
            mock_settings_instance.get_last_folder.return_value = None 
            mock_settings_instance.settings = {} 

            window = GitManagerWindow()

        # 3. Configure CommitHistoryView
        initial_load_batch_size = 5
        window.commit_history_view.load_batch_size = initial_load_batch_size
        
        window.git_manager = mock_git_manager
        
        if hasattr(window.branch_combo, 'currentTextChanged') and window.branch_combo.currentTextChanged is not None:
            try:
                window.branch_combo.currentTextChanged.disconnect()
            except TypeError: 
                pass 
        
        window.update_branches() 
        window.branch_combo.setCurrentText("test_branch") 
        window.update_commit_history() 

        self.assertEqual(window.commit_history_view.history_list.topLevelItemCount(), initial_load_batch_size, "Initial load incorrect")
        self.assertFalse(window.commit_history_view._all_loaded, "Should not be all loaded initially")

        # 4. Target Commit
        target_commit_index = 7 
        self.assertTrue(target_commit_index >= initial_load_batch_size, "Target commit should be outside initial load")
        target_commit_hash = mock_commits_data[target_commit_index]["hash"]
        short_target_hash = target_commit_hash[:7] 
        
        mocked_commit_obj_for_selection.hexsha = target_commit_hash 
        mock_git_manager.repo.commit = MagicMock(return_value=mocked_commit_obj_for_selection)

        found_before_click = False
        for i in range(window.commit_history_view.history_list.topLevelItemCount()):
            item_short_hash = window.commit_history_view.history_list.topLevelItem(i).text(0)
            if item_short_hash == short_target_hash:
                found_before_click = True
                break
        self.assertFalse(found_before_click, f"Target commit {short_target_hash} should not be loaded yet. Loaded items: {[window.commit_history_view.history_list.topLevelItem(i).text(0) for i in range(window.commit_history_view.history_list.topLevelItemCount())]}")

        # 5. Simulate Blame Click
        window.handle_blame_click_from_editor(target_commit_hash)

        # 6. Verify Commit Selection
        current_item = window.commit_history_view.history_list.currentItem()
        self.assertIsNotNone(current_item, "No item selected after blame click")
        self.assertEqual(current_item.text(0), short_target_hash, "Incorrect commit selected")
        
        expected_loaded_count = initial_load_batch_size * 2 
        self.assertEqual(window.commit_history_view.history_list.topLevelItemCount(), expected_loaded_count, "More commits should have been loaded")
        self.assertEqual(window.commit_history_view.loaded_count, expected_loaded_count, "loaded_count property incorrect")

        # 7. Verify Tab Switch
        self.assertEqual(window.tab_widget.currentIndex(), 0, "'提交历史' tab not selected")

        if expected_loaded_count >= total_commits : 
            self.assertTrue(window.commit_history_view._all_loaded, "_all_loaded should be true if all commits are now loaded")
        else:
            self.assertFalse(window.commit_history_view._all_loaded, "_all_loaded should be false if not all commits are loaded")

    def test_blame_click_loads_commit_when_all_commits_needed(self):
        # 1. Mock GitManager
        mock_git_manager = MagicMock(spec=GitManager)
        total_commits = 8  # e.g. 3 batches: 0-2, 3-5, 6-7
        mock_commits_data = self.generate_mock_commits(total_commits)
        
        def mock_get_commit_history(branch, limit, skip):
            return mock_commits_data[skip : skip + limit]

        mock_git_manager.get_commit_history.side_effect = mock_get_commit_history
        
        mock_git_manager.repo = MagicMock()
        mocked_commit_obj_for_selection = MagicMock() 
        mock_git_manager.repo.commit = MagicMock(return_value=mocked_commit_obj_for_selection)
        mock_git_manager.get_branches = MagicMock(return_value=["main", "test_branch"])
        mock_git_manager.get_default_branch = MagicMock(return_value="main")
        mock_git_manager.initialize = MagicMock(return_value=True) 

        # 2. Instantiate GitManagerWindow
        with patch('git_manager_window.Settings', MagicMock()) as mock_settings_constructor:
            mock_settings_instance = mock_settings_constructor.return_value
            mock_settings_instance.get_last_folder.return_value = None 
            mock_settings_instance.settings = {}

            window = GitManagerWindow()

        # 3. Configure CommitHistoryView
        initial_load_batch_size = 3 # Small batch size
        window.commit_history_view.load_batch_size = initial_load_batch_size
        
        window.git_manager = mock_git_manager
        
        if hasattr(window.branch_combo, 'currentTextChanged') and window.branch_combo.currentTextChanged is not None:
            try:
                window.branch_combo.currentTextChanged.disconnect()
            except TypeError: 
                pass 
        
        window.update_branches() 
        window.branch_combo.setCurrentText("test_branch") 
        window.update_commit_history() 

        self.assertEqual(window.commit_history_view.history_list.topLevelItemCount(), initial_load_batch_size, "Initial load incorrect")
        self.assertFalse(window.commit_history_view._all_loaded, "Should not be all loaded initially after first batch")

        # 4. Target Commit - e.g., the second to last commit (index 6 for total_commits=8)
        # This should force loading all batches.
        target_commit_index = total_commits - 2 # Commit index 6
        self.assertTrue(target_commit_index >= initial_load_batch_size, "Target commit should be outside initial load")
        target_commit_hash = mock_commits_data[target_commit_index]["hash"]
        short_target_hash = target_commit_hash[:7]
        
        mocked_commit_obj_for_selection.hexsha = target_commit_hash 
        mock_git_manager.repo.commit = MagicMock(return_value=mocked_commit_obj_for_selection)

        found_before_click = False
        for i in range(window.commit_history_view.history_list.topLevelItemCount()):
            item_short_hash = window.commit_history_view.history_list.topLevelItem(i).text(0)
            if item_short_hash == short_target_hash:
                found_before_click = True
                break
        self.assertFalse(found_before_click, f"Target commit {short_target_hash} should not be loaded yet.")

        # 5. Simulate Blame Click
        window.handle_blame_click_from_editor(target_commit_hash)

        # 6. Verify Commit Selection
        current_item = window.commit_history_view.history_list.currentItem()
        self.assertIsNotNone(current_item, "No item selected after blame click")
        self.assertEqual(current_item.text(0), short_target_hash, "Incorrect commit selected")
        
        # All commits should now be loaded
        self.assertEqual(window.commit_history_view.history_list.topLevelItemCount(), total_commits, "All commits should have been loaded")
        self.assertEqual(window.commit_history_view.loaded_count, total_commits, "loaded_count should be total_commits")

        # 7. Verify Tab Switch
        self.assertEqual(window.tab_widget.currentIndex(), 0, "'提交历史' tab not selected")

        # 8. Verify All Commits Loaded state
        self.assertTrue(window.commit_history_view._all_loaded, "_all_loaded should be true as target forces loading all batches")


if __name__ == '__main__':
    unittest.main()
