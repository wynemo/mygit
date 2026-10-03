use crate::model::{Diff, DiffRow};
use anyhow::{Context, Result};

pub fn calculate(left: &[u8], right: &[u8]) -> Result<Diff> {
    if left.contains(&0) || right.contains(&0) {
        return Ok(Diff::notice("二进制文件：暂不提供内容预览"));
    }
    if left.len() + right.len() > 2_000_000 {
        return Ok(Diff::notice("文件超过原型的 2 MB 预览上限"));
    }
    let left = std::str::from_utf8(left).context("旧版本不是 UTF-8 文本")?;
    let right = std::str::from_utf8(right).context("新版本不是 UTF-8 文本")?;
    Ok(Diff::from_rows(align(left, right)))
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
    fn replacement_alignment_and_distinct_blocks() {
        let diff = calculate(b"a\nb\nc\nd\ne\n", b"a\nx\ny\nc\nd\nz\n").unwrap();
        assert_eq!(
            (&diff.rows[1].left[..], &diff.rows[1].right[..]),
            ("b", "x")
        );
        assert_eq!(
            (diff.rows[2].left_no, diff.rows[2].right_no),
            (None, Some(3))
        );
        assert_eq!(
            (diff.rows[3].left_no, diff.rows[3].right_no),
            (Some(3), Some(4))
        );
        assert_eq!(diff.blocks, vec![1..3, 5..6]);
    }
    #[test]
    fn insertion_deletion_and_unchanged() {
        let inserted = calculate(b"", "中文\n\n".as_bytes()).unwrap();
        assert_eq!(inserted.blocks, vec![0..2]);
        assert!(inserted.rows.iter().all(|r| r.left_no.is_none()));
        let deleted = calculate(b"a\n\nb\n", b"").unwrap();
        assert_eq!(deleted.blocks, vec![0..3]);
        assert!(deleted.rows.iter().all(|r| r.right_no.is_none()));
        assert!(calculate(b"same\n", b"same\n").unwrap().blocks.is_empty());
    }
}
