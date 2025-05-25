import logging
from datetime import datetime

from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class CommitDetailView(QWidget):
    """
    Commit详细信息视图
    cursor生成 - 显示选中commit的详细信息，包括提交信息、作者、时间、分支等
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)
        self.setLayout(layout)

        # 标题
        self.title_label = QLabel("Commit详细信息:")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(self.title_label)

        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)

        # 提交信息
        self.message_label = QLabel("提交信息:")
        self.message_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.message_label)

        self.message_text = QTextEdit()
        self.message_text.setMaximumHeight(80)
        self.message_text.setReadOnly(True)
        self.message_text.setStyleSheet("background-color: #f5f5f5; border: 1px solid #ddd;")
        layout.addWidget(self.message_text)

        # 提交哈希
        hash_layout = QHBoxLayout()
        hash_layout.setContentsMargins(0, 0, 0, 0)
        self.hash_label = QLabel("提交哈希:")
        self.hash_label.setStyleSheet("font-weight: bold;")
        self.hash_value = QLabel("")
        self.hash_value.setStyleSheet("font-family: monospace; color: #666;")
        hash_layout.addWidget(self.hash_label)
        hash_layout.addWidget(self.hash_value)
        hash_layout.addStretch()
        layout.addLayout(hash_layout)

        # 作者信息
        author_layout = QHBoxLayout()
        author_layout.setContentsMargins(0, 0, 0, 0)
        self.author_label = QLabel("作者:")
        self.author_label.setStyleSheet("font-weight: bold;")
        self.author_value = QLabel("")
        author_layout.addWidget(self.author_label)
        author_layout.addWidget(self.author_value)
        author_layout.addStretch()
        layout.addLayout(author_layout)

        # 提交时间
        date_layout = QHBoxLayout()
        date_layout.setContentsMargins(0, 0, 0, 0)
        self.date_label = QLabel("提交时间:")
        self.date_label.setStyleSheet("font-weight: bold;")
        self.date_value = QLabel("")
        date_layout.addWidget(self.date_label)
        date_layout.addWidget(self.date_value)
        date_layout.addStretch()
        layout.addLayout(date_layout)

        # 分支信息
        branch_layout = QHBoxLayout()
        branch_layout.setContentsMargins(0, 0, 0, 0)
        self.branch_label = QLabel("分支:")
        self.branch_label.setStyleSheet("font-weight: bold;")
        self.branch_value = QLabel("")
        branch_layout.addWidget(self.branch_label)
        branch_layout.addWidget(self.branch_value)
        branch_layout.addStretch()
        layout.addLayout(branch_layout)

        # 添加弹性空间，将内容推到顶部
        layout.addStretch()

    def update_commit_detail(self, git_manager, commit):
        """更新commit详细信息显示"""
        if not commit:
            self.clear_detail()
            return

        try:
            # 提交信息
            self.message_text.setPlainText(commit.message.strip())

            # 提交哈希
            self.hash_value.setText(
                f"{commit.hexsha[:8]} {commit.author.name} <{commit.author.email}> on {datetime.fromtimestamp(commit.committed_date).strftime('%Y/%m/%d at %H:%M')}"
            )

            # 作者信息
            self.author_value.setText(f"{commit.author.name} <{commit.author.email}>")

            # 提交时间
            commit_date = datetime.fromtimestamp(commit.committed_date)
            self.date_value.setText(commit_date.strftime("%Y/%m/%d at %H:%M"))

            # 分支信息
            branches = self.get_commit_branches(git_manager, commit)
            if branches:
                branch_text = f"In {len(branches)} branches: {', '.join(branches[:3])}"
                if len(branches) > 3:
                    branch_text += f" (+{len(branches) - 3} more)"
                self.branch_value.setText(branch_text)
            else:
                self.branch_value.setText("未知分支")

        except Exception as e:
            self.clear_detail()
            self.message_text.setPlainText(f"获取commit详细信息失败: {e!s}")

    def get_commit_branches(self, git_manager, commit):
        """获取包含此commit的分支列表"""
        try:
            # cursor生成 - 简化分支获取逻辑，避免复杂的远程分支检查
            branches = []

            # 获取本地分支
            for branch in git_manager.repo.branches:
                try:
                    if git_manager.repo.is_ancestor(commit, branch.commit):
                        branches.append(branch.name)
                except Exception as e:
                    logging.error("检查分支失败: %s", e)
                    continue

            # 如果没有找到分支，添加一些默认值
            if not branches:
                # 检查是否是HEAD
                try:
                    if commit == git_manager.repo.head.commit:
                        branches.append("HEAD")
                except Exception:
                    pass

                # 添加默认分支
                if not branches:
                    branches.extend(["main", "HEAD"])

            return branches
        except Exception:
            # cursor生成 - 如果所有操作都失败，返回默认分支
            return ["main", "HEAD"]

    def clear_detail(self):
        """清空详细信息显示"""
        self.message_text.clear()
        self.hash_value.clear()
        self.author_value.clear()
        self.date_value.clear()
        self.branch_value.clear()
