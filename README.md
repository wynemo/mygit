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

## 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## todos

1. ~仓库所有文件视图~
2. 代码语法高亮
3. 对比工作区，可以修改工作区文件
4. 文件历史，可以查看文件历史；放到提交历史旁边，这里要弄一个tab 参考jetbrains的布局
5. 现有的点击提交历史的文件，比较视图弄到工作区右边的tab_widget里面，现在是视图下方
6. 把字符串抽离出来，后续做国际化
7. 多分支视图的绘制
8. 在完成7以后，可以进行 git 3-ways merge
