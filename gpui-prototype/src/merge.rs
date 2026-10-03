//! Historical merge inspection; never reads or writes the worktree/index.
use crate::{
    git,
    model::{CommitDetail, Comparison, Diff, FileChange, Revision},
    text::Document,
};
use anyhow::{Result, bail};
use std::{collections::BTreeMap, ops::Range, path::Path, sync::Arc};

#[derive(Clone, Debug)]
pub struct File {
    pub path: String,
    pub parent_paths: [String; 2],
}
#[derive(Clone, Debug)]
pub struct Selection {
    pub detail: CommitDetail,
    pub files: Vec<File>,
}
/// Union both parent comparisons: a first-parent-only list hides files inherited
/// unchanged from parent 1 but changed relative to parent 2.
pub fn selection(root: &Path, sha: &str) -> Result<Selection> {
    let detail = git::commit_detail(root, sha)?;
    if detail.parents.len() != 2 {
        bail!(
            "三栏历史查看需要恰好两个父提交；当前提交有 {} 个父提交",
            detail.parents.len()
        );
    }
    let mut files: BTreeMap<String, [Option<String>; 2]> = BTreeMap::new();
    for (side, parent) in detail.parents.iter().enumerate() {
        let pair = git::comparison_selection(
            root,
            &Comparison {
                left: Revision::Commit(parent.clone()),
                right: Revision::Commit(detail.sha.clone()),
            },
        )?;
        for file in pair.files {
            files.entry(file.path.clone()).or_default()[side] = Some(file.old_path);
        }
    }
    let files = files
        .into_iter()
        .map(|(path, parents)| File {
            parent_paths: parents.map(|p| p.unwrap_or_else(|| path.clone())),
            path,
        })
        .collect();
    Ok(Selection { detail, files })
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Row {
    /// One-based source line numbers; None means alignment padding.
    pub lines: [Option<usize>; 3],
    pub changed: [bool; 3],
}
#[derive(Clone, Debug)]
pub struct View {
    pub revisions: [String; 3],
    pub paths: [String; 3],
    pub documents: [Document; 3],
    pub syntax: [crate::syntax::Highlighted; 3],
    pub rows: Arc<Vec<Row>>,
    pub blocks: Vec<Range<usize>>,
    pub message: Option<String>,
}
fn revision(root: &Path, sha: &str, path: &str) -> Result<Revision> {
    git::validate_paths(&[path.into()])?;
    if git::git(root, &["ls-tree", "-z", sha, "--", path])?.is_empty() {
        Ok(Revision::Empty)
    } else {
        Ok(Revision::Commit(sha.into()))
    }
}
pub fn load(root: &Path, selection: &Selection, file: &File, limit: usize) -> Result<View> {
    if selection.detail.parents.len() != 2 {
        bail!("三栏历史查看需要恰好两个父提交");
    }
    let revisions = [
        selection.detail.parents[0].clone(),
        selection.detail.sha.clone(),
        selection.detail.parents[1].clone(),
    ];
    let paths = [
        file.parent_paths[0].clone(),
        file.path.clone(),
        file.parent_paths[1].clone(),
    ];
    let result = revision(root, &revisions[1], &paths[1])?;
    let limit = limit.min(20_000_000);
    let pair = |side: usize| {
        git::compare_with_limit(
            root,
            &Comparison {
                left: revision(root, &revisions[side], &paths[side])?,
                right: result.clone(),
            },
            &FileChange {
                old_path: paths[side].clone(),
                path: paths[1].clone(),
                status: "M".into(),
            },
            limit,
        )
    };
    let left = pair(0)?;
    let right = pair(2)?;
    let mut view = align(&left, &right)?;
    view.revisions = revisions;
    view.paths = paths;
    if view.documents.iter().map(|d| d.text.len()).sum::<usize>() > limit {
        view.documents = Default::default();
        view.syntax = Default::default();
        view.rows = Default::default();
        view.blocks.clear();
        view.message = Some(format!(
            "三侧内容合计超过 {} MB 预览上限",
            limit / 1_000_000
        ));
    }
    if view.message.is_none() {
        view.syntax = std::array::from_fn(|side| {
            crate::syntax::highlight(&view.documents[side], &view.paths[side])
        });
    }
    Ok(view)
}
struct Projection {
    lines: Vec<Option<usize>>,
    changed: Vec<bool>,
    gaps: Vec<Vec<usize>>,
}
fn project(diff: &Diff) -> Result<Projection> {
    let count = diff.right_document.lines.len();
    let mut projection = Projection {
        lines: vec![None; count],
        changed: vec![false; count],
        gaps: vec![vec![]; count + 1],
    };
    let mut consumed = 0;
    for row in diff.rows.iter() {
        crate::process::check()?;
        if let Some(result) = row.right_no {
            if result != consumed + 1 || result > count {
                bail!("合并结果行映射无效");
            }
            projection.lines[result - 1] = row.left_no;
            projection.changed[result - 1] = row.changed;
            consumed = result;
        } else if let Some(parent) = row.left_no {
            projection.gaps[consumed].push(parent);
        }
    }
    if consumed != count {
        bail!("合并结果行映射不完整");
    }
    Ok(projection)
}
/// Join both pairwise alignments on the result's source lines. Parent-only
/// deletion groups occupy shared gaps before/between/after result lines.
pub fn align(left: &Diff, right: &Diff) -> Result<View> {
    let message = match (&left.message, &right.message) {
        (Some(l), Some(r)) => Some(format!("父提交 1：{l}\n父提交 2：{r}")),
        (Some(l), _) => Some(format!("父提交 1：{l}")),
        (_, Some(r)) => Some(format!("父提交 2：{r}")),
        _ => None,
    };
    let mut view = View {
        revisions: Default::default(),
        paths: Default::default(),
        documents: Default::default(),
        syntax: Default::default(),
        rows: Default::default(),
        blocks: vec![],
        message,
    };
    if view.message.is_some() {
        return Ok(view);
    }
    if left.right_document.text != right.right_document.text {
        bail!("两侧比较的合并结果不一致");
    }
    let l = project(left)?;
    let r = project(right)?;
    let count = left.right_document.lines.len();
    let mut rows = vec![];
    for gap in 0..=count {
        crate::process::check()?;
        for i in 0..l.gaps[gap].len().max(r.gaps[gap].len()) {
            let lines = [
                l.gaps[gap].get(i).copied(),
                None,
                r.gaps[gap].get(i).copied(),
            ];
            rows.push(Row {
                changed: [lines[0].is_some(), false, lines[2].is_some()],
                lines,
            });
        }
        if gap < count {
            rows.push(Row {
                lines: [l.lines[gap], Some(gap + 1), r.lines[gap]],
                changed: [
                    l.changed[gap],
                    l.changed[gap] || r.changed[gap],
                    r.changed[gap],
                ],
            });
        }
    }
    let mut start = None;
    for (i, row) in rows.iter().enumerate() {
        if row.changed.iter().any(|c| *c) {
            start.get_or_insert(i);
        } else if let Some(start) = start.take() {
            view.blocks.push(start..i);
        }
    }
    if let Some(start) = start {
        view.blocks.push(start..rows.len());
    }
    view.documents = [
        left.left_document.clone(),
        left.right_document.clone(),
        right.left_document.clone(),
    ];
    view.rows = Arc::new(rows);
    Ok(view)
}

#[cfg(test)]
mod tests {
    use super::*;
    fn view(a: &str, result: &str, b: &str) -> View {
        align(
            &crate::diff::calculate(a.as_bytes(), result.as_bytes()).unwrap(),
            &crate::diff::calculate(b.as_bytes(), result.as_bytes()).unwrap(),
        )
        .unwrap()
    }
    fn assert_sources(view: &View) {
        for side in 0..3 {
            let lines: Vec<_> = view.rows.iter().filter_map(|r| r.lines[side]).collect();
            assert_eq!(
                lines,
                (1..=view.documents[side].lines.len()).collect::<Vec<_>>()
            );
            let raw: String = lines
                .iter()
                .map(|line| {
                    &view.documents[side].text[view.documents[side].lines[line - 1].clone()]
                })
                .collect();
            assert_eq!(raw, &*view.documents[side].text);
        }
    }
    #[test]
    fn alignment_preserves_each_source_through_asymmetric_gaps_and_replacements() {
        for (a, result, b) in [
            ("head\na\nb\ntail\n", "head\ntail\n", "head\nx\ntail\n"),
            ("a\nb\nc\n", "a\nnew\nc\n", "a\nc\n"),
            ("", "新增😀\r\n第二行", "旧行\r\n"),
            ("a\nb", "", "x\ny\nz\n"),
            (
                "before\nhead\ntail\nafter\n",
                "head\ntail\n",
                "head\ntail\n",
            ),
            ("", "", ""),
        ] {
            let view = view(a, result, b);
            assert_sources(&view);
            for block in &view.blocks {
                assert!(
                    view.rows[block.clone()]
                        .iter()
                        .all(|r| r.changed.iter().any(|c| *c))
                );
            }
        }
    }
    #[test]
    fn unchanged_result_lines_and_endings_have_correct_three_side_flags() {
        let changed = view("a\r\n", "a\n", "a\n");
        assert_eq!(changed.rows[0].changed, [true, true, false]);
        assert_sources(&changed);
        let same = view("a\n", "a\n", "a\n");
        assert_eq!(same.rows[0].changed, [false; 3]);
        assert!(same.blocks.is_empty());
    }
    #[test]
    fn every_combination_of_insertions_and_deletions_preserves_source_order() {
        let variants: Vec<_> = (0..8)
            .map(|mask| {
                ["pre\r\n", "中😀\n", "tail"]
                    .iter()
                    .enumerate()
                    .filter(|(bit, _)| mask & (1 << bit) != 0)
                    .map(|(_, text)| *text)
                    .collect::<String>()
            })
            .collect();
        for a in &variants {
            for result in &variants {
                for b in &variants {
                    assert_sources(&view(a, result, b));
                }
            }
        }
    }
    #[test]
    fn incompatible_result_or_notice_never_looks_like_empty_matching_text() {
        let left = crate::diff::calculate(b"a", b"b").unwrap();
        let right = crate::diff::calculate(b"a", b"c").unwrap();
        assert!(align(&left, &right).is_err());
        let notice = align(&Diff::notice("binary"), &left).unwrap();
        assert!(notice.rows.is_empty());
        assert!(notice.message.unwrap().contains("binary"));
    }
}
