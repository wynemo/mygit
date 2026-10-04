# 性能基准

2026-10-04，本机 macOS arm64，Rust release、Python 3.9。先记录数据层，再补启动、历史分页、渲染、滚动与连续仓库切换的内存数据。以下结果不代表整个应用性能，也不能替代 R01 完整验收。

## Diff 样本与复现

样本共 10000 行，CRLF，含中文与 emoji，左侧 377780 字节，右侧 377784 字节。每行为 `let value_{i} = "中文 🙂 {i}";\r\n`；右侧将 2500 和 7500 行编号对应的 `value_` 改为 `changed_`。两个实现均识别两处差异。

```sh
cargo build --locked --release --no-default-features --manifest-path gpui-prototype/Cargo.toml --example diff_benchmark
/usr/bin/time -l gpui-prototype/target/release/examples/diff_benchmark LEFT RIGHT 20
/usr/bin/time -l python3 gpui-prototype/scripts/legacy_diff_benchmark.py LEFT RIGHT 20
```

输入为外部文件，只读，不修改仓库。Rust 按应用默认内容上限拒绝不适用样本，迭代次数限制为 1–1000；每次结果释放后再计算。`time` 包含进程启动及文件读取，JSON 计时只覆盖计算。

| 实现 | 中位耗时 | 最小 / 最大 | 进程峰值 RSS |
| --- | --- | --- | --- |
| Python 原版 DifflibCalculator | 7.512 ms | 7.392 / 8.435 ms | 26,001,408 字节 |
| Rust 应用 Diff | 11.293 ms | 11.228 / 30.918 ms | 21,004,288 字节 |

Python 计时包含 splitlines 和差异块计算；Rust 包含原文解析、10000 行对齐、双栏/统一映射、文档以及行内标记。均不含语法高亮和 UI；它们不是相同计算范围，不能用比例宣称框架快慢。峰值 RSS 包含各自运行时、分配器和输入数据，不是文档净大小。20 次迭代只用于初始基线，不证明长期内存稳定。

后续需补同仓库历史分页、实际窗口首次绘制和滚动、多轮切换后的常驻内存，以及大文件/重复行/完全替换样本。优化目标以这些数据为依据。

## 本仓库读取基准（2026-10-04）

用户指定本仓库作为实际性能样本。测量时 HEAD 为 `796d4e0`，221 个跟踪文件，所有引用共 1287 条提交，HEAD 可达 1242 条提交，`.git` 约 30 MB。这覆盖本项目的实际规模，不代表十万文件/百万提交规模。

使用当前代码的 debug 与 `cargo build --release --no-default-features --lib` 数据层；临时 Rust 驱动直接调用应用公共函数，读取相同工作区，每项连续 5 次取中位数/最大值，系统缓存未清空。全历史只遍历一次，每页 100 条。驱动及原始输出保存在本次外部临时目录 `mygit-self-performance-68a6e5o2`，不加入项目运行入口。

| 操作 | debug 中位 / 最大 | release 中位 / 最大 |
| --- | --- | --- |
| `git::snapshot` 首批历史与引用 | 148.57 / 191.53 ms | 140.17 / 209.36 ms |
| `quick_open::read` 文件索引 | 14.85 / 15.10 ms | 14.60 / 14.61 ms |
| `Index::search("git_tests", 100)` | 0.16 / 0.20 ms | 0.01 / 0.02 ms |
| `git::refresh_snapshot`，无活动文档 | 176.76 / 220.50 ms | 176.22 / 187.13 ms |
| `search::run`，查询 Confirmation | 12.82 / 37.99 ms | 12.82 / 46.82 ms |
| `git::compare`，git_tests.rs 相同两侧 | 2982.33 / 3164.90 ms | 331.98 / 357.45 ms |

遍历全部 HEAD 历史：debug 539.96 ms，release 542.38 ms，均得到 1242 条。搜索返回 11 个文件、60 个匹配行且未截断。Diff 文件严格为 79094 字节、2197 行、零差异块；表中完整 compare 包含 Git 读取、文档/行映射及两侧语法高亮，不能与上面的纯 Diff 样本计时直接比较。

独立配置的 macOS debug 原生窗口验证：初始 100 条历史正常，分页载入完全部 1242 条，滚动到 2025 年旧提交；221 项索引定位 git_tests.rs 正确，长文件滚动显示 113–134 行，项目搜索显示同样 11 个文件/60 个匹配行（69 处匹配）。两次运行中 RSS 快照为 177312/188208 KiB，后者约 184 MiB；这不是峰值或长期稳定性证据。窗口仍为 debug，release 数据层结果不等于 release 首帧/滚动耗时。

本次只读测试前后 HEAD、index 文件字节及工作区状态完全相同。所有 app 配置写入外部临时目录，未执行保存、暂存、还原、提交或远程操作。记录文档在完成此核对后单独更新。

完整 R01 尚需旧 Python 相同仓库/操作对照、release 原生启动/首帧、帧时间及峰值/长期内存；完整 Diff 的高亮成本仍可进一步分析，本轮不依据 debug 耗时直接判断发布版瓶颈。
