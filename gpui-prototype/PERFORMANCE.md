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
