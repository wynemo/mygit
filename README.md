# MyGit

这是一个基于 Python 的 Git 仓库管理工具，提供图形界面来简化 Git 操作。

意义在于提供一个类似 idea 里面的 git 支持。

idea 好用是好用，就是太重了，内存占用太大了。

## 功能特点

- Git 仓库可视化管理
- 代码差异查看器
- 语法高亮显示
- 自定义设置

## 项目原理

本项目是一个使用 Python 和 PyQt6 图形库构建的桌面应用程序。它通过在后台执行标准的 Git 命令行指令来与 Git 仓库进行交互，并将结果以用户友好的图形界面展示出来。用户通过界面进行的操作（如提交、拉取、推送、查看历史等）会被转换成相应的 Git 命令执行。这种方式使得不熟悉 Git 命令的用户也能方便地管理代码版本，同时也为熟悉命令的用户提供了一个直观的可视化工具。

## 环境要求

- Python 3.7+，因为是 pyqt6 实现的
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

或者使用 uv 启动：

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

在 windows 以及 mac 下都测试过，linux 没有测试过

## 项目结构

### 主目录文件
- `main.py`: 程序入口
- `git_manager.py`: Git 操作核心功能
- `git_manager_window.py`: 图形界面实现
- `commit_dialog.py`: git commit 提交
- `commit_detail_view.py`: 显示选定提交的详细信息
- `commit_graph.py`: 提交图绘制
- `commit_history_view.py`: 提交历史视图
- `compare_view.py`: 比较视图
- `compare_with_working_dialog.py`: 与工作区比较对话框
- `custom_tree_widget.py`: 自定义树形控件
- `diff_calculator.py`: 差异计算器
- `diff_highlighter.py`: 差异高亮
- `file_changes_view.py`: 文件更改视图
- `file_history_view.py`: 文件历史视图
- `find_dialog.py`: 查找功能对话框
- `git_graph_data.py`: 提交图数据管理
- `git_graph_items.py`: 提交图图形元素
- `git_graph_layout.py`: 提交图布局算法
- `git_graph_view.py`: 提交历史图形视图
- `git_log_parser.py`: git log 解析器
- `settings.py`: 程序设置管理
- `settings_dialog.py`: 设置对话框
- `syntax_highlighter.py`: 语法高亮
- `test_text_diff_viewer.py`: 文本差异查看器测试
- `text_diff_viewer.py`: 文本差异查看器
- `top_bar_widget.py`: 顶部工具栏控件
- `workspace_explorer.py`: 工作区文件浏览器

### editors 目录
- `text_edit.py`: 文本编辑器组件 (集成行号、语法高亮等功能)
- `modified_text_edit.py`: 修改版文本编辑器

### icons 目录
- 包含各种 SVG 和 PNG 图标资源

### tests 目录
- 包含单元测试和测试数据文件

### utils 目录
- `language_map.py`: 语言名称到文件扩展名的映射

## 配置设置

程序使用 `settings.py` 文件来管理配置。以下是可用的配置选项：

- **font_family**: 默认字体，例如 "Courier New"。

- **font_size**: 默认字体大小，单位为点。

- **code_style**: 代码风格设置，例如 "friendly"。

- **api_url**: 用于生成注释的 api url

- **api_secret**: 用于生成注释的 api secret

- **model_name**: 用于生成注释的模型名称

- **prompt**: 用于生成注释的提示词，可选

这些设置可以被修改，并且会保存到配置文件中。
## 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

