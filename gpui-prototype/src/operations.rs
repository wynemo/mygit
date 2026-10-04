//! Network, merge and reset operations retain Git credentials/configuration and protections.
use crate::{
    git::{git, git_timeout},
    model::Revision,
};
use anyhow::{Context, Result, bail};
use std::{path::Path, time::Duration};
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RemoteOperation {
    Fetch,
    Pull,
    Push,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ResetMode {
    Soft,
    Mixed,
    Hard,
}
impl ResetMode {
    pub fn argument(self) -> &'static str {
        match self {
            Self::Soft => "--soft",
            Self::Mixed => "--mixed",
            Self::Hard => "--hard",
        }
    }
    pub fn description(self) -> &'static str {
        match self {
            Self::Soft => crate::i18n::text("soft：移动 HEAD，保留暂存区及工作区内容。"),
            Self::Mixed => crate::i18n::text("mixed：移动 HEAD 并重置暂存区，保留工作区磁盘内容。"),
            Self::Hard => crate::i18n::text(
                "hard：移动 HEAD、重置暂存区及工作区；丢弃未提交的 tracked 修改，并可能删除妨碍检出的未跟踪文件。未提交内容无法用 Git reflog 恢复。",
            ),
        }
    }
}
pub fn remote(root: &Path, operation: RemoteOperation, name: &str) -> Result<String> {
    let remotes = git(root, &["remote"])?;
    if !std::str::from_utf8(&remotes)?
        .lines()
        .any(|remote| remote == name)
    {
        bail!(crate::localized_format!(
            "远程 {name} 不存在，请检查仓库配置",
            "Remote {name} does not exist; check repository configuration"
        ));
    }
    let mut arguments = match operation {
        RemoteOperation::Fetch => vec!["fetch", "--progress", "--", name],
        RemoteOperation::Pull => vec!["pull", "--progress", "--no-edit", "--", name],
        RemoteOperation::Push => vec!["push", "--progress", "--", name],
    };
    let branches = crate::branches::list(root)?;
    let branch = branches.iter().find(|branch| branch.current);
    let refspec;
    if operation != RemoteOperation::Fetch {
        let branch = branch.context(crate::i18n::text(
            "当前没有已提交的本地分支，detached HEAD/空仓库不能 Pull 或 Push",
        ))?;
        if operation == RemoteOperation::Push && branch.upstream.is_empty() {
            refspec = format!("{}:{}", branch.reference, branch.reference);
            arguments = vec!["push", "--progress", "--set-upstream", "--", name, &refspec];
        }
    }
    let output = git_timeout(root, &arguments, Duration::from_secs(600))?;
    let verb = match operation {
        RemoteOperation::Fetch => "Fetch",
        RemoteOperation::Pull => "Pull",
        RemoteOperation::Push => "Push",
    };
    Ok(crate::localized_format!(
        "{verb} 完成 · {name}\n{}",
        "{verb} complete · {name}\n{}",
        String::from_utf8_lossy(&output).trim()
    ))
}
pub fn merge(root: &Path, reference: &str) -> Result<String> {
    let branch = crate::branches::list(root)?
        .into_iter()
        .find(|branch| branch.reference == reference)
        .context(crate::i18n::text("合并目标分支已不存在，请刷新"))?;
    let output = git_timeout(
        root,
        &["merge", "--no-edit", "--", &branch.reference],
        Duration::from_secs(120),
    )?;
    Ok(crate::localized_format!(
        "合并完成 · {}\n{}",
        "Merge complete · {}\n{}",
        branch.name,
        String::from_utf8_lossy(&output).trim()
    ))
}
pub fn reset_target(root: &Path, target: &str) -> Result<String> {
    match crate::git::resolve_revision(root, target)? {
        Revision::Commit(sha) => Ok(sha),
        _ => bail!(crate::localized_format!(
            "Reset 目标必须是提交/分支/标签",
            "Reset target must be a commit, branch or tag"
        )),
    }
}
pub fn reset(
    root: &Path,
    sha: &str,
    mode: ResetMode,
    expected_head: Option<&str>,
    expected_branch: Option<&str>,
) -> Result<String> {
    let snapshot = crate::git::snapshot(root)?;
    let current_branch = (!snapshot.detached).then_some(snapshot.branch.as_str());
    if snapshot.history_tip.as_deref() != expected_head || current_branch != expected_branch {
        bail!(crate::localized_format!(
            "HEAD 或当前分支在确认后改变，请重新选择 Reset 目标",
            "HEAD or the current branch changed after confirmation; select the reset target again"
        ));
    }
    let target = reset_target(root, sha)?;
    let output = git_timeout(
        root,
        &["reset", mode.argument(), &target, "--"],
        Duration::from_secs(120),
    )?;
    Ok(crate::localized_format!(
        "Reset 完成 · {} · {}\n{}",
        "Reset complete · {} · {}\n{}",
        mode.argument(),
        crate::model::short_sha(&target),
        String::from_utf8_lossy(&output).trim()
    ))
}
