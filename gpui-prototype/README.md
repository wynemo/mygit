# MyGit GPUI 原型

独立的 Rust + GPUI 桌面原型，用于验证提交历史和双栏 Diff 的迁移方案。

## 启动

在项目根目录执行：

```sh
cargo run --manifest-path gpui-prototype/Cargo.toml -- .
```

最后一个参数可以替换为任意本地 Git 工作区路径。窗口内的“打开仓库”支持选择其他目录；“刷新”重新读取仓库并返回工作区。

本原型固定使用 GPUI 0.2.2，提交 Cargo.lock。当前验证目标为 macOS，要求 Rust、Git、完整 Xcode 和 Metal Toolchain。若编译提示 Metal Toolchain 缺失：

```sh
xcodebuild -downloadComponent MetalToolchain
```

## 已实现

- 打开本地仓库、显示分支、查看最近 100 条当前 HEAD 的提交。
- 查看工作区文件状态（包含暂存、未暂存和未跟踪文件）。
- 点击提交查看变更文件，点击文件查看行号对齐的双栏只读 Diff。
- 工作区比较 HEAD 与磁盘文件；历史比较首个父提交与选中提交，初始提交与空内容比较。
- 删除与新增行底色、统一的左右滚动、通过文件标题栏 ← / → 同步横向移动长行、虚拟列表。
- 后台执行 Git 和 Diff，忽略切换操作后迟到的结果。
- 二进制、非 UTF-8 和大文件提示；内容合计超过 2 MB 暂不生成 Diff。

## 验证

Git 数据层可脱离图形依赖运行：

```sh
cargo test --manifest-path gpui-prototype/Cargo.toml --no-default-features
cargo check --manifest-path gpui-prototype/Cargo.toml
```

测试在临时仓库中验证重命名、初始提交、合并首父比较、修改、删除和二进制；不修改用户仓库。

## 本机验证结果

已通过 macOS 编译、四项 Git/Diff 测试及 Clippy 检查。已实际启动窗口，验证提交选择、文件切换、左右垂直滚动、横向移动按钮，以及原生目录选择器。

## 当前边界

这是只读原型。编辑、文本选择/复制、语法高亮、提交/推拉、分支管理、DAG、Blame、搜索和配置迁移尚未实现。工作区视图暂不分别显示暂存与未暂存 Diff；暂存后再次修改的文件仍显示 HEAD 与当前磁盘的总体差异。子模块暂未提供专用视图。非 UTF-8 文件名暂通过替代字符显示。

列表采用虚拟渲染，但文本和差异行仍保存在内存中，尚未做性能或内存基准测试。Windows/Linux 尚未验证；新版本 GPUI 的平台支持和 API 不等同于固定的 0.2.2。
