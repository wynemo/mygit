# MyGit

这是一个基于 Python 的 Git 仓库管理工具，提供图形界面来简化 Git 操作。

意义在于提供一个类似 idea 里面的 git 支持。

idea 好用是好用，就是太重了，内存占用太大了。

## 功能特点

- Git 仓库可视化管理
- **增强型代码差异查看器**: 支持工作区文件编辑、行级变更指示以及精细化差异比较
- **全方位代码语法高亮**: 覆盖文件编辑和差异比较视图，并支持字体大小自定义
- **强大的分支管理**: 包含便捷的分支切换、远程分支合并、提交历史中的本地/远程分支显示及快捷操作
- **详尽的文件历史与 Git Blame**: 提供文件和文件夹历史视图，交互式 Git blame 注释可联动选中提交历史
- **高效文件内容搜索**: 支持全项目文件（基于 ripgrep）和提交历史（含哈希值）搜索，编辑器内集成浮动查找对话框及高亮优化
- **智能提交信息生成**: 利用兼容 OpenAI API 的服务自动生成提交信息
- **直观工作区管理**: 文件树清晰展示修改/未跟踪文件及文件夹状态（颜色区分），支持按字母排序、大仓库懒加载及 `.gitignore` 文件识别
- **流畅用户交互**: 优化界面布局（如可折叠视图、自适应窗口）、高级标签页管理、差异快速导航、实时 Git 操作反馈、多处右键菜单增强及未保存修改标记等
- **全面提交历史**: 支持滚动加载更多、多行提交信息显示、悬停详情及提交后自动刷新

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

安装 ripgrepy (可选，不装会影响文件搜索功能)
ubuntu:
```bash
sudo apt-get install ripgrep
```

mac:
```bash
brew install ripgrep
```

windows:
```bash
scoop install ripgrep
```

## 使用方法

运行主程序：
```bash
python main.py
```

在 windows 以及 mac 下都测试过，linux 没有测试过

## 项目结构

### 主目录文件
- `blame_tooltip_plan.md`: blame 工具提示的计划文件
- `check.sh`: 检查脚本
- `commit_detail_view.py`: 显示选定提交的详细信息
- `commit_history_view.py`: 提交历史视图
- `commit_widget.py`: 提交相关控件
- `compare_view.py`: 比较视图
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
- `git_log_parser.py`: Git 日志解析器
- `git_manager.py`: Git 操作核心功能
- `git_manager_window.md`: Git 管理器窗口的 Markdown 文档
- `git_manager_window.py`: Git 管理器窗口的 Python 实现
- `main.py`: 程序入口
- `mygit.icns`: 应用程序图标
- `notification_widget.py`: 通知控件
- `pyproject.toml`: 项目配置和依赖管理
- `README.md`: 项目说明文件
- `readme.txt`: 额外的说明文件
- `requirements.txt`: Python 依赖列表
- `settings.py`: 程序设置管理
- `side_bar_widget.py`: 侧边栏控件
- `syntax_highlighter.py`: 语法高亮
- `test_text_diff_viewer.py`: 文本差异查看器测试
- `text_diff_viewer.py`: 文本差异查看器
- `threads.py`: 线程管理
- `todo.md`: 待办事项 Markdown 文件
- `todo.txt`: 待办事项文本文件

### 目录
- `components/`: 包含各种UI组件
    - `__init__.py`
    - `file_quick_search_popup.py`: 文件快速搜索弹窗
    - `file_search_widget.py`: 文件搜索控件
    - `find_dialog.py`: 查找对话框
    - `new_branch_dialog.py`: 新建分支对话框
    - `notification_widget.py`: 通知控件
    - `spin_icons.py`: 旋转图标资源
- `dialogs/`: 包含各种对话框组件
    - `__init__.py`
    - `compare_with_working_dialog.py`: 与工作区比较对话框
    - `settings_dialog.py`: 设置对话框
- `docs/`: 包含项目文档和说明
    - `git_manager_window.md`: Git 管理器窗口的 Markdown 文档
    - `readme.txt`: 额外的说明文件
    - `todo.md`: 待办事项 Markdown 文件
    - `todo.txt`: 待办事项文本文件
    - `translations.md`: 翻译相关文档
- `editors/`: 包含文本编辑器相关组件
    - `__init__.py`
    - `modified_text_edit.py`: 修改版文本编辑器
    - `text_edit.py`: 文本编辑器组件 (集成行号、语法高亮等功能)
- `icons/`: 包含各种 SVG 和 PNG 图标资源 (此目录文件较多，不一一列出)
- `tests/`: 包含单元测试和测试数据文件 (此目录文件较多，不一一列出)
- `translations/`: 包含应用翻译文件
    - `app_zh_CN.qm`: 中文翻译的 QM 文件
    - `app_zh_CN.ts`: 中文翻译的 TS 文件
- `utils/`: 包含工具函数和辅助脚本
    - `__init__.py`
    - `language_map.py`: 语言名称到文件扩展名的映射
    - `translator.py`: 翻译加载和管理工具
- `views/`: 包含主要的视图组件
    - `__init__.py`
    - `side_bar_widget.py`: 侧边栏控件
    - `top_bar_widget.py`: 顶部栏控件

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

