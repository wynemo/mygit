use super::*;
use mygit_gpui::{
    process::Cancellation,
    search::{Options, Results},
};
use std::sync::Arc;
#[derive(Default)]
pub struct State {
    pub shown: bool,
    pub inputs: Vec<Entity<Editor>>,
    subscriptions: Vec<Subscription>,
    pub options: Options,
    pub results: Arc<Results>,
    pub loading: bool,
    pub error: Option<String>,
    pub selected: usize,
    pub scroll: UniformListScrollHandle,
    pub serial: u64,
    pending: Cancellation,
}
impl State {
    pub fn cancel(&mut self) {
        self.pending.cancel();
        self.serial += 1;
        self.loading = false;
    }
    pub fn reset(&mut self) {
        self.cancel();
        *self = Self::default();
    }
}
impl MyGit {
    pub fn toggle_project_search(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        if self.state.repo.is_none() {
            return;
        }
        if self.search.shown {
            self.close_project_search(window, cx);
            return;
        }
        self.hide_quick_open();
        self.show_branches = false;
        self.show_history_search = false;
        self.show_compare = false;
        self.show_settings = false;
        self.hide_commit();
        self.search.shown = true;
        if self.search.inputs.is_empty() {
            for _ in 0..3 {
                let font = self.state.font_family.clone();
                let size = self.state.font_size;
                let input = cx.new(|cx| {
                    let mut editor =
                        Editor::new(mygit_gpui::editor::Buffer::new(""), font, size, cx);
                    editor.compact = true;
                    editor
                });
                self.search
                    .subscriptions
                    .push(cx.subscribe(&input, |this, _, event, cx| {
                        if matches!(event, Changed::Edited) {
                            this.search_project(cx);
                        }
                    }));
                self.search.inputs.push(input);
            }
        }
        window.focus(&self.search.inputs[0].read(cx).focus);
        self.search_project(cx);
    }
    pub(crate) fn hide_project_search(&mut self) {
        if self.search.shown {
            self.search.shown = false;
            self.search.cancel();
        }
    }
    pub fn close_project_search(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        if self.search_composing(cx) {
            return;
        }
        self.hide_project_search();
        window.focus(&self.focus);
        cx.notify();
    }
    pub fn search_project(&mut self, cx: &mut Context<Self>) {
        self.search.cancel();
        self.search.results = Default::default();
        self.search.selected = 0;
        self.search.error = None;
        if !self.search.shown || self.search.inputs.len() != 3 {
            cx.notify();
            return;
        }
        let Some(repo) = &self.state.repo else {
            return;
        };
        let root = repo.root.clone();
        let mut options = self.search.options.clone();
        options.query = self.search.inputs[0].read(cx).buffer.text().to_owned();
        options.include = self.search.inputs[1].read(cx).buffer.text().to_owned();
        options.exclude = self.search.inputs[2].read(cx).buffer.text().to_owned();
        if options.query.trim().is_empty() {
            cx.notify();
            return;
        }
        self.search.pending = Default::default();
        let token = self.search.pending.clone();
        let serial = self.search.serial;
        let epoch = self.repository_epoch;
        self.search.loading = true;
        let task = cx.background_executor().spawn(async move {
            Timer::after(std::time::Duration::from_millis(250)).await;
            mygit_gpui::process::scope(token, || mygit_gpui::search::run(&root, &options))
        });
        cx.spawn(async move |this, cx| {
            let result = task.await;
            let _ = this.update(cx, |this, cx| {
                if this.repository_epoch != epoch || this.search.serial != serial {
                    return;
                }
                this.search.loading = false;
                match result {
                    Ok(results) => {
                        this.search.results = Arc::new(results);
                        this.search.scroll = Default::default();
                    }
                    Err(error) => this.search.error = Some(format!("{error:#}")),
                }
                cx.notify();
            });
        })
        .detach();
        cx.notify();
    }
    fn search_composing(&self, cx: &App) -> bool {
        self.search
            .inputs
            .iter()
            .any(|input| input.read(cx).buffer.marked.is_some())
    }
    pub fn project_search_move(&mut self, down: bool, cx: &mut Context<Self>) {
        let count = self.search.results.hits.len();
        if self.search_composing(cx) || self.search.loading || count == 0 {
            return;
        }
        self.search.selected = if down {
            (self.search.selected + 1).min(count - 1)
        } else {
            self.search.selected.saturating_sub(1)
        };
        self.search
            .scroll
            .scroll_to_item(self.search.selected, ScrollStrategy::Center);
        cx.notify();
    }
    pub fn accept_project_search(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        if self.search_composing(cx) || self.search.loading {
            return;
        }
        let Some(hit) = self.search.results.hits.get(self.search.selected).cloned() else {
            return;
        };
        if let Err(error) = self.tree.reveal(&hit.path) {
            self.search.error = Some(format!("{error:#}"));
            cx.notify();
            return;
        }
        self.quick.reveal = Some(hit.path.clone());
        self.settings.files_visible = true;
        self.refresh_tree(cx);
        self.open_workspace_hit(hit, cx);
        window.focus(&self.focus);
        cx.notify();
    }
}
