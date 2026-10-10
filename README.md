# MyGit

MyGit 是使用 **Rust + GPUI** 开发的桌面 Git 仓库管理工具，目标是提供类似 IDE 的 Git 使用体验，方便浏览代码、查看差异和管理提交。

当前只维护 [`gpui-prototype/`](gpui-prototype/) 中的 Rust 版本。目录名沿用迁移初期命名，现已包含主要应用功能。根目录的 Python/PyQt 版本已废弃，仅保留作历史参考。

## 主要功能

- **仓库与工作区**：打开和切换本地仓库、最近仓库、文件树、多标签编辑、自动刷新及布局保存。
- **编辑器**：语法高亮、查找、撤销/重做、保存冲突检查，以及未保存修改保护。
- **差异比较**：双栏与统一 Diff、行内变化、差异块导航、任意提交比较、提交与工作区比较，以及合并提交的三栏只读视图。
- **变更与提交**：区分全部、已暂存和未暂存变更；多文件暂存/取消暂存；提交草稿；文件或差异块还原与撤销还原。
- **历史与分支**：提交 DAG、分页、消息/SHA/作者搜索、文件历史、Blame、本地与远程分支管理、Fetch/Pull/Push、合并及 Reset。
- **文件搜索**：快速文件定位与全项目内容搜索，支持正则、整词及包含/排除规则；内置 ripgrep Rust 库，无需另装 `rg`。
- **AI 提交信息**：调用本地 `pi`、`claude` 或 `codex` CLI，按当前文件变更生成可编辑的提交草稿。
- **设置与交互**：字体、代码配色、中英文界面、面板显隐、通知记录及原生快捷键。

Git 操作通过本机 Git CLI 执行，沿用现有 Git 凭据和 SSH 配置。AI 生成只填写草稿，暂存和提交由用户操作。

## 启动

从源码运行需要 Rust（支持 Edition 2024）和 Git。GPUI 固定为 `0.2.2`，依赖版本由 `Cargo.lock` 锁定。

当前本机验证主要在 macOS 上进行，构建需要完整 Xcode 和 Metal Toolchain。在项目根目录执行：

```sh
cargo run --locked --manifest-path gpui-prototype/Cargo.toml -- .
```

最后的 `.` 表示打开当前仓库，可替换为其他本地 Git 工作区路径；窗口内也可通过“打开文件夹”切换仓库。

若构建提示缺少 Metal Toolchain：

```sh
xcodebuild -downloadComponent MetalToolchain
```

AI 功能需要先安装所选 CLI 并完成登录或配置，再在应用设置中选择 agent、填写额外参数和提示词。认证与模型由 CLI 管理。

## 使用与配置

主窗口上方为文件树和编辑器 / Diff，下方为提交历史、变更列表与提交详情。选择提交查看详情，点击文件打开对应内容；分割条可拖动调整。

| 快捷键 | 操作 |
| --- | --- |
| Cmd/Ctrl+O | 打开仓库 |
| Cmd/Ctrl+R | 刷新 |
| Cmd/Ctrl+P | 快速定位文件 |
| Cmd/Ctrl+Shift+F | 项目内容搜索 |
| Cmd/Ctrl+S | 保存工作区文件 |
| Cmd/Ctrl+K | 切换提交面板 |
| Cmd/Ctrl+B | 显示/隐藏文件树 |
| Cmd/Ctrl+J | 显示/隐藏下方 Git 面板 |

设置兼容 `~/.git_manager/settings.json`，GPUI 专属设置独立保存。可通过 `MYGIT_CONFIG_DIR` 指定其他配置目录，用于隔离运行或验收。

完整操作说明见 [GPUI README](gpui-prototype/README.md)。

## 构建与验证

数据层测试可脱离图形依赖运行：

```sh
cargo test --locked --manifest-path gpui-prototype/Cargo.toml --no-default-features
cargo check --locked --manifest-path gpui-prototype/Cargo.toml
```

macOS 应用打包：

```sh
python3 gpui-prototype/scripts/package_macos.py
```

打包脚本需要 Python 3.9+，应用运行不需要 Python 或 Rust。默认输出为 `gpui-prototype/dist/MyGit.app`。版本标签触发的 GitHub Actions 工作流配置了 macOS arm64 和 Windows x86_64 的构建与 Release 附件上传，详见 [打包说明](gpui-prototype/PACKAGING.md)。

主要功能已实现，部分流程已有 macOS 原生窗口验证；完整跨平台、发布、输入法边界和长期性能验收仍在推进。Windows/Linux 的运行验证不能由构建配置代替。三栏视图用于历史比较，冲突解决器和子模块专用管理视图尚未提供。

## 项目结构与文档

| 路径 | 内容 |
| --- | --- |
| [`gpui-prototype/src/`](gpui-prototype/src/) | Rust 应用、Git 数据层和 GPUI 界面 |
| [`gpui-prototype/assets/`](gpui-prototype/assets/) | 内嵌图标及平台资源 |
| [`gpui-prototype/tests/`](gpui-prototype/tests/) | 集成测试；单元测试也位于源码模块中 |
| [`gpui-prototype/scripts/`](gpui-prototype/scripts/) | 打包与辅助脚本 |
| [功能对照表](gpui-prototype/FUNCTIONAL_PARITY.md) | 迁移功能与验收状态 |
| [迁移清单](gpui-prototype/MIGRATION.md) | 分阶段任务及验收条件 |
| [原生窗口验证记录](gpui-prototype/NATIVE_VALIDATION.md) | 已验证场景与待验证边界 |
| [性能记录](gpui-prototype/PERFORMANCE.md) | 性能测量及其限制 |

## 许可证

[MIT License](LICENSE)
