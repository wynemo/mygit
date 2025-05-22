import os

from PyQt6.QtCore import QMimeData, QPoint, Qt
from PyQt6.QtGui import QAction, QDrag, QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QMenu,
    QSplitter,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

# BlameViewWidget is no longer used directly by _show_context_menu's "Git Blame" action.
# It might be used elsewhere, or can be removed if this was its only use.
# For now, let's assume it might be used by other parts, so we won't remove the import line itself,
# but the _show_git_blame method that used it will be removed.
from file_history_view import FileHistoryView
from syntax_highlighter import CodeHighlighter
from text_edit import SyncedTextEdit  # Ensure this is present
from utils.language_map import LANGUAGE_MAP


class WorkspaceExplorer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        # 创建主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 创建水平分割器
        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        # 创建文件树
        self.file_tree = FileTreeWidget(self)  # 传入self作为父部件
        self.file_tree.setHeaderLabels(["工作区文件"])

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
        self.splitter.addWidget(self.tab_widget)

        # 设置分割器的初始比例(1:2)
        self.splitter.setSizes([200, 400])

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
            text_edit = SyncedTextEdit()
            text_edit.setProperty("file_path", file_path)
            text_edit.setPlainText(content)

            text_edit.highlighter = CodeHighlighter(text_edit.document())
            language = LANGUAGE_MAP.get(file_path.split(".")[-1], "text")
            print("language is", language, file_path)
            text_edit.highlighter.set_language(language)

            # 添加新标签页
            file_name = os.path.basename(file_path)
            self.tab_widget.addTab(text_edit, file_name)
            self.tab_widget.setCurrentWidget(text_edit)

        except Exception as e:
            print(f"Error opening file: {e}")

    def close_tab(self, index: int):
        """关闭标签页"""
        self.tab_widget.removeTab(index)

    def set_workspace_path(self, path):
        """设置并加载工作区路径"""
        self.workspace_path = path
        self.refresh_file_tree()

    def refresh_file_tree(self):
        """刷新文件树"""
        self.file_tree.clear()
        if hasattr(self, "workspace_path"):
            self._add_directory_items(self.workspace_path, self.file_tree.invisibleRootItem())

    def _add_directory_items(self, path, parent):
        """递归添加目录内容到树形结构"""
        try:
            # item 排序 按首字母
            for item in sorted(os.listdir(path), key=lambda x: x[0]):
                item_path = os.path.join(path, item)
                tree_item = QTreeWidgetItem(parent)
                tree_item.setText(0, item)
                tree_item.setData(0, Qt.ItemDataRole.UserRole, item_path)

                if os.path.isdir(item_path):
                    self._add_directory_items(item_path, tree_item)

        except Exception as e:
            print(f"Error loading directory {path}: {e}")

    def show_tab_context_menu(self, pos: QPoint):
        tab_index = self.tab_widget.tabBar().tabAt(pos)
        if tab_index == -1:
            return

        menu = QMenu(self)

        close_others_action = QAction("关闭其他标签页", self)
        close_others_action.triggered.connect(lambda: self.close_other_tabs(tab_index))
        menu.addAction(close_others_action)

        menu.exec(self.tab_widget.tabBar().mapToGlobal(pos))

    def close_other_tabs(self, current_index):
        for i in reversed(range(self.tab_widget.count())):
            if i != current_index:
                self.tab_widget.removeTab(i)


class FileTreeWidget(QTreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
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
            print("drag")
            self.is_dragging = True
            drag = QDrag(self)
            mime_data = QMimeData()
            mime_data.setText(item.data(0, Qt.ItemDataRole.UserRole))
            drag.setMimeData(mime_data)
            drag.exec()
            self.is_dragging = False
            self.drag_start_pos = None

    def mouseReleaseEvent(self, event):
        print("mouseReleaseEvent")
        self.drag_start_pos = None
        super().mouseReleaseEvent(event)

    def _handle_double_click(self, item):
        """处理双击事件"""
        print("handle_double_click")
        if self.is_dragging:  # 如果正在拖放，不处理双击
            return

        file_path = item.data(0, Qt.ItemDataRole.UserRole)
        if os.path.isfile(file_path):
            # 获取父部件(WorkspaceExplorer)的引用
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
        if not os.path.isfile(file_path):
            return

        context_menu = QMenu(self)

        # 添加"文件历史"菜单项
        history_action = context_menu.addAction("文件历史")
        history_action.triggered.connect(lambda: self._show_file_history(file_path))

        # 添加"Git Blame"菜单项
        blame_action = context_menu.addAction("Toggle Git Blame Annotations")  # Renamed for clarity
        blame_action.triggered.connect(lambda: self._toggle_blame_annotation_in_editor(file_path))

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
        target_editor: SyncedTextEdit = None

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
            while main_window and not hasattr(main_window, "git_manager"):
                main_window = main_window.parent()
            if not main_window or not hasattr(main_window, "git_manager"):
                print("GitManager not found.")
                return

            git_manager = main_window.git_manager
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
                # SyncedTextEdit needs to have its file_path attribute set for context if not already
                # This is crucial if load_blame_data or other functions inside SyncedTextEdit
                # depend on its own self.file_path.
                # We assume SyncedTextEdit's file_path is already correctly set when the tab was opened.
                target_editor.blame_annotations_per_line = blame_data_list
                target_editor.showing_blame = True
                # target_editor.load_blame_data(blame_data_list)
                print(f"Blame annotations shown for {os.path.basename(file_path)}.")
            else:
                print(f"No blame information available for {os.path.basename(file_path)}.")
                target_editor.clear_blame_data()  # Clear any potential stale data

    def _show_file_history(self, file_path):
        """显示文件历史"""
        # 获取GitManagerWindow的引用
        main_window = self.window()

        print("main_window", id(main_window), main_window)

        # 确认是否能找到主窗口的tab_widget
        if not hasattr(main_window, "tab_widget"):
            print("无法找到主窗口的标签页组件")
            return

        # 创建文件历史视图
        file_history_view = FileHistoryView(file_path, parent=self)

        # 在GitManagerWindow的tab_widget中添加新标签页
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

        main_window.bottom_widget.show()
