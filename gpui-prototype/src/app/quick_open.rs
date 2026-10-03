use super::*;
use mygit_gpui::{
    process::Cancellation,
    quick_open::{Index, Matches},
};
use std::sync::Arc;
#[derive(Default)]
pub struct State {
    pub shown: bool,
    pub input: Option<Entity<Editor>>,
    subscription: Option<Subscription>,
    index: Arc<Index>,
    index_ready: bool,
    pub indexing: bool,
    pub searching: bool,
    pub error: Option<String>,
    pub matches: Matches,
    pub selected: usize,
    pub scroll: UniformListScrollHandle,
    index_serial: u64,
    query_serial: u64,
    index_pending: Cancellation,
    query_pending: Cancellation,
    pub reveal: Option<String>,
}
impl State {
    pub fn cancel(&mut self) {
        self.index_pending.cancel();
        self.query_pending.cancel();
        self.index_serial += 1;
        self.query_serial += 1;
        self.indexing = false;
        self.searching = false;
    }
    pub fn reset(&mut self) {
        self.cancel();
        *self = Self::default();
    }
    pub fn count(&self) -> usize {
        self.index.len()
    }
}
impl MyGit {
    pub fn toggle_quick_open(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        if self.state.repo.is_none() {
            return;
        }
        if self.quick.shown {
            self.close_quick_open(window, cx);
            return;
        }
        self.quick.shown = true;
        self.show_branches = false;
        self.show_history_search = false;
        self.show_compare = false;
        self.show_settings = false;
        self.show_commit = false;
        if self.quick.input.is_none() {
            let font = self.state.font_family.clone();
            let size = self.state.font_size;
            let input = cx.new(|cx| {
                let mut editor = Editor::new(mygit_gpui::editor::Buffer::new(""), font, size, cx);
                editor.compact = true;
                editor
            });
            self.quick.subscription = Some(cx.subscribe(&input, |this, _, event, cx| {
                if matches!(event, Changed::Edited) {
                    this.search_quick_open(cx);
                }
            }));
            self.quick.input = Some(input);
        }
        if let Some(input) = &self.quick.input {
            window.focus(&input.read(cx).focus);
        }
        self.refresh_quick_index(cx);
        cx.notify();
    }
    pub(crate) fn hide_quick_open(&mut self) {
        if self.quick.shown {
            self.quick.shown = false;
            self.quick.cancel();
        }
    }
    pub fn close_quick_open(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        self.quick.shown = false;
        self.quick.cancel();
        window.focus(&self.focus);
        cx.notify();
    }
    pub fn refresh_quick_index(&mut self, cx: &mut Context<Self>) {
        if !self.quick.shown {
            return;
        }
        let Some(repo) = &self.state.repo else {
            return;
        };
        let root = repo.root.clone();
        let epoch = self.repository_epoch;
        self.quick.cancel();
        self.quick.index_pending = Default::default();
        self.quick.indexing = true;
        self.quick.index_ready = false;
        self.quick.matches = Default::default();
        self.quick.error = None;
        let serial = self.quick.index_serial;
        let token = self.quick.index_pending.clone();
        let task = cx.background_executor().spawn(async move {
            mygit_gpui::process::scope(token, || mygit_gpui::quick_open::read(&root))
        });
        cx.spawn(async move |this, cx| {
            let result = task.await;
            let _ = this.update(cx, |this, cx| {
                if this.repository_epoch != epoch || this.quick.index_serial != serial {
                    return;
                }
                this.quick.indexing = false;
                match result {
                    Ok(index) => {
                        this.quick.index_ready = true;
                        this.quick.index = Arc::new(index);
                        this.search_quick_open(cx);
                    }
                    Err(error) => this.quick.error = Some(format!("{error:#}")),
                }
                cx.notify();
            });
        })
        .detach();
        cx.notify();
    }
    pub(super) fn search_quick_open(&mut self, cx: &mut Context<Self>) {
        self.quick.query_pending.cancel();
        self.quick.query_pending = Default::default();
        self.quick.query_serial += 1;
        self.quick.matches = Default::default();
        self.quick.selected = 0;
        if self.quick.indexing || !self.quick.shown || !self.quick.index_ready {
            self.quick.searching = false;
            cx.notify();
            return;
        }
        let query = self
            .quick
            .input
            .as_ref()
            .map(|e| e.read(cx).buffer.text().to_owned())
            .unwrap_or_default();
        let index = self.quick.index.clone();
        let epoch = self.repository_epoch;
        let serial = self.quick.query_serial;
        let index_serial = self.quick.index_serial;
        let token = self.quick.query_pending.clone();
        self.quick.searching = true;
        self.quick.error = None;
        let task = cx.background_executor().spawn(async move {
            Timer::after(std::time::Duration::from_millis(150)).await;
            mygit_gpui::process::scope(token, || index.search(&query, 50))
        });
        cx.spawn(async move |this, cx| {
            let result = task.await;
            let _ = this.update(cx, |this, cx| {
                if this.repository_epoch != epoch
                    || this.quick.query_serial != serial
                    || this.quick.index_serial != index_serial
                {
                    return;
                }
                this.quick.searching = false;
                match result {
                    Ok(matches) => {
                        this.quick.matches = matches;
                        this.quick.scroll = Default::default();
                    }
                    Err(error) => this.quick.error = Some(format!("{error:#}")),
                }
                cx.notify();
            });
        })
        .detach();
        cx.notify();
    }
    pub fn quick_move(&mut self, down: bool, cx: &mut Context<Self>) {
        if self
            .quick
            .input
            .as_ref()
            .is_some_and(|e| e.read(cx).buffer.marked.is_some())
        {
            return;
        }
        let count = self.quick.matches.paths.len();
        if count == 0 || self.quick.indexing || self.quick.searching {
            return;
        }
        self.quick.selected = if down {
            (self.quick.selected + 1).min(count - 1)
        } else {
            self.quick.selected.saturating_sub(1)
        };
        self.quick
            .scroll
            .scroll_to_item(self.quick.selected, ScrollStrategy::Center);
        cx.notify();
    }
    pub fn accept_quick_open(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        if self
            .quick
            .input
            .as_ref()
            .is_some_and(|e| e.read(cx).buffer.marked.is_some())
        {
            return;
        }
        if self.quick.indexing || self.quick.searching {
            return;
        }
        let Some(path) = self.quick.matches.paths.get(self.quick.selected).cloned() else {
            return;
        };
        if let Err(error) = self.tree.reveal(&path) {
            self.quick.error = Some(format!("{error:#}"));
            cx.notify();
            return;
        }
        self.quick.shown = false;
        self.quick.cancel();
        self.quick.reveal = Some(path.clone());
        self.show_tree = true;
        self.refresh_tree(cx);
        self.open_workspace_file(path, cx);
        window.focus(&self.focus);
        cx.notify();
    }
}
