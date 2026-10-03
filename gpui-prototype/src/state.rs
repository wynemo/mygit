use crate::model::*;

/// UI-independent state, shared by task results and view rendering.
pub struct AppState {
    pub repo: Option<Snapshot>,
    pub mode: BrowseMode,
    pub detail: Option<CommitDetail>,
    pub comparison: Option<Comparison>,
    pub listed_comparison: Option<Comparison>,
    pub files: Vec<FileChange>,
    pub selected: Option<usize>,
    pub current_file: Option<FileChange>,
    pub diff: Diff,
    pub message: String,
    pub loading: bool,
    pub generation: u64,
    pub panel_width: f32,
    pub horizontal_offset: f32,
    pub current_block: Option<usize>,
    pub text_selection: crate::text::TextSelection,
    pub font_size: f32,
    pub font_family: String,
}
impl Default for AppState {
    fn default() -> Self {
        Self {
            repo: None,
            mode: BrowseMode::Workspace,
            detail: None,
            comparison: None,
            listed_comparison: None,
            files: vec![],
            selected: None,
            current_file: None,
            diff: Diff::default(),
            message: "打开一个 Git 仓库".into(),
            loading: false,
            generation: 0,
            panel_width: 420.,
            horizontal_offset: 0.,
            current_block: None,
            text_selection: crate::text::TextSelection::default(),
            font_size: 12.,
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
        self.diff = Diff::default();
        self.text_selection = crate::text::TextSelection::default();
        self.current_block = None;
        self.horizontal_offset = 0.;
        self.panel_width = 420.;
    }
    pub fn set_diff(&mut self, diff: Diff) {
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
    pub fn tab_snapshot(&self) -> Option<FileTab> {
        Some(FileTab {
            file: self.current_file.clone()?,
            comparison: self.comparison.clone()?,
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
        self.comparison = Some(tab.comparison);
        self.detail = tab.detail;
        self.set_diff(tab.diff);
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
