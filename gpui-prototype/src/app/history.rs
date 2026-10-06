use super::*;
use mygit_gpui::history::{self, Filter};
#[derive(Clone, Default)]
pub struct Snapshot {
    query: Option<history::Query>,
    commits: Vec<Commit>,
    next: usize,
    more: bool,
    cursor: Option<usize>,
    scroll: UniformListScrollHandle,
    error: Option<String>,
    failed: bool,
}
pub struct PathTab {
    pub path: String,
    pub directory: bool,
    state: Snapshot,
}
impl MyGit {
    fn history_snapshot(&self) -> Snapshot {
        Snapshot {
            query: self.history_query.clone(),
            commits: self.filtered_commits.clone(),
            next: self.filtered_next,
            more: self.filtered_more,
            cursor: self.history_cursor,
            scroll: self.history_scroll.clone(),
            error: self.history_search_error.clone(),
            failed: self.history_failed,
        }
    }
    fn remember_history_tab(&mut self) {
        let state = self.history_snapshot();
        if let Some(index) = self.active_history_tab {
            self.path_history_tabs[index].state = state;
        } else {
            self.ordinary_history = Some(state);
        }
    }
    fn restore_history_tab(&mut self, index: Option<usize>, cx: &mut Context<Self>) {
        self.history_pending.cancel();
        self.history_pending = Default::default();
        self.history_query_generation += 1;
        self.history_search_pending = false;
        self.history_loading = false;
        self.show_history_search = false;
        self.active_history_tab = index;
        let (state, path) = match index {
            Some(index) => {
                let tab = &self.path_history_tabs[index];
                (tab.state.clone(), Some((tab.path.clone(), tab.directory)))
            }
            None => (self.ordinary_history.clone().unwrap_or_default(), None),
        };
        self.history_query = state.query;
        self.filtered_commits = state.commits;
        self.filtered_next = state.next;
        self.filtered_more = state.more;
        self.history_cursor = state.cursor;
        self.history_scroll = state.scroll;
        self.history_search_error = state.error;
        self.history_failed = state.failed;
        self.history_path = path.clone();
        self.history_graph_key = None;
        if self.history_query.is_none()
            && let Some((path, directory)) = path
        {
            self.start_history_filter(
                Filter {
                    path: Some(path),
                    follow: !directory,
                    ..Default::default()
                },
                cx,
            );
        }
        cx.notify();
    }
    pub fn select_history_tab(&mut self, index: Option<usize>, cx: &mut Context<Self>) {
        if index == self.active_history_tab {
            return;
        }
        self.remember_history_tab();
        self.restore_history_tab(index, cx);
    }
    pub fn close_history_tab(&mut self, index: usize, cx: &mut Context<Self>) {
        if self.active_history_tab == Some(index) {
            self.path_history_tabs.remove(index);
            self.restore_history_tab(None, cx);
        } else {
            self.path_history_tabs.remove(index);
            if let Some(active) = &mut self.active_history_tab
                && *active > index
            {
                *active -= 1;
            }
            cx.notify();
        }
    }

    pub fn history_commits(&self) -> &[Commit] {
        if self.history_query.is_some() || self.active_history_tab.is_some() {
            &self.filtered_commits
        } else {
            self.state
                .repo
                .as_ref()
                .map(|r| r.commits.as_slice())
                .unwrap_or(&[])
        }
    }
    pub fn history_more(&self) -> bool {
        if self.history_query.is_some() || self.active_history_tab.is_some() {
            self.filtered_more
        } else {
            self.state.repo.as_ref().is_some_and(|r| r.history_more)
        }
    }
    pub fn toggle_history_search(&mut self, cx: &mut Context<Self>) {
        if self.active_history_tab.is_some() {
            self.select_history_tab(None, cx);
        }
        if self.state.repo.is_none() {
            return;
        }
        self.show_history_search = !self.show_history_search || !self.settings.git_panel_visible;
        if self.show_history_search {
            self.reveal_git_panel(cx);
        }
        self.prepare_history_inputs(cx);
        if self.show_history_search {
            self.hide_quick_open();
            self.hide_project_search();
            self.show_branches = false;
            self.show_compare = false;
            self.show_settings = false;
            self.hide_commit();
        }
        cx.notify();
    }
    pub(crate) fn prepare_history_inputs(&mut self, cx: &mut Context<Self>) {
        if !self.history_inputs.is_empty() {
            return;
        }
        let font = self.state.font_family.clone();
        let size = self.state.font_size;
        for value in ["", "HEAD", "", "", ""] {
            self.history_inputs.push(cx.new(|cx| {
                let mut editor = Editor::new(
                    mygit_gpui::editor::Buffer::new(value),
                    font.clone(),
                    size,
                    cx,
                );
                editor.compact = true;
                editor
            }));
        }
        self.history_input_subscription =
            Some(cx.subscribe(&self.history_inputs[0], |this, _, event, cx| {
                if matches!(event, Changed::SearchNext) {
                    this.search_history_inputs(cx);
                }
            }));
    }
    pub fn search_history_inputs(&mut self, cx: &mut Context<Self>) {
        if self.history_inputs.len() != 5 {
            return;
        }
        let values: Vec<_> = self
            .history_inputs
            .iter()
            .map(|input| input.read(cx).buffer.text().trim().to_owned())
            .collect();
        self.start_history_filter(
            Filter {
                text: values[0].clone(),
                scope: values[1].clone(),
                author: values[2].clone(),
                since: values[3].clone(),
                until: values[4].clone(),
                path: self.history_path.as_ref().map(|p| p.0.clone()),
                follow: self.history_path.as_ref().is_some_and(|p| !p.1),
            },
            cx,
        );
    }
    pub fn show_path_history(&mut self, path: String, directory: bool, cx: &mut Context<Self>) {
        self.reveal_git_panel(cx);
        self.hide_quick_open();
        self.hide_project_search();
        self.show_branches = false;
        self.show_compare = false;
        self.show_history_search = false;
        let index = self
            .path_history_tabs
            .iter()
            .position(|tab| tab.path == path && tab.directory == directory)
            .unwrap_or_else(|| {
                self.path_history_tabs.push(PathTab {
                    path,
                    directory,
                    state: Snapshot::default(),
                });
                self.path_history_tabs.len() - 1
            });
        self.select_history_tab(Some(index), cx);
    }

    pub fn current_file_history(&mut self, cx: &mut Context<Self>) {
        if let Some(file) = &self.state.current_file {
            self.show_path_history(file.path.clone(), false, cx);
        }
    }
    pub fn selected_tree_history(&mut self, cx: &mut Context<Self>) {
        if let Some((entry, _)) = self
            .tree
            .rows()
            .into_iter()
            .find(|(e, _)| Some(&e.path) == self.tree.selected.as_ref())
        {
            self.show_path_history(entry.path, entry.directory, cx);
        }
    }
    pub(super) fn start_history_filter(&mut self, filter: Filter, cx: &mut Context<Self>) {
        let Some(repo) = &self.state.repo else {
            return;
        };
        let root = repo.root.clone();
        self.history_pending.cancel();
        self.history_pending = Default::default();
        let token = self.history_pending.clone();
        self.history_query_generation += 1;
        let generation = self.history_query_generation;
        let epoch = self.repository_epoch;
        self.history_search_pending = true;
        self.history_loading = true;
        self.history_failed = false;
        self.history_search_error = None;
        let task = cx.background_executor().spawn(async move {
            mygit_gpui::process::scope(token, || -> anyhow::Result<_> {
                let query = history::prepare(&root, filter)?;
                let page = history::page(&root, &query, 0)?;
                Ok((query, page))
            })
        });
        cx.spawn(async move |this, cx| {
            let result = task.await;
            let _ = this.update(cx, |this, cx| {
                if this.repository_epoch != epoch || this.history_query_generation != generation {
                    return;
                }
                this.history_loading = false;
                this.history_search_pending = false;
                match result {
                    Ok((query, page)) => {
                        this.history_query = Some(query);
                        this.filtered_commits = page.commits;
                        this.filtered_next = page.next;
                        this.filtered_more = page.more;
                        this.history_cursor = None;
                        this.history_scroll = Default::default();
                    }
                    Err(error) => {
                        this.history_failed = true;
                        this.history_search_error = Some(mygit_gpui::localized_format!(
                            "历史查询失败：{error:#}",
                            "History search failed: {error:#}"
                        ));
                    }
                }
                cx.notify();
            });
        })
        .detach();
        cx.notify();
    }
    pub(super) fn load_more_filtered(&mut self, cx: &mut Context<Self>) {
        if self.history_loading || !self.filtered_more {
            return;
        }
        let (Some(repo), Some(query)) = (&self.state.repo, self.history_query.clone()) else {
            return;
        };
        let root = repo.root.clone();
        let offset = self.filtered_next;
        let generation = self.history_query_generation;
        let epoch = self.repository_epoch;
        let token = self.history_pending.clone();
        self.history_loading = true;
        self.history_failed = false;
        let task = cx.background_executor().spawn(async move {
            mygit_gpui::process::scope(token, || history::page(&root, &query, offset))
        });
        cx.spawn(async move |this, cx| {
            let result = task.await;
            let _ = this.update(cx, |this, cx| {
                if this.repository_epoch != epoch
                    || this.history_query_generation != generation
                    || this.filtered_next != offset
                {
                    return;
                }
                this.history_loading = false;
                match result {
                    Ok(page) => {
                        this.filtered_commits.extend(page.commits);
                        this.filtered_next = page.next;
                        this.filtered_more = page.more;
                    }
                    Err(error) => {
                        this.history_failed = true;
                        this.history_search_error = Some(mygit_gpui::localized_format!(
                            "历史分页失败：{error:#}",
                            "Unable to load more history: {error:#}"
                        ));
                    }
                }
                cx.notify();
            });
        })
        .detach();
        cx.notify();
    }
    pub fn clear_history_filter(&mut self, cx: &mut Context<Self>) {
        if self.active_history_tab.is_some() {
            self.select_history_tab(None, cx);
        }
        self.history_pending.cancel();
        self.history_pending = Default::default();
        self.history_query_generation += 1;
        self.history_search_pending = false;
        self.history_query = None;
        self.filtered_commits.clear();
        self.filtered_next = 0;
        self.filtered_more = false;
        self.history_loading = false;
        self.history_failed = false;
        self.history_cursor = None;
        self.history_path = None;
        self.history_search_error = None;
        self.history_scroll = Default::default();
        for (input, value) in self.history_inputs.iter().zip(["", "HEAD", "", "", ""]) {
            input.update(cx, |editor, cx| {
                editor.buffer = mygit_gpui::editor::Buffer::new(value);
                editor.refresh(cx);
            });
        }
        cx.notify();
    }
    pub(super) fn reset_history_search(&mut self) {
        self.path_history_tabs.clear();
        self.active_history_tab = None;
        self.ordinary_history = None;
        self.history_query_generation += 1;
        self.history_search_pending = false;
        self.history_query = None;
        self.filtered_commits.clear();
        self.filtered_next = 0;
        self.filtered_more = false;
        self.history_inputs.clear();
        self.history_input_subscription = None;
        self.history_path = None;
        self.show_history_search = false;
        self.history_search_error = None;
    }
}
