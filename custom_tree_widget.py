from functools import partial

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMenu,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from hover_reveal_tree_widget import HoverRevealTreeWidget
from utils import get_main_window_by_parent


class CustomTreeWidget(HoverRevealTreeWidget):
    empty_scrolled_signal = pyqtSignal()  # cursor 生成

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def _merge_branch(self, git_manager, branch_name):
        """执行合并分支操作"""
        error = git_manager.merge_branch(branch_name)
        if error:
            get_main_window_by_parent(self).notification_widget.show_message(f"合并失败：{error}")
        else:
            self.parent().update_history(self.parent().git_manager, self.parent().branch)
            get_main_window_by_parent(self).notification_widget.show_message(f"成功合并分支：{branch_name}")

    def show_context_menu(self, position):
        item = self.itemAt(position)
        if not item:
            return

        menu = QMenu(self)

        # 添加原有的复制功能
        copy_commit_action = menu.addAction("copy commit")
        copy_commit_action.triggered.connect(partial(self.copy_commit_to_clipboard, item))
        copy_commit_message_action = menu.addAction("copy commit message")
        copy_commit_message_action.triggered.connect(partial(self.copy_commmit_message_to_clipboard, item))

        # 获取父窗口 (CommitHistoryView) 以访问 GitManager
        parent = self.parent()
        while parent and not hasattr(parent, "git_manager"):
            parent = parent.parent()

        if parent and hasattr(parent, "git_manager") and parent.git_manager:
            git_manager = parent.git_manager
            repo = git_manager.repo
            current_branch = repo.active_branch

            # 从 item 获取分支信息 (假设分支信息在第 2 列)
            item_branches = item.text(2).split(", ")

            # 检查 item 是否属于其他分支
            if current_branch.name not in item_branches:
                # 创建 Checkout 主菜单项
                checkout_menu = menu.addMenu("Checkout")

                # 获取所有分支
                all_branches = git_manager.get_branches()

                # 为每个分支创建子菜单项
                for branch in all_branches:
                    if branch != current_branch.name and branch in item_branches:
                        action = checkout_menu.addAction(branch)
                        action.triggered.connect(partial(self._checkout_branch, git_manager, branch))

            # 检查是否是远程分支且当前分支跟踪它
            for branch_name in item_branches:
                if branch_name.startswith("☁️ origin/"):
                    remote_branch = branch_name.strip("☁️").lstrip()
                    try:
                        # 检查当前分支是否跟踪此远程分支
                        if (
                            current_branch.tracking_branch()
                            and current_branch.tracking_branch().name == remote_branch
                            and current_branch.commit.hexsha != repo.refs[remote_branch].commit.hexsha
                        ):
                            merge_action = menu.addAction(f"Merge {remote_branch}")
                            merge_action.triggered.connect(partial(self._merge_branch, git_manager, remote_branch))
                    except Exception as e:
                        print(f"检查远程分支状态失败：{e}")

        menu.exec(self.mapToGlobal(position))

    def copy_commit_to_clipboard(self, item):
        if item:
            print("commit is", item.text(0))
            QApplication.clipboard().setText(item.text(0))
        else:
            print("item is None")

    def copy_commmit_message_to_clipboard(self, item):
        if item:
            print("commit is", item.text(0))
            QApplication.clipboard().setText(item.text(1))
        else:
            print("item is None")

    def _checkout_branch(self, git_manager, branch_name):
        """执行分支切换操作"""
        error = git_manager.switch_branch(branch_name)
        if error:
            print(f"切换分支失败：{error}")
        else:
            print(f"已切换到分支：{branch_name}")

    def wheelEvent(self, event):
        """重写滚轮事件，当没有有效滚动条时触发信号"""
        scroll_bar = self.verticalScrollBar()

        # 当滚动条不可见或不可用时触发
        if not scroll_bar.isVisible() or not scroll_bar.isEnabled() or scroll_bar.value() == scroll_bar.maximum():
            self.empty_scrolled_signal.emit()

        super().wheelEvent(event)  # 确保正常滚动行为


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QTreeWidget Overlay Text Example")
        self.setGeometry(100, 100, 700, 400)

        self.treeWidget = CustomTreeWidget()
        self.treeWidget.setColumnCount(3)
        self.treeWidget.setHeaderLabels(["Column 1 (Long Text)", "Column 2", "Column 3"])

        # 调整列宽，让第一列的文本更容易被截断
        self.treeWidget.setColumnWidth(0, 200)
        self.treeWidget.setColumnWidth(1, 150)
        self.treeWidget.setColumnWidth(2, 150)

        # 示例数据
        data = [
            (
                "这是一段非常非常非常非常长的文本，它肯定无法在第一列中完全显示出来，我们希望选中时能看到全部。",
                "Item A2",
                "Item A3",
            ),
            ("短文本 1", "Item B2", "Item B3"),
            ("这是另一段也比较长的文本内容，用于测试当它被选中时的浮动显示效果。", "Item C2", "Item C3"),
            ("正常长度文本", "Item D2", "Item D3"),
            (
                "这是一个超级无敌究极旋风霹雳长长长长长长长长长长长长长长长长长长长长长长长长长长长长长长长长的文本串串串串串",
                "Item E2",
                "Item E3",
            ),
        ]

        for d in data:
            item = QTreeWidgetItem(self.treeWidget)
            item.setText(0, d[0])
            item.setText(1, d[1])
            item.setText(2, d[2])
            # 可选：仍然设置 ToolTip 作为备用
            item.setToolTip(0, d[0])

        self.treeWidget.currentItemChanged.connect(self.on_current_item_changed)

        # 如果希望鼠标悬停时也显示（更复杂，需要事件过滤器或 mouseMoveEvent）
        # self.treeWidget.setMouseTracking(True)
        # self.treeWidget.viewport().installEventFilter(self)

        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        layout.addWidget(self.treeWidget)
        self.setCentralWidget(central_widget)

    def on_current_item_changed(self, current: QTreeWidgetItem, previous: QTreeWidgetItem):
        if previous:  # 隐藏之前可能显示的浮层（如果逻辑放在这里）
            pass
        if current:
            self.treeWidget.show_full_text_for_item(current, 0)
        else:
            self.treeWidget.hide_overlay()

    # --- 如果想用事件过滤器实现悬停（更复杂） ---
    # def eventFilter(self, source, event):
    #     if source == self.treeWidget.viewport():
    #         if event.type() == QEvent.Type.MouseMove:
    #             index = self.treeWidget.indexAt(event.pos())
    #             if index.isValid() and index.column() == 0:
    #                 item = self.treeWidget.itemFromIndex(index)
    #                 self.treeWidget.show_full_text_for_item(item, 0, hover=True, pos=event.globalPos()) # 需要修改 show_full_text_for_item
    #             else:
    #                 self.treeWidget.hide_overlay() # 鼠标移出有效区域
    #         elif event.type() == QEvent.Type.Leave: # 鼠标离开 viewport
    #             self.treeWidget.hide_overlay()
    #
    #     return super().eventFilter(source, event)


if __name__ == "__main__":
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()
