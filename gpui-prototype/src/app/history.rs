use super::*;
use mygit_gpui::history::{self, Filter};
impl MyGit {
    pub fn history_commits(&self) -> &[Commit] {
        if self.history_query.is_some() {
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
        if self.history_query.is_some() {
            self.filtered_more
        } else {
            self.state.repo.as_ref().is_some_and(|r| r.history_more)
        }
    }
    pub fn toggle_history_search(&mut self, cx: &mut Context<Self>) {
        if self.state.repo.is_none() {
            return;
        }
        self.show_history_search = !self.show_history_search;
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
    fn prepare_history_inputs(&mut self, cx: &mut Context<Self>) {
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
        self.prepare_history_inputs(cx);
        self.history_path = Some((path.clone(), directory));
        self.hide_quick_open();
        self.hide_project_search();
        self.show_history_search = true;
        self.show_branches = false;
        self.show_compare = false;
        for (input, value) in self.history_inputs.iter().zip(["", "HEAD", "", "", ""]) {
            input.update(cx, |editor, cx| {
                editor.buffer = mygit_gpui::editor::Buffer::new(value);
                editor.refresh(cx);
            });
        }
        self.start_history_filter(
            Filter {
                path: Some(path),
                follow: !directory,
                ..Default::default()
            },
            cx,
        );
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
                        this.history_search_error = Some(format!("历史查询失败：{error:#}"));
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
                        this.history_search_error = Some(format!("历史分页失败：{error:#}"));
                    }
                }
                cx.notify();
            });
        })
        .detach();
        cx.notify();
    }
    pub fn clear_history_filter(&mut self, cx: &mut Context<Self>) {
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
