use super::*;
impl MyGit {
    pub fn toggle_branches(&mut self, cx: &mut Context<Self>) {
        if self.state.repo.is_none() {
            return;
        }
        self.show_branches = !self.show_branches;
        self.branch_filter_sha = None;
        self.prepare_branch_inputs(cx);
        if self.show_branches {
            self.show_compare = false;
            self.show_commit = false;
            self.show_settings = false;
        }
        cx.notify();
    }
    fn prepare_branch_inputs(&mut self, cx: &mut Context<Self>) {
        if self.branch_name.is_some() {
            return;
        }
        let font = self.state.font_family.clone();
        let size = self.state.font_size;
        self.branch_name = Some(cx.new(|cx| {
            let mut editor =
                Editor::new(mygit_gpui::editor::Buffer::new(""), font.clone(), size, cx);
            editor.compact = true;
            editor
        }));
        self.branch_base = Some(cx.new(|cx| {
            let mut editor = Editor::new(mygit_gpui::editor::Buffer::new("HEAD"), font, size, cx);
            editor.compact = true;
            editor
        }));
    }
    pub fn show_commit_branches(&mut self, sha: String, cx: &mut Context<Self>) {
        self.show_branches = true;
        self.branch_filter_sha = Some(sha);
        self.prepare_branch_inputs(cx);
        self.show_compare = false;
        self.show_commit = false;
        self.show_settings = false;
        cx.notify();
    }
    pub fn branch_rows(&self) -> Vec<BranchRef> {
        self.state
            .repo
            .as_ref()
            .map(|repo| {
                repo.branches
                    .iter()
                    .filter(|branch| {
                        self.branch_filter_sha
                            .as_ref()
                            .is_none_or(|sha| sha == &branch.sha)
                    })
                    .cloned()
                    .collect()
            })
            .unwrap_or_default()
    }
    pub fn choose_branch(&mut self, reference: String, cx: &mut Context<Self>) {
        self.branch_selected = Some(reference.clone());
        if let Some(base) = &self.branch_base {
            base.update(cx, |editor, cx| {
                editor.buffer = mygit_gpui::editor::Buffer::new(&reference);
                editor.refresh(cx);
            });
        }
        cx.notify();
    }
    fn branch_write_ready(&mut self, cx: &mut Context<Self>) -> bool {
        if self.write_busy || self.state.repo.is_none() {
            return false;
        }
        if self
            .editors
            .values()
            .any(|editor| editor.read(cx).buffer.dirty() || editor.read(cx).buffer.marked.is_some())
        {
            self.write_message = "请先保存或关闭未保存的编辑内容，再切换/新建分支".into();
            cx.notify();
            return false;
        }
        true
    }
    pub fn move_branch(&mut self, forward: bool, cx: &mut Context<Self>) {
        let rows = self.branch_rows();
        if rows.is_empty() {
            return;
        }
        let current = rows
            .iter()
            .position(|b| Some(&b.reference) == self.branch_selected.as_ref());
        let index = match current {
            None => 0,
            Some(index) if forward => (index + 1).min(rows.len() - 1),
            Some(index) => index.saturating_sub(1),
        };
        self.choose_branch(rows[index].reference.clone(), cx);
        self.branch_scroll
            .scroll_to_item(index, ScrollStrategy::Center);
    }
    pub fn switch_branch(&mut self, cx: &mut Context<Self>) {
        if !self.branch_write_ready(cx) {
            return;
        }
        let Some(reference) = self.branch_selected.clone() else {
            return;
        };
        if !self.branch_rows().iter().any(|b| b.reference == reference) {
            return;
        }
        let root = self.state.repo.as_ref().unwrap().root.clone();
        let name = self
            .branch_name
            .as_ref()
            .map(|e| e.read(cx).buffer.text().trim().to_owned());
        self.run_write(
            "正在切换分支…",
            BrowseMode::Workspace,
            false,
            move || mygit_gpui::branches::switch(&root, &reference, name.as_deref()),
            cx,
        );
    }
    pub fn create_branch(&mut self, cx: &mut Context<Self>) {
        if !self.branch_write_ready(cx) {
            return;
        }
        let (Some(name), Some(base)) = (&self.branch_name, &self.branch_base) else {
            return;
        };
        let name = name.read(cx).buffer.text().trim().to_owned();
        let base = base.read(cx).buffer.text().trim().to_owned();
        let root = self.state.repo.as_ref().unwrap().root.clone();
        self.run_write(
            "正在创建分支…",
            BrowseMode::Workspace,
            false,
            move || mygit_gpui::branches::create(&root, &name, &base),
            cx,
        );
    }
}
