### 🤖 Assistant

以下是 `git_manager_window.py` 中 `main_layout` 的完整容器层次结构 **整合版**（使用树形符号统一展示三层嵌套关系）：

```
[main_layout] (QVBoxLayout 主容器)
│
├── [top_widget] (QWidget 顶部栏)
│   │
│   └── [top_layout] (QHBoxLayout 水平布局)
│       │
│       ├── [folder_layout] (QHBoxLayout 文件夹操作区)
│       │   ├── open_button (打开按钮)
│       │   └── recent_button (最近菜单按钮)
│       │
│       ├── branch_combo (分支选择下拉框)
│       ├── commit_button (提交按钮)
│       └── settings_button (设置按钮)
│
├── [vertical_splitter] (QSplitter 垂直分割器)
│   │
│   ├── [上半部分] workspace_explorer (文件树导航)
│   │
│   └── [下半部分] bottom_widget (QWidget)
│       │
│       └── [horizontal_splitter] (QSplitter 水平分割器)
│           │
│           ├── [左侧] tab_widget (QTabWidget 标签页容器)
│           │   ├── 固定页0: commit_history_view (提交历史表格)
│           │   └── 动态页: 文件比较视图 (按需生成)
│           │
│           ├── [中部] file_changes_view (文件变更树形列表)
│           │
│           └── [右侧] compare_view (差异对比编辑器，默认隐藏)
│
└── (隐式状态栏)
```

### 关键特性说明
1. **动态交互节点**：
   - `tab_widget` 的动态页通过 `_on_file_selected` 方法实时创建
   - `compare_view` 的显示/隐藏与标签页切换联动

2. **比例控制**：
   ```python
   # 垂直分割比例 6:2 (通过像素值计算)
   vertical_splitter.setSizes([int(total_height*0.75), int(total_height*0.25)])

   # 水平分割比例 1:2 
   horizontal_splitter.setSizes([width//3, width*2//3])
   ```

3. **布局约束**：
   - 所有分割器禁止子面板折叠 (`setChildrenCollapsible(False)`)
   - 分割条宽度固定为8像素 (`setHandleWidth(8)`)

需要进一步展开某个具体容器的实现细节吗？例如：
1. `workspace_explorer` 如何监听文件系统变化
2. 提交按钮与Git命令的绑定逻辑
3. 差异对比视图的语法高亮方案