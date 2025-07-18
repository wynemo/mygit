import os
import shutil

# Assuming GitManager is in a module that can be imported, e.g., from git_manager import GitManager
# Adjust the import path if your GitManager is in a subdirectory or package
import sys
import tempfile
import unittest
from datetime import datetime, timezone

import git  # Make sure 'gitpython' is installed in the test environment
from git import Actor

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from git_manager import GitManager


class TestGitManagerFileStatus(unittest.TestCase):
    def setUp(self):
        self.repo_path = tempfile.mkdtemp()
        self.repo = git.Repo.init(self.repo_path)
        self.git_manager = GitManager(self.repo_path)
        # initialize() is called implicitly by get_file_status if repo is None,
        # but it's good practice to ensure it's ready for tests.
        self.git_manager.initialize() 

        # Create an initial commit
        self.initial_file_rel = "initial_file.txt"
        self.initial_file_abs = os.path.join(self.repo_path, self.initial_file_rel)
        with open(self.initial_file_abs, "w") as f:
            f.write("Initial content")
        self.repo.index.add([self.initial_file_rel])
        self.repo.index.commit("Initial commit")

    def tearDown(self):
        shutil.rmtree(self.repo_path)

    def test_get_status_normal(self):
        status = self.git_manager.get_file_status(self.initial_file_abs)
        self.assertEqual(status, "normal")

    def test_get_status_modified(self):
        with open(self.initial_file_abs, "w") as f:
            f.write("Modified content")
        status = self.git_manager.get_file_status(self.initial_file_abs)
        self.assertEqual(status, "modified")

    def test_get_status_staged(self):
        staged_file_rel = "staged_file.txt"
        staged_file_abs = os.path.join(self.repo_path, staged_file_rel)
        with open(staged_file_abs, "w") as f:
            f.write("Content to be staged")
        self.repo.index.add([staged_file_rel])
        status = self.git_manager.get_file_status(staged_file_abs)
        self.assertEqual(status, "staged")
        
        # Test case for a file that is staged and then modified
        # The current implementation of get_file_status checks for modified (unstaged) first.
        # So, a file that is staged and then modified again in the working directory
        # will be reported as "modified".
        modified_after_stage_rel = "mod_after_stage.txt"
        modified_after_stage_abs = os.path.join(self.repo_path, modified_after_stage_rel)
        with open(modified_after_stage_abs, "w") as f:
            f.write("Content")
        self.repo.index.add([modified_after_stage_rel]) # Stage it
        with open(modified_after_stage_abs, "w") as f: # Modify it again in the working directory
            f.write("Modified content after stage")
        status_mod_after_stage = self.git_manager.get_file_status(modified_after_stage_abs)
        self.assertEqual(status_mod_after_stage, "modified")

    def test_get_status_untracked(self):
        untracked_file_rel = "untracked_file.txt"
        untracked_file_abs = os.path.join(self.repo_path, untracked_file_rel)
        with open(untracked_file_abs, "w") as f:
            f.write("Untracked content")
        status = self.git_manager.get_file_status(untracked_file_abs)
        self.assertEqual(status, "untracked")

    def test_get_status_non_repo_file(self):
        # Create a temporary file outside the repo
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file_path = tmp_file.name
        
        status = self.git_manager.get_file_status(tmp_file_path)
        # According to the implementation, a file outside the repo path is "untracked"
        self.assertEqual(status, "untracked") 
        
        os.remove(tmp_file_path) # Clean up the temporary file

    def test_get_status_invalid_path(self):
        # A path that does not exist anywhere
        invalid_path = os.path.join(self.repo_path, "non_existent_file.txt")
        status = self.git_manager.get_file_status(invalid_path)
        # If a file doesn't exist, it's considered "untracked" by the logic
        # (specifically, it won't be in untracked_files, diffs, or tree, leading to "normal"
        #  unless it's explicitly handled. The current logic would likely return "normal"
        #  if it's not in untracked, modified, or staged, and not in HEAD.
        #  Let's trace:
        #  1. Not in untracked_files (because it doesn't exist to be listed by git ls-files --others)
        #  2. Not in index.diff(None)
        #  3. Not in index.diff("HEAD")
        #  4. Not in repo.head.commit.tree (KeyError) -> then returns "normal"
        # This behavior might need adjustment in GitManager for non-existent files.
        # For now, let's assert the current behavior.
        # Based on current get_file_status, an invalid path that's not explicitly an error
        # and doesn't fall into other categories might return "normal" due to the final fallback.
        # However, repo.untracked_files for a non-existent file is an empty list.
        # It won't be in diffs.
        # It won't be in the tree.
        # The current implementation's `os.path.abspath(file_path)` will work.
        # `os.path.relpath` will also work.
        # `self.repo.untracked_files` won't list it.
        # Diffs won't list it.
        # `self.repo.head.commit.tree[relative_file_path]` will raise KeyError.
        # So it falls to the final `return "normal"`.
        # This is arguably a case that could be "unknown" or specifically "non-existent".
        # Given the current code, it will be "normal".
        self.assertEqual(status, "normal") # This reflects the current code's behavior for non-existent paths within repo.


    def test_get_status_subdirectory_file(self):
        subdir_name = "subdir"
        os.makedirs(os.path.join(self.repo_path, subdir_name), exist_ok=True)
        
        # Normal file in subdir
        normal_subdir_file_rel = os.path.join(subdir_name, "normal_in_subdir.txt")
        normal_subdir_file_abs = os.path.join(self.repo_path, normal_subdir_file_rel)
        with open(normal_subdir_file_abs, "w") as f:
            f.write("Normal content in subdir")
        self.repo.index.add([normal_subdir_file_rel])
        self.repo.index.commit("Add normal file in subdir")
        status_normal = self.git_manager.get_file_status(normal_subdir_file_abs)
        self.assertEqual(status_normal, "normal")

        # Modified file in subdir
        modified_subdir_file_rel = os.path.join(subdir_name, "modified_in_subdir.txt")
        modified_subdir_file_abs = os.path.join(self.repo_path, modified_subdir_file_rel)
        with open(modified_subdir_file_abs, "w") as f:
            f.write("Original for modified in subdir")
        self.repo.index.add([modified_subdir_file_rel])
        self.repo.index.commit("Add file to be modified in subdir")
        with open(modified_subdir_file_abs, "w") as f:
            f.write("This is modified in subdir")
        status_modified = self.git_manager.get_file_status(modified_subdir_file_abs)
        self.assertEqual(status_modified, "modified")

        # Staged file in subdir
        staged_subdir_file_rel = os.path.join(subdir_name, "staged_in_subdir.txt")
        staged_subdir_file_abs = os.path.join(self.repo_path, staged_subdir_file_rel)
        with open(staged_subdir_file_abs, "w") as f:
            f.write("Content to be staged in subdir")
        self.repo.index.add([staged_subdir_file_rel])
        status_staged = self.git_manager.get_file_status(staged_subdir_file_abs)
        self.assertEqual(status_staged, "staged")

        # Untracked file in subdir
        untracked_subdir_file_rel = os.path.join(subdir_name, "untracked_in_subdir.txt")
        untracked_subdir_file_abs = os.path.join(self.repo_path, untracked_subdir_file_rel)
        with open(untracked_subdir_file_abs, "w") as f:
            f.write("Untracked content in subdir")
        status_untracked = self.git_manager.get_file_status(untracked_subdir_file_abs)
        self.assertEqual(status_untracked, "untracked")

    def test_get_all_statuses_initial_repo(self):
        """Test get_all_file_statuses on a clean repository."""
        # In the setUp, an initial_file.txt is created and committed.
        # So, the repo is clean with one file.
        statuses = self.git_manager.get_all_file_statuses()
        
        self.assertEqual(len(statuses["modified"]), 0, "Modified set should be empty")
        self.assertEqual(len(statuses["staged"]), 0, "Staged set should be empty")
        self.assertEqual(len(statuses["untracked"]), 0, "Untracked set should be empty")

    def test_get_all_statuses_with_changes(self):
        # Normal file (already committed in setUp as initial_file.txt)
        normal_file_rel = self.initial_file_rel # "initial_file.txt"

        # Modified file
        modified_file_rel = "modified_file.txt"
        modified_file_abs = os.path.join(self.repo_path, modified_file_rel)
        with open(modified_file_abs, "w") as f: f.write("content")
        self.repo.index.add([modified_file_abs])
        self.repo.index.commit("add modified_file")
        with open(modified_file_abs, "w") as f: f.write("new content") # Modified

        # Staged file
        staged_file_rel = "staged_file.txt"
        staged_file_abs = os.path.join(self.repo_path, staged_file_rel)
        with open(staged_file_abs, "w") as f: f.write("content to be staged")
        self.repo.index.add([staged_file_abs]) # Staged

        # Untracked file
        untracked_file_rel = "untracked_file.txt"
        # untracked_file_abs = os.path.join(self.repo_path, untracked_file_rel) # Not needed for untracked
        with open(os.path.join(self.repo_path, untracked_file_rel), "w") as f: f.write("untracked content")

        # Staged then modified file
        staged_mod_file_rel = "staged_mod_file.txt"
        staged_mod_file_abs = os.path.join(self.repo_path, staged_mod_file_rel)
        with open(staged_mod_file_abs, "w") as f: f.write("content")
        self.repo.index.add([staged_mod_file_abs]) # Staged
        with open(staged_mod_file_abs, "w") as f: f.write("modified after stage") # Then modified

        statuses = self.git_manager.get_all_file_statuses()

        # GitPython paths are usually with forward slashes, ensure consistency if needed
        # For these simple filenames, it should be fine.
        self.assertIn(modified_file_rel, statuses["modified"])
        self.assertIn(staged_file_rel, statuses["staged"])
        self.assertIn(untracked_file_rel, statuses["untracked"])
        
        self.assertIn(staged_mod_file_rel, statuses["modified"]) # Has unstaged changes
        self.assertIn(staged_mod_file_rel, statuses["staged"])   # Also has staged changes against HEAD

        self.assertNotIn(normal_file_rel, statuses["modified"])
        self.assertNotIn(normal_file_rel, statuses["staged"])
        self.assertNotIn(normal_file_rel, statuses["untracked"])

        # Ensure no overlaps where not expected (e.g. untracked should not be in modified/staged)
        self.assertNotIn(untracked_file_rel, statuses["modified"])
        self.assertNotIn(untracked_file_rel, statuses["staged"])

    def test_get_all_statuses_with_subdirectories(self):
        subdir_name = "mysubdir"
        os.makedirs(os.path.join(self.repo_path, subdir_name), exist_ok=True)

        # Modified file in subdir
        mod_subdir_rel = os.path.join(subdir_name, "mod_in_sub.txt").replace(os.sep, '/')
        mod_subdir_abs = os.path.join(self.repo_path, mod_subdir_rel)
        with open(mod_subdir_abs, "w") as f: f.write("content")
        self.repo.index.add([mod_subdir_rel])
        self.repo.index.commit(f"add {mod_subdir_rel}")
        with open(mod_subdir_abs, "w") as f: f.write("new content in subdir") # Modified

        # Staged file in subdir
        staged_subdir_rel = os.path.join(subdir_name, "staged_in_sub.txt").replace(os.sep, '/')
        staged_subdir_abs = os.path.join(self.repo_path, staged_subdir_rel)
        with open(staged_subdir_abs, "w") as f: f.write("content to be staged in subdir")
        self.repo.index.add([staged_subdir_rel]) # Staged

        # Untracked file in subdir
        untracked_subdir_rel = os.path.join(subdir_name, "untracked_in_sub.txt").replace(os.sep, '/')
        with open(os.path.join(self.repo_path, untracked_subdir_rel), "w") as f: f.write("untracked in subdir")

        statuses = self.git_manager.get_all_file_statuses()

        self.assertIn(mod_subdir_rel, statuses["modified"])
        self.assertIn(staged_subdir_rel, statuses["staged"])
        self.assertIn(untracked_subdir_rel, statuses["untracked"])
        
        # Check initial file is still normal
        self.assertNotIn(self.initial_file_rel, statuses["modified"])
        self.assertNotIn(self.initial_file_rel, statuses["staged"])
        self.assertNotIn(self.initial_file_rel, statuses["untracked"])

    def test_get_blame_data_date_format(self):
        test_dt = datetime(2023, 5, 8, 10, 0, 0, tzinfo=timezone.utc)

        with open(self.initial_file_abs, "a") as f:
            f.write("\nTest line for blame date formatting.\n")

        self.repo.index.add([self.initial_file_rel])
        author = Actor("Test Blamer", "blamer@example.com")
        c = self.repo.index.commit("Blame date test commit", author=author, commit_date=test_dt, author_date=test_dt)

        blame_entries = self.git_manager.get_blame_data(self.initial_file_abs, commit_hash=c.hexsha)

        entry_checked = False
        correct_date_found = False
        expected_date_str = f"{test_dt.year}/{test_dt.month}/{test_dt.day}"
        for entry in blame_entries:
            if entry["commit_hash"] == c.hexsha:
                entry_checked = True
                if entry["committed_date"] == expected_date_str:
                    correct_date_found = True
                    break

        self.assertTrue(entry_checked, f"No blame entries from the test commit {c.hexsha} were found to check the date.")
        self.assertTrue(correct_date_found, f"Date format test failed. Expected {expected_date_str}, but was not found for commit {c.hexsha}.")


if __name__ == "__main__":
    unittest.main()
