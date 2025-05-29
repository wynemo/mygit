### 🤖 Assistant

以下是 `git_manager_window.py` 的容器结构与信号连接（基于当前代码实现）：

```
[main_layout] (QVBoxLayout 主容器)
│
├── [TopBarWidget] (自定义顶部工具栏组件)
│   ├── open_folder_requested → open_folder_dialog()
│   ├── recent_folder_selected → open_folder()
│   ├── clear_recent_folders_requested → clear_recent_folders()
│   ├── branch_changed → on_branch_changed()
│   ├── commit_requested → show_commit_dialog()
│   ├── settings_requested → show_settings_dialog()
│   ├── fetch_requested → fetch_repo()
│   ├── pull_requested → pull_repo()
│   ├── push_requested → push_repo()
│   └── toggle_bottom_panel_requested → toggle_bottom_widget()
│
├── [vertical_splitter] (QSplitter 垂直分割器)
│   │
│   ├── [上半部分] workspace_explorer (WorkspaceExplorer)
│   │   └── compare_tab_widget (QTabWidget 用于文件比较的标签页容器)
│   │       ├── 动态创建标签页: CompareView 实例显示文件差异
│   │       └── 标签页标题格式: "文件名 @ commit短哈希"
│   │
│   └── [下半部分] bottom_widget (QWidget 可切换显示/隐藏)
│       │
│       └── [horizontal_splitter] (QSplitter 水平分割器)
│           │
│           ├── [左侧] tab_widget (QTabWidget 主标签页)
│           │   ├── 固定页0: commit_history_view (CommitHistoryView)
│           │   │   ├── history_list (提交列表视图)
│           │   │   └── history_graph_list (提交图视图)
│           │   └── 动态页: 文件历史视图（按需创建）
│           │
│           ├── [右侧外框] right_splitter (QSplitter 垂直分割器)
│           │   ├── file_changes_view (FileChangesView)
│           │   └── commit_detail_view (CommitDetailView)
│           │
│           └── [备选视图] compare_view (CompareView 差异对比)
│
└── (隐式状态栏)
```

### 关键功能说明
1. **布局调整**:
   - 垂直分割比例默认 5:3 (工作区:底部面板)
   - 水平分割比例默认 1:2 (主标签页:右侧区域)
   - 右侧分割器默认比例 300:200 (文件变更:提交详情)
   - 所有分割器禁止折叠，分割条宽8px
   - 底部面板最小高度100px

2. **动态UI行为**:
   - 提交历史视图: 根据分支显示列表视图或图视图
   - 工作区标签: 通过文件选择动态创建compare_view标签页
   - 提交详情: 随提交选择自动更新
   - 文件比较: 通过工作区选择或对话框触发

3. **状态持久化**:
   - 分割器尺寸恢复保存
   - 底部面板可见状态保存
   - 最近访问文件夹记录
   - 自动恢复上次打开的仓库

4. **交互增强**:
   - 底部面板切换按钮更新图标状态
   - 标签页可关闭功能(除提交历史页)
   - 工作区文件树激活窗口时刷新
   - 编辑器责备注释点击跳转到提交历史

### 信号连接关系
```python
# TopBarWidget信号
top_bar.open_folder_requested → open_folder_dialog()
top_bar.recent_folder_selected → open_folder()
top_bar.clear_recent_folders_requested → clear_recent_folders()
top_bar.branch_changed → on_branch_changed()
top_bar.commit_requested → show_commit_dialog()
top_bar.settings_requested → show_settings_dialog()
top_bar.fetch_requested → fetch_repo()
top_bar.pull_requested → pull_repo()
top_bar.push_requested → push_repo()
top_bar.toggle_bottom_panel_requested → toggle_bottom_widget()

# 主窗口信号
commit_history_view.commit_selected → on_commit_selected()
file_changes_view.file_selected → on_file_selected() 
file_changes_view.compare_with_working_requested → show_compare_with_working_dialog()
tab_widget.currentChanged → on_tab_changed()
tab_widget.tabCloseRequested → close_tab()

# UI行为信号
workspace_explorer.notify_blame_click → handle_blame_click_from_editor()
```

### 特殊功能说明
1. **窗口激活行为**:
   ```python
   def changeEvent(self, event: QEvent):
       if self.isActiveWindow():
           self.workspace_explorer.refresh_file_tree()
   ```

2. **责备注释处理**:
   ```python
   def handle_blame_click_from_editor(commit_hash):
       # 在提交历史中定位并选中指定提交
       # 自动切换到提交历史标签页
   ```

3. **文件比较工作流**:
   ```python
   def _on_file_selected(file_path, current_commit):
       # 创建唯一标签页标题
       # 动态创建并显示compare_view
   ```