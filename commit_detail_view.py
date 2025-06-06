import logging
from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QTextEdit,
)

# 常量用于分支显示
MAX_BRANCHES_TO_SHOW = 3


class CommitDetailView(QTextEdit):
    """
    Commit详细信息视图
    直接使用QTextEdit作为主控件, 显示选中commit的详细信息
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setStyleSheet("""
            background-color: #f5f5f5;
            border: 1px solid #ddd;
            font-family: monospace;
            padding: 5px;

            QScrollBar:vertical {
                background: #f0f0f0;
                width: 12px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #c0c0c0;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #a8a8a8;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }

            QScrollBar:horizontal {
                background: #f0f0f0;
                height: 12px;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background: #c0c0c0;
                min-width: 20px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #a8a8a8;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: none;
            }
        """)
        self.setFrameShape(QTextEdit.Shape.NoFrame)
        self.setMinimumHeight(100)
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

            # 获取分支信息 (调用get_commit_branches方法)
            branches = self.get_commit_branches(git_manager, commit)
            branch_text = "未知分支"  # 如果没有获取到分支信息，则显示"未知分支"
            if branches:
                branch_text = f"In {len(branches)} branches: {', '.join(branches[:MAX_BRANCHES_TO_SHOW])}"
                if len(branches) > MAX_BRANCHES_TO_SHOW:
                    branch_text += f" (+{len(branches) - MAX_BRANCHES_TO_SHOW} more)"
                # todos 如果超过 MAX_BRANCHES_TO_SHOW 想想该怎么交互

            # 组合所有信息
            detail_content = f"{message}\n\n{info_line}\n\n分支: {branch_text}"

            self.setPlainText(detail_content)

        except Exception as e:
            self.clear()
            self.setPlainText(f"获取commit详细信息失败: {e!s}")

    def get_commit_branches(self, git_manager, commit):
        """获取包含此commit的分支列表"""
        try:
            # 使用 git branch --contains <commit_sha> --all 命令获取包含特定commit的所有分支（本地和远程）
            branch_str = git_manager.repo.git.branch("--contains", commit.hexsha, "--all")
            branches = []
            # 处理git命令的输出字符串
            for line in branch_str.splitlines():
                line = line.strip()  # 去除行首尾的空白字符
                # 如果是当前分支，git输出会以 "* " 开头，需要移除
                if line.startswith("* "):
                    line = line[2:]
                # 对于远程分支，例如 "remotes/origin/main"，简化为 "origin/main"
                if line.startswith("remotes/"):
                    line = line[len("remotes/") :]
                branches.append(line)
            return branches
        except Exception:
            # 如果发生任何异常，记录错误并返回空列表
            logging.exception("Error getting commit branches")
            return []
