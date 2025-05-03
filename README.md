# MyGit

这是一个基于Python的Git仓库管理工具，提供图形界面来简化Git操作。
意义在于提供一个类似idea里面的git支持。
idea好用是好用，就是太中重了。

## 功能特点

- Git仓库可视化管理
- 代码差异查看器
- 语法高亮显示
- 自定义设置

## 环境要求

- Python 3.x
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
- `diff_viewer.py`: 代码差异查看器
- `syntax_highlighter.py`: 代码语法高亮
- `settings.py`: 程序设置管理

## 贡献指南

欢迎提交 Pull Request 来改进项目。请确保遵循以下步骤：

1. Fork 项目
2. 创建新的功能分支
3. 提交更改
4. 推送到分支
5. 创建 Pull Request

## 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## 问题反馈

如有任何问题，请创建 Issue 或联系项目维护者。

## todos

1. ~仓库所有文件视图~
2. 代码语法高亮
3. 对比工作区，可以修改工作区文件
4. 文件历史，可以查看文件历史；放到提交历史旁边，这里要弄一个tab 参考jetbrains的布局
5. 点击提交历史的文件，比较试图弄到工作区右边的tab_widget里面
