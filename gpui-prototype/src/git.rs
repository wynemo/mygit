use crate::{diff, model::*};
use anyhow::{Context, Result, bail};
use std::{
    collections::{HashMap, HashSet},
    path::{Path, PathBuf},
    process::Command,
};

fn git(root: &Path, args: &[&str]) -> Result<Vec<u8>> {
    let output = Command::new("git")
        .arg("-C")
        .arg(root)
        .arg("--literal-pathspecs")
        .args(args)
        .env("GIT_OPTIONAL_LOCKS", "0")
        .output()
        .context("无法启动 Git")?;
    if !output.status.success() {
        bail!("{}", String::from_utf8_lossy(&output.stderr).trim());
    }
    Ok(output.stdout)
}
fn string(bytes: Vec<u8>) -> Result<String> {
    String::from_utf8(bytes).context("Git 返回非 UTF-8 文本，暂不支持该路径或编码")
}
fn head(root: &Path) -> Result<Revision> {
    match git(root, &["rev-parse", "--verify", "HEAD"]) {
        Ok(bytes) => Ok(Revision::Head(string(bytes)?.trim().into())),
        Err(error) => {
            // An unborn symbolic branch is expected; an invalid repository is not.
            git(root, &["symbolic-ref", "--quiet", "HEAD"]).map_err(|_| error)?;
            Ok(Revision::Empty)
        }
    }
}
pub fn snapshot(path: &Path) -> Result<Snapshot> {
    let root = PathBuf::from(
        string(git(path, &["rev-parse", "--show-toplevel"])?)?.trim_end_matches('\n'),
    );
    let branch = string(
        git(&root, &["symbolic-ref", "--short", "--quiet", "HEAD"])
            .or_else(|_| git(&root, &["rev-parse", "--short", "HEAD"]))?,
    )?
    .trim()
    .to_string();
    let commits = if let Revision::Head(sha) = head(&root)? {
        string(git(
            &root,
            &["log", "-100", "--format=%H%x1f%s%x1f%an%x1f%as", &sha, "--"],
        )?)?
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
    Ok(Snapshot {
        root,
        branch,
        commits,
    })
}
fn parse_files(bytes: &[u8]) -> Result<Vec<FileChange>> {
    let text = std::str::from_utf8(bytes).context("文件路径不是 UTF-8，暂不支持预览")?;
    let mut records = text.split('\0').filter(|r| !r.is_empty());
    let mut files = vec![];
    let mut seen = HashSet::new();
    while let Some(status) = records.next() {
        let first = records.next().context("Git 文件列表缺少路径")?.to_string();
        let path = if status.starts_with('R') || status.starts_with('C') {
            records
                .next()
                .context("重命名记录缺少目标路径")?
                .to_string()
        } else {
            first.clone()
        };
        // Unmerged entries can be emitted twice (U and M). Keep U and show a notice.
        if seen.insert(path.clone()) {
            files.push(FileChange {
                path,
                old_path: first,
                status: status.into(),
            });
        }
    }
    Ok(files)
}
fn changes(root: &Path, args: &[&str]) -> Result<Vec<FileChange>> {
    parse_files(&git(root, args)?)
}
fn untracked(root: &Path) -> Result<Vec<FileChange>> {
    let output = git(root, &["ls-files", "--others", "--exclude-standard", "-z"])?;
    let text = std::str::from_utf8(&output).context("未跟踪文件路径不是 UTF-8")?;
    Ok(text
        .split('\0')
        .filter(|p| !p.is_empty())
        .map(|path| FileChange {
            path: path.into(),
            old_path: path.into(),
            status: "??".into(),
        })
        .collect())
}
pub fn selection(root: &Path, mode: &BrowseMode) -> Result<Selection> {
    let (comparison, mut files) = match mode {
        BrowseMode::History(sha) => {
            let sha = string(git(
                root,
                &[
                    "rev-parse",
                    "--verify",
                    "--end-of-options",
                    &format!("{sha}^{{commit}}"),
                ],
            )?)?
            .trim()
            .to_string();
            let ancestry = string(git(root, &["rev-list", "--parents", "-n", "1", &sha])?)?;
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
            args.extend([&sha, "--"]);
            let files = changes(root, &args)?;
            (
                Comparison {
                    left: parent
                        .map(|p| Revision::Commit(p.into()))
                        .unwrap_or(Revision::Empty),
                    right: Revision::Commit(sha),
                },
                files,
            )
        }
        BrowseMode::Staged => (
            Comparison {
                left: head(root)?,
                right: Revision::Index,
            },
            changes(
                root,
                &["diff", "--cached", "--name-status", "-z", "-M", "--"],
            )?,
        ),
        BrowseMode::Unstaged => (
            Comparison {
                left: Revision::Index,
                right: Revision::Worktree,
            },
            changes(root, &["diff", "--name-status", "-z", "-M", "--"])?,
        ),
        BrowseMode::Workspace => {
            let left = head(root)?;
            let files = if let Revision::Head(sha) = &left {
                changes(root, &["diff", "--name-status", "-z", "-M", sha, "--"])?
            } else {
                // Without HEAD, every tracked file is an addition to the empty tree.
                changes(root, &["diff", "--cached", "--name-status", "-z", "--"])?
                    .into_iter()
                    .filter(|file| root.join(&file.path).exists())
                    .collect()
            };
            (
                Comparison {
                    left,
                    right: Revision::Worktree,
                },
                files,
            )
        }
    };
    if matches!(mode, BrowseMode::Workspace | BrowseMode::Unstaged) {
        let mut positions: HashMap<String, usize> = files
            .iter()
            .enumerate()
            .map(|(i, file)| (file.path.clone(), i))
            .collect();
        for file in untracked(root)? {
            if let Some(index) = positions.get(&file.path) {
                let existing = &mut files[*index];
                // A staged deletion followed by a recreated untracked file still
                // compares HEAD with the disk in the overall view.
                if matches!(mode, BrowseMode::Workspace) && existing.status.starts_with('D') {
                    existing.status = "M".into();
                }
            } else {
                positions.insert(file.path.clone(), files.len());
                files.push(file);
            }
        }
    }
    files.sort_by(|a, b| a.path.cmp(&b.path));
    Ok(Selection { comparison, files })
}
fn content(root: &Path, target: &FileTarget) -> Result<Vec<u8>> {
    match &target.revision {
        Revision::Empty => Ok(vec![]),
        Revision::Worktree => std::fs::read(root.join(&target.path))
            .with_context(|| format!("无法读取工作区文件 {}", target.path)),
        Revision::Index => git(root, &["show", &format!(":{}", target.path)]),
        Revision::Head(sha) | Revision::Commit(sha) => {
            git(root, &["show", &format!("{sha}:{}", target.path)])
        }
    }
}
pub fn compare(root: &Path, comparison: &Comparison, file: &FileChange) -> Result<Diff> {
    if file.status.starts_with('U') {
        return Ok(Diff::notice("冲突文件：暂不支持预览未合并的 index 内容"));
    }
    let (left, right) = comparison.targets(file);
    let mut diff = diff::calculate(&content(root, &left)?, &content(root, &right)?)?;
    if diff.message.is_none() {
        diff::highlight(&mut diff, &file.old_path, &file.path);
    }
    Ok(diff)
}

#[cfg(test)]
#[path = "git_tests.rs"]
mod tests;
