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

## 配置设置

程序使用 `settings.py` 文件来管理配置。以下是可用的配置选项：

- **recent_folders**: 最近打开的文件夹列表，自动记录。

- **last_folder**: 上次打开的文件夹路径。

- **max_recent**: 最大记录的最近文件夹数量，默认为 10。

- **font_family**: 默认字体，例如 "Courier New"。

- **font_size**: 默认字体大小，单位为点。

- **code_style**: 代码风格设置，例如 "friendly"。

这些设置可以被修改，并且会保存到配置文件中。
## 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

