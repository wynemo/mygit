use crate::model::*;

/// UI-independent state, shared by task results and view rendering.
pub struct AppState {
    pub merge: Option<std::sync::Arc<crate::merge::View>>,
    pub repo: Option<Snapshot>,
    pub mode: BrowseMode,
    pub detail: Option<CommitDetail>,
    pub listed_detail: Option<CommitDetail>,
    pub comparison: Option<Comparison>,
    pub listed_comparison: Option<Comparison>,
    pub files: Vec<FileChange>,
    pub selected: Option<usize>,
    pub current_file: Option<FileChange>,
    pub editable: bool,
    pub diff: Diff,
    pub message: String,
    pub loading: bool,
    pub generation: u64,
    pub panel_width: f32,
    pub horizontal_offset: f32,
    pub current_block: Option<usize>,
    pub text_selection: crate::text::TextSelection,
    pub font_size: f32,
    pub unified: bool,
    pub font_family: String,
}
impl Default for AppState {
    fn default() -> Self {
        Self {
            merge: None,
            repo: None,
            mode: BrowseMode::Workspace,
            detail: None,
            listed_detail: None,
            comparison: None,
            listed_comparison: None,
            files: vec![],
            selected: None,
            current_file: None,
            editable: false,
            diff: Diff::default(),
            message: "打开一个 Git 仓库".into(),
            loading: false,
            generation: 0,
            panel_width: 420.,
            horizontal_offset: 0.,
            current_block: None,
            text_selection: crate::text::TextSelection::default(),
            font_size: 12.,
            unified: false,
            font_family: "Menlo".into(),
        }
    }
}
impl AppState {
    pub fn begin(&mut self, message: String) -> u64 {
        self.generation += 1;
        self.loading = true;
        self.message = message;
        self.generation
    }
    pub fn clear_diff(&mut self) {
        self.merge = None;
        self.diff = Diff::default();
        self.text_selection = crate::text::TextSelection::default();
        self.current_block = None;
        self.horizontal_offset = 0.;
        self.panel_width = 420.;
    }
    pub fn set_diff(&mut self, diff: Diff) {
        self.merge = None;
        self.text_selection = crate::text::TextSelection::default();
        self.panel_width = diff.panel_width();
        self.message = diff.message.clone().unwrap_or_else(|| {
            if diff.blocks.is_empty() {
                "无内容差异".into()
            } else {
                format!("{} 行 · {} 处差异", diff.rows.len(), diff.blocks.len())
            }
        });
        self.diff = diff;
        self.current_block = None;
    }
    pub fn set_merge(&mut self, view: crate::merge::View) {
        self.set_diff(view.pair_diff());
        self.panel_width = view
            .documents
            .iter()
            .flat_map(|doc| {
                doc.lines.iter().map(|range| {
                    doc.text[range.clone()]
                        .chars()
                        .map(|c| {
                            if c == '\t' {
                                4
                            } else if c.is_ascii() {
                                1
                            } else {
                                2
                            }
                        })
                        .sum::<usize>()
                })
            })
            .max()
            .unwrap_or(0)
            .saturating_mul(8)
            .saturating_add(68)
            .max(420) as f32;
        self.editable = false;
        self.merge = Some(std::sync::Arc::new(view));
    }
    /// Refresh retains source offsets and viewport; changed text clamps to grapheme boundaries.
    pub fn refresh_diff(&mut self, diff: Diff) -> bool {
        let unchanged = self.diff.left_document.text == diff.left_document.text
            && self.diff.right_document.text == diff.right_document.text;
        let mut selection = self.text_selection.clone();
        if selection.side == crate::text::Side::Third && diff.third.is_none() {
            selection.side = crate::text::Side::Right;
        }
        let horizontal = self.horizontal_offset;
        let block = self.current_block;
        self.set_diff(diff);
        let document = self.diff.document(selection.side);
        selection.anchor = document.snap(selection.anchor);
        selection.head = document.snap(selection.head);
        self.text_selection = selection;
        self.horizontal_offset = horizontal;
        self.current_block = block.filter(|i| *i < self.diff.blocks.len());
        unchanged
    }
    pub fn navigation_target(&self, forward: bool) -> Option<usize> {
        if self.loading || self.diff.blocks.is_empty() {
            return None;
        }
        match (self.current_block, forward) {
            (None, true) => Some(0),
            (None, false) => Some(self.diff.blocks.len() - 1),
            (Some(i), true) => (i + 1 < self.diff.blocks.len()).then_some(i + 1),
            (Some(i), false) => i.checked_sub(1),
        }
    }
    pub fn navigate(&mut self, forward: bool) -> Option<usize> {
        let block = self.navigation_target(forward)?;
        self.current_block = Some(block);
        Some(self.diff.blocks[block].start)
    }
    pub fn active_row(&self, index: usize) -> bool {
        self.current_block
            .and_then(|b| self.diff.blocks.get(b))
            .is_some_and(|b| b.contains(&index))
    }
    pub fn view_row(&self, row: usize, side: crate::text::Side) -> usize {
        if !self.unified || self.merge.is_some() {
            return row;
        }
        self.diff
            .unified
            .iter()
            .position(|r| r.row == row && r.side == side)
            .or_else(|| self.diff.unified.iter().position(|r| r.row == row))
            .unwrap_or(0)
    }
    pub fn view_count(&self) -> usize {
        if self.unified && self.merge.is_none() {
            self.diff.unified.len()
        } else {
            self.diff.rows.len()
        }
    }
    pub fn restore_positions(&mut self, previous: &FileTab) -> bool {
        if self.diff.left_document.text != previous.diff.left_document.text
            || self.diff.right_document.text != previous.diff.right_document.text
            || match (&self.diff.third, &previous.diff.third) {
                (None, None) => false,
                (Some(a), Some(b)) => a.document.text != b.document.text || a.rows != b.rows,
                _ => true,
            }
        {
            return false;
        }
        self.text_selection = previous.selection.clone();
        self.horizontal_offset = previous.horizontal;
        self.current_block = previous.block.filter(|i| *i < self.diff.blocks.len());
        true
    }
    pub fn tab_snapshot(&self) -> Option<FileTab> {
        Some(FileTab {
            merge: self.merge.clone(),
            panel_width: self.panel_width,
            file: self.current_file.clone()?,
            comparison: self.comparison.clone()?,
            editable: self.editable,
            detail: self.detail.clone(),
            diff: self.diff.clone(),
            selection: self.text_selection.clone(),
            horizontal: self.horizontal_offset,
            block: self.current_block,
        })
    }
    pub fn restore_tab(&mut self, tab: FileTab) {
        let listed = self.listed_comparison.as_ref() == Some(&tab.comparison);
        self.selected = self
            .files
            .iter()
            .position(|f| listed && f.path == tab.file.path);
        self.current_file = Some(tab.file);
        self.editable = tab.editable;
        self.comparison = Some(tab.comparison);
        self.detail = tab.detail;
        self.set_diff(tab.diff);
        self.merge = tab.merge;
        self.panel_width = tab.panel_width;
        self.text_selection = tab.selection;
        self.horizontal_offset = tab.horizontal;
        self.current_block = tab.block;
    }
    pub fn active_file(&self) -> Option<&FileChange> {
        self.current_file
            .as_ref()
            .or_else(|| self.selected.and_then(|i| self.files.get(i)))
    }
    pub fn labels(&self) -> (String, String) {
        match (&self.comparison, self.active_file()) {
            (Some(comparison), Some(file)) => {
                let (left, right) = comparison.targets(file);
                (left.revision.label(), right.revision.label())
            }
            (Some(comparison), None) => (comparison.left.label(), comparison.right.label()),
            _ => ("旧版本".into(), "新版本".into()),
        }
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn refresh_preserves_selection_and_clamps_changed_unicode() {
        let mut state = AppState::default();
        state.set_diff(crate::diff::calculate(b"old", "🙂new".as_bytes()).unwrap());
        state.text_selection.anchor = 4;
        state.text_selection.head = 7;
        state.horizontal_offset = 50.;
        state.current_block = Some(0);
        assert!(state.refresh_diff(crate::diff::calculate(b"old", "🙂new".as_bytes()).unwrap()));
        assert_eq!(
            (state.text_selection.anchor, state.text_selection.head),
            (4, 7)
        );
        assert_eq!(state.horizontal_offset, 50.);
        assert_eq!(state.current_block, Some(0));
        assert!(!state.refresh_diff(crate::diff::calculate(b"old", "你".as_bytes()).unwrap()));
        assert_eq!(
            (state.text_selection.anchor, state.text_selection.head),
            (3, 3)
        );
    }
    #[test]
    fn navigation_tracks_blocks_and_stops_at_boundaries() {
        let mut state = AppState::default();
        assert_eq!(state.navigate(true), None);
        state.set_diff(crate::diff::calculate(b"a\nb\nc\nd\n", b"x\nb\nc\ny\n").unwrap());
        assert_eq!(state.navigate(true), Some(0));
        assert!(state.active_row(0));
        assert!(!state.active_row(1));
        assert_eq!(state.navigate(true), Some(3));
        assert_eq!(state.navigate(true), None);
        assert_eq!(state.navigate(false), Some(0));
        assert_eq!(state.navigate(false), None);
        state.clear_diff();
        assert_eq!(state.current_block, None);
        state.set_diff(crate::diff::calculate(b"a\nb\nc\nd\n", b"x\nb\nc\ny\n").unwrap());
        assert_eq!(state.navigate(false), Some(3));
        state.begin("loading".into());
        assert_eq!(state.navigate(false), None);
    }
    #[test]
    fn third_side_selection_copies_raw_text_skips_padding_and_preserves_graphemes() {
        use crate::text::{Motion, Side};
        let result = "a\t😀\r\ninserted\nb";
        let third = "a\t😀\r\nb";
        let view = crate::merge::align(
            &crate::diff::calculate(result.as_bytes(), result.as_bytes()).unwrap(),
            &crate::diff::calculate(third.as_bytes(), result.as_bytes()).unwrap(),
        )
        .unwrap();
        let mut state = AppState::default();
        state.set_merge(view);
        state.unified = true;
        assert_eq!(state.view_count(), state.diff.rows.len());
        let padding = (0..state.diff.rows.len())
            .find(|row| state.diff.source_line(Side::Third, *row).is_none())
            .unwrap();
        let offset = state.diff.padding_offset(Side::Third, padding);
        assert_eq!(&state.diff.document(Side::Third).text[offset..], "b");
        assert_eq!(state.view_row(padding, Side::Third), padding);
        state
            .text_selection
            .point(Side::Third, 0, false, state.diff.document(Side::Third));
        state
            .text_selection
            .select_all(state.diff.document(Side::Third));
        assert_eq!(
            state
                .text_selection
                .copy(state.diff.document(Side::Third))
                .unwrap(),
            third
        );
        state
            .text_selection
            .point(Side::Third, 2, false, state.diff.document(Side::Third));
        state
            .text_selection
            .move_cursor(state.diff.document(Side::Third), Motion::Right, true);
        assert_eq!(
            state
                .text_selection
                .copy(state.diff.document(Side::Third))
                .unwrap(),
            "😀"
        );
        state
            .text_selection
            .point(Side::Left, 0, true, state.diff.document(Side::Left));
        assert_eq!(state.text_selection.anchor, 0);
        assert_eq!(state.text_selection.head, 0);
        state.text_selection.point(
            Side::Third,
            third.len(),
            false,
            state.diff.document(Side::Third),
        );
        state.refresh_diff(crate::diff::calculate(b"a", b"b").unwrap());
        assert_eq!(state.text_selection.side, Side::Right);
        assert_eq!(state.text_selection.head, 1);
    }
    #[test]
    fn merge_tabs_preserve_third_parent_navigation_width_and_read_only_state() {
        let left = crate::diff::calculate(b"a\nb\nc\nd\n", b"a\nb\nc\nd\n").unwrap();
        let right = crate::diff::calculate(b"x\nb\nc\ny\n", b"a\nb\nc\nd\n").unwrap();
        let view = crate::merge::align(&left, &right).unwrap();
        let mut state = AppState {
            current_file: Some(FileChange {
                path: "file".into(),
                old_path: "file".into(),
                status: "M".into(),
            }),
            comparison: Some(Comparison {
                left: Revision::Commit("parent".into()),
                right: Revision::Commit("merged".into()),
            }),
            ..Default::default()
        };
        state.set_merge(view);
        assert!(!state.editable);
        assert_eq!(state.navigate(true), Some(0));
        assert_eq!(state.navigate(true), Some(3));
        assert_eq!(state.navigate(true), None);
        state.horizontal_offset = 55.;
        state.text_selection.point(
            crate::text::Side::Third,
            0,
            false,
            state.diff.document(crate::text::Side::Third),
        );
        state
            .text_selection
            .select_all(state.diff.document(crate::text::Side::Third));
        let tab = state.tab_snapshot().unwrap();
        let width = state.panel_width;
        let mut same_two_columns = tab.diff.clone();
        same_two_columns.third = None;
        state.set_diff(same_two_columns);
        assert!(!state.restore_positions(&tab));
        state.set_diff(crate::diff::calculate(b"normal", b"normal").unwrap());
        assert!(state.merge.is_none());
        state.restore_tab(tab);
        assert!(state.merge.is_some());
        assert_eq!(state.current_block, Some(1));
        assert_eq!(state.horizontal_offset, 55.);
        assert_eq!(state.panel_width, width);
        assert_eq!(state.text_selection.side, crate::text::Side::Third);
        assert_eq!(
            state
                .text_selection
                .copy(state.diff.document(crate::text::Side::Third))
                .unwrap(),
            "x\nb\nc\ny\n"
        );
        assert_eq!(state.navigate(false), Some(0));
        state.clear_diff();
        assert!(state.merge.is_none());
        assert!(state.diff.rows.is_empty());
    }
    #[test]
    fn tabs_restore_own_version_and_do_not_retarget_browsed_file_list() {
        let file = |path: &str| FileChange {
            path: path.into(),
            old_path: path.into(),
            status: "M".into(),
        };
        let listed = Comparison {
            left: Revision::Index,
            right: Revision::Worktree,
        };
        let mut state = AppState {
            listed_comparison: Some(listed.clone()),
            files: vec![file("a/same.rs"), file("b/same.rs")],
            ..Default::default()
        };
        state.current_file = Some(file("a/same.rs"));
        state.comparison = Some(listed.clone());
        state.set_diff(crate::diff::calculate(b"old\n", b"new\n").unwrap());
        state.horizontal_offset = 42.;
        state.current_block = Some(0);
        state.text_selection.select_all(&state.diff.right_document);
        let a = state.tab_snapshot().unwrap();
        state.current_file = Some(file("b/same.rs"));
        state.comparison = Some(Comparison {
            left: Revision::Empty,
            right: Revision::Commit("other".into()),
        });
        state.set_diff(crate::diff::calculate(b"", b"historical\n").unwrap());
        let b = state.tab_snapshot().unwrap();
        assert_ne!(a.file.path, b.file.path);
        state.restore_tab(a);
        assert_eq!(state.selected, Some(0));
        assert_eq!(state.horizontal_offset, 42.);
        assert_eq!(
            state
                .text_selection
                .copy(&state.diff.right_document)
                .as_deref(),
            Some("new\n")
        );
        state.restore_tab(b);
        assert_eq!(state.selected, None);
        assert_eq!(state.listed_comparison, Some(listed));
        assert_eq!(&*state.diff.right_document.text, "historical\n");
    }
}
