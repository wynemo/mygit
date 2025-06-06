import logging
from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTextBrowser, QTextEdit

# 常量用于分支显示
MAX_BRANCHES_TO_SHOW = 3


class CommitDetailView(QTextBrowser):
    """
    Commit详细信息视图
    直接使用QTextEdit作为主控件, 显示选中commit的详细信息
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        # 初始化实例变量
        self.all_branches = []  # 存储当前提交涉及的所有分支名称
        self.branches_expanded = False  # 标记分支列表是否已展开
        self.current_commit = None  # 存储当前正在显示的提交对象
        self.git_manager = None  # 存储Git仓库管理器实例
        self.setStyleSheet(
            """
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
        """
        )
        self.setFrameShape(QTextEdit.Shape.NoFrame)
        self.setMinimumHeight(100)
        # 设置文本交互标志，允许鼠标和键盘选择文本，并启用链接点击
        self.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
            | Qt.TextInteractionFlag.LinksAccessibleByMouse  # 允许鼠标点击链接
            | Qt.TextInteractionFlag.LinksAccessibleByKeyboard  # 允许键盘激活链接
        )
        # 连接 anchorClicked 信号到处理方法, 用于处理HTML链接点击事件
        self.anchorClicked.connect(self.handle_branch_link_click)

    def update_commit_detail(self, git_manager, commit):
        """
        更新commit详细信息显示。
        当选择的commit变化时调用此方法。
        """
        # 存储 git_manager 和 commit 对象，以便在点击链接或后续刷新时使用
        self.git_manager = git_manager
        self.current_commit = commit

        if not self.current_commit:
            self.clear()  # 如果没有commit对象，则清空视图
            return

        try:
            # 获取并存储当前commit关联的所有分支信息
            self.all_branches = self.get_commit_branches(self.git_manager, self.current_commit)
            # 调用内部方法来渲染提交详情的HTML内容
            self._render_commit_detail()

        except Exception as e:
            self.clear()
            # 使用setHtml以防错误信息包含可能被错误解析的特殊字符
            self.setHtml(f"获取commit详细信息失败: {e!s}")

    def _render_commit_detail(self):
        """
        根据当前存储的提交信息 (self.current_commit, self.all_branches) 和
        分支展开状态 (self.branches_expanded) 来渲染提交详情的HTML内容。
        此方法负责生成最终在视图中显示的HTML字符串。
        """
        if not self.current_commit:  # 如果没有当前提交信息，则不执行任何操作
            return

        # 准备提交信息：替换换行符为<br>以在HTML中正确显示多行消息
        message = self.current_commit.message.strip().replace("\n", "<br>")
        # 格式化提交日期和作者信息
        commit_date = datetime.fromtimestamp(self.current_commit.committed_date)
        # HTML转义作者邮箱中的 '<' 和 '>' 符号，防止它们被解析为HTML标签
        info_line = (
            f"{self.current_commit.hexsha[:8]} {self.current_commit.author.name} "
            f"&lt;{self.current_commit.author.email}&gt; on "
            f"{commit_date.strftime('%Y/%m/%d at %H:%M')}"
        )

        # --- 分支显示逻辑 ---
        branch_text = "未知分支"  # 默认分支文本
        num_branches = len(self.all_branches)  # 获取分支总数

        if num_branches > 0:  # 仅当存在关联分支时才处理分支显示
            # 情况1: 分支数量超过最大显示限制 (MAX_BRANCHES_TO_SHOW) 且当前未展开
            if num_branches > MAX_BRANCHES_TO_SHOW and not self.branches_expanded:
                # 截取部分分支用于显示
                shown_branches = ", ".join(self.all_branches[:MAX_BRANCHES_TO_SHOW])
                # 计算隐藏的分支数量
                hidden_count = num_branches - MAX_BRANCHES_TO_SHOW
                # 构建分支文本，包含 "more" 链接 (<a> 标签)，其 href 指向 #more_branches
                branch_text = (
                    f"In {num_branches} branches: {shown_branches} "
                    f'<a href="#more_branches">(+{hidden_count} more)</a>'  # 点击此链接会展开分支列表
                )
            # 情况2: 分支列表已展开 (self.branches_expanded is True)
            elif self.branches_expanded:
                # 显示所有分支
                all_branches_str = ", ".join(self.all_branches)
                # 计算可折叠的分支数量 (即当前显示的超出 MAX_BRANCHES_TO_SHOW 的部分)
                collapsible_count = num_branches - MAX_BRANCHES_TO_SHOW
                less_link = ""  # 初始化 "less" 链接为空
                # 仅当确实有分支可以折叠时 (即分支总数大于初始显示数)，才创建 "less" 链接
                if collapsible_count > 0:
                    less_link = f' <a href="#less_branches">(-{collapsible_count} less)</a>'  # 点击此链接会折叠分支列表
                branch_text = f"In {num_branches} branches: {all_branches_str}{less_link}"
            # 情况3: 分支数量未超过最大显示限制，或等于限制
            else:
                # 直接显示所有分支，无需展开/折叠功能
                branch_text = f"In {num_branches} branches: {', '.join(self.all_branches)}"

        # --- 组合所有信息为HTML ---
        # 使用 <pre> 标签来保留提交消息的原始格式 (如空格和换行)，同时允许CSS控制自动换行 (white-space: pre-wrap; word-wrap: break-word;)
        # 使用 <p> 标签来组织提交信息行和分支信息行
        detail_content = (
            f"<pre style='white-space: pre-wrap; word-wrap: break-word;'>{message}</pre>"
            f"<p>{info_line}</p>"
            f"<p>分支: {branch_text}</p>"
        )
        # 将生成的HTML内容设置到QTextEdit控件中
        self.setHtml(detail_content)

    def handle_branch_link_click(self, url):
        """
        处理HTML中分支展开/折叠链接 (<a> 标签) 的点击事件。
        此方法由 QTextEdit 的 anchorClicked 信号触发。
        """
        # url.fragment() 获取链接的片段标识符 (例如 "#more_branches" 中的 "more_branches")
        if url.fragment() == "more_branches":  # 如果点击的是 "more" 链接
            self.branches_expanded = True  # 设置分支列表为展开状态
            self._render_commit_detail()  # 重新渲染提交详情以反映状态变化
        elif url.fragment() == "less_branches":  # 如果点击的是 "less" 链接
            self.branches_expanded = False  # 设置分支列表为折叠状态
            self._render_commit_detail()  # 重新渲染提交详情以反映状态变化

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
            logging.exception("Error getting commit branches")  # 获取提交分支时出错
            return []
