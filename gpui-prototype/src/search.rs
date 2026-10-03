//! Bounded ripgrep JSON search over the repository's disk contents.
use anyhow::{Context, Result, bail};
use serde_json::Value;
use std::{
    collections::BTreeSet,
    hash::{Hash, Hasher},
    ops::Range,
    path::Path,
    process::Command,
    time::Duration,
};
#[derive(Clone, Debug, Default)]
pub struct Options {
    pub query: String,
    pub case_sensitive: bool,
    pub regex: bool,
    pub whole_word: bool,
    pub include: String,
    pub exclude: String,
    pub hidden: bool,
}
#[derive(Clone, Debug)]
pub struct Hit {
    pub path: String,
    pub line: usize,
    pub preview: String,
    pub ranges: Vec<Range<usize>>,
    pub occurrences: usize,
    line_hash: u64,
    line_length: usize,
}
#[derive(Clone, Debug, Default)]
pub struct Results {
    pub hits: Vec<Hit>,
    pub files: usize,
    pub occurrences: usize,
    pub skipped_encoding: usize,
    pub truncated: bool,
    pub diagnostic: String,
}
fn display_line(raw: &str) -> &str {
    raw.strip_suffix("\r\n")
        .or_else(|| raw.strip_suffix('\n'))
        .unwrap_or(raw)
}
fn hash(text: &str) -> u64 {
    let mut hash = std::collections::hash_map::DefaultHasher::new();
    text.hash(&mut hash);
    hash.finish()
}
impl Hit {
    /// Verify the line snapshot before placing a selection. External edits or an
    /// unsaved buffer must never reuse offsets from different text.
    pub fn locate(&self, document: &crate::text::Document) -> Result<Range<usize>> {
        let source = document
            .lines
            .get(self.line.saturating_sub(1))
            .context("匹配行已不存在，请重新搜索")?;
        let raw = &document.text[source.clone()];
        if raw.len() != self.line_length || hash(raw) != self.line_hash {
            bail!("文件内容在搜索后改变，请重新搜索");
        }
        let range = self
            .ranges
            .first()
            .cloned()
            .unwrap_or(0..display_line(raw).len());
        let start = document.snap(source.start + range.start);
        let end = source.start + range.end;
        let snapped = document.snap(end);
        Ok(start..if snapped == end {
            end
        } else {
            document.next(snapped)
        })
    }
}
struct Collector {
    results: Results,
    limit: usize,
    preview_bytes: usize,
    files: BTreeSet<String>,
}
impl Collector {
    fn consume(&mut self, record: &[u8]) -> Result<bool> {
        let value: Value = serde_json::from_slice(record).context("ripgrep 返回无效 JSON")?;
        if value["type"] != "match" {
            return Ok(true);
        }
        let data = &value["data"];
        let (Some(path), Some(raw)) = (
            data["path"]["text"].as_str(),
            data["lines"]["text"].as_str(),
        ) else {
            self.results.skipped_encoding += 1;
            return Ok(true);
        };
        let path = path.strip_prefix("./").unwrap_or(path);
        crate::git::validate_paths(&[path.into()])?;
        let line = data["line_number"].as_u64().context("搜索结果缺少行号")?;
        let line = usize::try_from(line).context("搜索行号超出范围")?;
        if line == 0 {
            bail!("搜索行号必须从 1 开始");
        }
        let matches = data["submatches"]
            .as_array()
            .context("搜索结果缺少匹配范围")?;
        let mut ranges = vec![];
        for found in matches {
            let start = usize::try_from(found["start"].as_u64().context("匹配起点无效")?)?;
            let end = usize::try_from(found["end"].as_u64().context("匹配终点无效")?)?;
            if start > end
                || end > raw.len()
                || !raw.is_char_boundary(start)
                || !raw.is_char_boundary(end)
            {
                bail!("匹配范围不在 UTF-8 文本边界内");
            }
            if ranges.len() < 128 {
                ranges.push(start..end);
            }
        }
        let display = display_line(raw);
        let mut end = display.len().min(4096);
        while !display.is_char_boundary(end) {
            end -= 1;
        }
        let preview = if end < display.len() {
            format!("{}…", &display[..end])
        } else {
            display.to_owned()
        };
        if self.results.hits.len() >= self.limit || self.preview_bytes + preview.len() > 8_000_000 {
            self.results.truncated = true;
            return Ok(false);
        }
        self.preview_bytes += preview.len();
        self.files.insert(path.into());
        self.results.occurrences += matches.len();
        self.results.hits.push(Hit {
            path: path.into(),
            line,
            preview,
            ranges,
            occurrences: matches.len(),
            line_hash: hash(raw),
            line_length: raw.len(),
        });
        Ok(true)
    }
}
pub fn run(root: &Path, options: &Options) -> Result<Results> {
    run_with_limit(root, options, 2000)
}
pub fn run_with_limit(root: &Path, options: &Options, limit: usize) -> Result<Results> {
    crate::process::check()?;
    if options.query.trim().is_empty() {
        return Ok(Results::default());
    }
    if [&options.query, &options.include, &options.exclude]
        .iter()
        .any(|s| s.chars().count() > 4096 || s.contains('\0'))
    {
        bail!("查询最多 4096 字符，查询与过滤不能含 NUL");
    }
    let mut command = Command::new("rg");
    command.current_dir(root).args([
        "--no-config",
        "--json",
        "--color=never",
        "--line-number",
        "--sort=path",
        "--max-filesize=20M",
        "--encoding=none",
    ]);
    if !options.case_sensitive {
        command.arg("--ignore-case");
    } else {
        command.arg("--case-sensitive");
    }
    if !options.regex {
        command.arg("--fixed-strings");
    }
    if options.whole_word {
        command.arg("--word-regexp");
    }
    if options.hidden {
        command.arg("--hidden");
    }
    if !options.include.trim().is_empty() {
        command.arg(format!("--glob={}", options.include.trim()));
    }
    if !options.exclude.trim().is_empty() {
        command.arg(format!("--glob=!{}", options.exclude.trim()));
    }
    command
        .args(["--glob=!**/.git", "--glob=!**/.git/**"])
        .arg(format!("--regexp={}", options.query))
        .args(["--", "."]);
    let mut collector = Collector {
        results: Default::default(),
        limit: limit.min(10_000),
        preview_bytes: 0,
        files: Default::default(),
    };
    let output = crate::process::lines(
        &mut command,
        Duration::from_secs(30),
        64 * 1024 * 1024,
        |record| collector.consume(record),
    )
    .context("项目搜索失败（需要可执行的 ripgrep/rg）")?;
    if !output.stopped && !matches!(output.status.code(), Some(0 | 1)) {
        bail!(
            "ripgrep 搜索失败：{}",
            String::from_utf8_lossy(&output.stderr).trim()
        );
    }
    collector.results.truncated |= output.stopped;
    collector.results.files = collector.files.len();
    collector.results.diagnostic =
        crate::process::display_diagnostic(String::from_utf8_lossy(&output.stderr).trim().into());
    if output.record_exceeded {
        collector
            .results
            .diagnostic
            .push_str("\n单条搜索输出超过 64 MB，已停止读取");
    }
    Ok(collector.results)
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn parser_and_location_preserve_raw_unicode_and_reject_stale_or_invalid_offsets() {
        let mut collector = Collector {
            results: Default::default(),
            limit: 2,
            preview_bytes: 0,
            files: Default::default(),
        };
        let record = serde_json::json!({"type":"match","data":{"path":{"text":"./中文 文件.rs"},"line_number":2,"lines":{"text":"\t😀 e\u{301}\r\n"},"submatches":[{"start":1,"end":5},{"start":6,"end":7}]}});
        collector
            .consume(&serde_json::to_vec(&record).unwrap())
            .unwrap();
        let hit = &collector.results.hits[0];
        assert_eq!(hit.path, "中文 文件.rs");
        assert_eq!(hit.occurrences, 2);
        let document = crate::text::Document::new("first\n\t😀 e\u{301}\r\n");
        assert_eq!(&document.text[hit.locate(&document).unwrap()], "😀");
        assert!(
            hit.locate(&crate::text::Document::new("first\nchanged\n"))
                .is_err()
        );
        let mut invalid = record.clone();
        invalid["data"]["submatches"][0]["end"] = 3.into();
        assert!(
            collector
                .consume(&serde_json::to_vec(&invalid).unwrap())
                .is_err()
        );
        let bytes = serde_json::json!({"type":"match","data":{"path":{"bytes":"AA=="},"lines":{"text":"text"}}});
        collector
            .consume(&serde_json::to_vec(&bytes).unwrap())
            .unwrap();
        assert_eq!(collector.results.skipped_encoding, 1);
        assert!(collector.consume(b"not json").is_err());
    }
}
