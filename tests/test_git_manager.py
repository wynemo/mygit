import unittest
import tempfile
import shutil
import os
import git # Make sure 'gitpython' is installed in the test environment

# Assuming GitManager is in a module that can be imported, e.g., from git_manager import GitManager
# Adjust the import path if your GitManager is in a subdirectory or package
import sys
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


if __name__ == "__main__":
    unittest.main()
