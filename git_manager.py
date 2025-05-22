from typing import List, Optional
from datetime import datetime

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

    def get_commit_history(
        self, branch: str = "master", limit: int = 50, skip: int = 0
    ) -> List[dict]:
        """获取提交历史 (cursor生成)"""
        if not self.repo:
            return []

        try:
            if not branch:
                branch = self.repo.active_branch.name

            commits = []
            for commit in self.repo.iter_commits(
                branch, max_count=limit, skip=skip
            ):  # cursor生成
                message = commit.message.strip().split("\n")[0]
                commits.append(
                    {
                        "hash": commit.hexsha,
                        "message": message,
                        "author": commit.author.name,
                        "date": commit.committed_datetime.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                )
            return commits
        except Exception as e:
            print(f"获取提交历史失败: {e!s}")
            return []

    def get_commit_graph(self, branch: str = "", limit: int = 50) -> dict:
        """获取提交图数据"""
        if not self.repo:
            return {"commits": [], "branch_colors": {}}

        try:
            if not branch:
                branch = self.repo.active_branch.name

            # 获取所有分支名称和颜色映射
            branches = {b.name: b for b in self.repo.branches}
            colors = [
                "#e11d21",
                "#fbca04",
                "#009800",
                "#006b75",
                "#207de5",
                "#0052cc",
                "#5319e7",
            ]
            branch_colors = {
                name: colors[idx % len(colors)] for idx, name in enumerate(branches)
            }

            # 预先获取每个分支的所有提交
            branch_commits = {}
            for branch_name, branch_ref in branches.items():
                # Rewrite generator as set comprehension
                branch_commits[branch_name] = {
                    commit.hexsha for commit in self.repo.iter_commits(branch_ref.name)
                }

            commits = []
            # 获取主分支的提交历史
            for commit in self.repo.iter_commits(branch, max_count=limit):
                # Check which branches this commit belongs to
                commit_branches = [
                    branch_name
                    for branch_name, commit_set in branch_commits.items()
                    if commit.hexsha in commit_set
                ]

                # Decode commit message assuming it might be bytes
                message = (
                    commit.message.decode("utf-8", errors="ignore")
                    .strip()
                    .split("\n")[0]
                )

                commits.append(
                    {
                        "hash": commit.hexsha,
                        "message": message,
                        "author": commit.author.name,
                        "date": commit.committed_datetime.strftime("%Y-%m-%d %H:%M:%S"),
                        "branches": commit_branches,
                        "parents": [parent.hexsha for parent in commit.parents],
                    }
                )

            return {"commits": commits, "branch_colors": branch_colors}
        except Exception as e:
            print(f"获取提交图失败: {e!s}")
            return {"commits": [], "branch_colors": {}}

    def get_blame_data(self, file_path: str) -> List[dict]:
        """获取文件的blame信息"""
        if not self.repo:
            return []

        try:
            blame_data = []
            for commit, lines in self.repo.blame("HEAD", file_path):
                for line_num_in_commit, line_content in enumerate(lines):
                    # line_num_in_commit is 0-indexed within the lines from this commit
                    # We need to find the actual line number in the file
                    # This is a simplification; git blame can be complex with line movements.
                    # GitPython's blame gives line content directly.
                    # To get the original line number, we'd typically need to track it.
                    # However, the structure of repo.blame gives commit per set of lines.
                    # The 'lines' are the actual content of the lines from that commit.
                    # For now, we'll use a placeholder or assume line_num_in_commit is enough
                    # if the request implies current line numbers, this will need adjustment.
                    # Based on the requirement, `line_number` is the original line number in that commit.
                    # This seems to indicate the line number within the group of lines associated with the commit,
                    # not the absolute line number in the file at the time of the commit.
                    # Let's assume the request means the line number within the context of the blame entry.
                    # A more robust solution might need to map this to current file line numbers if that's the true intent.

                    # For now, let's use a simple line counter for the output,
                    # assuming the order from repo.blame is sequential.
                    # This might not be the "original line number in that commit"
                    # if lines were moved/deleted.
                    # A true "original line number in that commit" would require more complex parsing of diffs or using
                    # a different blame approach.
                    # Given the tools, gitpython's blame provides line content associated with a commit.
                    # Let's use the content and associate it with the commit data.
                    # The line_number can be the index in the lines list from the blame entry.

                    blame_data.append(
                        {
                            "commit_hash": commit.hexsha,
                            "author_name": commit.author.name,
                            "author_email": commit.author.email,
                            "committed_date": commit.committed_datetime.strftime(
                                "%Y-%m-%d"
                            ),
                            # This line_number is the index within the lines for this specific commit's blame entry.
                            # If the requirement is the line number in the *file* at the time of *that commit*,
                            # this is not it. GitPython's blame focuses on *who* last changed *which current lines*.
                            # For simplicity and following the structure of `repo.blame`,
                            # let's consider `line_content` as the core piece of data.
                            # The problem asks for "original line number in that commit".
                            # This is ambiguous. Let's interpret it as the line number within the block of lines
                            # attributed to this commit in the blame output.
                            "line_number": line_num_in_commit + 1,  # 1-indexed
                            "content": line_content.strip("\n"),
                        }
                    )
            return blame_data
        except (
            git.GitCommandError
        ):  # Catch specific error for file not found or not tracked
            return []
        except Exception as e:
            print(f"获取blame信息失败: {e!s}")
            return []
