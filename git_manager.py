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

    def get_commit_history(self, branch: str = "master", limit: int = 50) -> List[dict]:
        """获取提交历史"""
        if not self.repo:
            return []

        try:
            # 如果分支名为空,使用当前分支
            if not branch:
                branch = self.repo.active_branch.name

            commits = []
            for commit in self.repo.iter_commits(branch, max_count=limit):
                # 只取第一行提交信息
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
            print(f"获取提交历史失败: {str(e)}")
            return []
