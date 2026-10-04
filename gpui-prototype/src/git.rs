use crate::{diff, model::*};
use anyhow::{Context, Result, bail};
use std::{
    collections::{BTreeMap, HashMap, HashSet},
    io::Read,
    path::{Path, PathBuf},
};

pub(crate) fn git(root: &Path, args: &[&str]) -> Result<Vec<u8>> {
    git_timeout(root, args, std::time::Duration::from_secs(30))
}
pub(crate) fn git_timeout(
    root: &Path,
    args: &[&str],
    timeout: std::time::Duration,
) -> Result<Vec<u8>> {
    let mut command = crate::external::command("git");
    command
        .arg("-C")
        .arg(root)
        .arg("--literal-pathspecs")
        .args(args)
        .env("GIT_OPTIONAL_LOCKS", "0");
    let output = crate::process::output(&mut command, timeout)?;
    if !output.status.success() {
        bail!(
            "{}\n{}",
            String::from_utf8_lossy(&output.stderr).trim(),
            String::from_utf8_lossy(&output.stdout).trim()
        );
    }
    Ok(output.stdout)
}
fn string(bytes: Vec<u8>) -> Result<String> {
    String::from_utf8(bytes).context("Git 返回非 UTF-8 文本，暂不支持该路径或编码")
}
pub(crate) fn head(root: &Path) -> Result<Revision> {
    match git(root, &["rev-parse", "--verify", "HEAD"]) {
        Ok(bytes) => Ok(Revision::Head(string(bytes)?.trim().into())),
        Err(error) => {
            // An unborn symbolic branch is expected; an invalid repository is not.
            git(root, &["symbolic-ref", "--quiet", "HEAD"]).map_err(|_| error)?;
            Ok(Revision::Empty)
        }
    }
}
pub struct RefreshSnapshot {
    pub repo: Snapshot,
    pub selection: Selection,
    pub active: Option<(FileChange, Comparison, Diff)>,
}
/// Re-read mutable versions while retaining pinned historical/custom comparisons.
pub fn refresh_snapshot(
    root: &Path,
    mode: &BrowseMode,
    active: Option<(FileChange, Comparison)>,
    follows_list: bool,
) -> Result<RefreshSnapshot> {
    let repo = snapshot(root)?;
    let selection = selection(root, mode)?;
    if let Revision::Head(sha) = &selection.comparison.left
        && repo.history_tip.as_ref() != Some(sha)
    {
        bail!("HEAD 在刷新期间改变，稍后重试");
    }
    let active = if let Some((mut file, mut comparison)) = active {
        if follows_list {
            comparison = selection.comparison.clone();
            if let Some(updated) = selection.files.iter().find(|f| f.path == file.path) {
                file = updated.clone();
            } else if matches!(
                mode,
                BrowseMode::Workspace | BrowseMode::Staged | BrowseMode::Unstaged
            ) {
                // A committed/unstaged rename must no longer read the obsolete old path.
                file.old_path = file.path.clone();
                file.status = "M".into();
            }
        } else if matches!(comparison.left, Revision::Head(_))
            && comparison.right == Revision::Worktree
        {
            comparison.left = repo
                .history_tip
                .clone()
                .map(Revision::Head)
                .unwrap_or(Revision::Empty);
        }
        let diff = compare(root, &comparison, &file)?;
        Some((file, comparison, diff))
    } else {
        None
    };
    Ok(RefreshSnapshot {
        repo,
        selection,
        active,
    })
}

/// Watch both per-worktree and shared metadata (which may be outside the worktree).
pub fn metadata_directories(root: &Path) -> Result<Vec<PathBuf>> {
    let mut paths = vec![];
    for option in ["--git-dir", "--git-common-dir"] {
        let path = PathBuf::from(
            string(git(root, &["rev-parse", "--path-format=absolute", option])?)?
                .trim_end_matches('\n'),
        );
        let path = path.canonicalize()?;
        if !paths.contains(&path) {
            paths.push(path);
        }
    }
    Ok(paths)
}
pub fn snapshot(path: &Path) -> Result<Snapshot> {
    let root = PathBuf::from(
        string(git(path, &["rev-parse", "--show-toplevel"])?)?.trim_end_matches('\n'),
    );
    let (branch, detached) = match git(&root, &["symbolic-ref", "--short", "--quiet", "HEAD"]) {
        Ok(bytes) => (string(bytes)?.trim().to_string(), false),
        Err(_) => (
            string(git(&root, &["rev-parse", "--short", "HEAD"])?)?
                .trim()
                .to_string(),
            true,
        ),
    };
    let history_tip = match head(&root)? {
        Revision::Head(sha) => Some(sha),
        _ => None,
    };
    let page = match &history_tip {
        Some(sha) => history_page(&root, sha, 0)?,
        None => HistoryPage {
            commits: vec![],
            more: false,
        },
    };
    let branches = crate::branches::list(&root)?;
    let references = reference_labels(&root, history_tip.as_deref(), &branch, detached)?;
    Ok(Snapshot {
        references,
        branches,
        root,
        branch,
        detached,
        commits: page.commits,
        history_tip,
        history_more: page.more,
    })
}
/// Current labels are separate from pinned history, so moving/deleting a ref
/// updates even commits on previously loaded pages.
pub fn reference_labels(
    root: &Path,
    head: Option<&str>,
    branch: &str,
    detached: bool,
) -> Result<std::collections::HashMap<String, String>> {
    let output = string(git(
        root,
        &[
            "for-each-ref",
            "--format=%(objectname)%00%(*objectname)%00%(refname:short)%00%(refname)",
        ],
    )?)?;
    let mut labels: std::collections::HashMap<String, Vec<String>> = Default::default();
    for line in output.lines() {
        let fields: Vec<_> = line.split('\0').collect();
        if fields.len() != 4 {
            bail!("引用标签格式无效");
        }
        let sha = if fields[1].is_empty() {
            fields[0]
        } else {
            fields[1]
        };
        labels
            .entry(sha.into())
            .or_default()
            .push(if fields[3].starts_with("refs/tags/") {
                format!("tag: {}", fields[2])
            } else {
                fields[2].into()
            });
    }
    if let Some(head) = head {
        labels.entry(head.into()).or_default().insert(
            0,
            if detached {
                "HEAD".into()
            } else {
                format!("HEAD → {branch}")
            },
        );
    }
    Ok(labels
        .into_iter()
        .map(|(sha, labels)| (sha, labels.join(", ")))
        .collect())
}
/// All pages use the same pinned tip, even when HEAD changes between requests.
pub fn history_page(root: &Path, tip: &str, skip: usize) -> Result<HistoryPage> {
    let output = string(git(
        root,
        &[
            "log",
            "-101",
            &format!("--skip={skip}"),
            "-z",
            "--format=%H%x00%s%x00%an%x00%aI%x00%P%x00%D",
            "--topo-order",
            tip,
            "--",
        ],
    )?)?;
    let fields: Vec<_> = output
        .strip_suffix('\0')
        .unwrap_or(&output)
        .split('\0')
        .collect();
    if output.is_empty() {
        return Ok(HistoryPage {
            commits: vec![],
            more: false,
        });
    }
    if !fields.len().is_multiple_of(6) {
        bail!("提交历史格式无效");
    }
    let mut commits: Vec<_> = fields
        .as_chunks::<6>()
        .0
        .iter()
        .map(|f| Commit {
            sha: f[0].into(),
            subject: f[1].into(),
            author: f[2].into(),
            date: f[3].into(),
            parents: f[4].split_whitespace().map(String::from).collect(),
            references: f[5].into(),
        })
        .collect();
    let more = commits.len() > 100;
    commits.truncate(100);
    Ok(HistoryPage { commits, more })
}

pub fn commit_detail(root: &Path, sha: &str) -> Result<CommitDetail> {
    let sha = string(git(
        root,
        &[
            "rev-parse",
            "--verify",
            "--end-of-options",
            &format!("{sha}^{{commit}}"),
        ],
    )?)?;
    let output = string(git(
        root,
        &[
            "show",
            "-s",
            "--format=%H%x00%B%x00%an%x00%ae%x00%aI%x00%cn%x00%ce%x00%cI%x00%D%x00%P",
            sha.trim(),
            "--",
        ],
    )?)?;
    let f: Vec<_> = output.trim_end_matches('\n').split('\0').collect();
    if f.len() != 10 {
        bail!("提交详情格式无效");
    }
    Ok(CommitDetail {
        sha: f[0].into(),
        message: f[1].into(),
        author: f[2].into(),
        author_email: f[3].into(),
        author_date: f[4].into(),
        committer: f[5].into(),
        committer_email: f[6].into(),
        commit_date: f[7].into(),
        references: f[8].into(),
        parents: f[9].split_whitespace().map(String::from).collect(),
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
        BrowseMode::Compare(comparison) => return comparison_selection(root, comparison),
        BrowseMode::Merge(sha) => {
            let selected = crate::merge::selection(root, sha)?;
            return Ok(Selection {
                comparison: Comparison {
                    left: Revision::Commit(selected.detail.parents[0].clone()),
                    right: Revision::Commit(selected.detail.sha),
                },
                files: selected
                    .files
                    .into_iter()
                    .map(|f| FileChange {
                        old_path: f.parent_paths[0].clone(),
                        path: f.path,
                        status: "M".into(),
                    })
                    .collect(),
            });
        }
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
pub fn resolve_revision(root: &Path, reference: &str) -> Result<Revision> {
    match reference.trim() {
        "WORKTREE" => Ok(Revision::Worktree),
        "INDEX" => Ok(Revision::Index),
        "EMPTY" => Ok(Revision::Empty),
        reference => {
            if reference.is_empty() {
                bail!("比较版本不能为空");
            }
            let sha = string(git(
                root,
                &[
                    "rev-parse",
                    "--verify",
                    "--end-of-options",
                    &format!("{reference}^{{commit}}"),
                ],
            )?)?;
            Ok(Revision::Commit(sha.trim().into()))
        }
    }
}
pub fn comparison_selection(root: &Path, comparison: &Comparison) -> Result<Selection> {
    // The editable workspace/index modes have their own entry points. Custom comparisons are read-only.
    let treeish = |revision: &Revision| -> Result<String> {
        match revision {
            Revision::Empty => Ok(
                string(git(root, &["hash-object", "-t", "tree", "--stdin"])?)?
                    .trim()
                    .into(),
            ),
            Revision::Head(sha) | Revision::Commit(sha) => Ok(sha.clone()),
            _ => bail!("自定义比较左侧必须是提交或 EMPTY，右侧可用提交或 WORKTREE"),
        }
    };
    let left = treeish(&comparison.left)?;
    let mut files = if comparison.right == Revision::Worktree {
        changes(root, &["diff", "--name-status", "-z", "-M", &left, "--"])?
    } else {
        let right = treeish(&comparison.right)?;
        changes(
            root,
            &["diff", "--name-status", "-z", "-M", &left, &right, "--"],
        )?
    };
    if comparison.right == Revision::Worktree {
        for file in untracked(root)? {
            if let Some(existing) = files.iter_mut().find(|f| f.path == file.path) {
                if existing.status.starts_with('D') {
                    existing.status = "M".into();
                }
            } else {
                files.push(file);
            }
        }
    }
    files.sort_by(|a, b| a.path.cmp(&b.path));
    Ok(Selection {
        comparison: comparison.clone(),
        files,
    })
}

pub(crate) fn validate_paths(paths: &[String]) -> Result<()> {
    for path in paths {
        if path.is_empty()
            || Path::new(path).is_absolute()
            || Path::new(path).components().any(|c| {
                matches!(
                    c,
                    std::path::Component::ParentDir | std::path::Component::Prefix(_)
                )
            })
        {
            bail!("文件路径必须位于当前仓库");
        }
    }
    Ok(())
}
pub fn stage(root: &Path, paths: &[String], all: bool) -> Result<()> {
    validate_paths(paths)?;
    if !all && paths.is_empty() {
        bail!("请选择要暂存的文件");
    }
    let mut filtered = vec![];
    if !all {
        for path in paths {
            if root.join(path).symlink_metadata().is_ok()
                || !git(root, &["ls-files", "-z", "--", path])?.is_empty()
            {
                filtered.push(path.as_str());
            }
        }
        if filtered.is_empty() {
            bail!("所选路径已不存在，请刷新状态");
        }
    }
    let mut args = vec!["add", "--all", "--"];
    if all {
        args.push(".");
    } else {
        args.extend(filtered);
    }
    git_timeout(root, &args, std::time::Duration::from_secs(120))?;
    Ok(())
}
pub fn unstage(root: &Path, paths: &[String], all: bool) -> Result<()> {
    validate_paths(paths)?;
    if !all && paths.is_empty() {
        bail!("请选择要取消暂存的文件");
    }
    let mut args = match head(root)? {
        Revision::Empty => vec!["rm", "--cached", "-r", "--ignore-unmatch", "--"],
        _ => vec!["reset", "--quiet", "HEAD", "--"],
    };
    if all {
        args.push(".");
    } else {
        args.extend(paths.iter().map(String::as_str));
    }
    git_timeout(root, &args, std::time::Duration::from_secs(120))?;
    Ok(())
}
pub fn commit_index(root: &Path, message: &str) -> Result<String> {
    if message.trim().is_empty() {
        bail!("提交信息不能为空");
    }
    if !git(root, &["ls-files", "--unmerged", "-z"])?.is_empty() {
        bail!("仍有未解决的冲突，不能提交");
    }
    if git(root, &["diff", "--cached", "--name-only", "-z", "--"])?.is_empty() {
        bail!("暂存区为空，请先暂存文件");
    }
    let output = string(git_timeout(
        root,
        &["commit", "-m", message, "--"],
        std::time::Duration::from_secs(120),
    )?)?;
    Ok(output.trim().into())
}

pub fn workspace_status(root: &Path) -> Result<BTreeMap<String, String>> {
    let bytes = git(
        root,
        &[
            "status",
            "--porcelain=v1",
            "-z",
            "--ignored=matching",
            "--untracked-files=all",
        ],
    )?;
    let text = std::str::from_utf8(&bytes).context("状态路径不是 UTF-8")?;
    let mut records = text.split('\0').filter(|r| !r.is_empty());
    let mut result = BTreeMap::new();
    while let Some(record) = records.next() {
        if record.len() < 4 || !record.is_char_boundary(3) {
            bail!("状态记录无效");
        }
        let status = &record[..2];
        let path = record[3..].trim_end_matches('/');
        result.insert(path.to_owned(), status.to_owned());
        if status.contains('R') || status.contains('C') {
            let old = records.next().context("重命名缺少原路径")?;
            result.insert(old.into(), "D".into());
        }
    }
    Ok(result)
}
pub fn workspace_file(root: &Path, path: &str) -> Result<(Comparison, FileChange)> {
    let left = head(root)?;
    let exists_in_head = match &left {
        Revision::Head(sha) => git(root, &["cat-file", "-e", &format!("{sha}:{path}")]).is_ok(),
        _ => false,
    };
    Ok((
        Comparison {
            left,
            right: Revision::Worktree,
        },
        FileChange {
            path: path.into(),
            old_path: path.into(),
            status: if exists_in_head { "M" } else { "A" }.into(),
        },
    ))
}

#[derive(Clone, Debug)]
struct ContentInfo {
    kind: &'static str,
    size: u64,
    object: Option<String>,
}
fn info(root: &Path, target: &FileTarget) -> Result<ContentInfo> {
    let empty = || ContentInfo {
        kind: "空内容",
        size: 0,
        object: None,
    };
    let record = match &target.revision {
        Revision::Empty => return Ok(empty()),
        Revision::Worktree => {
            let path = root.join(&target.path);
            let metadata = std::fs::symlink_metadata(&path)
                .with_context(|| format!("无法读取工作区 {}", target.path))?;
            if metadata.file_type().is_symlink() {
                return Ok(ContentInfo {
                    kind: "符号链接",
                    size: metadata.len(),
                    object: None,
                });
            }
            if metadata.is_dir() {
                let indexed = string(git(
                    root,
                    &["ls-files", "--stage", "-z", "--", &target.path],
                )?)?;
                if indexed.starts_with("160000 ") {
                    let sha = if path.join(".git").exists() {
                        git(&path, &["rev-parse", "--verify", "HEAD"])
                    } else {
                        Err(anyhow::anyhow!("子模块未检出"))
                    }
                    .ok()
                    .and_then(|b| String::from_utf8(b).ok())
                    .map(|s| s.trim().into());
                    return Ok(ContentInfo {
                        kind: "子模块",
                        size: 0,
                        object: sha,
                    });
                }
                bail!("目录不是普通文件或已登记的子模块");
            }
            if !metadata.is_file() {
                bail!("特殊文件不支持预览");
            }
            return Ok(ContentInfo {
                kind: "文本/二进制文件",
                size: metadata.len(),
                object: None,
            });
        }
        Revision::Index => string(git(
            root,
            &["ls-files", "--stage", "-z", "--", &target.path],
        )?)?,
        Revision::Head(sha) | Revision::Commit(sha) => {
            string(git(root, &["ls-tree", "-z", sha, "--", &target.path])?)?
        }
    };
    let header = record.split('\t').next().context("缺少对象信息")?;
    let fields: Vec<_> = header.split_whitespace().collect();
    let mode = *fields.first().context("对象模式无效")?;
    let object = match target.revision {
        Revision::Index => fields.get(1),
        _ => fields.get(2),
    }
    .context("缺少对象 ID")?
    .to_string();
    if mode == "160000" {
        return Ok(ContentInfo {
            kind: "子模块",
            size: 0,
            object: Some(object),
        });
    }
    if !matches!(mode, "100644" | "100755" | "120000") {
        bail!("不支持的 Git 对象模式：{mode}");
    }
    let size = string(git(root, &["cat-file", "-s", &object])?)?
        .trim()
        .parse::<u64>()?;
    Ok(ContentInfo {
        kind: if mode == "120000" {
            "符号链接"
        } else {
            "文本/二进制文件"
        },
        size,
        object: Some(object),
    })
}
fn content(root: &Path, target: &FileTarget, info: &ContentInfo, limit: usize) -> Result<Vec<u8>> {
    if target.revision == Revision::Empty {
        return Ok(vec![]);
    }
    if target.revision == Revision::Worktree {
        let path = root.join(&target.path);
        if info.kind == "符号链接" {
            return Ok(std::fs::read_link(&path)?
                .to_string_lossy()
                .as_bytes()
                .to_vec());
        }
        let mut options = std::fs::OpenOptions::new();
        options.read(true);
        #[cfg(unix)]
        {
            use std::os::unix::fs::OpenOptionsExt;
            options.custom_flags(libc::O_NOFOLLOW | libc::O_NONBLOCK);
        }
        let file = options.open(&path)?;
        if !file.metadata()?.is_file() {
            bail!("特殊文件不支持预览");
        }
        let mut bytes = vec![];
        file.take(limit as u64 + 1).read_to_end(&mut bytes)?;
        return Ok(bytes);
    }
    git(
        root,
        &[
            "cat-file",
            "blob",
            info.object.as_ref().context("缺少 blob ID")?,
        ],
    )
}
pub struct VersionContent {
    pub bytes: Vec<u8>,
    pub symlink: bool,
    pub executable: bool,
}
pub fn version_content(
    root: &Path,
    revision: &Revision,
    path: &str,
) -> Result<Option<VersionContent>> {
    if *revision == Revision::Empty {
        return Ok(None);
    }
    let record = match revision {
        Revision::Index => string(git(root, &["ls-files", "--stage", "-z", "--", path])?)?,
        Revision::Head(sha) | Revision::Commit(sha) => {
            string(git(root, &["ls-tree", "-z", sha, "--", path])?)?
        }
        _ => bail!("还原来源必须是提交、index 或空内容"),
    };
    if record.is_empty() {
        return Ok(None);
    }
    let fields: Vec<_> = record
        .split('\t')
        .next()
        .unwrap_or("")
        .split_whitespace()
        .collect();
    let mode = fields.first().copied().context("还原来源缺少模式")?;
    if *revision == Revision::Index && fields.get(2) != Some(&"0") {
        bail!("未合并 index 不能作为还原来源");
    }
    if mode == "160000" {
        bail!("子模块目录不能使用文件还原操作");
    }
    let target = FileTarget {
        revision: revision.clone(),
        path: path.into(),
    };
    let metadata = info(root, &target)?;
    if metadata.size > 20_000_000 {
        bail!("还原文件超过 20 MB 恢复记录上限");
    }
    let bytes = content(root, &target, &metadata, 20_000_000)?;
    Ok(Some(VersionContent {
        bytes,
        symlink: mode == "120000",
        executable: mode == "100755",
    }))
}
/// Read the exact bounded ordinary-file version for consumers such as Blame.
pub fn text_version(root: &Path, revision: &Revision, path: &str, limit: usize) -> Result<Vec<u8>> {
    validate_paths(&[path.to_owned()])?;
    if *revision == Revision::Empty {
        return Ok(vec![]);
    }
    let target = FileTarget {
        revision: revision.clone(),
        path: path.into(),
    };
    let metadata = info(root, &target)?;
    if metadata.kind != "文本/二进制文件" {
        bail!("逐行归属仅支持普通文本文件");
    }
    if metadata.size > limit as u64 {
        bail!("文件超过逐行归属读取上限");
    }
    content(root, &target, &metadata, limit)
}
pub fn compare(root: &Path, comparison: &Comparison, file: &FileChange) -> Result<Diff> {
    compare_with_limit(root, comparison, file, 2_000_000)
}
pub fn compare_with_limit(
    root: &Path,
    comparison: &Comparison,
    file: &FileChange,
    limit: usize,
) -> Result<Diff> {
    if file.status.starts_with('U') {
        return Ok(Diff::notice("冲突文件：暂不支持预览未合并的 index 内容"));
    }
    let (left, right) = comparison.targets(file);
    let li = info(root, &left)?;
    let ri = info(root, &right)?;
    let description = format!(
        "左侧：{} · {} 字节；右侧：{} · {} 字节",
        li.kind, li.size, ri.kind, ri.size
    );
    if li.kind == "子模块" || ri.kind == "子模块" {
        return Ok(Diff::notice(&format!(
            "子模块提交引用\n左侧：{}\n右侧：{}\n目录内容不作为普通文本读取",
            li.object.as_deref().unwrap_or("空/未检出"),
            ri.object.as_deref().unwrap_or("空/未检出")
        )));
    }
    if li.size.saturating_add(ri.size) > limit.min(20_000_000) as u64 {
        let mut diff = Diff::notice(&format!(
            "文件超过 {} MB 预览上限；{description}",
            limit.min(20_000_000) / 1_000_000
        ));
        diff.description = Some(description);
        return Ok(diff);
    }
    let left_bytes = content(root, &left, &li, limit)?;
    let right_bytes = content(root, &right, &ri, limit)?;
    let mut diff = diff::calculate_with_limit(&left_bytes, &right_bytes, limit.min(20_000_000))?;
    diff.description = Some(description.clone());
    if diff.message.is_none() {
        diff::highlight(&mut diff, &file.old_path, &file.path);
    } else if let Some(message) = &mut diff.message {
        *message = format!("{message}；{description}");
    }
    Ok(diff)
}

#[cfg(test)]
#[path = "git_tests.rs"]
mod tests;
