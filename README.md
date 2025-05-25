# MyGit

这是一个基于Python的Git仓库管理工具，提供图形界面来简化Git操作。

意义在于提供一个类似idea里面的git支持。

idea好用是好用，就是太重了, 内存占用太大了。

## 功能特点

- Git仓库可视化管理
- 代码差异查看器
- 语法高亮显示
- 自定义设置

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

## 项目结构

- `main.py`: 程序入口
- `git_manager.py`: Git操作核心功能
- `git_manager_window.py`: 图形界面实现
- `commit_dialog.py`: git commit 提交对话框
- `commit_graph.py`: 提交图绘制
- `commit_history_view.py`: 提交历史视图
- `compare_view.py`: 比较视图
- `compare_with_working_dialog.py`: 与工作区比较对话框
- `diff_calculator.py`: 差异计算器
- `diff_highlighter.py`: 差异高亮
- `file_changes_view.py`: 文件更改视图
- `file_history_view.py`: 文件历史视图
- `settings.py`: 程序设置管理
- `settings_dialog.py`: 设置对话框
- `syntax_highlighter.py`: 语法高亮
- `text_diff_viewer.py`: 文本差异查看器
- `text_edit.py`: 文本编辑器组件
- `workspace_explorer.py`: 工作区文件浏览器

## 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## todos

1. ~~仓库所有文件视图~~
2. 编辑器代码语法高亮，多种语言支持;完成一半了
3. 对比工作区，可以修改工作区文件
4. ~~工作区文件，右键点击，可以查看单个文件历史；放到提交历史旁边，这里要弄一个tab，也就是说，有多个tab，一个是提交历史，其他的是单个文件的历史~~
5. ~~现有的点击提交历史的文件，比较视图弄到工作区右边的tab_widget里面，现在是视图下方~~
6. 把字符串抽离出来，后续做国际化
7. 多分支视图的绘制
8. 在完成7以后，可以进行 git 3-ways merge
9. ~~接4的改动，点击文件历史，在右侧显示文件变化, 现在放到下面的tab里确实好像不好用，一个文件出现那么多tab~~
10. ~~提交历史现在只显示了一部分，需要支持拖动，加载更多~~
11. ~~提交信息太长，或者有换行时，界面上显示不出来~~
12. ~~标签页，增加关闭其他标签页的功能~~
13. ~~把提交历史、文件历史，文件差异的视图，现在是在上方，需要放到下方，并且可以隐藏与显示~~
14. 工作区的更改，可以在文件编辑器中显示，比如删除了一行，修改了几行，都需要显示出来
15. commit_dialog.py 添加git push
16. ~~在“提交历史”标签右边，增加git push按钮~~
17. ~~在git commit 以后更新提交历史 CommitDialog.accept() commit_history_view update_history()~~
18. ~~工作区文件按字母顺序排序~~
19. ~~多行commit信息换行显示，参考jetbrains ide，放在文件变化下面~~
20. ~~接11的改动，在鼠标移动到提交历史上时，完整显示单行提交信息~~
21. ~~“提交历史”标签，不可关闭，那么样式不需要一个“x“的关闭按钮~~
22. ~~仓库需要优先显示默认分支~~
23. ~~工作区的文件，右键菜单，加入git annoation 支持;完成一半了~~
24. git push 以后，需要有点提示；或者说界面上有点不同；同时增加推送中的交互
25. 区别remote与local
26. ~~点击git annoation 单行的区域时，根据commit 信息，需要选中commit_history_view history_list的相应的item，然后 on_commit_clicked 触发~~
27. ~~git annoation 宽度不一致 希望能计算出最宽的宽度 然后合理的显示~~
28. ~~接26的改动，点击git annoation 单行的区域时，现在commit_history_view histroy_list如果没有相应的item 就触发不了on_commit_clicked 这是因为histroy_list还没有加载，因为是滚动触发的，所以需要加载更多，这需要合理的处理~~
29. ~~CompareView, 也就是比较的时候也支持 git annotation 的显示~~
30. ~~接29的改动，也像26说的那样触发on_commit_clicked~~
31. 工作区文件有修改，左边树形列表（FileTreeWidget）相应的文件显示有变化，颜色可变为棕色， 表示修改了次文件
