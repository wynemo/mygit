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

    def get_commit_graph(self, branch: str = "", limit: int = 50) -> dict:
        """获取提交图数据"""
        if not self.repo:
            return {'commits': [], 'branch_colors': {}}

        try:
            if not branch:
                branch = self.repo.active_branch.name

            # 获取所有分支名称和颜色映射
            branches = {b.name: b for b in self.repo.branches}
            colors = ['#e11d21', '#fbca04', '#009800', '#006b75', '#207de5', '#0052cc', '#5319e7']
            branch_colors = {name: colors[idx % len(colors)] for idx, name in enumerate(branches)}

            # 预先获取每个分支的所有提交
            branch_commits = {}
            for branch_name, branch_ref in branches.items():
                branch_commits[branch_name] = set(
                    commit.hexsha for commit in self.repo.iter_commits(branch_ref.name)
                )

            commits = []
            # 获取主分支的提交历史
            for commit in self.repo.iter_commits(branch, max_count=limit):
                # 检查提交属于哪些分支
                commit_branches = [
                    branch_name
                    for branch_name, commit_set in branch_commits.items()
                    if commit.hexsha in commit_set
                ]

                commits.append({
                    'hash': commit.hexsha,
                    'message': commit.message.strip().split('\n')[0],
                    'author': commit.author.name,
                    'date': commit.committed_datetime.strftime('%Y-%m-%d %H:%M:%S'),
                    'branches': commit_branches,
                    'parents': [parent.hexsha for parent in commit.parents]
                })

            return {
                'commits': commits,
                'branch_colors': branch_colors
            }
        except Exception as e:
            print(f"获取提交图失败: {str(e)}")
            return {'commits': [], 'branch_colors': {}}
