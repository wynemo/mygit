import git
from typing import List, Optional

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
            
        commits = []
        for commit in self.repo.iter_commits(branch, max_count=limit):
            commits.append({
                'hash': commit.hexsha,
                'message': commit.message.strip(),
                'author': commit.author.name,
                'date': commit.committed_datetime,
                'parents': [p.hexsha for p in commit.parents]
            })
        return commits 