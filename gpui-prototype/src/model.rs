use std::{ops::Range, path::PathBuf, sync::Arc};

#[derive(Clone, Debug)]
pub struct Commit {
    pub parents: Vec<String>,
    pub references: String,
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
    pub references: std::collections::HashMap<String, String>,
    pub root: PathBuf,
    pub branch: String,
    pub detached: bool,
    pub commits: Vec<Commit>,
    pub history_tip: Option<String>,
    pub history_more: bool,
    pub branches: Vec<BranchRef>,
}

#[derive(Clone, Debug)]
pub struct BranchRef {
    pub reference: String,
    pub name: String,
    pub sha: String,
    pub current: bool,
    pub remote: bool,
    pub upstream: String,
    pub tracking: String,
    pub local_name: Option<String>,
}

#[derive(Clone, Debug)]
pub struct CommitDetail {
    pub sha: String,
    pub message: String,
    pub author: String,
    pub author_email: String,
    pub author_date: String,
    pub committer: String,
    pub committer_email: String,
    pub commit_date: String,
    pub references: String,
    pub parents: Vec<String>,
}
#[derive(Clone, Debug)]
pub struct HistoryPage {
    pub commits: Vec<Commit>,
    pub more: bool,
}

/// HEAD and historical commits are pinned to an object ID for the selected comparison.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Revision {
    Head(String),
    Index,
    Worktree,
    Commit(String),
    Empty,
}
impl Revision {
    pub fn label(&self) -> String {
        match self {
            Self::Head(sha) => format!("HEAD · {}", short_sha(sha)),
            Self::Commit(sha) => format!("提交 · {}", short_sha(sha)),
            Self::Index => "暂存区（index）".into(),
            Self::Worktree => "工作区（磁盘）".into(),
            Self::Empty => "空内容".into(),
        }
    }
}
pub fn short_sha(sha: &str) -> String {
    sha.chars().take(8).collect()
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum BrowseMode {
    Workspace,
    Staged,
    Unstaged,
    History(String),
    Compare(Comparison),
}
impl BrowseMode {
    pub fn label(&self) -> &'static str {
        match self {
            Self::Workspace => "全部变更",
            Self::Staged => "已暂存",
            Self::Unstaged => "未暂存",
            Self::History(_) => "提交变更",
            Self::Compare(_) => "自定义比较",
        }
    }
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Comparison {
    pub left: Revision,
    pub right: Revision,
}
#[derive(Clone, Debug)]
pub struct FileTarget {
    pub revision: Revision,
    pub path: String,
}
impl Comparison {
    pub fn targets(&self, file: &FileChange) -> (FileTarget, FileTarget) {
        let added = file.status.starts_with('A') || file.status == "??";
        let deleted = file.status.starts_with('D');
        (
            FileTarget {
                revision: if added {
                    Revision::Empty
                } else {
                    self.left.clone()
                },
                path: file.old_path.clone(),
            },
            FileTarget {
                revision: if deleted {
                    Revision::Empty
                } else {
                    self.right.clone()
                },
                path: file.path.clone(),
            },
        )
    }
}
#[derive(Clone, Debug)]
pub struct Selection {
    pub comparison: Comparison,
    pub files: Vec<FileChange>,
}
#[derive(Clone, Debug)]
pub struct DiffRow {
    pub left_no: Option<usize>,
    pub right_no: Option<usize>,
    pub left: String,
    pub right: String,
    pub changed: bool,
    /// UTF-8 byte ranges in the visible source line, on grapheme boundaries.
    pub left_inline: Vec<Range<usize>>,
    pub right_inline: Vec<Range<usize>>,
    pub left_ending: Option<&'static str>,
    pub right_ending: Option<&'static str>,
}
#[derive(Clone, Debug)]
pub struct UnifiedRow {
    pub row: usize,
    pub side: crate::text::Side,
}
#[derive(Clone, Debug, Default)]
pub struct Diff {
    pub rows: Arc<Vec<DiffRow>>,
    pub unified: Arc<Vec<UnifiedRow>>,
    pub blocks: Vec<Range<usize>>,
    pub message: Option<String>,
    pub description: Option<String>,
    pub left_document: crate::text::Document,
    pub right_document: crate::text::Document,
    pub left_syntax: crate::syntax::Highlighted,
    pub right_syntax: crate::syntax::Highlighted,
}
impl Diff {
    pub fn from_rows(rows: Vec<DiffRow>) -> Self {
        let mut blocks = Vec::new();
        let mut start = None;
        for (index, row) in rows.iter().enumerate() {
            if row.changed {
                start.get_or_insert(index);
            } else if let Some(start) = start.take() {
                blocks.push(start..index);
            }
        }
        if let Some(start) = start {
            blocks.push(start..rows.len());
        }
        let mut unified = vec![];
        let mut i = 0;
        while i < rows.len() {
            if rows[i].changed {
                let start = i;
                while i < rows.len() && rows[i].changed {
                    i += 1;
                }
                for side in [crate::text::Side::Left, crate::text::Side::Right] {
                    for (row, item) in rows.iter().enumerate().take(i).skip(start) {
                        if match side {
                            crate::text::Side::Left => item.left_no.is_some(),
                            crate::text::Side::Right => item.right_no.is_some(),
                        } {
                            unified.push(UnifiedRow { row, side });
                        }
                    }
                }
            } else {
                unified.push(UnifiedRow {
                    row: i,
                    side: crate::text::Side::Right,
                });
                i += 1;
            }
        }
        Self {
            rows: Arc::new(rows),
            unified: Arc::new(unified),
            blocks,
            message: None,
            ..Self::default()
        }
    }
    pub fn notice(message: &str) -> Self {
        Self {
            message: Some(message.into()),
            ..Self::default()
        }
    }
    pub fn document(&self, side: crate::text::Side) -> &crate::text::Document {
        match side {
            crate::text::Side::Left => &self.left_document,
            crate::text::Side::Right => &self.right_document,
        }
    }
    pub fn syntax(&self, side: crate::text::Side) -> &crate::syntax::Highlighted {
        match side {
            crate::text::Side::Left => &self.left_syntax,
            crate::text::Side::Right => &self.right_syntax,
        }
    }
    pub fn source_line(&self, side: crate::text::Side, row: usize) -> Option<usize> {
        self.rows
            .get(row)
            .and_then(|r| match side {
                crate::text::Side::Left => r.left_no,
                crate::text::Side::Right => r.right_no,
            })
            .map(|n| n - 1)
    }
    pub fn padding_offset(&self, side: crate::text::Side, row: usize) -> usize {
        (row..self.rows.len())
            .find_map(|i| self.source_line(side, i))
            .map(|i| self.document(side).display_range(i).start)
            .unwrap_or(self.document(side).text.len())
    }
    pub fn row_for_offset(&self, side: crate::text::Side, offset: usize) -> usize {
        let line = self.document(side).line_index(offset);
        self.rows
            .iter()
            .enumerate()
            .find(|(i, _)| self.source_line(side, *i) == Some(line))
            .map(|(i, _)| i)
            .unwrap_or(0)
    }
    pub fn panel_width(&self) -> f32 {
        fn width(text: &str) -> usize {
            text.chars()
                .map(|c| {
                    if c == '\t' {
                        4
                    } else if c.is_ascii() {
                        1
                    } else {
                        2
                    }
                })
                .sum()
        }
        self.rows
            .iter()
            .map(|r| width(&r.left).max(width(&r.right)))
            .max()
            .unwrap_or(0)
            .saturating_mul(8)
            .saturating_add(68)
            .max(420) as f32
    }
}

#[derive(Clone, Debug)]
pub struct FileTab {
    pub file: FileChange,
    pub comparison: Comparison,
    pub editable: bool,
    pub detail: Option<CommitDetail>,
    pub diff: Diff,
    pub selection: crate::text::TextSelection,
    pub horizontal: f32,
    pub block: Option<usize>,
}
