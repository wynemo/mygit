# MyGit

这是一个基于Python的Git仓库管理工具，提供图形界面来简化Git操作。

意义在于提供一个类似idea里面的git支持。

idea好用是好用，就是太重了, 内存占用太大了。

## 功能特点

- Git仓库可视化管理
- 代码差异查看器
- 语法高亮显示
- 自定义设置

## 项目原理

本项目是一个使用 Python 和 PyQt6 图形库构建的桌面应用程序。它通过在后台执行标准的 Git 命令行指令来与 Git 仓库进行交互，并将结果以用户友好的图形界面展示出来。用户通过界面进行的操作（如提交、拉取、推送、查看历史等）会被转换成相应的 Git 命令执行。这种方式使得不熟悉 Git 命令的用户也能方便地管理代码版本，同时也为熟悉命令的用户提供了一个直观的可视化工具。

## 环境要求

- Python 3.7+， 因为是pyqt6实现的
- Git

## 安装步骤

1. 克隆仓库：
```bash
git clone https://github.com/yourusername/mygit.git
cd mygit
```

2. 创建并激活虚拟环境：
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# 或
.venv\Scripts\activate  # Windows
```

或者使用uv启动:

    uv run main.py

3. 安装依赖：
```bash
pip install -r requirements.txt
```

## 使用方法

运行主程序：
```bash
python main.py
```

在windows以及mac下都测试过，linux没有测试过

## 项目结构

- `main.py`: 程序入口
- `git_manager.py`: Git操作核心功能
- `git_manager_window.py`: 图形界面实现
- `commit_dialog.py`: git commit 提交对话框
- `commit_detail_view.py`: 显示选定提交的详细信息，如作者、日期、提交消息和更改的文件列表。
- `commit_graph.py`: 提交图绘制 (可能负责绘制提交历史的图形化分支结构)
- `commit_history_view.py`: 提交历史视图
- `compare_view.py`: 比较视图
- `compare_with_working_dialog.py`: 与工作区比较对话框 (提供一个对话框，用于比较当前工作区的文件与特定提交中的版本)
- `custom_tree_widget.py`: 自定义的树形控件，可能用于显示文件树、提交列表或其他层级数据。
- `diff_calculator.py`: 差异计算器 (计算文件之间的差异（diff）)
- `diff_highlighter.py`: 差异高亮 (对差异文本进行语法高亮，使其更易阅读)
- `file_changes_view.py`: 文件更改视图
- `file_history_view.py`: 文件历史视图 (显示单个文件的提交历史)
- `find_dialog.py`: 在文本视图中提供查找功能。
- `git_graph_data.py`: 管理和准备用于显示提交图的数据。
- `git_graph_items.py`: 定义在提交图中显示的各种图形元素。
- `git_graph_layout.py`: 负责提交图的布局算法。
- `git_graph_view.py`: 显示提交历史的图形化视图。
- `git_log_parser.py`: 解析 `git log` 命令的输出。
- `settings.py`: 程序设置管理
- `settings_dialog.py`: 设置对话框
- `syntax_highlighter.py`: 语法高亮 (为代码文件提供通用的语法高亮功能)
- `test_text_diff_viewer.py`: `text_diff_viewer.py` 的单元测试。
- `text_diff_viewer.py`: 文本差异查看器
- `text_edit.py`: 文本编辑器组件 (一个自定义的文本编辑组件，可能集成了行号、语法高亮等功能)
- `top_bar_widget.py`: 实现应用程序顶部工具栏的自定义控件。
- `utils/language_map.py`: 可能包含语言名称到文件扩展名或MIME类型的映射，用于语法高亮。
- `workspace_explorer.py`: 工作区文件浏览器

## 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## todos

1. ~~仓库所有文件视图~~
2. ~~编辑器代码语法高亮，多种语言支持;完成一半了~~
3. ~~对比工作区，可以修改工作区文件；现在加入了编辑功能~~ 编辑功能不太符合使用习惯 特别是这个确定保存
4. ~~工作区文件，右键点击，可以查看单个文件历史；放到提交历史旁边，这里要弄一个tab，也就是说，有多个tab，一个是提交历史，其他的是单个文件的历史~~
5. ~~现有的点击提交历史的文件，比较视图弄到工作区右边的tab_widget里面，现在是视图下方~~
6. 把字符串抽离出来，后续做国际化
7. ~~多分支视图的绘制~~ 还不够完善
8. 在完成7以后，可以进行 git 3-ways merge
9. ~~接4的改动，点击文件历史，在右侧显示文件变化, 现在放到下面的tab里确实好像不好用，一个文件出现那么多tab~~
10. ~~提交历史现在只显示了一部分，需要支持拖动，加载更多~~
11. ~~提交信息太长，或者有换行时，界面上显示不出来~~
12. ~~标签页，增加关闭其他标签页的功能~~
13. ~~把提交历史、文件历史，文件差异的视图，现在是在上方，需要放到下方，并且可以隐藏与显示~~
14. ~~工作区的更改，可以在文件编辑器中显示，比如删除了一行，修改了几行，都需要显示出来~~
15. ~~commit_dialog.py 添加git push 好像没有必要了~~
16. ~~在“提交历史”标签右边，增加git push按钮~~
17. ~~在git commit 以后更新提交历史 CommitDialog.accept() commit_history_view update_history()~~
18. ~~工作区文件按字母顺序排序~~
19. ~~多行commit信息换行显示，参考jetbrains ide，放在文件变化下面~~
20. ~~接11的改动，在鼠标移动到提交历史上时，完整显示单行提交信息~~
21. ~~“提交历史”标签，不可关闭，那么样式不需要一个“x“的关闭按钮~~
22. ~~仓库需要优先显示默认分支~~
23. ~~工作区的文件，右键菜单，加入git annoation 支持;完成一半了~~
24. git push 以后，需要有点提示；~~或者说界面上有点不同；~~同时增加推送中的交互, 添加一个旋转图标, 后续git fetch/pull 也需要有这个交互
25. ~~CommitHistoryView 的 history_list (CustomTreeWidget) 需要显示remote与local，现在只显示了local, remote可加emoji ☁️~~
26. ~~点击git annoation 单行的区域时，根据commit 信息，需要选中commit_history_view history_list的相应的item，然后 on_commit_clicked 触发~~
27. ~~git annoation 宽度不一致 希望能计算出最宽的宽度 然后合理的显示~~
28. ~~接26的改动，点击git annoation 单行的区域时，现在commit_history_view histroy_list如果没有相应的item 就触发不了on_commit_clicked 这是因为histroy_list还没有加载，因为是滚动触发的，所以需要加载更多，这需要合理的处理~~
29. ~~CompareView, 也就是比较的时候也支持 git annotation 的显示~~
30. ~~接29的改动，也像26说的那样触发on_commit_clicked~~
31. ~~工作区文件有修改，左边树形列表（FileTreeWidget）相应的文件显示有变化，颜色可变为棕色， 表示修改了次文件~~
32. ~~GitManagerWindow中的元素 窗口布局的大小，需要根据屏幕大小，自动调整，现在是固定大小; 比如 CommitDetailView 提交详情这个页面，需要根据内容大小，自动调整高度，现在完全挤在一起了~~
33. 接31的改动，文件视图，需要显示修改的地方
34. ~~set_texts 有的地方参数不对，git 短 hash的，现在设置的为None~~
35. ~~SyncedTextEdit 上添加上、下两个按钮，快速定位到上一个差异，下一个差异~~ 还有些问题，滚动不够灵敏，然后当前差异的处的行号显示应该不同，要不然以为点击上一个下一个没有反应
36. ~~Refresh 按钮占用太大空间了 另外想一个图标~~
37. ~~重构：GitManagerWindow top_widget top_layout 的东西能否抽离出去~~
38. ~~bug：点击“show blame” - 弹出的菜单与鼠标右键点击的地方隔太远了~~
39. bug: 文件差异的换行没有显示
40. ~~impovement: 2025-05-25 22:30:04,384 - ERROR - root - 拉取仓库时发生错误 -  出现git pull异常时要提示~~
41. ~~feature: 在synced_text_edit 上添加查找功能 ctrl/command + f 可以触发~~
42. ~~接41的改动，ctrl + f，如果有选中的文字，那么查找的文字就是选中的文字；此外，高亮的效果太差了，需要弄成蓝色背景~~
43. ~~text_edit.py/FindDialog 换成浮动的widget, 查找的过程浮动在 SyncedTextEdit 之上，然后SyncedTextEdit不会失焦~~
44. ~~git push以后，需要更新分支的remote提示~~
45. ~~SyncedTextEdit 字体大小是硬编码的~~
46. ~~比较页面，也需要有代码语法高亮的支持~~
47. ~~untracked files 在 workspace_explorer FileTreeWidget 需要显示状态 可显示为灰色~~
48. 修复git push时的动画bug: QPropertyAnimation: you're trying to animate a non-existing property _rotation_angle of your QObject
