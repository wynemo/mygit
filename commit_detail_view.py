import logging
from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# 常量用于分支显示
MAX_BRANCHES_TO_SHOW = 3


class CommitDetailView(QTextEdit):
    """
    Commit详细信息视图
    直接使用QTextEdit作为主控件，显示选中commit的详细信息
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setStyleSheet("""
            background-color: #f5f5f5;
            border: 1px solid #ddd;
            font-family: monospace;
            padding: 5px;
        """)
        self.setFrameShape(QTextEdit.Shape.NoFrame)
        self.setMinimumHeight(200)
        self.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )

    def update_commit_detail(self, git_manager, commit):
        """更新commit详细信息显示"""
        if not commit:
            self.clear()
            return

        try:
            # 获取格式化信息
            message = commit.message.strip()
            commit_date = datetime.fromtimestamp(commit.committed_date)
            info_line = (
                f"{commit.hexsha[:8]} {commit.author.name} "
                f"<{commit.author.email}> on "
                f"{commit_date.strftime('%Y/%m/%d at %H:%M')}"
            )

            # 获取分支信息
            branches = self.get_commit_branches(git_manager, commit)
            branch_text = "未知分支"
            if branches:
                branch_text = f"In {len(branches)} branches: {', '.join(branches[:MAX_BRANCHES_TO_SHOW])}"
                if len(branches) > MAX_BRANCHES_TO_SHOW:
                    branch_text += f" (+{len(branches) - MAX_BRANCHES_TO_SHOW} more)"

            # 组合所有信息
            detail_content = f"{message}\n\n{info_line}\n\n分支: {branch_text}"

            self.setPlainText(detail_content)

        except Exception as e:
            self.clear()
            self.setPlainText(f"获取commit详细信息失败: {e!s}")

    def get_commit_branches(self, git_manager, commit):
        """获取包含此commit的分支列表"""
        try:
            branches = []

            # 获取本地分支
            for branch in git_manager.repo.branches:
                try:
                    if git_manager.repo.is_ancestor(commit, branch.commit):
                        branches.append(branch.name)
                except Exception:
                    logging.exception("检查分支失败")
                    continue

            # 如果没有找到分支，添加一些默认值
            if not branches:
                try:
                    if commit == git_manager.repo.head.commit:
                        branches.append("HEAD")
                except Exception:
                    logging.exception("检查分支失败")

                if not branches:
                    branches.extend(["main", "HEAD"])

            return branches
        except Exception:
            return ["main", "HEAD"]
