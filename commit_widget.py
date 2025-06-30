import logging

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from components.spin_icons import SpinningButtonIcon
from text_diff_viewer import DiffViewer
from threads import AIGeneratorThread
from utils import get_main_window_by_parent


class CommitWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        parent = self.parent()
        if hasattr(parent, "file_tree"):
            self.setMinimumWidth(parent.file_tree.width())
            self.setMinimumHeight(parent.file_tree.height())
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFrameStyle(QFrame.Shape.StyledPanel)

        # 创建主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 创建分割器
        splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(splitter)

        # 上半部分 文件列表
        files_widget = QWidget()
        files_layout = QVBoxLayout(files_widget)
        files_layout.setContentsMargins(0, 0, 0, 0)

        # 暂存区域
        staged_widget = QWidget()
        staged_layout = QVBoxLayout(staged_widget)
        staged_layout.setContentsMargins(0, 0, 0, 0)
        staged_layout.setSpacing(0)
        staged_header = QHBoxLayout()
        staged_header.setContentsMargins(0, 0, 0, 0)
        staged_label = QLabel("Staged Files")
        unstage_button = QPushButton("-")
        unstage_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        unstage_button.setFixedWidth(30)
        unstage_button.clicked.connect(self.unstage_selected_file)
        staged_header.addWidget(staged_label)
        staged_header.addWidget(unstage_button)
        staged_header.addStretch()
        staged_layout.addLayout(staged_header)

        self.staged_tree = QTreeWidget()
        self.staged_tree.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.staged_tree.setHeaderLabels(["Staged Files", "Status"])
        staged_layout.addWidget(self.staged_tree)
        files_layout.addWidget(staged_widget)

        # 未暂存区域
        unstaged_widget = QWidget()
        unstaged_layout = QVBoxLayout(unstaged_widget)
        unstaged_layout.setContentsMargins(0, 0, 0, 0)
        unstaged_layout.setSpacing(0)
        unstaged_header = QHBoxLayout()
        unstaged_header.setContentsMargins(0, 0, 0, 0)
        unstaged_label = QLabel("Unstaged Files")
        stage_button = QPushButton("+")
        stage_button.setFixedWidth(30)
        stage_button.clicked.connect(self.stage_selected_file)
        unstaged_header.addWidget(unstaged_label)
        unstaged_header.addWidget(stage_button)
        unstaged_header.addStretch()
        unstaged_layout.addLayout(unstaged_header)

        self.unstaged_tree = QTreeWidget()
        self.unstaged_tree.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.unstaged_tree.setHeaderLabels(["Unstaged Files", "Status"])
        unstaged_layout.addWidget(self.unstaged_tree)
        files_layout.addWidget(unstaged_widget)

        splitter.addWidget(files_widget)

        # 下半部分，提交信息
        commit_widget = QWidget()
        commit_layout = QVBoxLayout(commit_widget)
        commit_layout.setContentsMargins(0, 0, 0, 0)
        commit_layout.setSpacing(0)

        message_header = QHBoxLayout()
        message_header.setContentsMargins(0, 0, 0, 0)
        message_label = QLabel("Commit Message:")
        self.ai_button = SpinningButtonIcon("icons/star.svg", "icons/hourglass.svg", "")
        self.ai_button.setFixedWidth(30)
        self.ai_button.setToolTip("使用 AI 生成提交信息")
        self.ai_button.clicked.connect(self.generate_commit_message)
        message_header.addWidget(message_label)
        message_header.addWidget(self.ai_button)
        message_header.addStretch()
        commit_layout.addLayout(message_header)

        self.message_edit = QTextEdit()
        commit_layout.addWidget(self.message_edit)

        splitter.addWidget(commit_widget)

        # 修改按钮区域
        button_box = QDialogButtonBox()
        self.commit_button = button_box.addButton("Commit", QDialogButtonBox.ButtonRole.ActionRole)
        layout.addWidget(button_box)

        # 连接信号
        self.commit_button.clicked.connect(self.accept)

        # 初始化 AI 生成器线程
        self.ai_thread = AIGeneratorThread(self)
        self.ai_thread.finished.connect(self._on_message_generated)
        self.ai_thread.error.connect(self._on_generation_error)

        # 为两个树形控件添加点击事件处理
        self.staged_tree.itemDoubleClicked.connect(lambda item: self.show_file_diff(item, True))
        self.unstaged_tree.itemDoubleClicked.connect(lambda item: self.show_file_diff(item, False))

        # 添加右键菜单支持
        self.unstaged_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.unstaged_tree.customContextMenuRequested.connect(self._show_unstaged_context_menu)

    def showEvent(self, event):
        self.refresh_file_status()
        super().showEvent(event)

    def focusInEvent(self, event):
        print("focusInEvent in commit_dialog")
        self.refresh_file_status()
        super().focusInEvent(event)

    # git manager property
    @property
    def git_manager(self):
        return self.parent_window.git_manager

    @property
    def parent_window(self):
        return get_main_window_by_parent(self)

    def revert_file(self, file_path: str):
        """还原文件"""
        try:
            # 还原文件修改
            self.git_manager.repo.git.checkout("--", file_path)
            self.refresh_file_status()
        except Exception:
            logging.exception("还原文件 %s 失败", file_path)

    def _show_unstaged_context_menu(self, position):
        """显示未暂存文件的右键菜单"""
        item = self.unstaged_tree.itemAt(position)
        if not item:
            return

        file_path = item.text(0)
        menu = QMenu(self)

        # 只有修改过的文件可以还原
        if item.text(1) == "Modified":
            revert_action = menu.addAction("Revert")
            revert_action.triggered.connect(lambda: self.revert_file(file_path))

        open_action = menu.addAction("在工作区打开")
        open_action.triggered.connect(
            lambda: self.parent_window.workspace_explorer.open_file_in_tab(
                f"{self.git_manager.repo.working_dir}/{file_path}"
            )
        )

        menu.exec(self.unstaged_tree.mapToGlobal(position))

    def refresh_file_status(self):
        """刷新文件状态显示"""
        self.staged_tree.clear()
        self.unstaged_tree.clear()

        repo = self.git_manager.repo

        # 获取暂存的文件
        staged = repo.index.diff("HEAD")
        CHANGE_TYPE_MAP = {
            "A": "新增",
            "D": "删除",
            "M": "修改",
            "R": "重命名",
            "T": "类型变更",
            "U": "未合并",
            "C": "复制",
        }
        for diff in staged:
            item = QTreeWidgetItem(self.staged_tree)
            # For renames/copies, a_path is old, b_path is new. We display new path.
            # For deletions, b_path is None. We display a_path.
            # For additions, a_path is None. We display b_path.
            # For modifications, a_path and b_path are typically the same.
            display_path = diff.b_path if diff.change_type in ('A', 'R', 'C') and diff.b_path else diff.a_path
            item.setText(0, display_path)
            status_char = diff.change_type
            # For renamed files, status_char can be e.g. 'R100' (100% similarity)
            # We only care about the first letter.
            status_description = CHANGE_TYPE_MAP.get(status_char[0], "未知")
            item.setText(1, status_description)

        # 获取未暂存的文件
        unstaged = repo.index.diff(None)
        for diff in unstaged:
            item = QTreeWidgetItem(self.unstaged_tree)
            # Similar logic for path display as above
            display_path = diff.b_path if diff.change_type in ('A', 'R', 'C') and diff.b_path else diff.a_path
            item.setText(0, display_path)
            status_char = diff.change_type
            status_description = CHANGE_TYPE_MAP.get(status_char[0], "未知")
            item.setText(1, status_description)
            logging.info("commit_dialog: unstaged file: %s, status: %s", display_path, status_description)


        # 获取未跟踪的文件
        untracked = repo.untracked_files
        for file_path in untracked:
            item = QTreeWidgetItem(self.unstaged_tree)
            item.setText(0, file_path)
            item.setText(1, "未跟踪") # Explicitly "Untracked" in Chinese

    def get_commit_message(self):
        return self.message_edit.toPlainText()

    def stage_selected_file(self):
        """暂存选中的文件"""
        selected_items = self.unstaged_tree.selectedItems()
        if selected_items:
            item = selected_items[0]
            file_path = item.text(0)
            try:
                self.git_manager.repo.index.add([file_path])
                self.refresh_file_status()
            except Exception as e:
                logging.error("无法暂存文件 %s: %s", file_path, e, exc_info=True)

    def unstage_selected_file(self):
        """取消暂存选中的文件"""
        selected_items = self.staged_tree.selectedItems()
        if selected_items:
            item = selected_items[0]
            file_path = item.text(0)
            try:
                self.git_manager.repo.git.reset("HEAD", file_path)
                self.refresh_file_status()
            except Exception as e:
                logging.error("无法取消暂存文件 %s: %s", file_path, e, exc_info=True)

    def generate_commit_message(self):
        """生成提交信息"""
        try:
            # 获取已暂存文件的变更
            repo = self.git_manager.repo
            diffs = []

            # 获取暂存区的变更
            staged = repo.index.diff("HEAD")
            for diff in staged:
                # 使用 "--" 来明确指定 diff.a_path 是一个文件路径，以避免在文件被删除时 git 无法正确解析路径
                diff_str = repo.git.diff("HEAD", "--", diff.a_path, cached=True)
                print(f"File: {diff.a_path}\n")
                diffs.append(f"File: {diff.a_path}\n{diff_str}")

            if not diffs:
                QMessageBox.warning(self, "警告", "没有已暂存的文件变更")
                return

            # 禁用 AI 按钮，显示正在生成中并启动旋转动画
            self.ai_button.setEnabled(False)
            self.ai_button.start()

            # 准备并启动线程
            self.ai_thread.diff_content = "\n\n".join(diffs)
            self.ai_thread.settings = self.parent_window.settings.settings
            self.ai_thread.start()

        except Exception as e:
            logging.exception("准备提交信息生成失败")
            QMessageBox.critical(self, "错误", f"准备提交信息生成失败：{e!s}")
            self._reset_ai_button()

    def _on_message_generated(self, message):
        """当消息生成完成时调用"""
        self.message_edit.setText(message)
        self._reset_ai_button()

    def _on_generation_error(self, error_message):
        """当消息生成出错时调用"""
        QMessageBox.critical(self, "错误", f"生成提交信息失败：{error_message!s}")
        self._reset_ai_button()

    def _reset_ai_button(self):
        """重置 AI 按钮状态"""
        self.ai_button.stop()  # 停止定时器
        self.ai_button.setEnabled(True)
        self.ai_button.setIcon(QIcon("icons/star.svg"))

    def show_file_diff(self, item, is_staged):
        """显示文件差异"""
        try:
            file_path = item.text(0)
            repo = self.git_manager.repo

            # 创建差异查看对话框
            diff_dialog = QDialog(self)
            diff_dialog.setWindowTitle(f"文件差异 - {file_path}")
            diff_dialog.resize(800, 600)

            layout = QVBoxLayout(diff_dialog)
            diff_viewer = DiffViewer()
            layout.addWidget(diff_viewer)

            # 获取文件内容
            file_status = item.text(1) # "新增", "删除", "修改", etc.

            if is_staged:
                # 对于暂存区文件，比较 HEAD 和暂存区
                # old_content is from HEAD
                if file_status == "新增": # File is in index, not in HEAD
                    old_content = ""
                else:
                    try:
                        old_content = repo.git.show(f"HEAD:{file_path}")
                    except git.exc.GitCommandError: # Should not happen if status is not "新增"
                        old_content = "" # Fallback

                # new_content is from Index
                if file_status == "删除": # File is in HEAD, not in index
                    new_content = ""
                else:
                    try:
                        new_content = repo.git.show(f":{file_path}")  # Index content
                    except git.exc.GitCommandError: # Should not happen if status is not "删除"
                        new_content = "" # Fallback
            else: # Unstaged files - comparing Index and Working Directory
                # old_content is from Index
                if file_status == "未跟踪": # File is in Workdir, not in Index
                    old_content = ""
                elif file_status == "新增": # This case implies file was added to index, then removed from workdir before commit? Or a state mismatch.
                                        # More likely "新增" appears for files added to index, viewed via staged.
                                        # For unstaged, "未跟踪" is for new files.
                                        # If truly "新增" in unstaged, it implies an odd state. For safety:
                    old_content = "" # Assuming it means new compared to empty index state for this path.
                else: # "修改" or "删除" from working directory compared to Index
                    try:
                        old_content = repo.git.show(f":{file_path}")  # Index content
                    except git.exc.GitCommandError: # File not in index (e.g. deleted from index then modified in workdir? Unlikely for "修改" status)
                        old_content = ""

                # new_content is from Working Directory
                if file_status == "删除": # File is in Index, but deleted from Workdir
                    new_content = ""
                else: # "修改" in Workdir, or "未跟踪" (new file in Workdir)
                    try:
                        full_file_path = f"{repo.working_dir}/{file_path}"
                        if os.path.exists(full_file_path):
                            with open(full_file_path, "r", encoding="utf-8") as f:
                                new_content = f.read()
                        else: # File does not exist in workdir, e.g. if status was "删除"
                            new_content = ""
                    except FileNotFoundError:
                        new_content = "" # Explicitly empty for deleted file
                    except Exception as e:
                        logging.warning("读取工作目录文件 %s 失败: %s", file_path, e)
                        new_content = f"读取文件错误: {e!s}"

            # 设置差异内容
            # Left side (old_content) is HEAD for staged, Index for unstaged.
            # Right side (new_content) is Index for staged, Working Directory for unstaged.
            left_commit_label = "HEAD" if is_staged else "索引"
            right_commit_label = "索引" if is_staged else "工作区"

            if file_status == "新增" and is_staged: # Staged Add (HEAD vs Index)
                left_commit_label = "空白" # Comparing empty with Index
            elif file_status == "删除" and is_staged: # Staged Delete (HEAD vs Index)
                right_commit_label = "空白" # Comparing HEAD with empty
            elif file_status == "未跟踪": # Unstaged Untracked (Index vs Workdir) - Index is effectively empty for this path
                left_commit_label = "空白"
            elif file_status == "删除" and not is_staged: # Unstaged Delete (Index vs Workdir)
                right_commit_label = "空白"


            diff_viewer.set_texts(old_content, new_content, file_path, file_path, left_commit_label, right_commit_label)
            diff_viewer.right_edit.set_editable()

            # 显示对话框
            diff_dialog.show()

        except Exception as e:
            logging.exception("显示文件差异失败")
            QMessageBox.critical(self, "错误", f"显示文件差异失败：{e!s}")

    def accept(self):
        """处理确认操作"""
        try:
            # 获取提交信息
            commit_message = self.get_commit_message()
            if not commit_message:
                QMessageBox.warning(self, "警告", "请输入提交信息")
                return

            # 检查是否有暂存的文件
            staged = self.git_manager.repo.index.diff("HEAD")
            if not staged:
                QMessageBox.warning(self, "警告", "没有暂存的文件")
                return

            # 执行提交
            self.git_manager.repo.index.commit(commit_message)

            self.parent_window.update_commit_history()
            self.refresh_file_status()

            # clear commit message
            self.message_edit.clear()

        except Exception as e:
            logging.exception("提交失败")
            QMessageBox.critical(self, "错误", f"提交失败：{e!s}")
