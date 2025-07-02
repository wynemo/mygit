import functools  # Added for partial
import logging
import os
import platform
import subprocess
import weakref
from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import QMimeData, Qt
from PyQt6.QtGui import QColor, QDrag
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QMenu,
    QTreeWidget,
    QTreeWidgetItem,
)

from editors.text_edit import SyncedTextEdit  # Ensure this is present
from utils import get_main_window_by_parent
from views.file_history_view import FileHistoryView

if TYPE_CHECKING:
    from git_manager_window import GitManagerWindow
    from workspace_explorer import WorkspaceExplorer


class FileTreeWidget(QTreeWidget):
    def __init__(self, parent=None, git_manager=None):
        super().__init__(parent)
        self.git_manager = git_manager
        self.workspace_explorer: "WorkspaceExplorer" = parent
        self.itemExpanded.connect(self._on_item_expanded)
        self.setDragEnabled(True)
        self.highlight_color = QColor(0, 120, 215)  # 蓝色高亮
        self.normal_color = QColor(0, 0, 0)  # 默认黑色
        self.itemDoubleClicked.connect(self._handle_double_click)
        self.drag_start_pos = None
        self.is_dragging = False
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def mousePressEvent(self, event):
        print("mousePressEvent")
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton) or not self.drag_start_pos:
            return

        # 如果移动距离太小，不开始拖放
        if (event.pos() - self.drag_start_pos).manhattanLength() < 10:
            return

        item = self.itemAt(self.drag_start_pos)
        if item and os.path.isfile(item.data(0, Qt.ItemDataRole.UserRole)):
            logging.debug("drag")
            self.is_dragging = True
            drag = QDrag(self)
            mime_data = QMimeData()
            mime_data.setText(item.data(0, Qt.ItemDataRole.UserRole))
            drag.setMimeData(mime_data)
            drag.exec()
            self.is_dragging = False
            self.drag_start_pos = None

    def mouseReleaseEvent(self, event):
        logging.debug("mouseReleaseEvent")
        self.drag_start_pos = None
        super().mouseReleaseEvent(event)

    def _handle_double_click(self, item):
        """处理双击事件"""
        logging.debug("handle_double_click")
        if self.is_dragging:  # 如果正在拖放，不处理双击
            return
        self.highlight_file_item(item.data(0, Qt.ItemDataRole.UserRole))

        file_path = item.data(0, Qt.ItemDataRole.UserRole)
        if os.path.isfile(file_path):
            # 获取父部件 (WorkspaceExplorer) 的引用

            self.workspace_explorer.open_file_in_tab(file_path)

    def _show_context_menu(self, position):
        """显示右键菜单"""
        item = self.itemAt(position)
        if not item:
            return

        file_path = item.data(0, Qt.ItemDataRole.UserRole)
        if not (os.path.isfile(file_path) or os.path.isdir(file_path)):
            return

        context_menu = QMenu(self)

        # 如果是文件，添加文件特有的菜单项
        if os.path.isfile(file_path):
            # 添加"文件历史"菜单项
            history_action = context_menu.addAction(self.tr("File History"))
            history_action.triggered.connect(lambda: self._show_file_history(file_path))

            # 添加"Git Blame"菜单项
            blame_action = context_menu.addAction(self.tr("Toggle Git Blame Annotations"))
            blame_action.triggered.connect(lambda: self._toggle_blame_annotation_in_editor(file_path))
        elif os.path.isdir(file_path):
            # 添加"文件夹历史"菜单项
            folder_history_action = context_menu.addAction(self.tr("View Folder History"))
            # Ensure workspace_explorer is available
            if self.workspace_explorer:
                folder_history_action.triggered.connect(
                    functools.partial(self.workspace_explorer.view_folder_history, file_path)
                )
            else:
                folder_history_action.setEnabled(False)  # Disable if workspace_explorer ref is missing

        # 添加"复制相对路径"菜单项（文件和文件夹都适用）
        copy_relative_path_action = context_menu.addAction(self.tr("Copy Relative Path"))
        copy_relative_path_action.triggered.connect(lambda: self._copy_relative_path(file_path))

        # 添加"拷贝完整路径"菜单项（文件和文件夹都适用）
        copy_full_path_action = context_menu.addAction(self.tr("Copy Full Path"))
        copy_full_path_action.triggered.connect(lambda: self._copy_full_path(file_path))

        # 添加"在文件管理器中打开"菜单项（文件和文件夹都适用）
        open_in_fm_action = context_menu.addAction(self.tr("Open in File Manager"))
        open_in_fm_action.triggered.connect(lambda: self._open_in_file_manager(file_path))

        # 只在 git 修改的文件上显示"Revert"菜单项
        workspace_explorer = self.workspace_explorer
        if workspace_explorer:
            try:
                # 获取相对于工作区的路径
                relative_path = os.path.relpath(file_path, workspace_explorer.workspace_path)
                relative_path = relative_path.replace(os.sep, "/")  # 统一使用斜杠

                # 检查文件是否在修改状态集合中
                if (
                    relative_path in workspace_explorer.all_file_statuses.get("modified", set())
                    or relative_path in workspace_explorer.all_file_statuses.get("staged", set())
                    or relative_path in workspace_explorer.all_file_statuses.get("untracked", set())
                ):
                    revert_action = context_menu.addAction(self.tr("Revert"))
                    revert_action.triggered.connect(lambda: self.revert_file(file_path))
            except Exception as e:
                logging.error("检查文件状态出错：%s", e)

        # 在鼠标位置显示菜单
        context_menu.exec(self.mapToGlobal(position))

    def _toggle_blame_annotation_in_editor(self, file_path: str):
        """Toggles Git blame annotations in the SyncedTextEdit for the given file_path."""
        main_window = self.parent()
        while main_window and not hasattr(main_window, "tab_widget"):
            main_window = main_window.parent()

        if not main_window:
            print("Main window not found.")
            return

        tab_widget = main_window.tab_widget
        target_editor: Optional[SyncedTextEdit] = None

        # Find the SyncedTextEdit for the given file_path
        for i in range(tab_widget.count()):
            widget = tab_widget.widget(i)
            if isinstance(widget, SyncedTextEdit):
                # SyncedTextEdit needs a file_path attribute to compare with.
                # Assuming it's set when the file is opened, e.g., widget.property("file_path")
                # or a direct attribute self.file_path on SyncedTextEdit.
                # From previous step, SyncedTextEdit has self.file_path
                editor_file_path = widget.property("file_path")
                if editor_file_path == file_path:
                    target_editor = widget
                    break

        if not target_editor:
            print(f"File '{os.path.basename(file_path)}' is not open in an editor or editor does not support blame.")
            # Optionally, open the file here if desired, then apply blame.
            # For now, we do nothing if not found.
            return

        # Now we have the target_editor
        if target_editor.showing_blame:
            target_editor.clear_blame_data()
            print(f"Blame annotations hidden for {os.path.basename(file_path)}.")
        else:
            # Attempt to find GitManager instance by traversing up from main_window
            # This part remains similar as it's about context/service location
            git_manager_owner = main_window
            while git_manager_owner and not hasattr(git_manager_owner, "git_manager"):
                git_manager_owner = git_manager_owner.parent()

            if not git_manager_owner or not hasattr(git_manager_owner, "git_manager"):
                print("GitManager not found.")
                return

            git_manager = git_manager_owner.git_manager
            if not git_manager.repo:
                print("Git repository not initialized in GitManager.")
                return

            try:
                relative_file_path = os.path.relpath(file_path, git_manager.repo_path)
            except ValueError:
                print(f"File path {file_path} is not within the repository path {git_manager.repo_path}")
                target_editor.clear_blame_data()  # Ensure clean state
                return

            blame_data_list = git_manager.get_blame_data(relative_file_path)

            if blame_data_list:
                target_editor.set_blame_data(blame_data_list)
                print(f"Blame annotations shown for {os.path.basename(file_path)}.")
            else:
                print(f"No blame information available for {os.path.basename(file_path)}.")
                target_editor.clear_blame_data()  # Clear any potential stale data

    def _show_file_history(self, file_path):
        """显示文件历史"""
        # 获取 GitManagerWindow 的引用
        main_window: "GitManagerWindow" = self.window()

        print("main_window", id(main_window), main_window)

        # 确认是否能找到主窗口的 tab_widget
        if not hasattr(main_window, "tab_widget"):
            print("无法找到主窗口的标签页组件")
            return

        # 创建文件历史视图
        file_history_view = FileHistoryView(file_path, parent=self)
        # 设置文件路径属性用于唯一标识
        file_history_view.setProperty("file_history_path", file_path)

        # 在 GitManagerWindow 的 tab_widget 中添加新标签页
        file_name = os.path.basename(file_path)
        tab_title = f"{file_name} {self.tr('History')}"

        # 检查标签页是否已存在
        for i in range(main_window.tab_widget.count()):
            widget = main_window.tab_widget.widget(i)
            if main_window.tab_widget.tabText(i) == tab_title and widget.property("file_history_path") == file_path:
                main_window.tab_widget.setCurrentIndex(i)
                return

        # 添加新标签页
        main_window.tab_widget.addTab(file_history_view, tab_title)
        main_window.tab_widget.setCurrentIndex(main_window.tab_widget.count() - 1)

        file_history_view.compare_with_working_requested.connect(main_window.show_compare_with_working_dialog)

        main_window.bottom_widget.show()

    def revert_file(self, file_path: str):
        """还原文件"""
        if self.git_manager and self.git_manager.repo:
            self.git_manager.revert(file_path)
            self.workspace_explorer.refresh_file_tree()
        else:
            print("Git repository not initialized in GitManager.")

    def _copy_relative_path(self, file_path: str):
        """复制文件相对于工作区目录的路径到剪贴板"""
        workspace_explorer = self.workspace_explorer

        if workspace_explorer and hasattr(workspace_explorer, "workspace_path") and workspace_explorer.workspace_path:
            try:
                relative_path = os.path.relpath(file_path, workspace_explorer.workspace_path)
                # 复制到剪贴板
                clipboard = QApplication.clipboard()
                clipboard.setText(relative_path)
            except Exception as e:
                logging.error("复制相对路径失败：%s", e)
        else:
            logging.error("无法获取工作区路径")

    def highlight_file_item(self, file_path: str):
        """高亮显示指定的文件项"""
        # 清除之前的高亮
        parent_workspace_explorer: WorkspaceExplorer = get_main_window_by_parent(self).workspace_explorer
        if parent_workspace_explorer and parent_workspace_explorer.current_highlighted_item:
            # 检查 weakref 是否仍然有效
            current_highlighted_item = parent_workspace_explorer.current_highlighted_item()
            if current_highlighted_item:  # 只有当引用有效时才清除高亮
                current_highlighted_item.setForeground(0, self.normal_color)
            parent_workspace_explorer.current_highlighted_item = None  # 清除旧的引用

        # 查找并高亮新项目
        items = self.findItems(os.path.basename(file_path), Qt.MatchFlag.MatchContains | Qt.MatchFlag.MatchRecursive)
        for item in items:
            if item.data(0, Qt.ItemDataRole.UserRole) == file_path:
                item.setForeground(0, self.highlight_color)
                if parent_workspace_explorer:
                    parent_workspace_explorer.current_highlighted_item = weakref.ref(item)
                self.scrollToItem(item, QAbstractItemView.ScrollHint.EnsureVisible)
                break

    def _on_item_expanded(self, item: QTreeWidgetItem):
        """处理目录展开事件"""
        if not self.workspace_explorer:
            return

        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path or not os.path.isdir(path):
            return

        # 检查是否有虚拟子项
        if item.childCount() == 1 and not item.child(0).data(0, Qt.ItemDataRole.UserRole):
            # 移除虚拟子项
            item.takeChild(0)
            # 加载实际内容
            self.workspace_explorer._add_directory_items(path, item, 2)

    def _copy_full_path(self, file_path: str):
        """复制文件的完整路径到剪贴板"""
        try:
            clipboard = QApplication.clipboard()
            clipboard.setText(file_path)
            logging.info("已复制完整路径：%s", file_path)
        except Exception as e:
            logging.error("复制完整路径失败：%s", e)

    def _open_in_file_manager(self, file_path: str):
        """在文件管理器中打开文件或文件夹"""
        try:
            # 如果是文件，获取其父目录
            if os.path.isfile(file_path):
                dir_path = os.path.dirname(file_path)
            else:
                dir_path = file_path

            full_path = os.path.join(self.workspace_explorer.workspace_path, file_path)

            system = platform.system().lower()

            if system == "darwin":  # macOS
                # 使用 open 命令
                print("full path", full_path)
                subprocess.run(["open", "-R", full_path], check=True)
            elif system == "windows":  # Windows
                # 使用 explorer 命令
                subprocess.run(["explorer", "/select,", full_path.replace("/", "\\")], check=True)
            else:  # Linux and other Unix-like systems
                # 尝试通用的 xdg-open 命令
                try:
                    subprocess.run(["xdg-open", dir_path], check=True)
                except FileNotFoundError:
                    # 如果 xdg-open 不存在，尝试其他常见的文件管理器
                    file_managers = ["nautilus", "dolphin", "thunar", "pcmanfm", "caja"]
                    for fm in file_managers:
                        try:
                            subprocess.run([fm, dir_path], check=True)
                            break
                        except FileNotFoundError:
                            continue
                    else:
                        logging.warning("无法找到适合的文件管理器")
                        return

            logging.info("已在文件管理器中打开：%s", dir_path)
        except Exception as e:
            logging.error("在文件管理器中打开失败：%s", e)

    def _get_expanded_paths(self, item: QTreeWidgetItem, expanded_paths: set):
        """递归获取所有展开的文件夹路径"""
        for i in range(item.childCount()):
            child = item.child(i)
            if child.isExpanded():
                child_path = child.data(0, Qt.ItemDataRole.UserRole)
                if child_path and os.path.isdir(child_path):
                    expanded_paths.add(child_path)
                    self._get_expanded_paths(child, expanded_paths)

    def save_expanded_state(self) -> set:
        """保存当前所有展开的文件夹路径"""
        expanded_paths = set()
        self._get_expanded_paths(self.invisibleRootItem(), expanded_paths)
        return expanded_paths

    def _restore_expanded_state(self, item: QTreeWidgetItem, expanded_paths: set):
        """递归恢复文件夹的展开状态"""
        for i in range(item.childCount()):
            child = item.child(i)
            child_path = child.data(0, Qt.ItemDataRole.UserRole)
            if child_path and os.path.isdir(child_path) and child_path in expanded_paths:
                child.setExpanded(True)
                self._restore_expanded_state(child, expanded_paths)

    def restore_expanded_state(self, expanded_paths: set):
        """恢复之前保存的文件夹展开状态"""
        self._restore_expanded_state(self.invisibleRootItem(), expanded_paths)
