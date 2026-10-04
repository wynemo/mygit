use crate::model::{Diff, DiffRow};
use anyhow::{Context, Result};

pub fn calculate(left: &[u8], right: &[u8]) -> Result<Diff> {
    calculate_with_limit(left, right, 2_000_000)
}
pub fn calculate_with_limit(left: &[u8], right: &[u8], limit: usize) -> Result<Diff> {
    crate::process::check()?;
    if left.contains(&0) || right.contains(&0) {
        return Ok(Diff::notice(crate::i18n::text(
            "二进制文件：暂不提供内容预览",
        )));
    }
    if left.len() + right.len() > limit {
        let mut diff = Diff::notice(&crate::localized_format!(
            "文件超过 {} MB 预览上限",
            "File exceeds the {} MB preview limit",
            limit / 1_000_000
        ));
        diff.can_expand_preview = limit < 20_000_000;
        return Ok(diff);
    }
    if left
        .iter()
        .chain(right)
        .filter(|byte| **byte == b'\n')
        .count()
        > 200_000
    {
        return Ok(Diff::notice(crate::i18n::text(
            "文本超过 200000 行预览上限，暂不支持分段预览",
        )));
    }
    let left = std::str::from_utf8(left).context(crate::i18n::text("旧版本不是 UTF-8 文本"))?;
    let right = std::str::from_utf8(right).context(crate::i18n::text("新版本不是 UTF-8 文本"))?;
    let mut diff = Diff::from_rows(align(left, right));
    diff.left_document = crate::text::Document::new(left);
    diff.right_document = crate::text::Document::new(right);
    annotate(&mut diff);
    Ok(diff)
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
                left_inline: vec![],
                right_inline: vec![],
                left_ending: None,
                right_ending: None,
            });
        }
        deleted.clear();
        inserted.clear();
    }
    for change in TextDiff::configure()
        .timeout(std::time::Duration::from_millis(200))
        .diff_lines(left, right)
        .iter_all_changes()
    {
        let raw = change.value();
        let text = raw
            .strip_suffix("\r\n")
            .or_else(|| raw.strip_suffix('\n'))
            .unwrap_or(raw)
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
                    left_inline: vec![],
                    right_inline: vec![],
                    left_ending: None,
                    right_ending: None,
                });
                l += 1;
                r += 1;
            }
        }
    }
    flush(&mut rows, &mut deleted, &mut inserted);
    rows
}
fn ending(document: &crate::text::Document, no: usize) -> &'static str {
    let text = &document.text[document.lines[no - 1].clone()];
    if text.ends_with("\r\n") {
        "CRLF"
    } else if text.ends_with('\n') {
        "LF"
    } else {
        "无末尾换行"
    }
}

fn annotate(diff: &mut Diff) {
    let deadline = std::time::Instant::now() + std::time::Duration::from_millis(150);
    for row in std::sync::Arc::make_mut(&mut diff.rows) {
        if !row.changed {
            continue;
        }
        match (row.left_no, row.right_no) {
            (Some(l), Some(r)) => {
                if crate::process::check().is_err() {
                    break;
                }
                if std::time::Instant::now() < deadline {
                    (row.left_inline, row.right_inline) = inline(&row.left, &row.right);
                } else {
                    row.left_inline = std::iter::once(0..row.left.len())
                        .filter(|r| !r.is_empty())
                        .collect();
                    row.right_inline = std::iter::once(0..row.right.len())
                        .filter(|r| !r.is_empty())
                        .collect();
                }
                let le = ending(&diff.left_document, l);
                let re = ending(&diff.right_document, r);
                if le != re {
                    row.left_ending = Some(le);
                    row.right_ending = Some(re);
                }
            }
            (Some(l), None) => {
                row.left_inline = if row.left.is_empty() {
                    vec![]
                } else {
                    std::iter::once(0..row.left.len()).collect()
                };
                if ending(&diff.left_document, l) == "无末尾换行" {
                    row.left_ending = Some("无末尾换行");
                }
            }
            (None, Some(r)) => {
                row.right_inline = if row.right.is_empty() {
                    vec![]
                } else {
                    std::iter::once(0..row.right.len()).collect()
                };
                if ending(&diff.right_document, r) == "无末尾换行" {
                    row.right_ending = Some("无末尾换行");
                }
            }
            _ => {}
        }
    }
}

fn inline(left: &str, right: &str) -> (Vec<std::ops::Range<usize>>, Vec<std::ops::Range<usize>>) {
    use similar::{Algorithm, DiffTag, capture_diff_slices_deadline};
    use unicode_segmentation::UnicodeSegmentation;
    let l: Vec<&str> = left.graphemes(true).collect();
    let r: Vec<&str> = right.graphemes(true).collect();
    let offsets = |parts: &[&str]| {
        let mut result = vec![0];
        for part in parts {
            result.push(result.last().unwrap() + part.len());
        }
        result
    };
    let lo = offsets(&l);
    let ro = offsets(&r);
    let mut lr = vec![];
    let mut rr = vec![];
    // Large/pathological lines remain bounded; the fallback still marks changed spans.
    for op in capture_diff_slices_deadline(
        Algorithm::Myers,
        &l,
        &r,
        Some(std::time::Instant::now() + std::time::Duration::from_millis(5)),
    ) {
        let (tag, a, b) = op.as_tag_tuple();
        if tag == DiffTag::Equal {
            continue;
        }
        if !a.is_empty() {
            lr.push(lo[a.start]..lo[a.end]);
        }
        if !b.is_empty() {
            rr.push(ro[b.start]..ro[b.end]);
        }
    }
    (lr, rr)
}

pub fn highlight(diff: &mut Diff, left_path: &str, right_path: &str) {
    diff.left_syntax = crate::syntax::highlight(&diff.left_document, left_path);
    diff.right_syntax = crate::syntax::highlight(&diff.right_document, right_path);
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
    #[test]
    fn inline_preserves_graphemes_and_spaces() {
        let d = calculate("前 é 👩‍💻 后\n".as_bytes(), "前 è 👨‍💻  后\n".as_bytes()).unwrap();
        let row = &d.rows[0];
        let left: Vec<_> = row
            .left_inline
            .iter()
            .map(|r| &row.left[r.clone()])
            .collect();
        let right: Vec<_> = row
            .right_inline
            .iter()
            .map(|r| &row.right[r.clone()])
            .collect();
        assert_eq!(left, ["é", "👩‍💻"]);
        assert_eq!(right, ["è 👨‍💻"]);
        assert!(row.left_ending.is_none());
    }
    #[test]
    fn line_endings_and_eof_are_visible_without_changing_text() {
        let d = calculate(b"same\r\nlast\n", b"same\nlast").unwrap();
        assert_eq!(d.blocks, std::iter::once(0..2).collect::<Vec<_>>());
        assert_eq!(
            (d.rows[0].left_ending, d.rows[0].right_ending),
            (Some("CRLF"), Some("LF"))
        );
        assert_eq!(
            (d.rows[1].left_ending, d.rows[1].right_ending),
            (Some("LF"), Some("无末尾换行"))
        );
        assert!(
            d.rows
                .iter()
                .all(|r| r.left_inline.is_empty() && r.right_inline.is_empty())
        );
        assert_eq!(&*d.left_document.text, "same\r\nlast\n");
        let cr = calculate(b"a\r", b"b\r").unwrap();
        assert_eq!(cr.rows[0].left, "a\r");
        assert_eq!(cr.left_document.display_range(0), 0..2);
    }
    #[test]
    fn repeated_lines_empty_lines_and_unpaired_rows_keep_mapping() {
        let d = calculate(b"repeat\n\nrepeat\nx\n", b"repeat\n\nrepeat\ny\nz\n").unwrap();
        assert!(!d.rows[1].changed);
        assert_eq!((d.rows[3].left_no, d.rows[3].right_no), (Some(4), Some(4)));
        assert_eq!(
            d.rows[3].left_inline,
            std::iter::once(0..1).collect::<Vec<_>>()
        );
        assert_eq!(
            d.rows[4].right_inline,
            std::iter::once(0..1).collect::<Vec<_>>()
        );
        assert!(d.rows[4].left_inline.is_empty());
        let empty = calculate(b"\n", b" \n").unwrap();
        assert!(empty.rows[0].left_inline.is_empty());
        assert_eq!(
            empty.rows[0].right_inline,
            std::iter::once(0..1).collect::<Vec<_>>()
        );
    }
    #[test]
    fn separated_edits_do_not_mark_unchanged_middle() {
        let (l, r) = inline("abc foo xyz", "aBc foo xYz");
        assert_eq!(l, [1..2, 9..10]);
        assert_eq!(r, [1..2, 9..10]);
        let tabs = calculate(b"a\tb\n", b"a  b\n").unwrap();
        assert_eq!(
            tabs.rows[0].left_inline,
            std::iter::once(1..2).collect::<Vec<_>>()
        );
        assert_eq!(
            tabs.rows[0].right_inline,
            std::iter::once(1..3).collect::<Vec<_>>()
        );
    }
    #[test]
    fn unified_rows_keep_source_mapping_and_group_deleted_before_inserted() {
        use crate::text::Side;
        let d = calculate(b"same\nold1\nold2\nend\n", b"same\nnew1\nnew2\nend\n").unwrap();
        let rows: Vec<_> = d.unified.iter().map(|r| (r.row, r.side)).collect();
        assert_eq!(
            rows,
            [
                (0, Side::Right),
                (1, Side::Left),
                (2, Side::Left),
                (1, Side::Right),
                (2, Side::Right),
                (3, Side::Right)
            ]
        );
        let state = crate::state::AppState {
            diff: d,
            unified: true,
            ..Default::default()
        };
        assert_eq!(state.view_row(2, Side::Right), 4);
        assert_eq!(state.view_count(), 6);
    }
}
