use std::{ops::Range, path::PathBuf};

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
}
impl BrowseMode {
    pub fn label(&self) -> &'static str {
        match self {
            Self::Workspace => "全部变更",
            Self::Staged => "已暂存",
            Self::Unstaged => "未暂存",
            Self::History(_) => "提交变更",
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
#[derive(Clone, Debug, Default)]
pub struct Diff {
    pub rows: Vec<DiffRow>,
    pub blocks: Vec<Range<usize>>,
    pub message: Option<String>,
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
        Self {
            rows,
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
