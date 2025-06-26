import functools  # Added for partial
import logging
import os
import platform
import subprocess
import weakref
from typing import TYPE_CHECKING, Optional, Union

from PyQt6.QtCore import QMimeData, QPoint, QSize, Qt
from PyQt6.QtGui import QAction, QColor, QDrag, QDragEnterEvent, QDropEvent, QIcon, QTextCursor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from commit_widget import CommitWidget
from components.file_quick_search_popup import FileQuickSearchPopup  # 新增导入
from components.file_search_widget import FileSearchWidget
from editors.modified_text_edit import ModifiedTextEdit
from editors.text_edit import SyncedTextEdit  # Ensure this is present
from file_changes_view import FileChangesView
from file_history_view import FileHistoryView
from folder_history_view import FolderHistoryView  # Import FolderHistoryView
from syntax_highlighter import CodeHighlighter
from utils import get_main_window_by_parent
from utils.language_icons import get_folder_icon, get_language_icon
from utils.language_map import LANGUAGE_MAP

if TYPE_CHECKING:
    from git_manager import GitManager
    from git_manager_window import GitManagerWindow


class WorkspaceExplorer(QWidget):
    def __init__(self, parent=None, git_manager=None):
        super().__init__(parent)
        self.git_manager: "GitManager" | None = git_manager
        # Initialize all_file_statuses
        self.all_file_statuses = {"modified": set(), "staged": set(), "untracked": set()}
        self.current_highlighted_item = None
        self.setup_ui()

    def setup_ui(self):
        # 创建主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 创建顶部水平布局来放置刷新按钮和搜索框
        top_bar_buttons_layout = QHBoxLayout()
        top_bar_buttons_layout.setContentsMargins(0, 0, 0, 0)
        top_bar_buttons_layout.setSpacing(5)  # Add spacing between elements

        # 创建刷新按钮
        self.refresh_button = QPushButton(QIcon("icons/refresh.svg"), "")
        self.refresh_button.setFixedSize(30, 30)
        self.refresh_button.setToolTip(self.tr("Refresh"))
        self.refresh_button.clicked.connect(self._handle_refresh_clicked)
        top_bar_buttons_layout.addWidget(self.refresh_button)  # Add button to top layout

        # --- Search Box ---
        self.search_box_widget = QWidget(self)
        self.search_box_layout = QHBoxLayout(self.search_box_widget)
        self.search_box_layout.setContentsMargins(10, 5, 10, 5)
        self.search_box_layout.setSpacing(0)  # 减少间距
        self.search_box_layout.addStretch(1)  # 添加左侧拉伸

        self.search_icon_label = QLabel(self)
        self.search_icon_label.setPixmap(QIcon("icons/search.svg").pixmap(QSize(15, 15)))
        self.search_box_layout.addWidget(self.search_icon_label)

        self.folder_name_label = QLabel("", self)  # 初始为空字符串
        self.folder_name_label.setStyleSheet("color: #000000;")
        self.search_box_layout.addWidget(self.folder_name_label)
        self.search_box_layout.addStretch(1)  # 添加右侧拉伸

        self.search_box_widget.setStyleSheet("""
            QWidget {
                background-color: #D3D3D3; /* 浅灰色 */
                border-radius: 15px; /* Rounded corners */
            }
        """)
        self.search_box_widget.setFixedSize(300, 25)  # Adjust size as needed
        top_bar_buttons_layout.addWidget(self.search_box_widget)

        # 新增：初始化文件快速搜索弹窗组件
        self.file_quick_search_popup = FileQuickSearchPopup(self)
        self.file_quick_search_popup.file_selected.connect(self.open_file_in_tab)
        self.search_box_widget.mousePressEvent = self._show_file_quick_search_popup_event

        top_bar_buttons_layout.addStretch(1)  # Add stretch to push elements to the left

        # 将顶部水平布局添加到主布局
        layout.addLayout(top_bar_buttons_layout)

        # 创建水平分割器
        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        # 创建文件树
        self.file_tree = FileTreeWidget(self, git_manager=self.git_manager)  # 传入 self 作为父部件和 git_manager
        self.file_tree.setHeaderLabels([self.tr("Workspace Files")])

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

        # 创建文件搜索组件
        self.file_search_widget = FileSearchWidget(self)
        self.file_search_widget.hide()

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

    def open_file_in_tab(self, file_path: str, line_number: Union[int, None] = None):
        """在新标签页中打开文件，并可选择跳转到指定行号
        Args:
            file_path: 文件路径
            line_number: 可选的行号，如果提供则跳转到该行
        """
        try:
            # 检查文件是否已经打开
            for i in range(self.tab_widget.count()):
                if self.tab_widget.widget(i).property("file_path") == file_path:
                    self.tab_widget.setCurrentIndex(i)
                    if line_number is not None:
                        text_edit = self.tab_widget.widget(i)
                        cursor = text_edit.textCursor()
                        cursor.movePosition(QTextCursor.MoveOperation.Start)
                        cursor.movePosition(
                            QTextCursor.MoveOperation.Down, QTextCursor.MoveMode.MoveAnchor, line_number - 1
                        )
                        text_edit.setTextCursor(cursor)
                        text_edit.ensureCursorVisible()
                    return

            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # 创建新的文本编辑器
            text_edit = ModifiedTextEdit(self)
            text_edit.setProperty("file_path", file_path)
            text_edit.file_path = file_path
            text_edit.setPlainText(content)
            text_edit.set_editable()

            text_edit.highlighter = CodeHighlighter(text_edit.document())
            language = LANGUAGE_MAP.get(file_path.split(".")[-1], "text")
            text_edit.highlighter.set_language(language)

            # 添加新标签页
            file_name = os.path.basename(file_path)
            tab_index = self.tab_widget.addTab(text_edit, file_name)
            # 为标签页设置语言图标
            self.tab_widget.setTabIcon(tab_index, get_language_icon(file_name))
            self.tab_widget.setCurrentWidget(text_edit)

            # 如果提供了行号，跳转到该行
            if line_number is not None:
                cursor = text_edit.textCursor()
                cursor.movePosition(QTextCursor.MoveOperation.Start)
                cursor.movePosition(QTextCursor.MoveOperation.Down, QTextCursor.MoveMode.MoveAnchor, line_number - 1)
                text_edit.setTextCursor(cursor)
                text_edit.ensureCursorVisible()

            # Connect blame_annotation_clicked signal to GitManagerWindow handler
            handler_name = "handle_blame_click_from_editor"
            main_git_window = get_main_window_by_parent(self)

            diffs = text_edit.get_diffs(main_git_window.git_manager)
            text_edit.set_line_modifications(diffs)

            if main_git_window and hasattr(main_git_window, handler_name):
                try:
                    text_edit.blame_annotation_clicked.connect(getattr(main_git_window, handler_name))
                    logging.info(
                        "Connected blame_annotation_clicked from editor for '%s' to %s in GitManagerWindow.",
                        file_path,
                        handler_name,
                    )
                except Exception as e_connect:
                    logging.error("Failed to connect blame_annotation_clicked for '%s': %s", file_path, e_connect)
            else:
                logging.warning(
                    "Could not find GitManagerWindow with handler '%s' for editor '%s'. Blame click will not be handled globally.",
                    handler_name,
                    file_path,
                )

            text_edit.dirty_status_changed.connect(self.update_filename_display)

        except Exception as e:
            logging.exception("Error opening file")
            print(f"Error opening file: {e}")

    def handle_file_event(self, file_path: str, event_type: str):
        """处理文件事件，刷新相应的打开文件
        Args:
            file_path: 文件路径
            event_type: 事件类型，'deleted' 或 'updated'
        """
        try:
            # 遍历所有打开的标签页，找到匹配的文件
            for i in range(self.tab_widget.count()):
                tab_widget = self.tab_widget.widget(i)
                if not tab_widget or not hasattr(tab_widget, "file_path"):
                    continue

                # 检查文件路径是否匹配
                if tab_widget.file_path == file_path:
                    if event_type == "deleted":
                        # 文件被删除，关闭对应的标签页
                        self.tab_widget.removeTab(i)
                        logging.info("文件 %s 已删除，关闭对应标签页", file_path)
                        break
                    elif event_type == "updated":
                        # 文件被更新，重新加载内容
                        if os.path.exists(file_path):
                            with open(file_path, "r", encoding="utf-8") as f:
                                content = f.read()

                            # 保存当前光标位置
                            cursor = tab_widget.textCursor()
                            cursor_position = cursor.position()

                            # 更新文本内容
                            tab_widget.setPlainText(content)

                            # 恢复光标位置（如果可能）
                            try:
                                cursor.setPosition(min(cursor_position, len(content)))
                                tab_widget.setTextCursor(cursor)
                            except:
                                pass  # 如果恢复光标位置失败，忽略错误

                            # 重新设置行修改标记
                            main_git_window = get_main_window_by_parent(self)
                            if main_git_window and main_git_window.git_manager:
                                diffs = tab_widget.get_diffs(main_git_window.git_manager)
                                tab_widget.set_line_modifications(diffs)

                            logging.info("文件 %s 已更新，重新加载内容", file_path)
                        else:
                            # 文件不存在，当作删除处理
                            self.tab_widget.removeTab(i)
                            logging.info("文件 %s 不存在，关闭对应标签页", file_path)
                        break
        except Exception:
            logging.exception("处理文件事件时出错")

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
        self.update_folder_name_label(path)  # 新增：调用更新标签的方法
        self.search_box_widget.setToolTip(f"{self.tr('Search')} - {self.folder_name_label.text()}")  # 新增 ToolTip

    def update_folder_name_label(self, path: str):
        """cursor 生成 - 更新文件夹名称标签的显示"""
        folder_name = os.path.basename(path)
        self.folder_name_label.setText(folder_name)

    def refresh_file_tree(self):
        """cursor 生成 - 刷新文件树，保留已展开的文件夹状态"""
        logging.debug("refresh_file_tree")

        if self.git_manager and self.git_manager.repo and hasattr(self, "workspace_path"):
            self.all_file_statuses = self.git_manager.get_all_file_statuses()
        else:
            self.all_file_statuses = {"modified": set(), "staged": set(), "untracked": set()}

        # 保存当前展开的文件夹路径
        expanded_paths = self.file_tree.save_expanded_state()

        # 保存当前高亮的文件路径
        saved_highlighted_path = None
        if self.current_highlighted_item:
            current_item = self.current_highlighted_item()
            if current_item:
                saved_highlighted_path = current_item.data(0, Qt.ItemDataRole.UserRole)

        # 在清空文件树之前，将 current_highlighted_item 设置为 None
        # 避免在文件树清空后，weakref 引用到已删除的 QTreeWidgetItem 对象
        self.current_highlighted_item = None

        self.file_tree.clear()
        if hasattr(self, "workspace_path"):
            self._add_directory_items(self.workspace_path, self.file_tree.invisibleRootItem(), 0)

        # 恢复展开状态
        if expanded_paths:
            self.file_tree.restore_expanded_state(expanded_paths)

        # 恢复高亮状态
        if saved_highlighted_path:
            self.file_tree.highlight_file_item(saved_highlighted_path)

        # 刷新文件快速搜索弹窗的文件列表
        self._update_file_quick_search_list()

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
                # 设置文件夹图标
                tree_item.setIcon(0, get_folder_icon())

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
                # 根据文件扩展名设置语言图标
                tree_item.setIcon(0, get_language_icon(item_name))

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
                            logging.debug("Cannot get relative path for %s against %s.", item_path, self.workspace_path)
                        except Exception as e_status:
                            logging.error("Error processing file status for %s: %s", item_path, e_status)
                    else:
                        logging.debug(
                            "Workspace path not suitable for file status: %s",
                            self.workspace_path if hasattr(self, "workspace_path") else "Not set",
                        )

                elif os.path.isdir(item_path):
                    if self._add_directory_items(item_path, tree_item):
                        tree_item.setForeground(0, QColor(165, 42, 42))  # Color directory brown
                        is_this_entry_modified = True

                if is_this_entry_modified:
                    current_dir_or_descendant_is_modified = True

        except FileNotFoundError:
            logging.warning("Directory not found during tree population: %s.", path)
        except PermissionError:
            logging.warning("Permission denied for directory: %s.", path)
        except Exception as e:
            logging.error("Error loading directory contents for %s: %s", path, e)

        return current_dir_or_descendant_is_modified

    def show_tab_context_menu(self, pos: QPoint):
        tab_index = self.tab_widget.tabBar().tabAt(pos)
        if tab_index == -1:
            return

        menu = QMenu(self)

        close_others_action = QAction(self.tr("Close Other Tabs"), self)
        close_others_action.triggered.connect(lambda: self.close_other_tabs(tab_index))
        menu.addAction(close_others_action)

        close_all_action = QAction(self.tr("Close All Tabs"), self)
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
                file_name = os.path.basename(file_path)
                if is_dirty:
                    self.tab_widget.setTabText(i, f"*{file_name}")
                else:
                    self.tab_widget.setTabText(i, file_name)
                # 确保图标仍然显示
                self.tab_widget.setTabIcon(i, get_language_icon(file_name))

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
        tab_title = f"{self.tr('History')}: {folder_name}"

        main_win.tab_widget.addTab(folder_history_view, tab_title)
        main_win.tab_widget.setCurrentIndex(main_win.tab_widget.count() - 1)

    def _handle_refresh_clicked(self):
        """
        cursor 生成
        处理刷新按钮点击事件，同时刷新文件树和提交历史
        """
        self.refresh_file_tree()  # 调用原有的刷新文件树方法

        # 刷新提交历史
        main_window = get_main_window_by_parent(self)
        if main_window and hasattr(main_window, "update_commit_history"):
            main_window.update_commit_history()

    def _show_file_quick_search_popup_event(self, event):
        # 只在左键点击时弹出
        if event.button() == Qt.MouseButton.LeftButton:
            # 传递 search_box_widget 作为 ref_widget
            self.file_quick_search_popup.show_popup(ref_widget=self.search_box_widget)
        # 继续原有事件处理
        QWidget.mousePressEvent(self.search_box_widget, event)

    def _update_file_quick_search_list(self):
        """cursor 生成 - 更新文件快速搜索弹窗的文件列表，过滤掉被 .gitignore 忽略的文件和文件夹"""
        if not self.git_manager:
            return

        def _is_dir_ignored(path: str) -> bool:
            _path = os.path.relpath(path, self.git_manager.repo_path)
            return self.git_manager.is_ignored(_path) or _path == ".git"

        file_list = []
        for root, dirs, files in os.walk(self.workspace_path):
            # 过滤被忽略的文件夹
            dirs[:] = [d for d in dirs if not _is_dir_ignored(os.path.join(root, d))]
            # 过滤被忽略的文件
            for f in files:
                file_path = os.path.join(root, f)
                if not self.git_manager.is_ignored(os.path.relpath(file_path, self.git_manager.repo_path)):
                    file_list.append(file_path)
        self.file_quick_search_popup.set_file_list(file_list)


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
                logging.error("复制相对路径失败：%s", e)
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
