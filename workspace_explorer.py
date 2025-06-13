import functools  # Added for partial
import logging
import os
import platform
import subprocess
import weakref
from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import QMimeData, QPoint, Qt
from PyQt6.QtGui import QAction, QColor, QDrag, QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QMenu,
    QPushButton,  # Added QPushButton
    QSplitter,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from commit_widget import CommitWidget
from components.file_search_widget import FileSearchWidget
from editors.modified_text_edit import ModifiedTextEdit
from editors.text_edit import SyncedTextEdit  # Ensure this is present
from file_changes_view import FileChangesView
from file_history_view import FileHistoryView
from folder_history_view import FolderHistoryView  # Import FolderHistoryView
from syntax_highlighter import CodeHighlighter
from utils import get_main_window_by_parent
from utils.language_map import LANGUAGE_MAP

if TYPE_CHECKING:
    from git_manager_window import GitManagerWindow


class WorkspaceExplorer(QWidget):
    def __init__(self, parent=None, git_manager=None):
        super().__init__(parent)
        self.git_manager = git_manager
        # Initialize all_file_statuses
        self.all_file_statuses = {"modified": set(), "staged": set(), "untracked": set()}
        self.current_highlighted_item = None
        self.setup_ui()

    def setup_ui(self):
        # 创建主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 创建刷新按钮
        self.refresh_button = QPushButton("🔄")
        self.refresh_button.setFixedSize(30, 30)
        self.refresh_button.clicked.connect(self.refresh_file_tree)
        layout.addWidget(self.refresh_button)  # Add button to layout

        # 创建水平分割器
        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        # 创建文件搜索组件
        self.file_search_widget = FileSearchWidget(self)
        self.file_search_widget.hide()

        # 创建文件树
        self.file_tree = FileTreeWidget(self, git_manager=self.git_manager)  # 传入 self 作为父部件和 git_manager
        self.file_tree.setHeaderLabels(["工作区文件"])

        self.commit_widget = CommitWidget(self)

        self.file_changes_view = FileChangesView(self)
        self.file_changes_view.file_selected.connect(get_main_window_by_parent(self).on_file_selected)
        self.file_changes_view.compare_with_working_requested.connect(
            get_main_window_by_parent(self).show_compare_with_working_dialog
        )

        # 创建标签页组件
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.setAcceptDrops(True)
        self.tab_widget.dragEnterEvent = self.tab_drag_enter_event
        self.tab_widget.dropEvent = self.tab_drop_event

        self.tab_widget.tabBar().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tab_widget.tabBar().customContextMenuRequested.connect(self.show_tab_context_menu)

        # 添加组件到分割器
        self.splitter.addWidget(self.file_tree)
        self.splitter.addWidget(self.commit_widget)
        self.splitter.addWidget(self.file_changes_view)
        self.splitter.addWidget(self.file_search_widget)
        self.splitter.addWidget(self.tab_widget)

        # 连接标签页切换信号
        self.tab_widget.currentChanged.connect(self.on_tab_changed)

        self.show_file_tree()

        # 添加分割器到布局
        layout.addWidget(self.splitter)

    def tab_drag_enter_event(self, event: QDragEnterEvent):
        """处理拖拽进入事件"""
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def tab_drop_event(self, event: QDropEvent):
        """处理拖放事件"""
        file_path = event.mimeData().text()
        if os.path.isfile(file_path):
            self.open_file_in_tab(file_path)

    def open_file_in_tab(self, file_path: str):
        """在新标签页中打开文件"""
        try:
            # 检查文件是否已经打开
            for i in range(self.tab_widget.count()):
                if self.tab_widget.widget(i).property("file_path") == file_path:
                    self.tab_widget.setCurrentIndex(i)
                    return

            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # 创建新的文本编辑器
            text_edit = ModifiedTextEdit(self)
            text_edit.setProperty("file_path", file_path)  # Keep for any existing logic relying on property
            text_edit.file_path = file_path  # Add this for consistency with show_blame
            text_edit.setPlainText(content)
            text_edit.set_editable()

            text_edit.highlighter = CodeHighlighter(text_edit.document())
            language = LANGUAGE_MAP.get(file_path.split(".")[-1], "text")
            print("language is", language, file_path)
            text_edit.highlighter.set_language(language)

            # 添加新标签页
            file_name = os.path.basename(file_path)
            self.tab_widget.addTab(text_edit, file_name)
            self.tab_widget.setCurrentWidget(text_edit)

            # Connect blame_annotation_clicked signal to GitManagerWindow handler
            main_git_window = self.parent()
            handler_name = "handle_blame_click_from_editor"
            while main_git_window:
                if hasattr(main_git_window, handler_name):
                    break  # Found GitManagerWindow with the handler
                if not hasattr(main_git_window, "parent"):  # Should always exist for QWidget until top
                    main_git_window = None
                    break
                parent_candidate = main_git_window.parent()
                if parent_candidate == main_git_window:  # Should not happen in typical Qt parentage
                    main_git_window = None
                    break
                main_git_window = parent_candidate

            diffs = text_edit.get_diffs(main_git_window.git_manager)
            text_edit.set_line_modifications(diffs)

            if main_git_window and hasattr(main_git_window, handler_name):
                try:
                    text_edit.blame_annotation_clicked.connect(getattr(main_git_window, handler_name))
                    logging.info(
                        f"Connected blame_annotation_clicked from editor for '{file_path}' to {handler_name} in GitManagerWindow."
                    )
                except Exception as e_connect:
                    logging.error(f"Failed to connect blame_annotation_clicked for '{file_path}': {e_connect}")
            else:
                logging.warning(
                    f"Could not find GitManagerWindow with handler '{handler_name}' for editor '{file_path}'. Blame click will not be handled globally."
                )

            text_edit.dirty_status_changed.connect(self.update_filename_display)

        except Exception as e:
            logging.exception("Error opening file")
            print(f"Error opening file: {e}")

    def close_tab(self, index: int):
        """关闭标签页"""
        self.tab_widget.removeTab(index)

    def close_all_tabs(self):
        """关闭所有标签页"""
        for i in range(self.tab_widget.count() - 1, -1, -1):
            self.tab_widget.removeTab(i)

    def on_tab_changed(self, index: int):
        """当标签页切换时高亮对应文件"""
        current_widget = self.tab_widget.widget(index)
        if current_widget and hasattr(current_widget, "file_path"):
            self.file_tree.highlight_file_item(current_widget.file_path)

    def get_current_file_path(self) -> Optional[str]:
        """获取当前标签页的文件路径"""
        current_widget = self.tab_widget.currentWidget()
        if current_widget and hasattr(current_widget, "file_path"):
            return current_widget.file_path
        return None

    def set_workspace_path(self, path):
        """设置并加载工作区路径"""
        self.workspace_path = path
        self.refresh_file_tree()

    def refresh_file_tree(self):
        """刷新文件树"""
        logging.debug("refresh_file_tree")
        if self.git_manager and self.git_manager.repo and hasattr(self, "workspace_path"):
            self.all_file_statuses = self.git_manager.get_all_file_statuses()
        else:
            self.all_file_statuses = {"modified": set(), "staged": set(), "untracked": set()}

        self.file_tree.clear()
        if hasattr(self, "workspace_path"):
            self._add_directory_items(self.workspace_path, self.file_tree.invisibleRootItem(), 0)

    def _add_directory_items(self, path: str, parent_item_in_tree: QTreeWidgetItem, level: int = 0) -> bool:
        """cursor 生成 - 优先显示目录
        将被.gitignore 忽略的文件/文件夹显示为灰色
        Args:
            path: 目录路径
            parent_item_in_tree: 父节点
            level: 当前目录深度 (0 表示根目录)
        """
        current_dir_or_descendant_is_modified = False
        try:
            # 分离目录和文件
            directories = []
            files = []

            for item_name in os.listdir(path):
                item_path = os.path.join(path, item_name)
                if os.path.isdir(item_path):
                    directories.append(item_name)
                elif os.path.isfile(item_path):
                    files.append(item_name)

            # 排序目录和文件
            directories = sorted(directories, key=lambda x: x.lower())
            files = sorted(files, key=lambda x: x.lower())

            # 先处理目录
            for item_name in directories:
                item_path = os.path.join(path, item_name)
                tree_item = QTreeWidgetItem(parent_item_in_tree)
                tree_item.setText(0, item_name)
                tree_item.setData(0, Qt.ItemDataRole.UserRole, item_path)

                # 检查是否被.gitignore 忽略
                if self.git_manager and self.git_manager.is_ignored(item_path):
                    tree_item.setForeground(0, QColor(128, 128, 128))  # 灰色

                is_this_entry_modified = False

                # 递归处理子目录
                if level < 2:
                    if self._add_directory_items(item_path, tree_item, level + 1):
                        tree_item.setForeground(0, QColor(165, 42, 42))  # 目录被修改
                        is_this_entry_modified = True
                else:
                    # 添加虚拟子项使目录可展开
                    placeholder = QTreeWidgetItem(tree_item)
                    tree_item.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)

                    # tree_item.setForeground(0, QColor(165, 42, 42))  # 这个后续再说
                    # is_this_entry_modified = True

                if is_this_entry_modified:
                    current_dir_or_descendant_is_modified = True

            # 再处理文件
            for item_name in files:
                item_path = os.path.join(path, item_name)
                tree_item = QTreeWidgetItem(parent_item_in_tree)
                tree_item.setText(0, item_name)
                tree_item.setData(0, Qt.ItemDataRole.UserRole, item_path)

                # 检查是否被.gitignore 忽略
                if self.git_manager and self.git_manager.is_ignored(item_path):
                    tree_item.setForeground(0, QColor(128, 128, 128))  # 灰色

                is_this_entry_modified = False

                if os.path.isfile(item_path):
                    if hasattr(self, "workspace_path") and self.workspace_path and os.path.isabs(self.workspace_path):
                        try:
                            relative_path = os.path.relpath(item_path, self.workspace_path)
                            relative_path = relative_path.replace(os.sep, "/")

                            if relative_path in self.all_file_statuses.get("modified", set()):
                                tree_item.setForeground(0, QColor(165, 42, 42))  # Brown color
                                is_this_entry_modified = True
                            elif relative_path in self.all_file_statuses.get("staged", set()):
                                tree_item.setForeground(0, QColor(210, 180, 140))  # Light brown color
                            elif relative_path in self.all_file_statuses.get("untracked", set()):
                                tree_item.setForeground(0, QColor(0, 128, 0))  # Green color
                        except ValueError:
                            logging.debug(f"Cannot get relative path for {item_path} against {self.workspace_path}.")
                        except Exception as e_status:
                            logging.error(f"Error processing file status for {item_path}: {e_status}")
                    else:
                        logging.debug(
                            f"Workspace path not suitable for file status: {self.workspace_path if hasattr(self, 'workspace_path') else 'Not set'}"
                        )

                elif os.path.isdir(item_path):
                    if self._add_directory_items(item_path, tree_item):
                        tree_item.setForeground(0, QColor(165, 42, 42))  # Color directory brown
                        is_this_entry_modified = True

                if is_this_entry_modified:
                    current_dir_or_descendant_is_modified = True

        except FileNotFoundError:
            logging.warning(f"Directory not found during tree population: {path}.")
        except PermissionError:
            logging.warning(f"Permission denied for directory: {path}.")
        except Exception as e:
            logging.error(f"Error loading directory contents for {path}: {e}")

        return current_dir_or_descendant_is_modified

    def show_tab_context_menu(self, pos: QPoint):
        tab_index = self.tab_widget.tabBar().tabAt(pos)
        if tab_index == -1:
            return

        menu = QMenu(self)

        close_others_action = QAction("关闭其他标签页", self)
        close_others_action.triggered.connect(lambda: self.close_other_tabs(tab_index))
        menu.addAction(close_others_action)

        close_all_action = QAction("关闭所有标签页", self)
        close_all_action.triggered.connect(self.close_all_tabs)
        menu.addAction(close_all_action)

        menu.exec(self.tab_widget.tabBar().mapToGlobal(pos))

    def close_other_tabs(self, current_index):
        for i in reversed(range(self.tab_widget.count())):
            if i != current_index:
                self.tab_widget.removeTab(i)

    def set_left_panel_visible(self, visible: bool):
        """显示或隐藏左侧文件树面板"""
        if visible:
            self.show_file_tree()
        else:
            self.file_tree.hide()
            self.file_search_widget.hide()
            self.commit_widget.hide()
            self.file_changes_view.hide()
            self.splitter.setSizes([0, 0, 0, 0, 1])  # 只显示右侧

    def show_file_tree(self):
        self.file_tree.show()
        self.file_search_widget.hide()
        self.commit_widget.hide()
        self.file_changes_view.hide()
        self.splitter.setSizes([200, 0, 0, 0, 400])

    def show_commit_dialog(self):
        """显示提交对话框并隐藏文件树"""
        self.commit_widget.show()
        self.file_tree.hide()
        self.file_search_widget.hide()
        self.file_changes_view.hide()
        self.splitter.setSizes([0, 200, 0, 0, 400])

    def show_file_changes_view(self):
        self.file_changes_view.show()
        self.file_tree.hide()
        self.file_search_widget.hide()
        self.commit_widget.hide()
        self.splitter.setSizes([0, 0, 200, 0, 400])

    def update_filename_display(self, file_path: str, is_dirty: bool):
        print("update_filename_display", file_path, is_dirty)
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if isinstance(tab, ModifiedTextEdit) and tab.file_path == file_path:
                if is_dirty:
                    self.tab_widget.setTabText(i, f"*{os.path.basename(file_path)}")
                else:
                    self.tab_widget.setTabText(i, os.path.basename(file_path))

    def show_file_search_widget(self):
        """显示文件搜索组件"""
        self.file_search_widget.show()
        self.file_tree.hide()
        self.commit_widget.hide()
        self.file_changes_view.hide()
        self.splitter.setSizes([0, 0, 0, 200, 400])

    def view_folder_history(self, folder_path: str):
        """显示文件夹历史视图"""
        if not folder_path:
            logging.error("错误：文件夹路径为空，无法查看历史。")
            return

        main_win = get_main_window_by_parent(self)
        if not main_win:
            logging.error("错误：无法获取主窗口实例。")
            return

        # Create the FolderHistoryView instance
        # FolderHistoryView gets git_manager from main_win internally
        folder_history_view = FolderHistoryView(folder_path, self)

        # Add it to the main window's tab widget
        folder_name = os.path.basename(folder_path.rstrip("/"))
        tab_title = f"历史：{folder_name}"

        main_win.tab_widget.addTab(folder_history_view, tab_title)
        main_win.tab_widget.setCurrentIndex(main_win.tab_widget.count() - 1)


class FileTreeWidget(QTreeWidget):
    def __init__(self, parent=None, git_manager=None):
        super().__init__(parent)
        self.git_manager = git_manager
        self.workspace_explorer = None
        # 查找父 WorkspaceExplorer 实例
        p = parent
        while p and not isinstance(p, WorkspaceExplorer):
            p = p.parent()
        if p:
            self.workspace_explorer = p
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
            workspace_explorer = self.parent()
            while workspace_explorer and not isinstance(workspace_explorer, WorkspaceExplorer):
                workspace_explorer = workspace_explorer.parent()

            if workspace_explorer:
                workspace_explorer.open_file_in_tab(file_path)

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
            history_action = context_menu.addAction("文件历史")  # "File History"
            history_action.triggered.connect(lambda: self._show_file_history(file_path))

            # 添加"Git Blame"菜单项
            blame_action = context_menu.addAction("切换 Git Blame 注释")  # "Toggle Git Blame Annotations"
            blame_action.triggered.connect(lambda: self._toggle_blame_annotation_in_editor(file_path))
        elif os.path.isdir(file_path):
            # 添加"文件夹历史"菜单项
            folder_history_action = context_menu.addAction("查看文件夹历史")  # "View Folder History"
            # Ensure workspace_explorer is available
            if self.workspace_explorer:
                folder_history_action.triggered.connect(
                    functools.partial(self.workspace_explorer.view_folder_history, file_path)
                )
            else:
                folder_history_action.setEnabled(False)  # Disable if workspace_explorer ref is missing

        # 添加"复制相对路径"菜单项（文件和文件夹都适用）
        copy_relative_path_action = context_menu.addAction("复制相对路径")
        copy_relative_path_action.triggered.connect(lambda: self._copy_relative_path(file_path))

        # 添加"拷贝完整路径"菜单项（文件和文件夹都适用）
        copy_full_path_action = context_menu.addAction("拷贝完整路径")
        copy_full_path_action.triggered.connect(lambda: self._copy_full_path(file_path))

        # 添加"在文件管理器中打开"菜单项（文件和文件夹都适用）
        open_in_fm_action = context_menu.addAction("在文件管理器中打开")
        open_in_fm_action.triggered.connect(lambda: self._open_in_file_manager(file_path))

        # 只在 git 修改的文件上显示"Revert"菜单项
        workspace_explorer = self.parent()
        while workspace_explorer and not isinstance(workspace_explorer, WorkspaceExplorer):
            workspace_explorer = workspace_explorer.parent()

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
                    revert_action = context_menu.addAction("Revert")
                    revert_action.triggered.connect(lambda: self.revert_file(file_path))
            except Exception as e:
                logging.error(f"检查文件状态出错：{e}")

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

        # 在 GitManagerWindow 的 tab_widget 中添加新标签页
        file_name = os.path.basename(file_path)
        tab_title = f"{file_name} 历史"

        # 检查标签页是否已存在
        for i in range(main_window.tab_widget.count()):
            if main_window.tab_widget.tabText(i) == tab_title:
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
            workspace_explorer = self.parent()
            while workspace_explorer and not isinstance(workspace_explorer, WorkspaceExplorer):
                workspace_explorer = workspace_explorer.parent()
            if workspace_explorer:
                workspace_explorer.refresh_file_tree()
        else:
            print("Git repository not initialized in GitManager.")

    def _copy_relative_path(self, file_path: str):
        """复制文件相对于工作区目录的路径到剪贴板"""
        workspace_explorer = self.parent()
        while workspace_explorer and not isinstance(workspace_explorer, WorkspaceExplorer):
            workspace_explorer = workspace_explorer.parent()

        if workspace_explorer and hasattr(workspace_explorer, "workspace_path") and workspace_explorer.workspace_path:
            try:
                relative_path = os.path.relpath(file_path, workspace_explorer.workspace_path)
                # 复制到剪贴板
                clipboard = QApplication.clipboard()
                clipboard.setText(relative_path)
            except Exception as e:
                logging.error(f"复制相对路径失败：{e}")
        else:
            logging.error("无法获取工作区路径")

    def get_parent_workspace_explorer(self) -> Optional[WorkspaceExplorer]:
        workspace_explorer = self.parent()
        while workspace_explorer and not isinstance(workspace_explorer, WorkspaceExplorer):
            workspace_explorer = workspace_explorer.parent()
        return workspace_explorer

    def highlight_file_item(self, file_path: str):
        """高亮显示指定的文件项"""
        # 清除之前的高亮
        parent_workspace_explorer: WorkspaceExplorer = self.get_parent_workspace_explorer()
        if parent_workspace_explorer and parent_workspace_explorer.current_highlighted_item:
            current_highlighted_item = parent_workspace_explorer.current_highlighted_item()
            if current_highlighted_item:
                current_highlighted_item.setForeground(0, self.normal_color)

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
            logging.info(f"已复制完整路径：{file_path}")
        except Exception as e:
            logging.error(f"复制完整路径失败：{e}")

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

            logging.info(f"已在文件管理器中打开：{dir_path}")
        except Exception as e:
            logging.error(f"在文件管理器中打开失败：{e}")
