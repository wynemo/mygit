import logging

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from text_diff_viewer import DiffViewer
from threads import AIGeneratorThread
from utils import get_main_window


class CommitDialog(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("提交更改")
        parent = self.parent()
        print("parent has file_tree", hasattr(parent, "file_tree"))
        if hasattr(parent, "file_tree"):
            self.setMinimumWidth(parent.file_tree.width())
            self.setMinimumHeight(parent.file_tree.height())
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # 创建主布局
        layout = QVBoxLayout(self)

        # 创建分割器
        splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(splitter)

        # 上半部分 文件列表
        files_widget = QWidget()
        files_layout = QVBoxLayout(files_widget)

        # 暂存区域
        staged_widget = QWidget()
        staged_layout = QVBoxLayout(staged_widget)
        staged_header = QHBoxLayout()
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
        unstaged_header = QHBoxLayout()
        unstaged_label = QLabel("Unstaged Files")
        stage_button = QPushButton("+")
        # stage_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
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

        message_header = QHBoxLayout()
        message_label = QLabel("Commit Message:")
        self.ai_button = QPushButton("✨")
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
        self.commit_button = button_box.addButton("Commit", QDialogButtonBox.ButtonRole.AcceptRole)
        self.commit_and_push_button = button_box.addButton("Commit & Push", QDialogButtonBox.ButtonRole.ActionRole)
        # self.cancel_button = button_box.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)

        # 连接信号
        self.commit_button.clicked.connect(self.accept)
        self.commit_and_push_button.clicked.connect(self.commit_and_push)
        # self.cancel_button.clicked.connect(self.reject)
        layout.addWidget(button_box)

        # 初始化显示文件状态
        # self.refresh_file_status()

        # 初始化 AI 生成器线程
        self.ai_thread = AIGeneratorThread(self)
        self.ai_thread.finished.connect(self._on_message_generated)
        self.ai_thread.error.connect(self._on_generation_error)

        # 为两个树形控件添加点击事件处理
        self.staged_tree.itemDoubleClicked.connect(lambda item: self.show_file_diff(item, True))
        self.unstaged_tree.itemDoubleClicked.connect(lambda item: self.show_file_diff(item, False))

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
        return get_main_window().git_manager

    @property
    def parent_window(self):
        return get_main_window()

    def refresh_file_status(self):
        """刷新文件状态显示"""
        self.staged_tree.clear()
        self.unstaged_tree.clear()

        repo = self.git_manager.repo

        # 获取暂存的文件
        staged = repo.index.diff("HEAD")
        for diff in staged:
            item = QTreeWidgetItem(self.staged_tree)
            item.setText(0, diff.a_path)
            item.setText(1, "Modified")

        # 获取未暂存的文件
        unstaged = repo.index.diff(None)
        for diff in unstaged:
            item = QTreeWidgetItem(self.unstaged_tree)
            logging.info(f"commit_dialog: unstaged file: {diff.a_path}")
            item.setText(0, diff.a_path)
            item.setText(1, "Modified")

        # 获取未跟踪的文件
        untracked = repo.untracked_files
        for file_path in untracked:
            item = QTreeWidgetItem(self.unstaged_tree)
            item.setText(0, file_path)
            item.setText(1, "Untracked")

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
                print(f"无法暂存文件：{e!s}")

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
                print(f"无法取消暂存文件：{e!s}")

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

            # 禁用 AI 按钮，显示正在生成中
            self.ai_button.setEnabled(False)
            self.ai_button.setText("⏳")

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
        self.ai_button.setEnabled(True)
        self.ai_button.setText("✨")

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
            if is_staged:
                # 对于暂存区文件，比较 HEAD 和暂存区
                try:
                    old_content = repo.git.show(f"HEAD:{file_path}")
                except:
                    # 如果是新文件，HEAD 中没有内容
                    old_content = ""
                new_content = repo.git.show(f":{file_path}")  # 暂存区内容
            # 对于未暂存文件，比较暂存区和工作区
            elif item.text(1) == "Untracked":
                # 未跟踪文件，显示空内容和当前文件内容
                old_content = ""
                try:
                    with open(f"{repo.working_dir}/{file_path}", "r", encoding="utf-8") as f:
                        new_content = f.read()
                except Exception as e:
                    new_content = f"Error reading file: {e!s}"
            else:
                # 已修改文件，比较暂存区和工作区
                try:
                    old_content = repo.git.show(f":{file_path}")  # 暂存区内容
                except:
                    old_content = ""
                try:
                    with open(f"{repo.working_dir}/{file_path}", "r", encoding="utf-8") as f:
                        new_content = f.read()
                except Exception as e:
                    new_content = f"Error reading file: {e!s}"

            # 设置差异内容
            diff_viewer.set_texts(old_content, new_content, file_path, "HEAD", None)
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

    def commit_and_push(self):
        """执行提交并推送"""
        try:
            # 先执行提交
            self.accept()
            if self.result() != QDialog.DialogCode.Accepted:
                # 如果提交失败，直接返回
                return

            # 获取当前分支
            current = self.git_manager.repo.active_branch

            # 执行推送
            origin = self.git_manager.repo.remote(name="origin")
            push_info = origin.push(refspec=f"{current.name}:{current.name}")

            # 检查推送结果
            if push_info[0].flags & push_info[0].ERROR:
                raise Exception("Push failed")
            self.parent_window.update_commit_history()

            QMessageBox.information(self, "成功", "推送成功")

        except Exception as e:
            logging.exception("推送失败")
            QMessageBox.critical(self, "错误", f"推送失败：{e!s}")
