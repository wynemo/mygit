本文档描述了 `git_manager_window.py` 中主窗口的用户界面布局和核心交互组件。

## UI 布局与核心组件

`GitManagerWindow` 的主界面由多个可调整大小的区域和功能组件构成，整体采用自上而下的垂直布局，并嵌套了水平和垂直分割器来实现灵活的界面划分。

```
[GitManagerWindow] (QMainWindow)
│
└── [main_widget] (QWidget - 中心部件)
    │
    └── [main_layout] (QVBoxLayout - 主垂直布局)
        │
        ├── [TopBarWidget] (自定义顶部工具栏)
        │   │ - **功能按钮**:
        │   │   - **Open Folder**: 打开仓库 (触发 `open_folder_requested` 信号)
        │   │   - **Recent**: 下拉菜单显示最近打开的仓库列表 (通过 `update_recent_menu` 更新)
        │   │   - **Branch**: 分支选择下拉框 (支持新建分支，通过 `update_branches` 更新)
        │   │   - **Settings**: 设置按钮 (触发 `settings_requested` 信号)
        │   │   - **Toggle Bottom Panel**: 切换底部面板显示/隐藏 (动态更新图标)
        │   │   - **Toggle Left Panel**: 切换左侧面板显示/隐藏 (动态更新图标)
        │   │ - **状态控制**: 通过 `set_buttons_enabled` 管理依赖仓库的按钮状态
        │
        └── [vertical_splitter] (QSplitter - 主垂直分割器)
            │
            ├── [左侧面板分割器] left_panel_splitter (QSplitter)
            │   ├── [SideBarWidget] (自定义侧边栏)
            │   │   └── 包含工程、提交和变更按钮
            │   └── [WorkspaceExplorer] (工作区浏览器)
            │       │ - 顶部: `QHBoxLayout` 包含刷新按钮和搜索框
            │       └── 主体: `QSplitter` (水平分割器)，内部包含以下视图 (根据功能切换显示)：
            │           ├── [FileTreeWidget] (文件树视图): 显示当前工作区的文件结构，支持右键操作
            │           ├── [CommitWidget] (提交面板): 用于执行 Git 提交操作
            │           ├── [FileChangesView] (文件变更视图): 显示当前提交的文件修改列表
            │           ├── [FileSearchWidget] (文件搜索组件): 提供工作区文件搜索功能
            │           └── [QTabWidget] (文件内容/比较标签页 - 对应 GitManagerWindow 中的 compare_tab_widget):
            │               └── 用于在新标签页中打开文件内容 (`ModifiedTextEdit`) 或显示文件比较视图 (`CompareView`)。
            │                   每个文件比较标签页标题格式: "文件名 @ commit短哈希"
            │
            └── [下半部分] bottom_widget (QWidget - 底部面板，可整体显示/隐藏)
                │
                └── [bottom_layout] (QHBoxLayout)
                    │
                    └── [horizontal_splitter] (QSplitter - 水平分割器)
                        │
                        ├── [左侧] git_and_tab_widget (QWidget)
                        │   │
                        │   └── [v_git_and_tab_layout] (QVBoxLayout)
                        │       │
                        │       ├── [git_widget] (QWidget - 包含 Fetch/Pull/Push 按钮)
                        │       │
                        │       └── [tab_widget] (QTabWidget - 主功能标签页)
                        │           ├── 固定标签页 (索引 0): "提交历史" (CommitHistoryView)
                        │           │   ├── history_list (CustomTreeWidget): 列表形式显示提交记录
                        │           │   └── history_graph_list (GitGraphView): 图形化显示提交历史
                        │           │       (CommitHistoryView 会根据情况显示列表或图形视图)
                        │           └── 动态标签页: 用于显示单个文件的提交历史 (FileHistoryView 实例，按需创建)
                        │
                        ├── [右侧中间区域] right_splitter (QSplitter - 垂直分割器)
                        │   ├── [上部] file_changes_view (FileChangesView)
                        │   │   └── 显示选定提交中所更改的文件列表
                        │   └── [下部] commit_detail_view (CommitDetailView)
                        │       └── 显示选定提交的详细信息（作者、日期、消息等）
                        │
                        └── [右侧最外层] compare_view (CompareView)
                            └── 当主功能标签页 (tab_widget) 切换到单个文件历史时，此视图会显示，用于对比文件版本
                                (注: WorkspaceExplorer 内的 compare_tab_widget 用于工作区文件与历史版本的对比，
                                 此处的 compare_view 用于文件历史视图中的版本对比)
```

## 关键功能说明

**界面布局与动态调整：**

*   主窗口界面采用垂直分割布局 (`vertical_splitter`)，默认将上方的 `WorkspaceExplorer`（工作区浏览器）与下方的 `bottom_widget`（底部面板）按大约 5:3 的比例划分。用户可以拖动分割条调整此比例。
*   底部面板 (`bottom_widget`) 内部包含一个水平分割器 (`horizontal_splitter`)，它将左侧的主功能标签区域 (`tab_widget`) 和右侧的文件变更与提交详情区域 (`right_splitter`) 默认按大约 1:2 的比例划分。
*   右侧区域 (`right_splitter`) 自身也是一个垂直分割器，用于划分上部的 `FileChangesView`（文件变更列表）和下部的 `CommitDetailView`（提交详情），默认比例约为 300:200 (实际像素值，可调整)。
*   所有分割器均设置为禁止子组件折叠 (`setChildrenCollapsible(False)`)，确保所有视图区域始终可见（除非父容器被隐藏）。分割条宽度设置为 8px，方便用户拖动。
*   底部面板 (`bottom_widget`) 具有最小高度限制（100px），并且可以通过顶部工具栏的按钮进行整体显示或隐藏。

**核心组件交互：**

*   **TopBarWidget**: 作为应用的全局操作入口，负责处理仓库选择、分支切换、执行核心 Git 命令（提交、拉取、推送、抓取）以及打开设置对话框。它还维护最近打开的仓库列表，并提供切换底部面板和左侧面板可见性的功能。
*   **WorkspaceExplorer**:
    *   `WorkspaceExplorer` 内部通过一个 `QSplitter` 管理多个视图区域，这些视图根据用户操作动态显示/隐藏：
        *   **文件树 (`FileTreeWidget`)**: 左侧的文件树视图，展示当前打开 Git 仓库的工作区文件。用户可以右键点击文件进行特定操作（如查看文件历史、进行 blame）。
        *   **提交面板 (`CommitWidget`)**: 用于显示暂存区和未暂存区的变更，并提供提交功能。
        *   **文件变更视图 (`FileChangesView`)**: 用于显示选定提交的文件变更列表。当用户在此视图中选择一个文件并请求与工作区版本比较，或通过其他方式触发文件对比时，结果会显示在 `WorkspaceExplorer` 内的"文件内容/比较标签页"中。
        *   **文件搜索组件 (`FileSearchWidget`)**: 提供全局文件搜索功能。
        *   **文件内容/比较标签页 (`QTabWidget` - 对应 `GitManagerWindow` 中的 `compare_tab_widget`)**: 用于在新标签页中打开文件内容 (`ModifiedTextEdit`) 或显示文件比较视图 (`CompareView`)。当用户在 `FileChangesView` 中选择文件或通过文件树双击文件时，文件内容或比较视图将在此标签页中打开。
*   **主功能标签 (`tab_widget`)**:
    *   `GitManagerWindow` 中的主功能标签页，主要包含"提交历史"视图。
        *   第一个标签页固定为 "提交历史" (`CommitHistoryView`)。此视图可以根据用户选择（如查看所有分支）在传统的列表视图和图形化的提交图之间切换。
        *   用户可以通过其他操作（如在 `WorkspaceExplorer` 的文件树中选择查看某个文件的历史）动态添加新的标签页，这些标签页通常是 `FileHistoryView` 的实例，专门显示特定文件的版本历史。
        *   当 `GitManagerWindow` 的主 `tab_widget` 的当前标签页不是 "提交历史" 时（即显示某个文件的历史），`horizontal_splitter` 最右侧的 `compare_view` 会被激活并显示，用于对比该文件在不同提交之间的差异。而 `right_splitter` (包含 `FileChangesView` 和 `CommitDetailView`) 会被隐藏。反之，当选中 "提交历史" 标签页时，`right_splitter` 显示，`compare_view` 隐藏。
*   **CommitHistoryView**: 当用户在此视图中选择一个提交时，会发出信号，触发 `FileChangesView` 更新显示该提交所修改的文件列表，并触发 `CommitDetailView` 显示该提交的详细元数据。
*   **FileChangesView**: 用户在此视图中选择一个文件时，可以触发在 `WorkspaceExplorer` 的"文件内容/比较标签页" (`compare_tab_widget`) 中打开一个新的比较视图，展示该文件在当前选定提交中的版本与 HEAD 或工作区版本的差异。

**状态持久化：**

*   应用程序会保存和恢复各个分割器的尺寸比例，以便用户下次打开时保持其自定义布局。
*   底部面板和左侧面板的显示/隐藏状态也会被保存。
*   最近成功打开的 Git 仓库路径会被记录，并在下次启动时尝试自动重新打开最后一个仓库。

## 信号连接关系与交互流程

`GitManagerWindow` 通过 PyQt6 的信号和槽机制协调各组件间的复杂交互。

**主要交互流程描述：**

1.  **仓库操作流程**:
    *   用户通过 `TopBarWidget` 选择或打开一个 Git 仓库。`TopBarWidget` 发出信号，`GitManagerWindow` 的 `open_folder()` 方法被调用。
    *   `open_folder()` 初始化 `GitManager`，更新 `WorkspaceExplorer` 显示文件树，并刷新 `CommitHistoryView` 和 `TopBarWidget` 上的分支列表。
    *   `TopBarWidget` 上的分支切换、提交、拉取、推送等按钮会触发相应的 `GitManager` 操作，并通过信号更新 `CommitHistoryView` 或其他相关视图。

2.  **提交历史浏览与文件查看流程**:
    *   用户在 `CommitHistoryView` 中选择一个提交。`CommitHistoryView` 发出 `commit_selected` 信号。
    *   `GitManagerWindow` 的 `on_commit_selected()` 槽函数响应，更新 `FileChangesView` 以显示该提交更改的文件，并更新 `CommitDetailView` 显示提交详情。
    *   用户在 `FileChangesView` 中选择一个文件。`FileChangesView` 发出 `file_selected` 信号。
    *   `GitManagerWindow` 的 `on_file_selected()` 槽函数响应，会在 `WorkspaceExplorer` 的 `compare_tab_widget` 中打开一个新的 `CompareView` 实例，显示该文件在该提交中的内容或与前一版本的差异。

3.  **文件历史与对比流程**:
    *   当用户从 `WorkspaceExplorer` 的文件树中选择查看某个文件的历史时，一个新的标签页（通常是 `FileHistoryView`）会在主 `tab_widget` 中打开。
    *   `tab_widget` 的 `currentChanged` 信号触发 `on_tab_changed()`，该方法会根据当前是否为 "提交历史" 标签页来切换 `right_splitter` 和 `compare_view` 的可见性。
    *   在文件历史视图中选择提交进行对比时，会利用 `horizontal_splitter` 右侧的 `compare_view`。

**详细信号列表 (部分核心连接):**

*   **TopBarWidget 信号：**
    *   `open_folder_requested` → `GitManagerWindow.open_folder_dialog()`
    *   `recent_folder_selected` → `GitManagerWindow.open_folder()`
    *   `branch_changed` → `GitManagerWindow.on_branch_changed()` (进而更新提交历史)
    *   `commit_requested` → `GitManagerWindow.show_commit_dialog()`
    *   `fetch_requested` / `pull_requested` / `push_requested` → 对应的 `fetch_repo()`, `pull_repo()`, `push_repo()` 方法。
    *   `toggle_bottom_panel_requested` → `GitManagerWindow.toggle_bottom_widget()`
    *   `toggle_left_panel_requested` → `GitManagerWindow.toggle_left_panel()`

*   **CommitHistoryView 信号：**
    *   `commit_selected` → `GitManagerWindow.on_commit_selected()`

*   **FileChangesView 信号：**
    *   `file_selected` → `GitManagerWindow.on_file_selected()` (在 `compare_tab_widget` 中显示差异)
    *   `compare_with_working_requested` → `GitManagerWindow.show_compare_with_working_dialog()`

*   **WorkspaceExplorer 信号 (间接):**
    *   `WorkspaceExplorer` 内部的 `FileTreeWidget` 或 `SyncedTextEdit` (用于 blame) 可能发出信号，由 `GitManagerWindow.handle_blame_click_from_editor()` 处理。

*   **QTabWidget 信号：**
    *   `tab_widget.currentChanged` → `GitManagerWindow.on_tab_changed()` (控制右侧视图切换)
    *   `tab_widget.tabCloseRequested` → `GitManagerWindow.close_tab()` (关闭动态添加的标签页)

## 特殊功能说明

1.  **窗口激活时刷新文件树**:
    当主窗口从非激活状态变为激活状态时（例如，用户切换回该应用），`changeEvent` 会被触发。如果窗口变为激活状态，`WorkspaceExplorer` 的文件树 (`file_tree`) 会自动刷新。这有助于确保文件树显示的是最新的工作区状态，尤其是在用户可能在外部修改了文件之后。

2.  **处理 Blame 注释点击**:
    如果用户在 `WorkspaceExplorer` 中打开的文件编辑器（集成了 blame 功能的 `SyncedTextEdit`）中点击了某行代码的 blame 注释，编辑器会发出一个包含 commit 哈希的信号。`GitManagerWindow` 的 `handle_blame_click_from_editor()` 方法会接收这个信号。该方法负责：
    *   在 `CommitHistoryView` 的提交列表 (`history_list`) 中查找并定位到对应的提交。
    *   如果 `CommitHistoryView` 没有加载完所有提交，会尝试加载更多提交以找到目标。
    *   选中找到的提交项，并滚动到视图中央。
    *   自动切换主 `tab_widget` 到 "提交历史" 标签页，以便用户可以看到高亮选中的提交及其上下文。

3.  **面板显隐切换**:
    *   **底部面板**: 用户可以通过 `TopBarWidget` 上的按钮切换底部面板 (`bottom_widget`) 的显示和隐藏状态。
    *   **左侧面板**: 用户可以通过 `TopBarWidget` 上的按钮或点击 `SideBarWidget` 的工程按钮来切换左侧面板 (`left_panel_splitter`) 的显示和隐藏状态。
    这些状态会被记录在设置中，并在下次启动时恢复。切换时，按钮图标也会相应更新。

4.  **异步操作处理**:
    拉取 (`pull`)、推送 (`push`) 和获取 (`fetch`) 操作使用专用线程 (`PullThread`, `PushThread`, `FetchThread`) 执行，避免阻塞 UI 线程。操作完成后会更新 UI 状态并显示通知消息。
