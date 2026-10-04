//! Read-only data-layer benchmark. Excludes syntax highlighting and UI rendering.
use anyhow::{Context, Result, ensure};
use std::{path::PathBuf, time::Instant};

fn main() -> Result<()> {
    let args: Vec<_> = std::env::args_os().skip(1).collect();
    ensure!(
        args.len() == 3,
        "usage: diff_benchmark LEFT RIGHT ITERATIONS"
    );
    let left = std::fs::read(PathBuf::from(&args[0]))?;
    let right = std::fs::read(PathBuf::from(&args[1]))?;
    let iterations: usize = args[2].to_str().context("invalid iterations")?.parse()?;
    ensure!(
        (1..=1000).contains(&iterations),
        "iterations must be 1..=1000"
    );
    let mut timings = Vec::with_capacity(iterations);
    let mut rows = 0;
    let mut blocks = 0;
    for _ in 0..iterations {
        let start = Instant::now();
        let diff = mygit_gpui::diff::calculate(&left, &right)?;
        ensure!(
            diff.message.is_none(),
            "sample cannot be previewed: {:?}",
            diff.message
        );
        rows = diff.rows.len();
        blocks = diff.blocks.len();
        std::hint::black_box(&diff);
        timings.push(start.elapsed().as_secs_f64() * 1000.0);
    }
    timings.sort_by(f64::total_cmp);
    println!(
        "{}",
        serde_json::json!({
            "implementation": "rust-aligned-diff", "iterations": iterations,
            "left_bytes": left.len(), "right_bytes": right.len(),
            "rows": rows, "changed_blocks": blocks,
            "min_ms": timings[0], "median_ms": timings[iterations / 2],
            "max_ms": timings[iterations - 1],
            "scope": "parse, alignment, source documents, inline annotation; no UI or syntax"
        })
    );
    Ok(())
}
