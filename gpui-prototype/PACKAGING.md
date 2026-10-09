# macOS 打包

在项目根目录执行：

```sh
python3 gpui-prototype/scripts/package_macos.py
```

构建机需要 Python 3.9+、Rust、完整 Xcode 和 Metal Toolchain。脚本使用锁定依赖构建 release，生成 `gpui-prototype/dist/MyGit.app`，包含原生二进制、GPUI 自有 assets 中的项目图标和 Cargo 版本信息，并检查 plist 和 ad-hoc 签名。输出目录已存在时拒绝覆盖；可用 `--output /另一目录/MyGit.app` 指定新路径，`--debug` 用于验证包结构。

应用运行不需要 Python、Rust 或项目源码。需要 Git；项目搜索另需 `rg`，AI 生成另需支持 HTTP/HTTPS 的 `curl`。应用优先使用 PATH 中的程序；macOS 找不到程序时，依次查找 `/opt/homebrew/bin`、`/usr/local/bin`、`/usr/bin` 和 `/bin` 的可执行文件，不修改全局环境。自定义安装位置仍需加入启动环境的 PATH。首次验证也可从终端启动：

```sh
gpui-prototype/dist/MyGit.app/Contents/MacOS/MyGit /路径/仓库
```

配置兼容 `~/.git_manager/settings.json`；使用 `MYGIT_CONFIG_DIR=/临时配置目录` 可隔离验收设置。回退仍使用根目录 Python 入口，打包脚本不修改默认入口或旧版配置。

本机 ad-hoc 签名用于本机验证，不等同于 Developer ID 签名或公证；分发前需要独立完成签名、公证及干净机器启动验收。当前只生成宿主机架构，尚无 universal、Windows 或 Linux 安装包。

已验证 debug 包的 plist、签名及动态依赖：仅链接 macOS 系统库/框架，没有 Python 或开发目录动态库依赖。release 包亦已构建并通过 plist 和签名校验，二进制为 arm64。干净环境及完整启动验收尚待完成，不能据此勾选整个 R06。

界面 SVG 编译嵌入二进制，ICNS 从 `assets/icons/mygit.icns` 复制；构建及运行不依赖旧版根目录 `icons/`。本轮从 `/tmp` 调用脚本生成隔离 debug 包，plist 与签名检查通过；没有将包结构检查当作干净机器启动或本轮新界面的窗口验收。

## GitHub Actions 构建

`Build Rust` 工作流仅在推送 `v*` 版本标签（例如 `v0.1.0`）时触发，使用 Cargo.lock 构建 Rust release，仅生成两个平台的产物：

- `MyGit-macos-arm64`：`MyGit-macos-arm64.zip`，内含带 ad-hoc 签名的 `MyGit.app`。
- `MyGit-windows-x86_64`：`MyGit-windows-x86_64.zip`，内含 `MyGit.exe`，目标为 `x86_64-pc-windows-msvc`。

在对应 Actions 运行页面的 Artifacts 下载。工作流不自动发布 GitHub Release；运行仍需自行安装 Git、ripgrep 和所选 AI agent CLI。Windows SDK 的 `fxc.exe` 仅用于构建 GPUI shaders，不作为运行依赖分发。
