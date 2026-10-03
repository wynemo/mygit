//! Original text and byte-based selection, independent of the aligned Diff rows.
use std::{ops::Range, sync::Arc};
use unicode_segmentation::UnicodeSegmentation;

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Hash)]
pub enum Side {
    Left,
    Third,
    #[default]
    Right,
}
#[derive(Clone, Debug)]
pub struct Document {
    pub text: Arc<str>,
    pub lines: Arc<Vec<Range<usize>>>,
    boundaries: Arc<Vec<usize>>,
}
impl Default for Document {
    fn default() -> Self {
        Self::new("")
    }
}
impl Document {
    pub fn new(text: &str) -> Self {
        let mut start = 0;
        let lines = text
            .split_inclusive('\n')
            .map(|line| {
                let range = start..start + line.len();
                start += line.len();
                range
            })
            .collect();
        let mut boundaries: Vec<usize> = text.grapheme_indices(true).map(|(i, _)| i).collect();
        boundaries.push(text.len());
        Self {
            text: text.into(),
            lines: Arc::new(lines),
            boundaries: Arc::new(boundaries),
        }
    }
    pub fn display_range(&self, index: usize) -> Range<usize> {
        let Some(range) = self.lines.get(index) else {
            return self.text.len()..self.text.len();
        };
        let mut end = range.end;
        if self.text[..end].ends_with('\n') {
            end -= 1;
            if self.text[..end].ends_with('\r') {
                end -= 1;
            }
        }
        range.start..end
    }
    pub fn line_index(&self, offset: usize) -> usize {
        self.lines
            .partition_point(|line| line.start <= offset)
            .saturating_sub(1)
    }
    pub fn snap(&self, offset: usize) -> usize {
        let offset = offset.min(self.text.len());
        self.boundaries[self
            .boundaries
            .partition_point(|b| *b <= offset)
            .saturating_sub(1)]
    }
    pub fn previous(&self, offset: usize) -> usize {
        self.boundaries[self
            .boundaries
            .partition_point(|b| *b < offset)
            .saturating_sub(1)]
    }
    pub fn next(&self, offset: usize) -> usize {
        self.boundaries
            .get(self.boundaries.partition_point(|b| *b <= offset))
            .copied()
            .unwrap_or(self.text.len())
    }
    pub fn vertical(&self, offset: usize, down: bool) -> usize {
        if self.lines.is_empty() {
            return 0;
        }
        let index = self.line_index(offset);
        let range = self.display_range(index);
        let column = self.text[range.start..offset.min(range.end)]
            .graphemes(true)
            .count();
        let target = if down {
            (index + 1).min(self.lines.len() - 1)
        } else {
            index.saturating_sub(1)
        };
        let range = self.display_range(target);
        self.text[range.clone()]
            .grapheme_indices(true)
            .nth(column)
            .map(|(i, _)| range.start + i)
            .unwrap_or(range.end)
    }
}
#[derive(Clone, Debug, Default)]
pub struct TextSelection {
    pub side: Side,
    pub anchor: usize,
    pub head: usize,
}
#[derive(Clone, Copy, Debug)]
pub enum Motion {
    Left,
    Right,
    Up,
    Down,
    Home,
    End,
    Start,
    Finish,
}
impl TextSelection {
    pub fn range(&self) -> Range<usize> {
        self.anchor.min(self.head)..self.anchor.max(self.head)
    }
    pub fn point(&mut self, side: Side, offset: usize, extend: bool, document: &Document) {
        let offset = document.snap(offset);
        if !extend || self.side != side {
            self.anchor = offset;
        }
        self.side = side;
        self.head = offset;
    }
    pub fn select_all(&mut self, document: &Document) {
        self.anchor = 0;
        self.head = document.text.len();
    }
    pub fn copy(&self, document: &Document) -> Option<String> {
        let range = self.range();
        (!range.is_empty()).then(|| document.text[range].to_string())
    }
    pub fn move_cursor(&mut self, document: &Document, motion: Motion, extend: bool) {
        let range = self.range();
        let offset = match motion {
            Motion::Left if !extend && !range.is_empty() => range.start,
            Motion::Right if !extend && !range.is_empty() => range.end,
            Motion::Left => document.previous(self.head),
            Motion::Right => document.next(self.head),
            Motion::Up => document.vertical(self.head, false),
            Motion::Down => document.vertical(self.head, true),
            Motion::Home => document.display_range(document.line_index(self.head)).start,
            Motion::End => document.display_range(document.line_index(self.head)).end,
            Motion::Start => 0,
            Motion::Finish => document.text.len(),
        };
        self.point(self.side, offset, extend, document);
    }
}
/// Tabs are expanded only for painting. Both maps preserve original byte offsets.
#[derive(Clone, Debug)]
pub struct DisplayLine {
    pub text: String,
    to_source: Vec<usize>,
    to_display: Vec<usize>,
}
impl DisplayLine {
    pub fn new(source: &str) -> Self {
        let mut text = String::new();
        let mut to_source = vec![0];
        let mut to_display = vec![0; source.len() + 1];
        for (index, c) in source.char_indices() {
            let display_start = text.len();
            if c == '\t' {
                text.push_str("    ");
                to_source.extend([index, index, index + 1, index + 1]);
            } else {
                text.push(c);
                for _ in 1..c.len_utf8() {
                    to_source.push(index);
                }
                to_source.push(index + c.len_utf8());
            }
            for slot in &mut to_display[index..index + c.len_utf8()] {
                *slot = display_start;
            }
            to_display[index + c.len_utf8()] = text.len();
        }
        Self {
            text,
            to_source,
            to_display,
        }
    }
    pub fn source_offset(&self, display: usize) -> usize {
        self.to_source[display.min(self.text.len())]
    }
    pub fn display_offset(&self, source: usize) -> usize {
        self.to_display[source.min(self.to_display.len() - 1)]
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn copy_preserves_tabs_crlf_blank_lines_and_direction() {
        let document = Document::new("a\t中文\r\n\r\nz🙂\n");
        let mut selection = TextSelection::default();
        selection.select_all(&document);
        assert_eq!(selection.copy(&document).unwrap(), &*document.text);
        selection.anchor = document.text.len();
        selection.head = 0;
        assert_eq!(selection.copy(&document).unwrap(), &*document.text);
        assert_eq!(&document.text[document.display_range(0)], "a\t中文");
    }
    #[test]
    fn movement_preserves_graphemes_and_extends_selection() {
        let document = Document::new("中e\u{301}👩‍💻\r\nx\n");
        let mut selection = TextSelection::default();
        selection.move_cursor(&document, Motion::Right, true);
        assert_eq!(selection.copy(&document).unwrap(), "中");
        selection.move_cursor(&document, Motion::Right, true);
        assert_eq!(selection.copy(&document).unwrap(), "中e\u{301}");
        selection.move_cursor(&document, Motion::Right, true);
        assert_eq!(selection.copy(&document).unwrap(), "中e\u{301}👩‍💻");
        selection.move_cursor(&document, Motion::Right, true);
        assert!(selection.copy(&document).unwrap().ends_with("\r\n"));
        selection.move_cursor(&document, Motion::Left, false);
        assert_eq!(selection.head, 0);
        assert_eq!(selection.anchor, 0);
    }
    #[test]
    fn display_map_roundtrips_tabs_and_unicode() {
        let source = "\t中🙂x";
        let display = DisplayLine::new(source);
        assert_eq!(display.text, "    中🙂x");
        for (i, _) in source
            .char_indices()
            .chain(std::iter::once((source.len(), '\0')))
        {
            assert_eq!(display.source_offset(display.display_offset(i)), i);
        }
    }
    #[test]
    fn vertical_selection_and_empty_documents() {
        let document = Document::new("中文ab\nx\nlast");
        let mut selection = TextSelection::default();
        selection.point(Side::Left, "中文".len(), false, &document);
        selection.move_cursor(&document, Motion::Down, true);
        assert_eq!(selection.copy(&document).unwrap(), "ab\nx");
        let empty = Document::default();
        selection = TextSelection::default();
        selection.select_all(&empty);
        assert_eq!(selection.copy(&empty), None);
        selection.move_cursor(&empty, Motion::Down, false);
        assert_eq!(selection.head, 0);
    }
    #[test]
    fn aligned_padding_is_never_copied() {
        let diff = crate::diff::calculate(b"a\nb\nc\n", b"a\nx\ny\nc\n").unwrap();
        assert_eq!(diff.source_line(Side::Left, 2), None);
        assert_eq!(diff.padding_offset(Side::Left, 2), 4);
        let mut selection = TextSelection {
            side: Side::Left,
            ..TextSelection::default()
        };
        selection.select_all(diff.document(Side::Left));
        assert_eq!(
            selection.copy(diff.document(Side::Left)).unwrap(),
            "a\nb\nc\n"
        );
        assert_eq!(diff.row_for_offset(Side::Left, 4), 3);
    }
}
