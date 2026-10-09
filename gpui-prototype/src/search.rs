//! Bounded in-process ripgrep search over the repository's disk contents.
use anyhow::{Context, Result, bail};
use grep_matcher::Matcher;
use grep_regex::{RegexMatcher, RegexMatcherBuilder};
use grep_searcher::{BinaryDetection, Searcher, SearcherBuilder, Sink, SinkMatch};
use ignore::{WalkBuilder, overrides::OverrideBuilder};
use std::{
    collections::BTreeSet,
    hash::{Hash, Hasher},
    io::{self, Read},
    ops::Range,
    path::Path,
    time::{Duration, Instant},
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
            .context(crate::i18n::text("匹配行已不存在，请重新搜索"))?;
        let raw = &document.text[source.clone()];
        if raw.len() != self.line_length || hash(raw) != self.line_hash {
            bail!(crate::localized_format!(
                "文件内容在搜索后改变，请重新搜索",
                "The file changed after searching; search again"
            ));
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
    deadline: Instant,
}
impl Collector {
    fn consume(
        &mut self,
        path: Option<&str>,
        line: usize,
        bytes: &[u8],
        matcher: &RegexMatcher,
    ) -> Result<bool> {
        let (Some(path), Ok(raw)) = (path, std::str::from_utf8(bytes)) else {
            self.results.skipped_encoding += 1;
            return Ok(true);
        };
        crate::git::validate_paths(&[path.into()])?;
        let mut ranges = vec![];
        let mut occurrences = 0;
        matcher.try_find_iter(raw.strip_suffix('\n').unwrap_or(raw).as_bytes(), |found| {
            if occurrences % 128 == 0 {
                check_search(self.deadline)?;
            }
            occurrences += 1;
            if ranges.len() < 128 {
                ranges.push(found.start()..found.end());
            }
            Ok::<_, anyhow::Error>(true)
        })??;
        if ranges
            .iter()
            .any(|r| !raw.is_char_boundary(r.start) || !raw.is_char_boundary(r.end))
        {
            bail!(crate::i18n::text("匹配范围不在 UTF-8 文本边界内"));
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
        self.results.occurrences += occurrences;
        self.results.hits.push(Hit {
            path: path.into(),
            line,
            preview,
            ranges,
            occurrences,
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
        bail!(crate::localized_format!(
            "查询最多 4096 字符，查询与过滤不能含 NUL",
            "Queries support up to 4096 characters; queries and filters cannot contain NUL"
        ));
    }
    let matcher = RegexMatcherBuilder::new()
        .case_insensitive(!options.case_sensitive)
        .fixed_strings(!options.regex)
        .word(options.whole_word)
        .line_terminator(Some(b'\n'))
        .build_many(&options.query.split('\n').collect::<Vec<_>>())
        .context(crate::i18n::text("ripgrep 搜索失败"))?;
    let mut overrides = OverrideBuilder::new(root);
    if !options.include.trim().is_empty() {
        overrides.add(options.include.trim())?;
    }
    if !options.exclude.trim().is_empty() {
        overrides.add(&format!("!{}", options.exclude.trim()))?;
    }
    overrides.add("!**/.git")?.add("!**/.git/**")?;
    let mut walk = WalkBuilder::new(root);
    walk.hidden(!options.hidden)
        .follow_links(false)
        .max_filesize(Some(20 * 1024 * 1024))
        .add_custom_ignore_filename(".rgignore")
        .overrides(overrides.build()?)
        .sort_by_file_path(|a, b| a.cmp(b));
    let deadline = Instant::now() + Duration::from_secs(30);
    let mut searcher = SearcherBuilder::new()
        .line_number(true)
        .bom_sniffing(false)
        .binary_detection(BinaryDetection::quit(0))
        .build();
    let mut collector = Collector {
        results: Default::default(),
        limit: limit.min(10_000),
        preview_bytes: 0,
        files: Default::default(),
        deadline,
    };
    for entry in walk.build() {
        check_search(deadline)?;
        let entry = match entry {
            Ok(entry) => entry,
            Err(error) => {
                return Err(error).context(crate::i18n::text("ripgrep 搜索失败"));
            }
        };
        if let Some(error) = entry.error() {
            collector.diagnostic(error);
        }
        if !entry.file_type().is_some_and(|kind| kind.is_file()) {
            continue;
        }
        let file = match std::fs::File::open(entry.path()) {
            Ok(file) => file,
            Err(error) => {
                return Err(error).context(crate::i18n::text("ripgrep 搜索失败"));
            }
        };
        let path = entry.path().strip_prefix(root)?.to_str();
        let sink = SearchSink {
            collector: &mut collector,
            matcher: &matcher,
            path,
            deadline,
        };
        // Bound reads as well as traversal: cancellation also works for files with no matches.
        let reader = CheckedReader {
            inner: file.take(20 * 1024 * 1024),
            deadline,
        };
        if let Err(error) = searcher.search_reader(&matcher, reader, sink) {
            check_search(deadline)?;
            return Err(error).context(crate::i18n::text("ripgrep 搜索失败"));
        }
        if collector.results.truncated {
            break;
        }
    }
    check_search(deadline)?;
    collector.results.files = collector.files.len();
    Ok(collector.results)
}
fn check_search(deadline: Instant) -> Result<()> {
    crate::process::check()?;
    if Instant::now() >= deadline {
        bail!(crate::localized_format!(
            "项目搜索超时",
            "Project search timed out"
        ));
    }
    Ok(())
}
struct CheckedReader<R> {
    inner: R,
    deadline: Instant,
}
impl<R: Read> Read for CheckedReader<R> {
    fn read(&mut self, buf: &mut [u8]) -> io::Result<usize> {
        check_search(self.deadline).map_err(io::Error::other)?;
        let length = buf.len().min(64 * 1024);
        self.inner.read(&mut buf[..length])
    }
}
struct SearchSink<'a> {
    collector: &'a mut Collector,
    matcher: &'a RegexMatcher,
    path: Option<&'a str>,
    deadline: Instant,
}
impl Sink for SearchSink<'_> {
    type Error = io::Error;
    fn matched(&mut self, _: &Searcher, found: &SinkMatch<'_>) -> io::Result<bool> {
        check_search(self.deadline).map_err(io::Error::other)?;
        let line = usize::try_from(found.line_number().unwrap()).map_err(io::Error::other)?;
        self.collector
            .consume(self.path, line, found.bytes(), self.matcher)
            .map_err(io::Error::other)
    }
}
impl Collector {
    fn diagnostic(&mut self, error: &impl std::fmt::Display) {
        if self.results.diagnostic.len() < 16_384 {
            let message = crate::process::display_diagnostic(error.to_string());
            self.results.diagnostic.push_str(&message);
            self.results.diagnostic.push('\n');
        }
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn collection_and_location_preserve_raw_unicode_and_reject_stale_offsets() {
        let mut collector = Collector {
            results: Default::default(),
            limit: 2,
            preview_bytes: 0,
            files: Default::default(),
            deadline: Instant::now() + Duration::from_secs(30),
        };
        let matcher = RegexMatcher::new("😀|e").unwrap();
        collector
            .consume(
                Some("中文 文件.rs"),
                2,
                "\t😀 e\u{301}\r\n".as_bytes(),
                &matcher,
            )
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
        collector.consume(None, 1, b"text", &matcher).unwrap();
        collector
            .consume(Some("invalid"), 1, b"\xff", &matcher)
            .unwrap();
        assert_eq!(collector.results.skipped_encoding, 2);
    }
    #[test]
    fn ignore_binary_encoding_size_and_raw_line_offsets() {
        let root = tempfile::tempdir().unwrap();
        std::fs::write(root.path().join(".rgignore"), "ignored.txt\n").unwrap();
        std::fs::write(root.path().join("ignored.txt"), "needle\n").unwrap();
        std::fs::write(root.path().join("binary"), b"\0needle\n").unwrap();
        std::fs::write(root.path().join("invalid"), b"needle\xff\n").unwrap();
        std::fs::write(root.path().join("a.txt"), "needle\r\nneedle").unwrap();
        let large = std::fs::File::create(root.path().join("large")).unwrap();
        large.set_len(20 * 1024 * 1024 + 1).unwrap();
        let options = Options {
            query: "needle".into(),
            ..Default::default()
        };
        let results = run(root.path(), &options).unwrap();
        assert_eq!(results.files, 1);
        assert_eq!(results.hits.len(), 2);
        assert_eq!(results.skipped_encoding, 1);
        assert_eq!(results.hits[0].preview, "needle");
        let document = crate::text::Document::new("needle\r\nneedle");
        for hit in &results.hits {
            assert_eq!(&document.text[hit.locate(&document).unwrap()], "needle");
        }
        let anchored = Options {
            query: "needle$".into(),
            regex: true,
            ..Default::default()
        };
        let results = run(root.path(), &anchored).unwrap();
        assert_eq!(results.hits.len(), 1);
        assert_eq!(results.hits[0].line, 2);
        assert!(run_with_limit(root.path(), &options, 0).unwrap().truncated);
    }
    #[test]
    fn reader_checks_cancellation_and_deadline_even_without_matches() {
        let token = crate::process::Cancellation::default();
        let mut reader = CheckedReader {
            inner: io::Cursor::new(b"no matches"),
            deadline: Instant::now() + Duration::from_secs(30),
        };
        token.cancel();
        assert!(crate::process::scope(token, || reader.read(&mut [0; 10])).is_err());
        reader.deadline = Instant::now();
        assert!(reader.read(&mut [0; 10]).is_err());
    }
    #[test]
    fn newline_patterns_and_zero_width_unicode_matches_keep_cli_semantics() {
        let root = tempfile::tempdir().unwrap();
        std::fs::write(root.path().join("file"), "foo\nbar\n🙂\n").unwrap();
        let options = Options {
            query: "foo\nbar".into(),
            ..Default::default()
        };
        let results = run(root.path(), &options).unwrap();
        assert_eq!(results.hits.len(), 2);
        let options = Options {
            query: "^|$".into(),
            regex: true,
            ..Default::default()
        };
        let results = run(root.path(), &options).unwrap();
        assert_eq!(results.hits[2].ranges, vec![0..0, 4..4]);
        let missing = root.path().join("missing");
        assert!(run(&missing, &options).is_err());
    }
}
