//! Pinned history queries scan bounded pages, including commits not loaded by the UI.
use crate::{
    git::git,
    model::{Commit, Revision},
};
use anyhow::{Context, Result, bail};
use std::{collections::BTreeSet, path::Path};

#[derive(Clone, Debug)]
pub struct Filter {
    pub scope: String,
    pub text: String,
    pub author: String,
    pub since: String,
    pub until: String,
    pub path: Option<String>,
    pub follow: bool,
}
impl Default for Filter {
    fn default() -> Self {
        Self {
            scope: "HEAD".into(),
            text: String::new(),
            author: String::new(),
            since: String::new(),
            until: String::new(),
            path: None,
            follow: false,
        }
    }
}
#[derive(Clone, Debug)]
pub struct Query {
    pub tips: Vec<String>,
    pub text: String,
    pub author: String,
    pub since: String,
    pub until: String,
    pub path: Option<String>,
    pub follow: bool,
}
pub struct Page {
    pub commits: Vec<Commit>,
    pub next: usize,
    pub more: bool,
}
fn date(value: &str) -> Result<()> {
    if value.is_empty() {
        return Ok(());
    }
    if !value
        .bytes()
        .all(|byte| byte.is_ascii_digit() || byte == b'-')
    {
        bail!(crate::localized_format!(
            "日期请使用 YYYY-MM-DD",
            "Use YYYY-MM-DD for dates"
        ));
    }
    let parts: Vec<_> = value.split('-').collect();
    if parts.len() != 3 || parts[0].len() != 4 || parts[1].len() != 2 || parts[2].len() != 2 {
        bail!(crate::localized_format!(
            "日期请使用 YYYY-MM-DD",
            "Use YYYY-MM-DD for dates"
        ));
    }
    let year: u32 = parts[0].parse()?;
    let month: u32 = parts[1].parse()?;
    let day: u32 = parts[2].parse()?;
    let days = match month {
        1 | 3 | 5 | 7 | 8 | 10 | 12 => 31,
        4 | 6 | 9 | 11 => 30,
        2 if year.is_multiple_of(400) || (year.is_multiple_of(4) && !year.is_multiple_of(100)) => {
            29
        }
        2 => 28,
        _ => 0,
    };
    if year == 0 || day == 0 || day > days {
        bail!(crate::localized_format!("日期无效", "Invalid date"));
    }
    Ok(())
}
pub fn prepare(root: &Path, filter: Filter) -> Result<Query> {
    let Filter {
        scope,
        text,
        author,
        since,
        until,
        path,
        follow,
    } = filter;
    if text.len() > 4096 || author.len() > 4096 {
        bail!(crate::localized_format!(
            "搜索内容超过 4096 字节上限",
            "Search text exceeds the 4096-byte limit"
        ));
    }
    date(&since)?;
    date(&until)?;
    if !since.is_empty() && !until.is_empty() && since > until {
        bail!(crate::localized_format!(
            "开始日期不能晚于结束日期",
            "Start date cannot be after end date"
        ));
    }
    if let Some(path) = &path {
        crate::git::validate_paths(std::slice::from_ref(path))?;
    }
    let tips = if scope.trim() == "ALL" {
        let output = git(root, &["rev-parse", "--all"])?;
        let mut tips: BTreeSet<String> = std::str::from_utf8(&output)?
            .lines()
            .map(str::to_owned)
            .collect();
        if let Ok(Revision::Commit(sha)) = crate::git::resolve_revision(root, "HEAD") {
            tips.insert(sha);
        }
        tips.into_iter().collect()
    } else {
        match crate::git::resolve_revision(root, scope.trim())? {
            Revision::Commit(sha) => vec![sha],
            _ => bail!(crate::localized_format!(
                "历史范围必须是提交/分支/标签或 ALL",
                "History scope must be a commit, branch, tag or ALL"
            )),
        }
    };
    Ok(Query {
        tips,
        text: text.to_lowercase(),
        author,
        since,
        until,
        path,
        follow,
    })
}
pub fn page(root: &Path, query: &Query, mut offset: usize) -> Result<Page> {
    let mut commits = vec![];
    if query.tips.is_empty() {
        return Ok(Page {
            commits,
            next: offset,
            more: false,
        });
    }
    loop {
        crate::process::check()?;
        let mut arguments = vec![
            "log".to_owned(),
            "-512".into(),
            format!("--skip={offset}"),
            "-z".into(),
            "--format=%H%x00%B%x00%an%x00%aI%x00%P%x00%D".into(),
            "--topo-order".into(),
            "--fixed-strings".into(),
            "--regexp-ignore-case".into(),
        ];
        if !query.author.is_empty() {
            arguments.push(format!("--author={}", query.author));
        }
        if !query.since.is_empty() {
            arguments.push(format!("--since-as-filter={}T00:00:00", query.since));
        }
        if !query.until.is_empty() {
            arguments.push(format!("--until={}T23:59:59", query.until));
        }
        if query.follow && query.path.is_some() {
            arguments.push("--follow".into());
        }
        arguments.extend(query.tips.iter().cloned());
        arguments.push("--".into());
        if let Some(path) = &query.path {
            arguments.push(path.clone());
        }
        let borrowed: Vec<_> = arguments.iter().map(String::as_str).collect();
        let bytes = git(root, &borrowed)?;
        let text =
            std::str::from_utf8(&bytes).context(crate::i18n::text("历史包含非 UTF-8 文本"))?;
        if text.is_empty() {
            return Ok(Page {
                commits,
                next: offset,
                more: false,
            });
        }
        let fields: Vec<_> = text
            .strip_suffix('\0')
            .unwrap_or(text)
            .split('\0')
            .collect();
        if !fields.len().is_multiple_of(6) {
            bail!(crate::localized_format!(
                "历史记录格式无效",
                "Invalid history record format"
            ));
        }
        let count = fields.len() / 6;
        for record in fields.as_chunks::<6>().0 {
            let matches = query.text.is_empty()
                || record[0].to_lowercase().contains(&query.text)
                || record[1].to_lowercase().contains(&query.text)
                || record[2].to_lowercase().contains(&query.text);
            if matches {
                if commits.len() == 100 {
                    return Ok(Page {
                        commits,
                        next: offset,
                        more: true,
                    });
                }
                commits.push(Commit {
                    sha: record[0].into(),
                    subject: record[1].lines().next().unwrap_or("").into(),
                    author: record[2].into(),
                    date: record[3].into(),
                    parents: record[4].split_whitespace().map(String::from).collect(),
                    references: record[5].into(),
                });
            }
            offset += 1;
        }
        if count < 512 {
            return Ok(Page {
                commits,
                next: offset,
                more: false,
            });
        }
    }
}
