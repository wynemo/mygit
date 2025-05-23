### 🤖 Assistant

以下是 `git_manager_window.py` 中 `main_layout` 的完整容器层次结构 **最新版**（使用树形符号统一展示三层嵌套关系）：

```
[main_layout] (QVBoxLayout 主容器)
│
├── [top_widget] (QWidget 顶部栏, 固定高度100px)
│   │
│   └── [top_layout] (QHBoxLayout 水平布局)
│       │
│       ├── [folder_layout] (QHBoxLayout 文件夹操作区)
│       │   ├── open_button (打开文件夹按钮)
│       │   └── recent_button (QToolButton 最近菜单按钮)
│       │
│       ├── branch_label ("当前分支:" 标签)
│       ├── branch_combo (分支选择下拉框)
│       ├── commit_button (提交按钮, 固定尺寸80x24)
│       ├── settings_button (QToolButton "⚙" 设置按钮)
│       │
│       ├── [repo_action_layout] (QHBoxLayout Git操作按钮组)
│       │   ├── fetch_button (QToolButton 获取按钮)
│       │   ├── pull_button (QToolButton 拉取按钮)
│       │   └── push_button (QToolButton 推送按钮)
│       │
│       └── toggle_bottom_button (QToolButton 切换底部面板按钮)
│
├── [vertical_splitter] (QSplitter 垂直分割器)
│   │
│   ├── [上半部分] workspace_explorer (WorkspaceExplorer 工作区浏览器)
│   │   │
│   │   └── compare_tab_widget (文件比较标签页容器)
│   │
│   └── [下半部分] bottom_widget (QWidget 可切换显示/隐藏)
│       │
│       └── [horizontal_splitter] (QSplitter 水平分割器)
│           │
│           ├── [左侧] tab_widget (QTabWidget 主标签页容器)
│           │   ├── 固定页0: commit_history_view (CommitHistoryView 提交历史)
│           │   └── 动态页: 文件历史视图 (按需生成，可关闭)
│           │
│           ├── [中部] right_splitter (QSplitter 垂直分割器)
│           │   ├── file_changes_view (FileChangesView 文件变更列表)
│           │   └── commit_detail_view (CommitDetailView 提交详情)
│           │
│           └── [右侧] compare_view (CompareView 差异对比，可隐藏)
│
└── (隐式状态栏)
```

### 关键特性说明
1. **新增功能**：
   - **底部面板切换**: 通过 `toggle_bottom_button` 可显示/隐藏整个底部区域
   - **Git操作按钮组**: fetch/pull/push 三个工具按钮，带图标
   - **双标签系统**: 主标签页(`tab_widget`) + 工作区标签页(`compare_tab_widget`)
   - **提交详情视图**: 新增 `CommitDetailView` 显示commit详细信息

2. **动态交互节点**：
   - 主标签页的文件历史页通过 `close_tab()` 方法可关闭
   - 工作区标签页通过 `_on_file_selected()` 方法实时创建比较视图
   - `compare_view` 根据标签页切换自动显示/隐藏
   - 右侧分割器在非提交历史标签时隐藏

3. **比例控制**：
   ```python
   # 垂直分割比例 6:2 (工作区:底部面板)
   vertical_splitter.setSizes([total_height*6//8, total_height*2//8])

   # 水平分割比例 1:2 (主标签:右侧区域)
   horizontal_splitter.setSizes([total_width//3, total_width*2//3])
   
   # 右侧垂直分割比例 3:2 (文件变更:提交详情)
   right_splitter.setSizes([300, 200])
   ```

4. **布局约束**：
   - 所有分割器禁止子面板折叠 (`setChildrenCollapsible(False)`)
   - 分割条宽度固定为8像素 (`setHandleWidth(8)`)
   - 顶部栏固定高度100px
   - 提交按钮固定尺寸80x24px
   - 底部面板最小高度100px

5. **状态持久化**：
   - 分割器尺寸通过 `Settings` 类保存/恢复
   - 底部面板显示状态持久化
   - 最近文件夹历史记录

### 信号连接关系
```python
# 主要信号连接
commit_history_view.commit_selected → on_commit_selected()
file_changes_view.file_selected → on_file_selected() 
file_changes_view.compare_with_working_requested → show_compare_with_working_dialog()
tab_widget.currentChanged → on_tab_changed()
tab_widget.tabCloseRequested → close_tab()
branch_combo.currentTextChanged → on_branch_changed()

# Git操作按钮
fetch_button.clicked → fetch_repo()
pull_button.clicked → pull_repo() 
push_button.clicked → push_repo()

# UI控制
toggle_bottom_button.clicked → toggle_bottom_widget()
settings_button.clicked → show_settings_dialog()
commit_button.clicked → show_commit_dialog()
```