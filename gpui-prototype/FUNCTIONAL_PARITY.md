# 主要功能迁移对照

此表记录 2026-10-04 对旧 Python 源码的功能对照，方便区分实现缺口与验收待办。GPUI 的入口按现有布局组织，不逐像素复刻 Qt 窗口。下表功能均已有实现；完整窗口、真实输入法、连续切换和平台验收仍按 [迁移清单](MIGRATION.md) 执行。

| 旧版功能与来源 | GPUI 实现及入口 |
| --- | --- |
| 打开/刷新仓库、最近项目、最后项目：`git_manager_window.py`、`settings.py` | 工具栏、原生仓库菜单、设置/最近仓库；空仓库、detached HEAD、子目录及失败重试由 `app.rs`、`git.rs` 处理。 |
| 字体/字号、语言、代码配色、面板显隐和尺寸：`dialogs/settings_dialog.py`、`views/top_bar_widget.py` | 设置、自定义字体输入、字号按钮、中文/English、三套 syntect 配色；Cmd/Ctrl+B/J 显隐，拖动尺寸，保存 GPUI 配置并保留旧字段。配色选择可用，未照搬 Pygments 的全部配色名称。 |
| 文件树、完整路径图标/提示、文件操作：`workspace_explorer.py`、`views/file_tree.py`、`utils/language_icons.py` | 懒加载工作区树、Git/忽略状态、图标、完整路径提示；右键/文件操作/Shift+F10 提供历史、路径复制、文件管理器显示、Blame 和还原。 |
| 从树拖入标签区、文件标签、关闭当前/其他/全部：`workspace_explorer.py` | 绑定仓库的文件拖动、完整路径唯一标签、关闭按钮及关闭其他/全部；未保存缓冲区确认、同名不同目录、切仓清理。 |
| 编辑器输入、剪贴板、撤销/重做、保存、查找、行标记/概览：`editors/text_edit.py`、`editors/modified_text_edit.py` | `views/editor.rs` 与 `editor.rs`；快捷键、原生编辑菜单、查找工具条，行号旁标记及右侧全文件概览。保存保留换行约定并检查磁盘冲突；真实 IME 验收待完成。 |
| Diff 双栏/统一、行内标记、差异导航、字号、文本复制：`text_diff_viewer.py`、`unified_diff_viewer.py`、`diff_calculator.py` | `views/diff.rs`、`text_line.rs`、`diff.rs`、`text.rs`；布局切换按钮、差异导航、原文选区、语法颜色、同步/横向滚动和限制文件提示。 |
| 任意提交比较、历史文件与工作区比较、编辑源文件：`compare_view.py`、`file_changes_view.py` | 比较面板及历史 Diff 的单文件比较/编辑工作区入口；可比较没有内容差异的文件，历史/比较视图只读，编辑明确打开磁盘版本。 |
| 提交历史、DAG、详情、复制 SHA/消息：`views/commit_history_view.py`、`custom_tree_widget.py`、`git_graph_*.py` | 历史分页/DAG 列表、详情复制按钮、引用筛选分支入口；目标提交完整消息来自后台 Git 查询。 |
| 历史搜索、文件/目录历史、重命名：`views/file_history_view.py`、`views/folder_history_view.py` | 历史搜索面板与文件历史入口；范围、作者、日期、消息/SHA、完整路径和文件重命名跟随。 |
| 逐行 Blame、详情/复制 SHA/跳历史：`editors/text_edit.py`、`git_manager_window.py` | Diff、三栏及工作区编辑器的 Blame；当前编辑缓冲区标注未提交行，详情、复制和联动历史；隐藏 Git 面板仍可使用。 |
| 合并提交三栏：`text_diff_viewer.py::MergeDiffViewer` | `views/merge.rs`、`merge.rs`；两位父提交/合并结果、三侧原文选择、同步滚动、导航与各侧 Blame。八爪鱼合并完整支持仍属于 X03。 |
| 暂存、取消暂存、提交与 AI 信息：`commit_widget.py`、`threads.py` | 暂存/未暂存列表、选中/全部写操作、提交面板及原生工作区菜单；暂存区提交、多行草稿、hook 错误、AI 候选和独立配置。 |
| 整文件/块还原：`views/file_tree.py`、Diff 编辑器 | Diff 还原及文件树还原到 HEAD；确认来源/目标、未保存内容保护、恢复记录与撤销，保留 index。 |
| 新建/切换/跟踪分支、Fetch/Pull/Push、合并、Reset：`git_manager.py`、`threads.py`、`components/*branch*`、`components/git_reset_dialog.py` | 分支面板、历史引用入口、远程/合并按钮与 Reset 确认；后台串行写操作、未保存编辑保护和状态刷新。旧新建分支对话框的 checkout/overwrite 复选框没有被旧调用方使用，未将这些无行为的控件认定为已实现旧功能。 |
| 全项目搜索、文件快速定位：`components/file_search_widget.py`、`components/file_quick_search_popup.py`、`utils/file_index_manager.py` | Cmd/Ctrl+Shift+F 内容搜索与 Cmd/Ctrl+P 文件定位；后台 ripgrep/索引、防抖、取消、完整路径、定位到树/标签和过期位置检查。 |
| 外部修改/提交自动更新、重新聚焦：`git_manager_window.py`、工作区监听 | `watch.rs`、`app/refresh.rs`；合并文件/元数据事件、重新聚焦、写操作后刷新，保留缓冲区和有效位置。 |
| 图标、通知、工具提示：`icons/`、`components/notification_widget.py` | 自有 assets 编译嵌入、文件/工具栏图标、7 秒通知与最近 16 条详情、双语按钮提示。取消/过期后台任务不产生错误通知。 |

本轮验证为 118 项库测试、1 项独立英文集成测试、Clippy、macOS 构建及隔离 debug 包结构/签名检查。资源使用与 GPUI 相同的 resvg 引擎验证解析和可见像素。它们不能替代实际窗口的布局、悬停、拖放、焦点或输入法验收。

此表不表示正式发布已经完成。性能对照/优化、Windows/Linux、签名公证及干净机器验收、默认入口切换继续保留待办；根目录旧版入口仍可回退。Stash、交互式冲突解决、非 UTF-8 路径及更大文件的完整支持仍按 X01–X03 的既有扩展范围处理。
