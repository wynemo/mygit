use super::*;
use mygit_gpui::{
    process,
    watch::{Debounce, RepositoryWatch},
};
use std::time::{Duration, Instant};

impl MyGit {
    pub(super) fn start_refresh_loop(cx: &mut Context<Self>) {
        cx.spawn(async move |this, cx| {
            loop {
                Timer::after(Duration::from_millis(150)).await;
                if this
                    .update(cx, |this, cx| {
                        if this.write_busy {
                            let text = this.write_progress.text();
                            if text != this.write_progress_text {
                                this.write_progress_text = text;
                                cx.notify();
                            }
                        }
                        let now = Instant::now();
                        if let Some(watcher) = &this.watcher {
                            this.refresh_debounce.observe(watcher.revision(), now);
                            if this.refresh_debounce.due(now) {
                                this.refresh_requested = true;
                            }
                        }
                        // Reconciliation also handles missed native events and failed watches.
                        if now.duration_since(this.last_reconcile) >= Duration::from_secs(30) {
                            this.last_reconcile = now;
                            this.refresh_requested = true;
                        }
                        if this.refresh_requested
                            && !this.refresh_running
                            && !this.write_busy
                            && !this.state.loading
                        {
                            this.refresh_repository(cx);
                        }
                    })
                    .is_err()
                {
                    break;
                }
            }
        })
        .detach();
    }
    pub(super) fn start_watcher(&mut self, cx: &mut Context<Self>) {
        let Some(repo) = &self.state.repo else {
            return;
        };
        let root = repo.root.clone();
        let epoch = self.repository_epoch;
        let token = self.refresh_pending.clone();
        let task = cx.background_executor().spawn(async move {
            process::scope(token, || {
                RepositoryWatch::new(&root, &git::metadata_directories(&root)?)
            })
        });
        cx.spawn(async move |this, cx| {
            let result = task.await;
            let _ = this.update(cx, |this, cx| {
                if this.repository_epoch != epoch {
                    return;
                }
                match result {
                    Ok(watcher) => this.watcher = Some(watcher),
                    Err(error) => {
                        this.write_message = format!("文件监听不可用，将定期刷新：{error:#}")
                    }
                }
                this.last_reconcile = Instant::now();
                // Cover changes between the initial snapshot and watcher registration.
                this.refresh_requested = true;
                cx.notify();
            });
        })
        .detach();
    }
    pub fn request_refresh(&mut self, cx: &mut Context<Self>) {
        self.refresh_requested = true;
        if !self.refresh_running && !self.write_busy && !self.state.loading {
            self.refresh_repository(cx);
        }
    }
    fn refresh_repository(&mut self, cx: &mut Context<Self>) {
        let Some(repo) = &self.state.repo else {
            self.refresh_requested = false;
            return;
        };
        let root = repo.root.clone();
        self.capture_tab();
        let mode = self.state.mode.clone();
        let active = self
            .state
            .current_file
            .clone()
            .zip(self.state.comparison.clone());
        // Historical merge documents are immutable and already pinned; keep the
        // three-column cache while refreshing refs and the file list.
        let follows_list = self.state.comparison == self.state.listed_comparison;
        let active = if self.state.merge.is_some()
            || (matches!(self.state.mode, BrowseMode::Merge(_)) && follows_list)
        {
            None
        } else {
            active
        };
        self.refresh_serial += 1;
        let serial = self.refresh_serial;
        let generation = self.state.generation;
        let epoch = self.repository_epoch;
        let token = self.refresh_pending.clone();
        self.refresh_requested = false;
        self.refresh_running = true;
        let task = cx.background_executor().spawn(async move {
            process::scope(token, || {
                git::refresh_snapshot(&root, &mode, active, follows_list)
            })
        });
        cx.spawn(async move |this, cx| {
            let result = task.await;
            let _ = this.update(cx, |this, cx| {
                if this.repository_epoch != epoch || this.refresh_serial != serial {
                    return;
                }
                this.refresh_running = false;
                // A file/mode switch or write supersedes this background result.
                if this.state.generation != generation || this.write_busy {
                    this.refresh_requested = true;
                    return;
                }
                match result {
                    Ok(git::RefreshSnapshot {
                        mut repo,
                        selection,
                        active: diff,
                    }) => {
                        if let Some(previous) = &this.state.repo {
                            if previous.history_tip == repo.history_tip {
                                repo.commits = previous.commits.clone();
                                repo.history_more = previous.history_more;
                            } else if this.history_query.is_none() && !this.history_search_pending {
                                this.history_query_generation += 1;
                                this.history_pending.cancel();
                                this.history_pending = Default::default();
                                this.history_loading = false;
                                this.history_cursor = None;
                            }
                        }
                        this.state.repo = Some(repo);
                        let selected_path = this
                            .state
                            .selected
                            .and_then(|i| this.state.files.get(i))
                            .map(|f| f.path.clone());
                        this.state.files = selection.files;
                        this.state.selected = selected_path
                            .and_then(|p| this.state.files.iter().position(|f| f.path == p));
                        this.file_selection
                            .retain(|p| this.state.files.iter().any(|f| &f.path == p));
                        this.state.listed_comparison = Some(selection.comparison);
                        if let Some((file, comparison, diff)) = diff {
                            this.state.current_file = Some(file);
                            this.state.comparison = Some(comparison);
                            if !this.state.refresh_diff(diff) {
                                this.line_layouts.clear();
                                this.dragging = false;
                            }
                            if let Some(editor) = this.current_editor() {
                                let reference = this.state.diff.left_document.clone();
                                if editor.read(cx).reference.text != reference.text {
                                    editor.update(cx, |editor, cx| {
                                        editor.reference = reference;
                                        editor.refresh(cx);
                                    });
                                }
                            }
                            this.remember_tab();
                        }
                        this.refresh_tree(cx);
                    }
                    Err(error) => this.write_message = format!("刷新失败：{error:#}"),
                }
                cx.notify();
            });
        })
        .detach();
    }
    pub fn observe_activation(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        cx.observe_window_activation(window, |this, window, cx| {
            if window.is_window_active() {
                this.request_refresh(cx);
            }
        })
        .detach();
    }
    pub(super) fn reset_refresh(&mut self) {
        self.watcher = None;
        self.refresh_serial += 1;
        self.refresh_pending.cancel();
        self.refresh_pending = Default::default();
        self.refresh_running = false;
        self.refresh_requested = false;
        self.refresh_debounce = Debounce::default();
        self.last_reconcile = Instant::now();
    }
}
