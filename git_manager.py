import logging
import os
from typing import List, Optional

import git
import git.exc
import pathspec
from git import GitCommandError


class GitManager:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.repo: Optional[git.Repo] = None
        self.ignore_spec: Optional[pathspec.PathSpec] = None

    def initialize(self) -> bool:
        """初始化 Git 仓库"""
        try:
            self.repo = git.Repo(self.repo_path)
            self._load_gitignore_patterns()
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

    def get_remote_branches(self) -> List[str]:
        """获取所有远程分支的完整名称（例如 'origin/main'）"""
        if not self.repo:
            return []
        remote_branches = []
        for remote in self.repo.remotes:
            for ref in remote.refs:
                # 我们只关心分支引用，通常以 'refs/remotes/' 开头，但我们可以直接取名字
                # ref.name 是完整的引用名称，如 'origin/main'
                remote_branches.append(ref.name)
        return remote_branches

    def get_commit_history(
        self, branch: str = "master", limit: int = 50, skip: int = 0, include_remotes: bool = False
    ) -> List[dict]:
        """获取提交历史 (cursor 生成)

        参数：
            branch: 要获取历史的分支名称（默认为'master'）
            limit: 返回的最大提交数量（默认为 50）
            skip: 跳过的提交数量（默认为 0）
            include_remotes: 是否包含远程分支的提交（默认为 False）
        """
        if not self.repo:
            return []

        try:
            revs = []
            if branch:
                revs.append(branch)

            if include_remotes:
                # 获取所有远程分支的名称
                remote_branches = self.get_remote_branches()
                revs.extend(remote_branches)

            # 如果没有指定分支且不包含远程分支，则使用当前活动分支
            if not revs:
                revs = [self.repo.active_branch.name]

            commits = []
            decorations_map = {}

            # Populate decorations_map with local branches
            for head in self.repo.heads:
                decorations_map.setdefault(head.commit.hexsha, []).append(head.name)

            # Populate decorations_map with remote references
            for remote in self.repo.remotes:
                for ref in remote.refs:
                    decorations_map.setdefault(ref.commit.hexsha, []).append(ref.name)

            # 使用 revs 列表来获取提交
            for commit in self.repo.iter_commits(revs, max_count=limit, skip=skip):  # cursor 生成
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
            print(f"获取提交历史失败：{e!s}")
            return []

    def get_blame_data(self, file_path: str, commit_hash: str = "HEAD") -> List[dict]:
        """获取文件的 blame 信息"""
        # todo 新增行 有 bug
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
                            "author_name": commit.author.name if not uncommited_yet else "未提交",
                            "author_email": commit.author.email if not uncommited_yet else "未提交",
                            "committed_date": f"{commit.committed_datetime.year}/{commit.committed_datetime.month}/{commit.committed_datetime.day}"
                            if not uncommited_yet
                            else "未提交",
                            "line_number": line_num_in_commit + 1,  # 1-indexed
                            "content": line_content.strip("\n"),
                            "message": commit.message if not uncommited_yet else "未提交",
                        }
                    )
            return blame_data
        except git.GitCommandError:  # Catch specific error for file not found or not tracked
            return []
        except Exception as e:
            logging.exception("获取 blame 信息失败")
            print(f"获取 blame 信息失败：{e!s}")
            return []

    def fetch(self):
        """获取仓库"""
        if not self.repo:
            raise Exception("Repository not initialized.")
        try:
            self.repo.remotes.origin.fetch()
        except GitCommandError as e:
            error_message = f"Fetch failed: {e!s}"
            if hasattr(e, "stderr") and e.stderr:
                error_message += f"\nDetails: {e.stderr.strip()}"
            raise Exception(error_message)
        except Exception as e:
            # Catch any other unexpected errors
            raise Exception(f"An unexpected error occurred during fetch: {e!s}")

    def pull(self):
        """拉取仓库"""
        if not self.repo:
            raise Exception("Repository not initialized.")
        try:
            self.repo.remotes.origin.pull()
        except GitCommandError as e:
            error_message = f"Pull failed: {e!s}"
            if hasattr(e, "stderr") and e.stderr:
                error_message += f"\nDetails: {e.stderr.strip()}"
            raise Exception(error_message)
        except Exception as e:
            raise Exception(f"An unexpected error occurred during pull: {e!s}")

    def push(self):
        """推送仓库"""
        if not self.repo:
            raise Exception("Repository not initialized.")
        try:
            # 检查当前分支是否有上游分支
            if not self.repo.active_branch.tracking_branch():
                # 如果没有上游分支，则设置上游分支
                branch_name = self.repo.active_branch.name
                self.repo.git.push("--set-upstream", "origin", branch_name)
            else:
                # 如果有上游分支，正常推送
                self.repo.remotes.origin.push()
        except GitCommandError as e:
            error_message = f"Push failed: {e!s}"
            if hasattr(e, "stderr") and e.stderr:
                error_message += f"\nDetails: {e.stderr.strip()}"
            raise Exception(error_message)
        except Exception as e:
            raise Exception(f"An unexpected error occurred during push: {e!s}")

    def get_file_status(self, file_path: str) -> str:
        """获取文件的 Git 状态"""
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
            # For deleted files in workdir, a_path is the path, b_path is None.
            # For new files in workdir (should be caught by untracked_files if not added),
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

    def switch_branch(self, branch_name: str) -> Optional[str]:
        """切换到指定分支。

        如果成功，返回 None。
        如果失败，返回错误信息字符串。
        """
        if branch_name == "all":
            return None
        if not self.repo:
            return "仓库未初始化。"  # Repository not initialized.
        try:
            # 检查当前分支是否已经是目标分支
            if self.repo.active_branch.name == branch_name:
                return None  # 已经是目标分支，无需切换

            # 检查工作区是否有未提交的更改
            # if self.repo.is_dirty(untracked_files=True):
            # return "工作区有未提交的更改，请先提交或贮藏更改后再切换分支。" # Workspace has uncommitted changes.

            self.repo.git.checkout(branch_name)
            return None
        except git.GitCommandError as e:
            logging.error(f"切换分支 {branch_name} 失败：{e!s}")  # Failed to switch branch
            # 提供更具体的错误信息
            if "did not match any file(s) known to git" in str(e):
                return f"分支 '{branch_name}' 不存在。"  # Branch does not exist.
            elif "Your local changes to the following files would be overwritten by checkout" in str(e):
                return "切换分支会覆盖本地未提交的更改，请先提交或贮藏。"  # Switching branches would overwrite local uncommitted changes.
            return f"切换到分支 '{branch_name}' 失败：{e.stderr.strip() if e.stderr else e!s}"  # Failed to switch to branch.
        except Exception as e:
            logging.error(
                f"切换分支 {branch_name} 时发生未知错误：{e!s}"
            )  # Unknown error occurred while switching branch.
            return f"切换到分支 '{branch_name}' 时发生未知错误。"  # Unknown error occurred while switching to branch.

    def create_and_switch_branch(self, new_branch_name: str, base_branch: Optional[str] = None) -> Optional[str]:
        """创建新分支并切换到该分支 (cursor 生成)

        参数：
            new_branch_name: 要创建的新分支名称
            base_branch: 可选，基于哪个分支创建。如果为 None 则基于当前分支

        返回：
            None: 成功
            str: 失败时的错误信息
        """
        if not self.repo:
            return "仓库未初始化。"

        # 验证分支名称
        if not new_branch_name or not new_branch_name.strip():
            return "分支名称不能为空。"

        # 检查分支是否已存在
        if new_branch_name in [branch.name for branch in self.repo.branches]:
            return f"分支 '{new_branch_name}' 已存在。"

        try:
            # 创建新分支
            if base_branch:
                self.repo.create_head(new_branch_name, commit=base_branch)
            else:
                self.repo.create_head(new_branch_name)

            # 切换到新分支
            return self.switch_branch(new_branch_name)

        except git.GitCommandError as e:
            error_msg = f"创建分支 '{new_branch_name}' 失败：{e.stderr.strip() if e.stderr else str(e)}"
            logging.error(error_msg)
            return error_msg
        except Exception as e:
            error_msg = f"创建分支 '{new_branch_name}' 时发生未知错误：{e!s}"
            logging.error(error_msg)
            return error_msg

    def merge_branch(self, branch_name: str) -> Optional[str]:
        """合并指定分支到当前分支

        参数：
            branch_name: 要合并的分支名称

        返回：
            None: 合并成功
            str: 合并失败时的错误信息
        """
        if not self.repo:
            return "仓库未初始化。"

        try:
            # 执行合并操作
            self.repo.git.merge(branch_name)
            return None
        except git.GitCommandError as e:
            error_message = f"合并失败：{e.stderr.strip() if e.stderr else str(e)}"
            logging.error(error_message)
            return error_message
        except Exception as e:
            error_message = f"合并分支时发生未知错误：{e}"
            logging.exception(error_message)
            return error_message

    def _load_gitignore_patterns(self):
        """加载.gitignore 文件中的忽略规则"""
        if not self.repo:
            return

        gitignore_path = os.path.join(self.repo_path, ".gitignore")
        if not os.path.exists(gitignore_path):
            self.ignore_spec = None
            return

        with open(gitignore_path, "r", encoding="utf-8") as f:
            patterns = f.readlines()

        self.ignore_spec = pathspec.PathSpec.from_lines("gitwildmatch", patterns)

    def is_ignored(self, path: str) -> bool:
        """检查路径是否被.gitignore 忽略"""
        if not self.ignore_spec:
            return False

        try:
            # 获取相对于仓库根目录的路径
            rel_path = os.path.relpath(path, self.repo_path)
            # 统一使用正斜杠
            rel_path = rel_path.replace(os.sep, "/")
            return self.ignore_spec.match_file(rel_path)
        except ValueError:
            return False

    def get_folder_commit_history(
        self, folder_path: str, branch: Optional[str] = None, max_count: int = 50, skip: int = 0
    ) -> list[dict]:
        """
        获取指定文件夹的提交历史。

        参数：
            folder_path (str): 文件夹的路径，可以是绝对路径或相对于仓库根目录的相对路径。
            branch (str, optional): 要从中获取历史的分支名称。默认为 None (通常是 HEAD 或所有分支)。
            max_count (int, optional): 要获取的最大提交数量。默认为 50。
            skip (int, optional): 要跳过的提交数量 (用于分页)。默认为 0。

        返回：
            list[dict]: 一个包含提交信息的字典列表，每个字典包含 hash, author, email, date, message。
                        如果发生错误或没有历史记录，则返回空列表。
        """
        if not self.repo:
            logging.warning("GitManager: 仓库未初始化，无法获取文件夹历史。")
            return []

        try:
            # 标准化文件夹路径
            if os.path.isabs(folder_path):
                # 如果是绝对路径，计算相对于仓库根目录的路径
                relative_folder_path = os.path.relpath(folder_path, self.repo.working_dir)
            else:
                # 如果已经是相对路径，则直接使用 (确保它是相对于 repo root)
                # os.path.normpath is important to clean up ".." or "."
                relative_folder_path = os.path.normpath(folder_path)

            # 确保路径使用操作系统的分隔符，GitPython 通常能处理好
            # relative_folder_path = relative_folder_path.replace("/", os.sep)

            logging.info(
                f"GitManager: 获取文件夹 '{relative_folder_path}' 的提交历史 (分支：{branch or '默认'}, 最大数量：{max_count}, 跳过：{skip})."
            )

            commits_data = []
            # 使用 iter_commits 获取提交迭代器
            # `paths` 参数用于指定只关心影响此路径的提交
            # `rev` 参数用于指定分支或引用
            commit_iterator = self.repo.iter_commits(
                rev=branch, paths=relative_folder_path, max_count=max_count, skip=skip
            )

            for commit in commit_iterator:
                commits_data.append(
                    {
                        "hash": commit.hexsha,
                        "author": commit.author.name,
                        "email": commit.author.email,  # 作者邮箱
                        "date": commit.authored_datetime.strftime("%Y-%m-%d %H:%M:%S"),  # 使用 authored_datetime
                        "message": commit.summary,  # 简短的提交信息
                    }
                )

            if not commits_data:
                logging.info(f"GitManager: 文件夹 '{relative_folder_path}' 没有找到提交历史。")

            return commits_data

        except git.exc.GitCommandError as e:
            # 特定 Git 命令错误，例如路径不存在于历史中
            logging.error(f"GitManager: 获取文件夹 '{folder_path}' 历史时发生 Git 命令错误：{e!s}")
            return []
        except ValueError as e:
            # 可能由 os.path.relpath 等路径操作引起
            logging.error(f"GitManager: 处理文件夹路径 '{folder_path}' 时发生值错误：{e!s}")
            return []
        except Exception:
            # 其他任何意外错误
            logging.exception(
                f"GitManager: 获取文件夹 '{folder_path}' 历史时发生未知错误."
            )  # 使用 logging.exception 记录堆栈跟踪
            return []

    def compare_commit_with_workspace(self, commit_hash: str) -> List[str]:
        """比较指定提交与工作区的差异，返回变更的文件列表。

        参数：
            commit_hash: 要比较的提交的哈希值。

        返回：
            变更的文件路径列表。如果发生错误或没有变更，返回空列表。
        """
        if not self.repo:
            return []

        try:
            # 使用 `name_only=True` 只返回文件名，不返回具体的差异内容
            diff_output = self.repo.git.diff(commit_hash, name_only=True)
            # 按行分割输出，并过滤掉空行
            changed_files = [line.strip() for line in diff_output.split("\n") if line.strip()]
            return changed_files
        except git.GitCommandError:
            logging.exception("比较提交 %s 与工作区失败", commit_hash)
            return []
        except Exception:
            logging.exception("比较提交 %s 与工作区时发生未知错误", commit_hash)
            return []

    def reset_branch(self, commit_hash: str, mode: str) -> Optional[str]:
        """重置当前分支到指定的提交。

        参数：
            commit_hash: 目标提交的哈希值。
            mode: 重置模式 ('soft', 'mixed', 'hard')。

        返回：
            None: 成功。
            str: 失败时的错误信息。
        """
        if not self.repo:
            return "仓库未初始化。"

        if mode not in ["soft", "mixed", "hard"]:
            return f"无效的重置模式: {mode}"

        try:
            self.repo.git.reset(commit_hash, f"--{mode}")
            return None
        except git.GitCommandError as e:
            logging.exception("重置到 %s 失败", commit_hash)
            return f"重置到 {commit_hash} 失败: {e.stderr.strip() if e.stderr else str(e)}"
        except Exception:
            logging.exception("重置分支时发生未知错误")
            return "重置分支时发生未知错误"
