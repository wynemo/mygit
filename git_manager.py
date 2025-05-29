import logging
import os
from typing import List, Optional

import git


class GitManager:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.repo: Optional[git.Repo] = None

    def initialize(self) -> bool:
        """初始化Git仓库"""
        try:
            self.repo = git.Repo(self.repo_path)
            return True
        except git.InvalidGitRepositoryError:
            return False

    def get_branches(self) -> List[str]:
        """获取所有分支"""
        if not self.repo:
            return []
        return [branch.name for branch in self.repo.branches]

    def get_default_branch(self) -> Optional[str]:
        """获取默认分支"""
        if not self.repo:
            return None
        return self.repo.active_branch.name

    def get_commit_history(self, branch: str = "master", limit: int = 50, skip: int = 0) -> List[dict]:
        """获取提交历史 (cursor生成)"""
        if not self.repo:
            return []

        try:
            if not branch:
                branch = self.repo.active_branch.name

            commits = []
            decorations_map = {}

            # Populate decorations_map with local branches
            for head in self.repo.heads:
                decorations_map.setdefault(head.commit.hexsha, []).append(head.name)

            # Populate decorations_map with remote references
            for remote in self.repo.remotes:
                for ref in remote.refs:
                    decorations_map.setdefault(ref.commit.hexsha, []).append(ref.name)

            for commit in self.repo.iter_commits(branch, max_count=limit, skip=skip):  # cursor生成
                message = commit.message.strip().split("\n")[0]
                decorations = decorations_map.get(commit.hexsha, [])
                commits.append(
                    {
                        "hash": commit.hexsha,
                        "message": message,
                        "author": commit.author.name,
                        "date": commit.committed_datetime.strftime("%Y-%m-%d %H:%M:%S"),
                        "decorations": decorations,
                    }
                )
            return commits
        except Exception as e:
            print(f"获取提交历史失败: {e!s}")
            return []

    def get_commit_graph(self, branch_specifier: str = "", limit: int = 500) -> dict: # Increased default limit
        if not self.repo:
            return {"commits": [], "branch_colors": {}}

        try:
            # Determine the revisions to iterate based on branch_specifier
            revs_to_iterate = []
            if branch_specifier == "__all__":
                revs_to_iterate = [b.name for b in self.repo.branches]
                # Consider adding --all flag or equivalent if iter_commits supports it directly for graph
                # For now, listing all branch heads is a good approach.
            elif not branch_specifier: # Empty specifier means active branch
                revs_to_iterate = self.repo.active_branch.name
            else: # Specific branch name
                revs_to_iterate = branch_specifier

            # Branch colors: based on all actual branches in the repo
            all_repo_branches = {b.name: b for b in self.repo.branches}
            colors = [
                "#e11d21", "#fbca04", "#009800", "#006b75", "#207de5",
                "#0052cc", "#5319e7", "#f781c6", "#8c8c8c", "#000000" 
            ] # Added more colors
            
            # Sort branch names for consistent color assignment
            sorted_branch_names_for_colors = sorted(all_repo_branches.keys())
            branch_colors = {
                name: colors[idx % len(colors)] for idx, name in enumerate(sorted_branch_names_for_colors)
            }

            # Pre-fetch all commits for each branch to determine which branches a commit belongs to
            # This helps in populating the 'branches' field for each commit object
            branch_commits_sets = {}
            for name, branch_ref_obj in all_repo_branches.items():
                try: # Add try-except for iter_commits per branch, in case of empty/weird branches
                    branch_commits_sets[name] = {c.hexsha for c in self.repo.iter_commits(branch_ref_obj.name)}
                except Exception:
                    branch_commits_sets[name] = set()


            commits_data = []
            # Use topo_order for better graph layout if possible, may affect performance slightly
            # GitPython's iter_commits takes a single rev or a list of revs.
            # If revs_to_iterate is a list, it iterates commits reachable from any of them.
            # The default order is reverse chronological per branch, then intermingled.
            # Adding topo_order=True might give a more "graph-like" sequence.
            # Note: iter_commits with multiple revs might not strictly follow 'limit' per branch,
            # but rather total commits.
            
            # We need a way to get a globally sorted list of commits for the graph view.
            # self.repo.iter_commits(revs_to_iterate, max_count=limit, topo_order=True) is good.
            # However, to ensure commits are unique if multiple branches point to them:
            processed_commits = set()
            raw_commits_list = []

            # Fetch commits using the determined revisions
            # For multiple revs, iter_commits explores history from all of them.
            # `topo_order=True` is good for graph structures.
            # `reverse=True` makes it chronological (older first), default is reverse-chrono (newer first)
            # CommitGraphView expects reverse-chronological (newer first).
            for commit_obj in self.repo.iter_commits(revs_to_iterate, max_count=limit, topo_order=True):
                if commit_obj.hexsha not in processed_commits:
                    raw_commits_list.append(commit_obj)
                    processed_commits.add(commit_obj.hexsha)
            
            # The list from iter_commits with multiple heads and topo_order=True is already good.
            # No need for further complex sorting if CommitGraphView handles display order via list index.

            for commit in raw_commits_list: # Iterate the globally collected and unique commits
                commit_member_of_branches = [
                    name for name, hc_set in branch_commits_sets.items() if commit.hexsha in hc_set
                ]
                # Sort for deterministic 'branches' field
                commit_member_of_branches.sort()


                message = commit.message.strip().split("\n")[0]
                # Ensure author and date are handled, even for unusual commits
                author_name = commit.author.name if commit.author else "Unknown Author"
                try:
                    committed_date_str = commit.committed_datetime.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    committed_date_str = "Unknown Date"


                commits_data.append({
                    "hash": commit.hexsha,
                    "message": message,
                    "author": author_name,
                    "date": committed_date_str,
                    "branches": commit_member_of_branches, 
                    "parents": [p.hexsha for p in commit.parents],
                })
            
            return {"commits": commits_data, "branch_colors": branch_colors}
        except Exception as e:
            logging.error(f"Error in get_commit_graph: {e!s}", exc_info=True) # Log with stack trace
            return {"commits": [], "branch_colors": {}}

    def get_blame_data(self, file_path: str, commit_hash: str = "HEAD") -> List[dict]:
        """获取文件的blame信息"""
        if not self.repo:
            return []

        try:
            blame_target = commit_hash
            print("blame_target is", blame_target)
            blame_data = []
            for commit, lines in self.repo.blame(blame_target, file_path):
                for line_num_in_commit, line_content in enumerate(lines):
                    # print("line_num_in_commit is", line_num_in_commit)
                    # print("line_content is", line_content)
                    # print("commit is", commit)
                    uncommited_yet = False
                    if commit.hexsha == "0000000000000000000000000000000000000000":
                        uncommited_yet = True
                    blame_data.append(
                        {
                            "commit_hash": commit.hexsha,
                            "author_name": commit.author.name,
                            "author_email": commit.author.email,
                            "committed_date": commit.committed_datetime.strftime("%Y-%m-%d")
                            if not uncommited_yet
                            else "未提交",
                            "line_number": line_num_in_commit + 1,  # 1-indexed
                            "content": line_content.strip("\n"),
                        }
                    )
            return blame_data
        except git.GitCommandError:  # Catch specific error for file not found or not tracked
            return []
        except Exception as e:
            logging.exception("获取blame信息失败")
            print(f"获取blame信息失败: {e!s}")
            return []

    def fetch(self):
        """获取仓库"""
        if not self.repo:
            return
        self.repo.remotes.origin.fetch()

    def pull(self):
        """拉取仓库"""
        if not self.repo:
            return
        self.repo.remotes.origin.pull()

    def push(self):
        """推送仓库"""
        if not self.repo:
            return
        self.repo.remotes.origin.push()

    def get_file_status(self, file_path: str) -> str:
        """获取文件的Git状态"""
        if not self.repo:
            if not self.initialize():
                return "unknown"

        # This check is important to ensure self.repo is not None
        if not self.repo:
            return "unknown"

        try:
            # Ensure file_path is absolute for consistent comparison
            abs_file_path = os.path.abspath(file_path)
            repo_root_path = os.path.abspath(self.repo_path)

            # Check if the file is within the repository path
            if not abs_file_path.startswith(repo_root_path):
                # This case might be treated as an error or a specific status.
                # For now, returning "untracked" as per one interpretation of the requirement.
                return "untracked"

            relative_file_path = os.path.relpath(abs_file_path, repo_root_path)

            # 1. Check if the file is untracked
            if relative_file_path in self.repo.untracked_files:
                return "untracked"

            # 2. Check if the file is modified (unstaged changes)
            # diff(None) compares the working directory with the index
            for diff_item in self.repo.index.diff(None):
                if diff_item.a_path == relative_file_path or diff_item.b_path == relative_file_path:
                    return "modified"

            # 3. Check if the file is staged (changes added to index but not committed)
            # diff("HEAD") compares the index with the HEAD commit
            for diff_item in self.repo.index.diff("HEAD"):
                if diff_item.a_path == relative_file_path or diff_item.b_path == relative_file_path:
                    return "staged"

            # 4. If none of the above, the file is considered "normal" (tracked and not modified)
            # This check is implicitly handled if the file is tracked and not in previous conditions.
            # However, we need to ensure the file is actually tracked.
            # If it's not untracked, not modified, not staged, it must be tracked and unchanged.
            # We can verify if the file is known to Git by checking if it appears in the tree of the current HEAD.
            try:
                self.repo.head.commit.tree[relative_file_path]
                return "normal"
            except KeyError:
                return "normal"  # If not in untracked, modified, or staged, assume normal.

        except git.GitCommandError as e:
            print(f"Git command error while getting file status for {file_path}: {e!s}")
            return "unknown"
        except Exception as e:
            print(f"Error getting file status for {file_path}: {e!s}")
            return "unknown"

    def get_all_file_statuses(self) -> dict[str, set[str]]:
        """
        Gets all file statuses (modified, staged, untracked) in the repository.
        Returns a dictionary where keys are status types and values are sets of relative file paths.
        """
        statuses = {"modified": set(), "staged": set(), "untracked": set()}

        if not self.repo:
            if not self.initialize():
                # Initialization failed, return empty sets
                return statuses

        # This check is important to ensure self.repo is not None after potential initialization
        if not self.repo:
            return statuses

        try:
            # Get Untracked Files
            # self.repo.untracked_files is a list of relative paths
            statuses["untracked"] = set(self.repo.untracked_files)

            # Get Modified (Unstaged) Files
            # self.repo.index.diff(None) compares the working directory with the index
            # diff_item.a_path is the path in the index
            # diff_item.b_path is the path in the working directory (for new/renamed files)
            # For simple modifications, a_path and b_path are often the same.
            # For deleted files in working dir, a_path is the path, b_path is None.
            # For new files in working dir (should be caught by untracked_files if not added),
            # this diff won't typically show them unless they were part of complex staging.
            for diff_item in self.repo.index.diff(None):
                # If a file is renamed, a_path is old, b_path is new.
                # If a file is modified, a_path and b_path are usually the same.
                # If a file is deleted from workdir (but still in index), b_path is None.
                # We are interested in paths that are currently modified in the working tree.
                if diff_item.a_path:  # Path in index
                    statuses["modified"].add(diff_item.a_path)
                if (
                    diff_item.b_path and diff_item.b_path != diff_item.a_path
                ):  # Path in working dir, if different and exists
                    statuses["modified"].add(diff_item.b_path)

            # Get Staged Files
            # self.repo.index.diff("HEAD") compares the index with the HEAD commit
            # diff_item.a_path is the path in HEAD
            # diff_item.b_path is the path in the index
            # For new files added to index, a_path is None.
            # For files deleted from index, b_path is None.
            for diff_item in self.repo.index.diff("HEAD"):
                # If a file is newly staged, a_path is None, b_path is the file.
                # If a file is staged for deletion, b_path is None, a_path is the file.
                # If a file is modified and staged, a_path and b_path are usually the same.
                if diff_item.b_path:  # Path in index (staged)
                    statuses["staged"].add(diff_item.b_path)
                elif diff_item.a_path:  # Path in HEAD (implies deletion staged if b_path is None)
                    statuses["staged"].add(diff_item.a_path)

            # Handle files that are both staged and then modified again in the working directory.
            # Such files will appear in `statuses["modified"]` (workdir vs index)
            # and `statuses["staged"]` (index vs HEAD).
            # The current logic is fine. If a file is in `statuses["modified"]`, it means
            # there are changes in the working directory not yet staged.
            # If it's also in `statuses["staged"]`, it means the staged version is different from HEAD.
            # This is consistent with how `git status` reports such states.

        except git.GitCommandError as e:
            print(f"Git command error while getting all file statuses: {e!s}")
            # Return whatever statuses were collected, or empty if error was early
            return statuses  # Or re-initialize to empty: {"modified": set(), "staged": set(), "untracked": set()}
        except Exception as e:
            print(f"Error getting all file statuses: {e!s}")
            return statuses  # Or re-initialize to empty

        return statuses

    def revert(self, file_path: str):
        """还原文件"""
        if not self.repo:
            return
        self.repo.git.checkout(file_path)

    def get_diff(self, file_path: str) -> dict:
        """
        获取文件差异
        "added" - 新增行
        "modified" - 修改行
        "deleted" - 删除行
        """

        d = {}
        if not self.repo:
            return {}
        source_line = 0
        target_line = 0
        diffs = self.repo.index.diff(None, create_patch=True)
        for diff in diffs:
            if file_path != diff.a_path:
                continue
            # print(f"\n📄 文件: {diff.a_path}")

            diff_text = diff.diff.decode()
            # print(f"🔸 {diff_text}")
            lines = diff_text.splitlines()

            source_line = 0
            target_line = 0

            for line in lines:
                print(line)
                if line.startswith("@@"):
                    # 解析 @@ -10,7 +10,8 @@ 这样的 Hunk 行
                    import re

                    m = re.match(r"^@@ -(\d+)(?:,\d+)? \+(\d+)", line)
                    if m:
                        source_line = int(m.group(1))
                        target_line = int(m.group(2))
                    print(f"\n  🔸 {line}")
                elif line.startswith("-") and not line.startswith("---"):
                    print(f"  ➖ 删除行 {source_line}: {line[1:].strip()}")
                    d[source_line] = "deleted"
                    source_line += 1
                elif line.startswith("+") and not line.startswith("+++"):
                    print(f"  ➕ 新增行 {target_line}: {line[1:].strip()}")
                    d[target_line] = "added"
                    target_line += 1
                else:
                    # 上下文行
                    source_line += 1
                    target_line += 1
        print("d is", d)
        return d
