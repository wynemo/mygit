use crate::model::*;

/// UI-independent state, shared by task results and view rendering.
pub struct AppState {
    pub repo: Option<Snapshot>,
    pub mode: BrowseMode,
    pub comparison: Option<Comparison>,
    pub files: Vec<FileChange>,
    pub selected: Option<usize>,
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
            comparison: None,
            files: vec![],
            selected: None,
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
    pub fn labels(&self) -> (String, String) {
        match (
            &self.comparison,
            self.selected.and_then(|i| self.files.get(i)),
        ) {
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
}
