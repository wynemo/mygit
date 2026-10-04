//! Exact-version porcelain Blame with shared commit metadata and original source paths.
use crate::{
    git,
    model::{BrowseMode, Revision},
};
use anyhow::{Context, Result, bail};
use std::{
    collections::HashMap,
    fs,
    io::Write,
    path::{Path, PathBuf},
    sync::Arc,
};
#[derive(Clone, Debug)]
pub struct Commit {
    pub sha: String,
    pub author: String,
    pub email: String,
    pub time: String,
    pub timezone: String,
    pub summary: String,
}
impl Commit {
    pub fn uncommitted(&self) -> bool {
        self.sha.bytes().all(|byte| byte == b'0')
    }
}
#[derive(Clone, Debug)]
pub struct Line {
    pub commit: Arc<Commit>,
    pub original_line: usize,
    pub line: usize,
    pub path: Arc<str>,
}
fn uncommitted(path: &str, text: &str) -> Vec<Line> {
    let commit = Arc::new(Commit {
        sha: "0".repeat(40),
        author: crate::i18n::text("未提交").into(),
        email: String::new(),
        time: String::new(),
        timezone: String::new(),
        summary: crate::i18n::text("当前文件尚无提交归属").into(),
    });
    let path: Arc<str> = path.into();
    text.split_inclusive('\n')
        .enumerate()
        .map(|(index, _)| Line {
            commit: commit.clone(),
            original_line: index + 1,
            line: index + 1,
            path: path.clone(),
        })
        .collect()
}
fn decode_path(value: &str) -> Result<String> {
    if !value.starts_with('"') {
        return Ok(value.into());
    }
    let source = value
        .strip_prefix('"')
        .and_then(|s| s.strip_suffix('"'))
        .context("Blame 路径引号无效")?
        .as_bytes();
    let mut bytes = vec![];
    let mut index = 0;
    while index < source.len() {
        if source[index] != b'\\' {
            bytes.push(source[index]);
            index += 1;
            continue;
        }
        index += 1;
        let escaped = *source.get(index).context("Blame 路径转义无效")?;
        if (b'0'..=b'7').contains(&escaped) {
            let mut value = 0u16;
            let mut count = 0;
            while count < 3 && index < source.len() && (b'0'..=b'7').contains(&source[index]) {
                value = value * 8 + (source[index] - b'0') as u16;
                index += 1;
                count += 1;
            }
            bytes.push(value.try_into().context("路径八进制转义超过字节范围")?);
        } else {
            bytes.push(match escaped {
                b't' => b'\t',
                b'n' => b'\n',
                b'r' => b'\r',
                b'b' => 8,
                b'f' => 12,
                b'v' => 11,
                b'a' => 7,
                b'\\' => b'\\',
                b'"' => b'"',
                _ => bail!("未知路径转义"),
            });
            index += 1;
        }
    }
    String::from_utf8(bytes).context("Blame 路径不是 UTF-8")
}
pub fn parse(bytes: &[u8], text: &str) -> Result<Vec<Line>> {
    let output = std::str::from_utf8(bytes).context("Blame 输出不是 UTF-8")?;
    let source_lines: Vec<_> = text.split_inclusive('\n').collect();
    let mut metadata: HashMap<String, (Arc<Commit>, Arc<str>)> = HashMap::new();
    let mut lines = vec![];
    let mut records = output.split_terminator('\n');
    while let Some(header) = records.next() {
        let fields: Vec<_> = header.split_whitespace().collect();
        if !(3..=4).contains(&fields.len())
            || !matches!(fields[0].len(), 40 | 64)
            || !fields[0].bytes().all(|b| b.is_ascii_hexdigit())
        {
            bail!("Blame 行头格式无效");
        }
        let sha = fields[0];
        let original_line: usize = fields[1].parse()?;
        let line: usize = fields[2].parse()?;
        if original_line == 0 || line != lines.len() + 1 {
            bail!("Blame 行号不连续");
        }
        let previous = metadata.get(sha);
        let mut commit = Commit {
            sha: String::new(),
            author: String::new(),
            email: String::new(),
            time: String::new(),
            timezone: String::new(),
            summary: String::new(),
        };
        let mut path = previous.map(|(_, path)| path.clone());
        let mut content = None;
        for record in records.by_ref() {
            if let Some(source) = record.strip_prefix('\t') {
                content = Some(source);
                break;
            }
            if let Some(value) = record.strip_prefix("author ") {
                commit.author = value.into();
            } else if let Some(value) = record.strip_prefix("author-mail ") {
                commit.email = value.into();
            } else if let Some(value) = record.strip_prefix("author-time ") {
                commit.time = value.into();
            } else if let Some(value) = record.strip_prefix("author-tz ") {
                commit.timezone = value.into();
            } else if let Some(value) = record.strip_prefix("summary ") {
                commit.summary = value.into();
            } else if let Some(value) = record.strip_prefix("filename ") {
                path = Some(decode_path(value)?.into());
            }
        }
        let source = content.context("Blame 记录缺少源码")?;
        let expected = source_lines.get(line - 1).context("Blame 行数超出源文档")?;
        if expected.strip_suffix('\n').unwrap_or(expected) != source {
            bail!("Blame 内容与当前版本不同，请刷新后重试");
        }
        let path = path.context("Blame 记录缺少路径")?;
        let commit = if let Some((cached, _)) = previous {
            cached.clone()
        } else {
            commit.sha = sha.into();
            Arc::new(commit)
        };
        metadata.insert(sha.into(), (commit.clone(), path.clone()));
        lines.push(Line {
            commit,
            original_line,
            line,
            path,
        });
    }
    if lines.len() != source_lines.len() {
        bail!("Blame 行数与源文档不同");
    }
    Ok(lines)
}
struct Contents(PathBuf);
impl Contents {
    fn new(text: &str) -> Result<Self> {
        let stamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)?
            .as_nanos();
        let path = std::env::temp_dir().join(format!("mygit-blame-{}-{stamp}", std::process::id()));
        let mut options = fs::OpenOptions::new();
        options.write(true).create_new(true);
        #[cfg(unix)]
        {
            use std::os::unix::fs::OpenOptionsExt;
            options.mode(0o600);
        }
        let mut file = options.open(&path)?;
        let contents = Self(path);
        file.write_all(text.as_bytes())?;
        file.sync_all()?;
        Ok(contents)
    }
}
impl Drop for Contents {
    fn drop(&mut self) {
        let _ = fs::remove_file(&self.0);
    }
}
pub fn annotate(
    root: &Path,
    revision: &Revision,
    path: &str,
    fallback: &str,
    text: &str,
) -> Result<Vec<Line>> {
    git::validate_paths(&[path.into(), fallback.into()])?;
    if text.is_empty() {
        return Ok(vec![]);
    }
    if text.len() > 20_000_000 || text.contains('\0') {
        bail!("Blame 仅支持 20 MB 内的普通文本");
    }
    if git::text_version(root, revision, path, 20_000_000)? != text.as_bytes() {
        bail!("文件版本已变化，请刷新后重试 Blame");
    }
    match revision {
        Revision::Empty => Ok(vec![]),
        Revision::Head(sha) | Revision::Commit(sha) => parse(
            &git::git(
                root,
                &[
                    "-c",
                    "core.quotePath=false",
                    "blame",
                    "--porcelain",
                    "--no-textconv",
                    sha,
                    "--",
                    path,
                ],
            )?,
            text,
        ),
        Revision::Index | Revision::Worktree => mutable(root, path, fallback, text),
    }
}
fn mutable(root: &Path, path: &str, fallback: &str, text: &str) -> Result<Vec<Line>> {
    let head = git::head(root)?;
    let Revision::Head(sha) = &head else {
        return Ok(uncommitted(path, text));
    };
    let exists = |path: &str| -> Result<bool> {
        Ok(!git::git(root, &["ls-tree", "-z", sha, "--", path])?.is_empty())
    };
    let mut origin = path.to_owned();
    if !exists(&origin)? {
        if exists(fallback)? {
            origin = fallback.into();
        } else if let Some(renamed) = git::selection(root, &BrowseMode::Staged)?
            .files
            .into_iter()
            .find(|f| f.path == path && f.old_path != path)
        {
            origin = renamed.old_path;
        } else {
            return Ok(uncommitted(path, text));
        }
    }
    let contents = Contents::new(text)?;
    let contents_path = contents.0.to_str().context("临时目录不是 UTF-8")?;
    let bytes = git::git(
        root,
        &[
            "-c",
            "core.quotePath=false",
            "blame",
            "--porcelain",
            "--no-textconv",
            "--contents",
            contents_path,
            sha,
            "--",
            &origin,
        ],
    )?;
    let mut lines = parse(&bytes, text)?;
    let target: Arc<str> = path.into();
    for line in &mut lines {
        if line.commit.uncommitted() {
            line.path = target.clone();
        }
    }
    Ok(lines)
}
pub fn annotate_buffer(root: &Path, path: &str, text: &str) -> Result<Vec<Line>> {
    git::validate_paths(&[path.into()])?;
    if text.is_empty() {
        return Ok(vec![]);
    }
    if text.len() > 20_000_000 || text.contains('\0') {
        bail!("Blame 仅支持 20 MB 内的普通文本");
    }
    if !fs::symlink_metadata(root.join(path))?.is_file() {
        bail!("缓冲区文件已变为目录/链接或特殊文件");
    }
    mutable(root, path, path, text)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn parser_rejects_stale_content_truncated_records_and_non_contiguous_lines() {
        let sha = "a".repeat(40);
        let record = format!(
            "{sha} 1 1 1\nauthor User\nauthor-mail <u@example.invalid>\nauthor-time 123\nauthor-tz +0000\nsummary message\nfilename file\n\tline\n"
        );
        assert_eq!(parse(record.as_bytes(), "line\n").unwrap()[0].line, 1);
        assert!(parse(record.as_bytes(), "different\n").is_err());
        assert!(parse(record.replace("\tline\n", "").as_bytes(), "line\n").is_err());
        assert!(parse(record.replace("1 1 1", "1 2 1").as_bytes(), "line\n").is_err());
        assert!(parse(record.as_bytes(), "line\nextra\n").is_err());
        assert_eq!(
            decode_path("\"tab\\tname\\n\\344\\270\\255\"").unwrap(),
            "tab\tname\n中"
        );
    }
}
