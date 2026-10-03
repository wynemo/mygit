use anyhow::{Context, Result, bail};
use std::{
    path::{Path, PathBuf},
    process::Command,
};

#[derive(Clone, Debug)]
pub struct Commit {
    pub sha: String,
    pub subject: String,
    pub author: String,
    pub date: String,
}
#[derive(Clone, Debug)]
pub struct FileChange {
    pub path: String,
    pub old_path: String,
    pub status: String,
}
#[derive(Clone, Debug)]
pub struct Snapshot {
    pub root: PathBuf,
    pub branch: String,
    pub commits: Vec<Commit>,
    pub files: Vec<FileChange>,
}
#[derive(Clone, Debug)]
pub struct DiffRow {
    pub left_no: Option<usize>,
    pub right_no: Option<usize>,
    pub left: String,
    pub right: String,
    pub changed: bool,
}
#[derive(Clone, Debug, Default)]
pub struct Diff {
    pub rows: Vec<DiffRow>,
    pub message: Option<String>,
}

fn git(root: &Path, args: &[&str]) -> Result<Vec<u8>> {
    let output = Command::new("git")
        .arg("-C")
        .arg(root)
        .args(args)
        .env("GIT_OPTIONAL_LOCKS", "0")
        .output()
        .context("无法启动 Git")?;
    if !output.status.success() {
        bail!("{}", String::from_utf8_lossy(&output.stderr).trim());
    }
    Ok(output.stdout)
}
fn string(bytes: Vec<u8>) -> String {
    String::from_utf8_lossy(&bytes).into_owned()
}

pub fn snapshot(path: &Path) -> Result<Snapshot> {
    let root = PathBuf::from(string(git(path, &["rev-parse", "--show-toplevel"])?).trim());
    let branch = string(
        git(&root, &["rev-parse", "--abbrev-ref", "HEAD"])
            .unwrap_or_else(|_| b"unborn HEAD".to_vec()),
    )
    .trim()
    .to_string();
    let has_head = git(&root, &["rev-parse", "--verify", "HEAD"]).is_ok();
    let commits = if has_head {
        string(git(
            &root,
            &["log", "-100", "--format=%H%x1f%s%x1f%an%x1f%as"],
        )?)
        .lines()
        .filter_map(|line| {
            let fields: Vec<_> = line.split('\x1f').collect();
            (fields.len() == 4).then(|| Commit {
                sha: fields[0].into(),
                subject: fields[1].into(),
                author: fields[2].into(),
                date: fields[3].into(),
            })
        })
        .collect()
    } else {
        vec![]
    };
    let files = parse_status(&git(
        &root,
        &["status", "--porcelain=v1", "-z", "--untracked-files=all"],
    )?);
    Ok(Snapshot {
        root,
        branch,
        commits,
        files,
    })
}
fn parse_status(bytes: &[u8]) -> Vec<FileChange> {
    let mut records = bytes.split(|b| *b == 0).filter(|r| !r.is_empty());
    let mut files = vec![];
    while let Some(record) = records.next() {
        if record.len() < 4 {
            continue;
        }
        let status = String::from_utf8_lossy(&record[..2]).into_owned();
        let path = String::from_utf8_lossy(&record[3..]).into_owned();
        let old_path = if status.contains('R') || status.contains('C') {
            String::from_utf8_lossy(records.next().unwrap_or(&[])).into_owned()
        } else {
            path.clone()
        };
        files.push(FileChange {
            path,
            old_path,
            status,
        });
    }
    files
}
pub fn commit_files(root: &Path, sha: &str) -> Result<Vec<FileChange>> {
    // Compare merges to the first parent, and initial commits to the empty tree.
    let ancestry = string(git(root, &["rev-list", "--parents", "-n", "1", sha])?);
    let parent = ancestry.split_whitespace().nth(1);
    let mut args = vec![
        "diff-tree",
        "--root",
        "--no-commit-id",
        "--name-status",
        "-r",
        "-z",
        "-M",
    ];
    if let Some(parent) = parent {
        args.push(parent);
    }
    args.push(sha);
    let output = git(root, &args)?;
    let mut records = output.split(|b| *b == 0).filter(|r| !r.is_empty());
    let mut files = vec![];
    while let Some(status) = records.next() {
        let status = String::from_utf8_lossy(status).into_owned();
        let first = String::from_utf8_lossy(records.next().unwrap_or(&[])).into_owned();
        let path = if status.starts_with('R') || status.starts_with('C') {
            String::from_utf8_lossy(records.next().unwrap_or(&[])).into_owned()
        } else {
            first.clone()
        };
        files.push(FileChange {
            path,
            old_path: first,
            status,
        });
    }
    Ok(files)
}
fn blob(root: &Path, rev: &str, path: &str) -> Result<Vec<u8>> {
    git(root, &["show", &format!("{rev}:{path}")])
}
pub fn diff(root: &Path, commit: Option<&str>, file: &FileChange) -> Result<Diff> {
    let (left, right) = if let Some(sha) = commit {
        let parent = string(git(root, &["rev-list", "--parents", "-n", "1", sha])?);
        let parent = parent.split_whitespace().nth(1);
        let left = match parent {
            Some(parent) if !file.status.starts_with('A') => blob(root, parent, &file.old_path)?,
            _ => vec![],
        };
        let right = if file.status.starts_with('D') {
            vec![]
        } else {
            blob(root, sha, &file.path)?
        };
        (left, right)
    } else {
        let left = if file.status == "??" || file.status.starts_with('A') {
            vec![]
        } else {
            blob(root, "HEAD", &file.old_path)?
        };
        let target = root.join(&file.path);
        let right = if file.status.contains('D') && !target.exists() {
            vec![]
        } else {
            std::fs::read(&target).context("无法读取工作区文件")?
        };
        (left, right)
    };
    if left.contains(&0) || right.contains(&0) {
        return Ok(Diff {
            rows: vec![],
            message: Some("二进制文件：暂不提供内容预览".into()),
        });
    }
    if left.len() + right.len() > 2_000_000 {
        return Ok(Diff {
            rows: vec![],
            message: Some("文件超过原型的 2 MB 预览上限".into()),
        });
    }
    let left = std::str::from_utf8(&left).context("旧版本不是 UTF-8 文本")?;
    let right = std::str::from_utf8(&right).context("新版本不是 UTF-8 文本")?;
    Ok(Diff {
        rows: align(left, right),
        message: None,
    })
}
fn align(left: &str, right: &str) -> Vec<DiffRow> {
    use similar::{ChangeTag, TextDiff};
    let mut rows = vec![];
    let mut deleted = vec![];
    let mut inserted = vec![];
    let (mut l, mut r) = (1, 1);
    fn flush(
        rows: &mut Vec<DiffRow>,
        deleted: &mut Vec<(usize, String)>,
        inserted: &mut Vec<(usize, String)>,
    ) {
        for i in 0..deleted.len().max(inserted.len()) {
            rows.push(DiffRow {
                left_no: deleted.get(i).map(|v| v.0),
                right_no: inserted.get(i).map(|v| v.0),
                left: deleted.get(i).map(|v| v.1.clone()).unwrap_or_default(),
                right: inserted.get(i).map(|v| v.1.clone()).unwrap_or_default(),
                changed: true,
            });
        }
        deleted.clear();
        inserted.clear();
    }
    for change in TextDiff::from_lines(left, right).iter_all_changes() {
        let text = change
            .value()
            .trim_end_matches('\n')
            .trim_end_matches('\r')
            .to_string();
        match change.tag() {
            ChangeTag::Delete => {
                deleted.push((l, text));
                l += 1;
            }
            ChangeTag::Insert => {
                inserted.push((r, text));
                r += 1;
            }
            ChangeTag::Equal => {
                flush(&mut rows, &mut deleted, &mut inserted);
                rows.push(DiffRow {
                    left_no: Some(l),
                    right_no: Some(r),
                    left: text.clone(),
                    right: text,
                    changed: false,
                });
                l += 1;
                r += 1;
            }
        }
    }
    flush(&mut rows, &mut deleted, &mut inserted);
    rows
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn replacement_aligns_and_preserves_numbers() {
        let rows = align("a\nb\nc\n", "a\nx\ny\nc\n");
        assert_eq!(rows.len(), 4);
        assert_eq!((&rows[1].left[..], &rows[1].right[..]), ("b", "x"));
        assert_eq!((rows[2].left_no, rows[2].right_no), (None, Some(3)));
        assert_eq!((rows[3].left_no, rows[3].right_no), (Some(3), Some(4)));
    }
    #[test]
    fn status_handles_rename_and_spaces() {
        let files = parse_status(b"R  new name\0old name\0?? another file\0");
        assert_eq!(files.len(), 2);
        assert_eq!(files[0].old_path, "old name");
        assert_eq!(files[0].path, "new name");
        assert_eq!(files[1].status, "??");
    }
    struct Fixture(PathBuf);
    impl Fixture {
        fn new() -> Self {
            let path = std::env::temp_dir().join(format!(
                "mygit-gpui-test-{}-{}",
                std::process::id(),
                std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .unwrap()
                    .as_nanos()
            ));
            std::fs::create_dir(&path).unwrap();
            git(&path, &["init", "-b", "main"]).unwrap();
            git(&path, &["config", "user.name", "Test"]).unwrap();
            git(&path, &["config", "user.email", "test@example.invalid"]).unwrap();
            Self(path)
        }
        fn commit(&self) -> String {
            git(&self.0, &["add", "-A"]).unwrap();
            git(
                &self.0,
                &["-c", "commit.gpgsign=false", "commit", "-m", "fixture"],
            )
            .unwrap();
            string(git(&self.0, &["rev-parse", "HEAD"]).unwrap())
                .trim()
                .into()
        }
    }
    impl Drop for Fixture {
        fn drop(&mut self) {
            let _ = std::fs::remove_dir_all(&self.0);
        }
    }
    #[test]
    fn real_repository_initial_commit_rename_and_worktree() {
        let f = Fixture::new();
        assert!(snapshot(&f.0).unwrap().commits.is_empty());
        std::fs::write(f.0.join("old name.txt"), "a\nb\n").unwrap();
        let initial = f.commit();
        let files = commit_files(&f.0, &initial).unwrap();
        let d = diff(&f.0, Some(&initial), &files[0]).unwrap();
        assert!(d.rows.iter().all(|r| r.left_no.is_none()));
        std::fs::rename(f.0.join("old name.txt"), f.0.join("新 name.txt")).unwrap();
        let renamed = f.commit();
        let files = commit_files(&f.0, &renamed).unwrap();
        assert_eq!(files[0].old_path, "old name.txt");
        assert!(
            diff(&f.0, Some(&renamed), &files[0])
                .unwrap()
                .rows
                .iter()
                .all(|r| !r.changed)
        );
        std::fs::write(f.0.join("新 name.txt"), "a\nc\n").unwrap();
        let repo = snapshot(&f.0).unwrap();
        assert_eq!(repo.commits.len(), 2);
        assert_eq!(repo.files.len(), 1);
        assert_eq!(diff(&f.0, None, &repo.files[0]).unwrap().rows[1].right, "c");
        std::fs::remove_file(f.0.join("新 name.txt")).unwrap();
        let repo = snapshot(&f.0).unwrap();
        assert!(
            diff(&f.0, None, &repo.files[0])
                .unwrap()
                .rows
                .iter()
                .all(|r| r.right_no.is_none())
        );
        std::fs::write(f.0.join("binary"), [0, 1, 2]).unwrap();
        let repo = snapshot(&f.0).unwrap();
        let binary = repo.files.iter().find(|f| f.path == "binary").unwrap();
        assert!(diff(&f.0, None, binary).unwrap().message.is_some());
    }
    #[test]
    fn merge_compares_first_parent() {
        let f = Fixture::new();
        std::fs::write(f.0.join("base"), "base\n").unwrap();
        f.commit();
        git(&f.0, &["checkout", "-b", "feature"]).unwrap();
        std::fs::write(f.0.join("feature"), "feature\n").unwrap();
        f.commit();
        git(&f.0, &["checkout", "main"]).unwrap();
        std::fs::write(f.0.join("main"), "main\n").unwrap();
        f.commit();
        git(
            &f.0,
            &[
                "-c",
                "commit.gpgsign=false",
                "merge",
                "--no-ff",
                "feature",
                "-m",
                "merge",
            ],
        )
        .unwrap();
        let sha = string(git(&f.0, &["rev-parse", "HEAD"]).unwrap())
            .trim()
            .to_string();
        let files = commit_files(&f.0, &sha).unwrap();
        assert_eq!(files.len(), 1);
        assert_eq!(files[0].path, "feature");
        assert_eq!(
            diff(&f.0, Some(&sha), &files[0]).unwrap().rows[0].right,
            "feature"
        );
    }
}
