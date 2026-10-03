//! Editable UTF-8 buffer, IME transactions, bounded undo and conflict-aware saving.
use crate::text::{Document, Motion, Side, TextSelection};
use anyhow::{Context, Result, bail};
use std::{
    fs,
    io::Write,
    ops::Range,
    path::{Path, PathBuf},
};
#[derive(Clone)]
struct Snapshot {
    document: Document,
    selection: TextSelection,
}
pub struct Buffer {
    pub document: Document,
    pub selection: TextSelection,
    pub marked: Option<Range<usize>>,
    pub path: Option<PathBuf>,
    pub crlf: bool,
    baseline: std::sync::Arc<str>,
    canonical: Option<PathBuf>,
    undo: Vec<Snapshot>,
    redo: Vec<Snapshot>,
    composition: Option<Snapshot>,
}
impl Buffer {
    pub fn new(text: &str) -> Self {
        Self {
            document: Document::new(text),
            selection: TextSelection::default(),
            marked: None,
            path: None,
            crlf: text.contains("\r\n"),
            baseline: text.into(),
            canonical: None,
            undo: vec![],
            redo: vec![],
            composition: None,
        }
    }
    pub fn load(path: &Path) -> Result<Self> {
        let bytes = disk(path)?;
        if bytes.len() > 2_000_000 {
            bail!("编辑文件超过 2 MB 上限");
        }
        if bytes.contains(&0) {
            bail!("二进制文件不可编辑");
        }
        let text = std::str::from_utf8(&bytes).context("编辑仅支持 UTF-8 文本")?;
        let mut buffer = Self::new(text);
        buffer.path = Some(path.into());
        buffer.canonical = Some(path.canonicalize()?);
        Ok(buffer)
    }
    pub fn dirty(&self) -> bool {
        self.document.text.as_ref() != self.baseline.as_ref()
    }
    pub fn can_undo(&self) -> bool {
        !self.undo.is_empty() || self.composition.is_some()
    }
    pub fn can_redo(&self) -> bool {
        !self.redo.is_empty()
    }
    pub fn text(&self) -> &str {
        &self.document.text
    }
    fn snapshot(&self) -> Snapshot {
        Snapshot {
            document: self.document.clone(),
            selection: self.selection.clone(),
        }
    }
    fn restore(&mut self, snapshot: Snapshot) {
        self.document = snapshot.document;
        self.selection = snapshot.selection;
        self.marked = None;
    }
    fn push_undo(&mut self, snapshot: Snapshot) {
        self.undo.push(snapshot);
        self.redo.clear();
        while self.undo.len() > 100
            || (self.undo.len() > 1
                && self
                    .undo
                    .iter()
                    .map(|s| s.document.text.len())
                    .sum::<usize>()
                    > 16_000_000)
        {
            self.undo.remove(0);
        }
    }
    pub fn finish_composition(&mut self) {
        if let Some(before) = self.composition.take()
            && before.document.text != self.document.text
        {
            self.push_undo(before);
        }
        self.marked = None;
    }
    fn replacement(&self, range: Option<Range<usize>>) -> Range<usize> {
        range
            .or_else(|| self.marked.clone())
            .unwrap_or_else(|| self.selection.range())
    }
    pub fn replace(&mut self, range: Option<Range<usize>>, text: &str) -> Result<()> {
        let range = self.replacement(range);
        self.validate(&range, text)?;
        let before = self.composition.take().unwrap_or_else(|| self.snapshot());
        self.apply(range, text);
        self.marked = None;
        if before.document.text != self.document.text {
            self.push_undo(before);
        }
        Ok(())
    }
    pub fn compose(
        &mut self,
        range: Option<Range<usize>>,
        text: &str,
        selected: Option<Range<usize>>,
    ) -> Result<()> {
        let range = self.replacement(range);
        self.validate(&range, text)?;
        if self.composition.is_none() {
            self.composition = Some(self.snapshot());
        }
        let start = range.start;
        self.apply(range, text);
        self.marked = (!text.is_empty()).then_some(start..start + text.len());
        if let Some(selected) = selected {
            let relative = utf16_range(text, selected);
            self.selection.anchor = start + relative.start;
            self.selection.head = start + relative.end;
        }
        Ok(())
    }
    fn validate(&self, range: &Range<usize>, text: &str) -> Result<()> {
        if range.start > range.end
            || range.end > self.document.text.len()
            || !self.document.text.is_char_boundary(range.start)
            || !self.document.text.is_char_boundary(range.end)
        {
            bail!("输入范围无效");
        }
        if self.document.text.len() - range.len() + text.len() > 2_000_000 {
            bail!("编辑文件超过 2 MB 上限");
        }
        Ok(())
    }
    fn apply(&mut self, range: Range<usize>, text: &str) {
        let mut updated = self.document.text.to_string();
        updated.replace_range(range.clone(), text);
        self.document = Document::new(&updated);
        let caret = range.start + text.len();
        self.selection = TextSelection {
            side: Side::Right,
            anchor: caret,
            head: caret,
        };
    }
    pub fn move_cursor(&mut self, motion: Motion, extend: bool) {
        self.finish_composition();
        let terminal =
            self.document.text.ends_with('\n') && self.selection.head == self.document.text.len();
        let destination = match motion {
            Motion::Up if terminal => Some(
                self.document
                    .display_range(self.document.lines.len() - 1)
                    .start,
            ),
            Motion::Home | Motion::End if terminal => Some(self.document.text.len()),
            Motion::Down
                if self.document.text.ends_with('\n')
                    && self.document.line_index(self.selection.head) + 1
                        == self.document.lines.len() =>
            {
                Some(self.document.text.len())
            }
            _ => None,
        };
        if let Some(offset) = destination {
            self.selection
                .point(Side::Right, offset, extend, &self.document);
        } else {
            self.selection.move_cursor(&self.document, motion, extend);
        }
    }
    pub fn delete(&mut self, backward: bool) -> Result<()> {
        self.finish_composition();
        let mut range = self.selection.range();
        if range.is_empty() {
            if backward {
                range.start = self.document.previous(range.start);
            } else {
                range.end = self.document.next(range.end);
            }
        }
        self.replace(Some(range), "")
    }
    pub fn paste(&mut self, text: &str) -> Result<()> {
        let normalized = text.replace("\r\n", "\n");
        let text = if self.crlf {
            normalized.replace('\n', "\r\n")
        } else {
            normalized
        };
        self.replace(None, &text)
    }
    pub fn undo(&mut self) {
        self.finish_composition();
        if let Some(previous) = self.undo.pop() {
            self.redo.push(self.snapshot());
            self.restore(previous);
        }
    }
    pub fn redo(&mut self) {
        self.finish_composition();
        if let Some(next) = self.redo.pop() {
            self.undo.push(self.snapshot());
            self.restore(next);
        }
    }
    pub fn external_snapshot(&self) -> Option<ExternalSnapshot> {
        Some(ExternalSnapshot {
            path: self.path.clone()?,
            canonical: self.canonical.clone()?,
            baseline: self.baseline.clone(),
        })
    }
    pub fn external_change(&self) -> Result<bool> {
        self.external_snapshot()
            .context("缓冲区没有文件路径")?
            .changed()
    }
    pub fn save(&mut self) -> Result<()> {
        self.finish_composition();
        let path = self.path.clone().context("缓冲区没有文件路径")?;
        if self.external_change()? {
            bail!("磁盘文件已被外部修改，未覆盖；请重新加载或另存内容");
        }
        let parent = path.parent().context("文件路径缺少目录")?;
        let temporary = parent.join(format!(
            ".mygit-save-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)?
                .as_nanos()
        ));
        let result = (|| -> Result<()> {
            let permissions = fs::metadata(&path)?.permissions();
            let mut file = fs::OpenOptions::new()
                .write(true)
                .create_new(true)
                .open(&temporary)?;
            file.set_permissions(permissions)?;
            file.write_all(self.text().as_bytes())?;
            file.sync_all()?;
            if self.external_change()? {
                bail!("保存期间文件发生外部修改，未覆盖");
            }
            fs::rename(&temporary, &path)?;
            Ok(())
        })();
        if result.is_err() {
            let _ = fs::remove_file(temporary);
        }
        result?;
        self.baseline = self.document.text.clone();
        Ok(())
    }
}
pub struct ExternalSnapshot {
    path: PathBuf,
    canonical: PathBuf,
    baseline: std::sync::Arc<str>,
}
impl ExternalSnapshot {
    pub fn changed(&self) -> Result<bool> {
        if self.path.canonicalize()? != self.canonical {
            return Ok(true);
        }
        Ok(disk(&self.path)? != self.baseline.as_bytes())
    }
}
fn disk(path: &Path) -> Result<Vec<u8>> {
    let metadata =
        fs::symlink_metadata(path).with_context(|| format!("无法读取 {}", path.display()))?;
    if !metadata.is_file() || metadata.file_type().is_symlink() {
        bail!("仅可编辑普通文件，符号链接及目录保持只读");
    }
    if metadata.len() > 2_000_000 {
        bail!("编辑文件超过 2 MB 上限");
    }
    fs::read(path).with_context(|| format!("无法读取 {}", path.display()))
}
pub fn to_utf16(text: &str, offset: usize) -> usize {
    text[..offset.min(text.len())].encode_utf16().count()
}
pub fn from_utf16(text: &str, offset: usize, ceil: bool) -> usize {
    let mut units = 0;
    for (byte, ch) in text.char_indices() {
        if units >= offset {
            return byte;
        }
        if units + ch.len_utf16() > offset {
            return if ceil { byte + ch.len_utf8() } else { byte };
        }
        units += ch.len_utf16();
    }
    text.len()
}
pub fn utf16_range(text: &str, range: Range<usize>) -> Range<usize> {
    from_utf16(text, range.start, false)..from_utf16(text, range.end, true)
}
#[derive(Clone, Debug, Default)]
pub struct LineMark {
    pub added: bool,
    pub modified: bool,
    pub deleted: usize,
}
pub fn line_marks(reference: &str, current: &str) -> std::collections::BTreeMap<usize, LineMark> {
    let mut marks = std::collections::BTreeMap::<usize, LineMark>::new();
    let Ok(diff) = crate::diff::calculate(reference.as_bytes(), current.as_bytes()) else {
        return marks;
    };
    let mut next = 0;
    for row in diff.rows {
        if let Some(no) = row.right_no {
            next = no;
        }
        if !row.changed {
            continue;
        }
        if let Some(no) = row.right_no {
            let mark = marks.entry(no - 1).or_default();
            mark.added = row.left_no.is_none();
            mark.modified = row.left_no.is_some();
        } else {
            marks.entry(next).or_default().deleted += 1;
        }
    }
    marks
}
pub fn find(text: &str, query: &str) -> Vec<Range<usize>> {
    if query.is_empty() {
        return vec![];
    }
    text.match_indices(query)
        .take(20_000)
        .map(|(start, s)| start..start + s.len())
        .collect()
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn ime_updates_are_one_undo_transaction_and_utf16_is_correct() {
        let mut b = Buffer::new("前🙂后");
        b.selection.anchor = "前🙂".len();
        b.selection.head = b.selection.anchor;
        b.compose(None, "n", None).unwrap();
        b.compose(None, "ni", None).unwrap();
        b.compose(None, "你", Some(1..1)).unwrap();
        assert_eq!(b.text(), "前🙂你后");
        assert_eq!(b.selection.head, "前🙂你".len());
        b.replace(None, "你好").unwrap();
        assert_eq!(b.text(), "前🙂你好后");
        b.undo();
        assert_eq!(b.text(), "前🙂后");
        b.redo();
        assert_eq!(b.text(), "前🙂你好后");
        assert_eq!(to_utf16("前🙂后", "前🙂".len()), 3);
        assert_eq!(utf16_range("前🙂后", 2..3), 3..7);
    }
    #[test]
    fn paste_crlf_grapheme_deletion_and_dirty_undo() {
        let mut b = Buffer::new("👩‍💻\r\n");
        b.selection.anchor = "👩‍💻".len();
        b.selection.head = b.selection.anchor;
        b.delete(true).unwrap();
        assert_eq!(b.text(), "\r\n");
        assert!(b.dirty());
        b.undo();
        assert!(!b.dirty());
        b.selection.select_all(&b.document);
        b.paste("a\nb\r\n").unwrap();
        assert_eq!(b.text(), "a\r\nb\r\n");
    }
    #[test]
    fn save_preserves_format_and_refuses_external_changes() {
        let dir = std::env::temp_dir().join(format!(
            "mygit-editor-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        fs::create_dir(&dir).unwrap();
        let path = dir.join("file");
        fs::write(&path, "原始\r\n").unwrap();
        let mut b = Buffer::load(&path).unwrap();
        b.selection.select_all(&b.document);
        b.paste("已编辑\n").unwrap();
        b.save().unwrap();
        assert_eq!(fs::read_to_string(&path).unwrap(), "已编辑\r\n");
        assert!(!b.dirty());
        b.paste("another").unwrap();
        fs::write(&path, "external\n").unwrap();
        assert!(b.external_change().unwrap());
        assert!(b.save().is_err());
        assert_eq!(fs::read_to_string(&path).unwrap(), "external\n");
        #[cfg(unix)]
        {
            let link = dir.join("link");
            std::os::unix::fs::symlink(&path, &link).unwrap();
            assert!(Buffer::load(&link).is_err());
        }
        fs::remove_dir_all(dir).unwrap();
    }
    #[test]
    fn editor_markers_and_literal_search_use_source_offsets() {
        let marks = line_marks("a\nb\nc\n", "a\n改动🙂\nc\n新增\n");
        assert!(marks[&1].modified);
        assert!(marks[&3].added);
        let deleted = line_marks("a\nb\nc\n", "a\nc\n");
        assert_eq!(deleted[&1].deleted, 1);
        assert_eq!(find("中文🙂 中文🙂", "中文🙂"), [0..10, 11..21]);
        assert!(find("abc", "").is_empty());
        assert!(find("abc", "missing").is_empty());
        let mut b = Buffer::new("a\n");
        b.selection.head = 2;
        b.selection.anchor = 2;
        b.move_cursor(Motion::Home, false);
        assert_eq!(b.selection.head, 2);
        b.move_cursor(Motion::Up, false);
        assert_eq!(b.selection.head, 0);
        b.move_cursor(Motion::Down, false);
        assert_eq!(b.selection.head, 2);
    }
}
