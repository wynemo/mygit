//! Branch references and safe checkout using Git's normal worktree protections.
use crate::{git::git, model::BranchRef};
use anyhow::{Context, Result, bail};
use std::path::Path;

pub fn list(root: &Path) -> Result<Vec<BranchRef>> {
    let output = git(
        root,
        &[
            "for-each-ref",
            "--sort=refname",
            "--format=%(refname)%00%(objectname)%00%(HEAD)%00%(upstream)%00%(upstream:track)%00%(symref)",
            "refs/heads/",
            "refs/remotes/",
        ],
    )?;
    let text = std::str::from_utf8(&output).context("分支引用不是 UTF-8")?;
    let remote_output = git(root, &["remote"])?;
    let mut remotes: Vec<_> = std::str::from_utf8(&remote_output)?.lines().collect();
    remotes.sort_by_key(|name| std::cmp::Reverse(name.len()));
    let mut branches = vec![];
    for line in text.lines() {
        let fields: Vec<_> = line.split('\0').collect();
        if fields.len() != 6 {
            bail!("无法读取完整分支引用");
        }
        if !fields[5].is_empty() {
            continue;
        } // origin/HEAD is an alias, not a checkout target.
        let remote = fields[0].starts_with("refs/remotes/");
        let name = fields[0]
            .strip_prefix(if remote {
                "refs/remotes/"
            } else {
                "refs/heads/"
            })
            .context("未知分支引用")?;
        let local_name = if remote {
            remotes
                .iter()
                .find_map(|r| name.strip_prefix(&format!("{r}/")).map(str::to_owned))
        } else {
            Some(name.into())
        };
        branches.push(BranchRef {
            reference: fields[0].into(),
            name: name.into(),
            sha: fields[1].into(),
            current: fields[2] == "*",
            remote,
            upstream: fields[3].into(),
            tracking: fields[4].into(),
            local_name,
        });
    }
    Ok(branches)
}
fn validate_name(root: &Path, name: &str) -> Result<()> {
    if name.is_empty() || name.starts_with('-') || name == "HEAD" {
        bail!("请输入有效分支名");
    }
    git(root, &["check-ref-format", &format!("refs/heads/{name}")])?;
    Ok(())
}
pub fn switch(root: &Path, reference: &str, local_name: Option<&str>) -> Result<String> {
    let branch = list(root)?
        .into_iter()
        .find(|b| b.reference == reference)
        .context("目标分支已不存在，请刷新列表")?;
    if branch.remote {
        let name = local_name
            .filter(|s| !s.is_empty())
            .or(branch.local_name.as_deref())
            .context("远程配置已不存在，请先检查远程")?;
        validate_name(root, name)?;
        // -c creates and switches as one operation; checkout failure leaves no new branch.
        git(root, &["switch", "--track", "-c", name, &branch.reference])?;
        Ok(format!("已建立跟踪分支 {name} → {}", branch.name))
    } else {
        git(root, &["switch", "--no-guess", "--", &branch.name])?;
        Ok(format!("已切换到 {}", branch.name))
    }
}
pub fn create(root: &Path, name: &str, base: &str) -> Result<String> {
    validate_name(root, name)?;
    let base = base.trim();
    if base.is_empty() || base == "HEAD" {
        git(root, &["switch", "-c", name])?;
    } else {
        let revision = crate::git::resolve_revision(root, base)?;
        let crate::model::Revision::Commit(sha) = revision else {
            bail!("新分支起点必须是提交/分支/标签");
        };
        git(root, &["switch", "-c", name, &sha])?;
    }
    Ok(format!("已创建并切换到 {name}"))
}
