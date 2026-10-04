mod ai;
mod blame;
mod branches;
mod history;
mod notifications;
mod preferences;
mod quick_open;
mod refresh;
mod search;
use crate::views::editor::{Changed, Editor};
use crate::views::text_line::LineHit;
use crate::{tasks, views};
use gpui::{prelude::*, *};
use mygit_gpui::text::{Motion, Side};
use mygit_gpui::{git, model::*, state::AppState};
use std::{
    collections::{HashMap, HashSet},
    path::PathBuf,
};

actions!(
    mygit,
    [
        ViewWorkspace,
        ViewStaged,
        ViewUnstaged,
        StageSelected,
        UnstageSelected,
        StageAll,
        UnstageAll,
        ToggleCommitPanel,
        CopyCommitSha,
        OpenRepo,
        RefreshRepo,
        ToggleSettings,
        ToggleFilesPanel,
        ToggleGitPanel,
        ToggleNotifications,
        ToggleBranches,
        ToggleHistorySearch,
        ToggleProjectSearch,
        ProjectSearchUp,
        ProjectSearchDown,
        ProjectSearchAccept,
        ProjectSearchDismiss,
        ToggleQuickOpen,
        QuickUp,
        QuickDown,
        QuickAccept,
        QuickDismiss,
        Quit,
        FocusNext,
        FocusPrevious,
        ListUp,
        ListDown,
        ListEnter,
        CancelTask,
        CopyText,
        SelectAllText,
        Left,
        Right,
        Up,
        Down,
        SelectLeft,
        SelectRight,
        SelectUp,
        SelectDown,
        Home,
        End,
        SelectHome,
        SelectEnd,
        Start,
        Finish,
        SelectStart,
        SelectFinish,
        NextDiff,
        PreviousDiff
    ]
);

#[derive(Clone)]
pub enum Confirmation {
    Close(String),
    CloseOthers(Option<String>),
    Load(PathBuf),
    Quit,
    Reset {
        target: String,
        mode: mygit_gpui::operations::ResetMode,
        expected_head: Option<String>,
        expected_branch: Option<String>,
    },
    Restore {
        file: FileChange,
        comparison: Comparison,
        diff: Box<Diff>,
        block: Option<usize>,
    },
}
pub struct MyGit {
    pub notifications: mygit_gpui::notifications::Notifications,
    pub show_notifications: bool,
    pub ai: ai::State,
    pub quick: quick_open::State,
    pub search: search::State,
    watcher: Option<mygit_gpui::watch::RepositoryWatch>,
    refresh_debounce: mygit_gpui::watch::Debounce,
    refresh_pending: mygit_gpui::process::Cancellation,
    refresh_requested: bool,
    refresh_running: bool,
    refresh_serial: u64,
    last_reconcile: std::time::Instant,
    pub state: AppState,
    pub tabs: Vec<FileTab>,
    pub editors: HashMap<String, Entity<Editor>>,
    pub editor_subscriptions: HashMap<String, Subscription>,
    pub edit_mode: bool,
    pub confirmation: Option<Confirmation>,
    pub file_selection: HashSet<String>,
    pub write_busy: bool,
    pub write_message: String,
    pub write_progress: mygit_gpui::process::Progress,
    pub write_progress_text: String,
    pub show_commit: bool,
    pub show_compare: bool,
    pub font_inputs: Vec<Entity<Editor>>,
    restore_main_focus: bool,
    pub show_blame: bool,
    blame_key: Option<blame::Key>,
    blame_pending: mygit_gpui::process::Cancellation,
    blame_epoch: u64,
    pub blame_left: std::sync::Arc<Vec<mygit_gpui::blame::Line>>,
    pub blame_right: std::sync::Arc<Vec<mygit_gpui::blame::Line>>,
    pub blame_third: std::sync::Arc<Vec<mygit_gpui::blame::Line>>,
    pub blame_loading: bool,
    pub blame_error: String,
    pub blame_details: HashMap<String, CommitDetail>,
    blame_detail_loading: Option<String>,
    blame_detail_pending: mygit_gpui::process::Cancellation,
    blame_detail_serial: u64,
    pub show_history_search: bool,
    pub history_inputs: Vec<Entity<Editor>>,
    pub history_input_subscription: Option<Subscription>,
    pub history_query: Option<mygit_gpui::history::Query>,
    pub history_query_generation: u64,
    pub history_search_pending: bool,
    pub history_path: Option<(String, bool)>,
    pub history_search_error: Option<String>,
    filtered_commits: Vec<Commit>,
    pub history_graph: Vec<mygit_gpui::graph::Row>,
    history_graph_key: Option<(usize, String, String, u64, u64)>,
    filtered_next: usize,
    filtered_more: bool,
    pub show_branches: bool,
    pub branch_name: Option<Entity<Editor>>,
    pub branch_base: Option<Entity<Editor>>,
    pub remote_name: Option<Entity<Editor>>,
    pub branch_selected: Option<String>,
    pub branch_filter_sha: Option<String>,
    pub branch_focus: FocusHandle,
    pub branch_scroll: UniformListScrollHandle,
    pub compare_left: Option<Entity<Editor>>,
    pub compare_right: Option<Entity<Editor>>,
    pub commit_editor: Option<Entity<Editor>>,
    write_pending: mygit_gpui::process::Cancellation,
    pub active_tab: Option<usize>,
    pub tab_scroll: HashMap<String, UniformListScrollHandle>,
    pub settings: mygit_gpui::settings::Settings,
    pub show_settings: bool,
    pub pending: mygit_gpui::process::Cancellation,
    pub history_pending: mygit_gpui::process::Cancellation,
    pub tree: mygit_gpui::workspace::Tree,
    pub tree_pending: mygit_gpui::process::Cancellation,
    pub tree_loading: bool,
    pub tree_epoch: u64,
    pub tree_error: Option<String>,
    pub show_tree: bool,
    pub history_loading: bool,
    pub history_failed: bool,
    pub history_focus: FocusHandle,
    pub files_focus: FocusHandle,
    pub history_scroll: UniformListScrollHandle,
    pub files_scroll: UniformListScrollHandle,
    pub history_cursor: Option<usize>,
    pub visible_history_width: f32,
    pub visible_files_width: f32,
    pub repository_epoch: u64,
    pub last_path: Option<PathBuf>,
    pub diff_scroll: UniformListScrollHandle,
    pub diff_bounds: Option<Bounds<Pixels>>,
    pub focus: FocusHandle,
    pub line_layouts: HashMap<(Side, usize), LineHit>,
    pub dragging: bool,
    pub drag_position: Option<Point<Pixels>>,
    pub drag_epoch: u64,
}
impl MyGit {
    pub fn new(cx: &mut Context<Self>) -> Self {
        let settings =
            mygit_gpui::settings::Settings::load(mygit_gpui::settings::Settings::default_path());
        cx.set_global(crate::views::editor::CodePalette(
            mygit_gpui::syntax::palette_index(&settings.code_theme),
        ));
        let state = AppState {
            font_size: settings.font_size,
            font_family: settings.font_family.clone(),
            ..Default::default()
        };
        Self::start_refresh_loop(cx);
        cx.on_app_quit(|this, _| {
            this.ai.cancel();
            this.quick.cancel();
            this.search.cancel();
            this.blame_pending.cancel();
            this.blame_detail_pending.cancel();
            this.refresh_pending.cancel();
            this.pending.cancel();
            this.history_pending.cancel();
            this.tree_pending.cancel();
            this.write_pending.cancel();
            async {
                Timer::after(std::time::Duration::from_millis(100)).await;
            }
        })
        .detach();
        Self {
            notifications: Default::default(),
            show_notifications: false,
            watcher: None,
            refresh_debounce: Default::default(),
            refresh_pending: Default::default(),
            refresh_requested: false,
            refresh_running: false,
            refresh_serial: 0,
            last_reconcile: std::time::Instant::now(),
            state,
            tabs: vec![],
            editors: HashMap::new(),
            editor_subscriptions: HashMap::new(),
            edit_mode: false,
            confirmation: None,
            file_selection: HashSet::new(),
            write_busy: false,
            write_message: String::new(),
            write_progress: Default::default(),
            write_progress_text: String::new(),
            show_commit: false,
            show_compare: false,
            font_inputs: vec![],
            restore_main_focus: false,
            show_blame: false,
            ai: Default::default(),
            quick: Default::default(),
            search: Default::default(),
            blame_key: None,
            blame_pending: Default::default(),
            blame_epoch: 0,
            blame_left: Default::default(),
            blame_right: Default::default(),
            blame_third: Default::default(),
            blame_loading: false,
            blame_error: String::new(),
            blame_details: HashMap::new(),
            blame_detail_loading: None,
            blame_detail_pending: Default::default(),
            blame_detail_serial: 0,
            show_history_search: false,
            history_inputs: vec![],
            history_input_subscription: None,
            history_query: None,
            history_query_generation: 0,
            history_search_pending: false,
            history_path: None,
            history_search_error: None,
            filtered_commits: vec![],
            history_graph: vec![],
            history_graph_key: None,
            filtered_next: 0,
            filtered_more: false,
            show_branches: false,
            branch_name: None,
            branch_base: None,
            remote_name: None,
            branch_selected: None,
            branch_filter_sha: None,
            branch_focus: cx.focus_handle(),
            branch_scroll: UniformListScrollHandle::new(),
            compare_left: None,
            compare_right: None,
            commit_editor: None,
            write_pending: Default::default(),
            active_tab: None,
            tab_scroll: HashMap::new(),
            settings,
            show_settings: false,
            pending: Default::default(),
            history_pending: Default::default(),
            tree: mygit_gpui::workspace::Tree::new(),
            tree_pending: Default::default(),
            tree_loading: false,
            tree_epoch: 0,
            tree_error: None,
            show_tree: false,
            history_loading: false,
            history_failed: false,
            history_focus: cx.focus_handle(),
            files_focus: cx.focus_handle(),
            history_scroll: UniformListScrollHandle::new(),
            files_scroll: UniformListScrollHandle::new(),
            history_cursor: None,
            visible_history_width: 260.,
            visible_files_width: 220.,
            repository_epoch: 0,
            last_path: None,
            diff_scroll: UniformListScrollHandle::new(),
            diff_bounds: None,
            focus: cx.focus_handle(),
            line_layouts: HashMap::new(),
            dragging: false,
            drag_position: None,
            drag_epoch: 0,
        }
    }
    pub fn open(&mut self, cx: &mut Context<Self>) {
        let picker = cx.prompt_for_paths(PathPromptOptions {
            files: false,
            directories: true,
            multiple: false,
            prompt: Some(mygit_gpui::i18n::text("选择 Git 仓库").into()),
        });
        cx.spawn(async move |this, cx| match picker.await {
            Ok(Ok(Some(paths))) => {
                if let Some(path) = paths.into_iter().next() {
                    let _ = this.update(cx, |this, cx| this.load(path, cx));
                }
            }
            Ok(Ok(None)) => {}
            other => {
                let _ = this.update(cx, |this, cx| {
                    this.state.message = mygit_gpui::localized_format!(
                        "无法打开目录选择器：{other:?}",
                        "Unable to open directory picker: {other:?}"
                    );
                    cx.notify();
                });
            }
        })
        .detach();
    }
    pub fn load(&mut self, path: PathBuf, cx: &mut Context<Self>) {
        if self.write_busy {
            self.state.message =
                mygit_gpui::i18n::text("Git 写操作正在执行，请等待完成后再切换或刷新仓库").into();
            cx.notify();
            return;
        }
        let switching = !self.state.repo.as_ref().is_some_and(|r| r.root == path);
        if switching && self.editors.values().any(|e| e.read(cx).buffer.dirty()) {
            self.confirmation = Some(Confirmation::Load(path));
            cx.notify();
            return;
        }
        self.load_unchecked(path, cx);
    }
    fn load_unchecked(&mut self, path: PathBuf, cx: &mut Context<Self>) {
        self.restore_main_focus = true;
        self.reset_refresh();
        self.reset_blame();
        self.reset_history_search();
        self.ai.reset();
        self.quick.reset();
        self.search.reset();
        self.edit_mode = false;
        self.capture_tab();
        self.active_tab = None;
        if !self.state.repo.as_ref().is_some_and(|r| r.root == path) {
            self.show_compare = false;
            self.compare_left = None;
            self.compare_right = None;
            self.file_selection.clear();
            self.write_message.clear();
            self.show_branches = false;
            self.branch_name = None;
            self.branch_base = None;
            self.remote_name = None;
            self.branch_selected = None;
            self.branch_filter_sha = None;
            self.commit_editor = None;
            self.hide_commit();
            self.editors.clear();
            self.editor_subscriptions.clear();
            self.tabs.clear();
            self.active_tab = None;
            self.tab_scroll.clear();
            self.tree = mygit_gpui::workspace::Tree::new();
        }
        self.tree_pending.cancel();
        self.tree_loading = false;
        self.tree_epoch += 1;
        self.pending.cancel();
        self.history_pending.cancel();
        self.history_pending = Default::default();
        self.repository_epoch += 1;
        self.history_loading = false;
        self.history_failed = false;
        self.history_cursor = None;
        self.history_scroll = UniformListScrollHandle::new();
        self.files_scroll = UniformListScrollHandle::new();
        self.last_path = Some(path.clone());
        self.state.detail = None;
        self.state.listed_detail = None;
        self.state.repo = None;
        self.state.comparison = None;
        self.state.listed_comparison = None;
        self.state.files.clear();
        self.state.selected = None;
        self.state.current_file = None;
        self.state.editable = false;
        self.state.mode = BrowseMode::Workspace;
        self.state.clear_diff();
        self.line_layouts.clear();
        self.dragging = false;
        self.diff_scroll = UniformListScrollHandle::new();
        let generation = self
            .state
            .begin(mygit_gpui::i18n::text("正在读取仓库…").into());
        cx.notify();
        self.pending.cancel();
        self.pending = Default::default();
        tasks::run(
            cx,
            generation,
            self.pending.clone(),
            move || git::snapshot(&path),
            |this, repo, cx| {
                this.settings.opened(&repo.root);
                this.state.repo = Some(repo);
                this.save_settings();
                this.start_watcher(cx);
                this.refresh_tree(cx);
                this.select_mode(BrowseMode::Workspace, cx);
            },
        );
    }
    pub fn select_mode(&mut self, mode: BrowseMode, cx: &mut Context<Self>) {
        self.hide_quick_open();
        self.hide_project_search();
        let Some(repo) = &self.state.repo else {
            return;
        };
        let root = repo.root.clone();
        self.capture_tab();
        self.active_tab = None;
        self.file_selection.clear();
        self.state.detail = None;
        self.state.listed_detail = None;
        self.state.current_file = None;
        self.show_tree = false;
        self.edit_mode = false;
        self.state.editable = matches!(mode, BrowseMode::Workspace | BrowseMode::Unstaged);
        self.state.mode = mode.clone();
        self.state.comparison = None;
        self.state.listed_comparison = None;
        self.state.files.clear();
        self.state.selected = None;
        self.state.clear_diff();
        self.line_layouts.clear();
        self.dragging = false;
        let generation = self.state.begin(mygit_gpui::localized_format!(
            "正在读取{}…",
            "Loading {}…",
            mode.label()
        ));
        cx.notify();
        self.pending.cancel();
        self.pending = Default::default();
        tasks::run(
            cx,
            generation,
            self.pending.clone(),
            move || {
                let detail = match &mode {
                    BrowseMode::History(sha) | BrowseMode::Merge(sha) => {
                        Some(git::commit_detail(&root, sha)?)
                    }
                    _ => None,
                };
                Ok((git::selection(&root, &mode)?, detail))
            },
            |this, (selection, detail), cx| {
                this.state.listed_detail = detail.clone();
                this.state.detail = detail;
                this.state.listed_comparison = Some(selection.comparison.clone());
                this.state.comparison = Some(selection.comparison);
                this.state.files = selection.files;
                this.state.message = mygit_gpui::localized_format!(
                    "{} · {} 个文件",
                    "{} · {} files",
                    this.state.mode.label(),
                    this.state.files.len()
                );
                if !this.state.files.is_empty() {
                    this.select_file(0, cx);
                }
            },
        );
    }
    pub fn select_file(&mut self, index: usize, cx: &mut Context<Self>) {
        let (Some(repo), Some(comparison), Some(file)) = (
            &self.state.repo,
            &self.state.listed_comparison,
            self.state.files.get(index),
        ) else {
            return;
        };
        let root = repo.root.clone();
        let comparison = comparison.clone();
        let file = file.clone();
        let merge_sha = match &self.state.mode {
            BrowseMode::Merge(sha) => Some(sha.clone()),
            _ => None,
        };
        self.capture_tab();
        self.active_tab = None;
        self.state.editable = matches!(
            self.state.mode,
            BrowseMode::Workspace | BrowseMode::Unstaged
        );
        let previous = self
            .tabs
            .iter()
            .find(|t| t.file.path == file.path && t.comparison == comparison)
            .cloned();
        self.state.detail = self.state.listed_detail.clone();
        self.state.comparison = Some(comparison.clone());
        self.edit_mode = false;
        self.state.selected = Some(index);
        self.state.current_file = Some(file.clone());
        self.state.clear_diff();
        self.line_layouts.clear();
        self.dragging = false;
        self.diff_scroll = UniformListScrollHandle::new();
        let generation = self.state.begin(mygit_gpui::localized_format!(
            "正在比较 {}…",
            "Comparing {}…",
            file.path
        ));
        cx.notify();
        self.pending.cancel();
        self.pending = Default::default();
        tasks::run(
            cx,
            generation,
            self.pending.clone(),
            move || {
                if let Some(sha) = merge_sha {
                    let selection = mygit_gpui::merge::selection(&root, &sha)?;
                    let target = selection
                        .files
                        .iter()
                        .find(|f| f.path == file.path)
                        .ok_or_else(|| anyhow::anyhow!("合并文件不再存在"))?;
                    let view = mygit_gpui::merge::load(&root, &selection, target, 2_000_000)?;
                    Ok((None, Some(view)))
                } else {
                    Ok((Some(git::compare(&root, &comparison, &file)?), None))
                }
            },
            move |this, (diff, merge), _| {
                if let Some(merge) = merge {
                    this.state.set_merge(merge);
                } else if let Some(diff) = diff {
                    this.state.set_diff(diff);
                }
                if let Some(previous) = &previous
                    && this.state.restore_positions(previous)
                {
                    this.diff_scroll = this
                        .tab_scroll
                        .get(&previous.file.path)
                        .cloned()
                        .unwrap_or_default();
                }
                this.remember_tab();
            },
        );
    }
    pub fn capture_tab(&mut self) {
        if self.state.loading {
            return;
        }
        let Some(index) = self.active_tab else {
            return;
        };
        let Some(tab) = self.tabs.get_mut(index) else {
            return;
        };
        tab.selection = self.state.text_selection.clone();
        tab.horizontal = self.state.horizontal_offset;
        tab.block = self.state.current_block;
        self.tab_scroll
            .insert(tab.file.path.clone(), self.diff_scroll.clone());
    }
    pub fn remember_tab(&mut self) {
        let Some(tab) = self.state.tab_snapshot() else {
            return;
        };
        let file = tab.file.clone();
        let index = match self.tabs.iter().position(|t| t.file.path == file.path) {
            Some(index) => {
                self.tabs[index] = tab;
                index
            }
            None => {
                self.tabs.push(tab);
                self.tabs.len() - 1
            }
        };
        self.active_tab = Some(index);
        self.tab_scroll.insert(file.path, self.diff_scroll.clone());
    }
    pub fn activate_tab(&mut self, index: usize, cx: &mut Context<Self>) {
        self.capture_tab();
        let Some(tab) = self.tabs.get(index).cloned() else {
            return;
        };
        self.pending.cancel();
        self.state.generation += 1;
        self.state.loading = false;
        let path = tab.file.path.clone();
        self.state.restore_tab(tab);
        self.edit_mode = self.state.editable
            && self.editors.contains_key(&path)
            && self
                .state
                .comparison
                .as_ref()
                .is_some_and(|c| c.right == Revision::Worktree);
        self.diff_scroll = self.tab_scroll.get(&path).cloned().unwrap_or_default();
        self.active_tab = Some(index);
        self.line_layouts.clear();
        self.dragging = false;
        if !self.settings.git_panel_visible {
            if self.state.editable
                && self
                    .state
                    .comparison
                    .as_ref()
                    .is_some_and(|c| c.right == Revision::Worktree)
            {
                self.open_current_editor(cx);
            } else {
                self.reveal_git_panel(cx);
            }
        }
        cx.notify();
    }
    pub fn close_tab(&mut self, index: usize, cx: &mut Context<Self>) {
        if let Some(tab) = self.tabs.get(index)
            && self.is_dirty(&tab.file.path, cx)
        {
            self.confirmation = Some(Confirmation::Close(tab.file.path.clone()));
            cx.notify();
            return;
        }
        self.close_tab_unchecked(index, cx);
    }
    fn close_tab_unchecked(&mut self, index: usize, cx: &mut Context<Self>) {
        if index >= self.tabs.len() {
            return;
        }
        self.capture_tab();
        let removed = self.tabs.remove(index);
        self.editors.remove(&removed.file.path);
        self.editor_subscriptions.remove(&removed.file.path);
        self.tab_scroll.remove(&removed.file.path);
        match self.active_tab {
            Some(active) if active == index => {
                self.active_tab = None;
                if !self.tabs.is_empty() {
                    self.activate_tab(index.min(self.tabs.len() - 1), cx);
                } else {
                    self.state.current_file = None;
                    self.state.selected = None;
                    self.state.clear_diff();
                }
            }
            Some(active) if active > index => self.active_tab = Some(active - 1),
            _ => {}
        }
        cx.notify();
    }
    pub fn close_other_tabs(&mut self, all: bool, cx: &mut Context<Self>) {
        let keep = if all {
            None
        } else {
            self.active_tab
                .and_then(|i| self.tabs.get(i))
                .map(|t| t.file.path.clone())
        };
        if !all && keep.is_none() {
            return;
        }
        if self
            .editors
            .iter()
            .any(|(path, e)| Some(path) != keep.as_ref() && e.read(cx).buffer.dirty())
        {
            self.confirmation = Some(Confirmation::CloseOthers(keep));
            cx.notify();
            return;
        }
        self.close_other_tabs_unchecked(all, cx);
    }
    fn close_other_tabs_unchecked(&mut self, all: bool, cx: &mut Context<Self>) {
        if !all && self.active_tab.is_none() {
            return;
        }
        self.capture_tab();
        self.pending.cancel();
        self.state.generation += 1;
        self.state.loading = false;
        if !all && let Some(tab) = self.active_tab.and_then(|i| self.tabs.get(i)).cloned() {
            let scroll = self.tab_scroll.remove(&tab.file.path);
            self.editors.retain(|path, _| path == &tab.file.path);
            self.editor_subscriptions
                .retain(|path, _| path == &tab.file.path);
            self.tabs = vec![tab.clone()];
            self.active_tab = Some(0);
            self.tab_scroll.clear();
            if let Some(scroll) = scroll {
                self.tab_scroll.insert(tab.file.path, scroll);
            }
        } else {
            self.editors.clear();
            self.editor_subscriptions.clear();
            self.edit_mode = false;
            self.tabs.clear();
            self.tab_scroll.clear();
            self.active_tab = None;
            self.state.current_file = None;
            self.state.selected = None;
            self.state.clear_diff();
        }
        cx.notify();
    }
    pub fn is_dirty(&self, path: &str, cx: &App) -> bool {
        self.editors
            .get(path)
            .is_some_and(|e| e.read(cx).buffer.dirty())
    }
    pub fn current_editor(&self) -> Option<Entity<Editor>> {
        if (!self.edit_mode && self.settings.git_panel_visible)
            || !self.state.editable
            || !self
                .state
                .comparison
                .as_ref()
                .is_some_and(|c| c.right == Revision::Worktree)
        {
            return None;
        }
        self.state
            .current_file
            .as_ref()
            .and_then(|f| self.editors.get(&f.path))
            .cloned()
    }
    pub fn edit_current(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        self.open_current_editor(cx);
        if let Some(editor) = self.current_editor() {
            window.focus(&editor.read(cx).focus);
        }
    }
    fn open_current_editor(&mut self, cx: &mut Context<Self>) {
        if !self.state.editable
            || !self
                .state
                .comparison
                .as_ref()
                .is_some_and(|c| c.right == Revision::Worktree)
        {
            return;
        }
        let (Some(repo), Some(file)) = (&self.state.repo, self.state.current_file.as_ref()) else {
            return;
        };
        let path = file.path.clone();
        if self.editors.contains_key(&path) {
            self.edit_mode = true;
            cx.notify();
            return;
        }
        let root = repo.root.clone();
        let generation = self.state.begin(mygit_gpui::localized_format!(
            "正在加载编辑器 {path}…",
            "Loading editor for {path}…"
        ));
        self.pending.cancel();
        self.pending = Default::default();
        tasks::run(
            cx,
            generation,
            self.pending.clone(),
            move || mygit_gpui::editor::Buffer::load(&root.join(&path)),
            |this, mut buffer, cx| {
                buffer.select_matching_document(
                    &this.state.diff.right_document,
                    &this.state.text_selection,
                );
                let Some(file) = this.state.current_file.clone() else {
                    return;
                };
                let font = this.state.font_family.clone();
                let size = this.state.font_size;
                let editor = cx.new(|cx| {
                    let mut editor = Editor::new(buffer, font, size, cx);
                    editor.reference = this.state.diff.left_document.clone();
                    editor.refresh(cx);
                    editor
                });
                let subscription = cx.subscribe(&editor, |this, _, event: &Changed, cx| {
                    if matches!(event, Changed::Saved) {
                        this.refresh_tree(cx);
                        this.refresh_visible_diff(cx);
                    }
                    cx.notify();
                });
                this.editors.insert(file.path.clone(), editor);
                this.editor_subscriptions.insert(file.path, subscription);
                this.edit_mode = true;
                this.state.message =
                    mygit_gpui::i18n::text("编辑器已打开，点击文本开始输入").into();
            },
        );
        cx.notify();
    }
    pub fn preview_large_file(&mut self, cx: &mut Context<Self>) {
        let (Some(repo), Some(file), Some(comparison)) = (
            &self.state.repo,
            self.state.current_file.clone(),
            self.state.comparison.clone(),
        ) else {
            return;
        };
        let root = repo.root.clone();
        let merge_sha = self
            .state
            .merge
            .as_ref()
            .map(|view| view.revisions[1].clone());
        let generation = self
            .state
            .begin(mygit_gpui::i18n::text("正在按需读取大文件（最高 20 MB）…").into());
        self.pending.cancel();
        self.pending = Default::default();
        tasks::run(
            cx,
            generation,
            self.pending.clone(),
            move || {
                if let Some(sha) = merge_sha {
                    let selection = mygit_gpui::merge::selection(&root, &sha)?;
                    let target = selection
                        .files
                        .iter()
                        .find(|f| f.path == file.path)
                        .ok_or_else(|| anyhow::anyhow!("合并文件不再存在"))?;
                    Ok((
                        None,
                        Some(mygit_gpui::merge::load(
                            &root, &selection, target, 20_000_000,
                        )?),
                    ))
                } else {
                    Ok((
                        Some(git::compare_with_limit(
                            &root,
                            &comparison,
                            &file,
                            20_000_000,
                        )?),
                        None,
                    ))
                }
            },
            |this, (diff, merge), _| {
                if let Some(merge) = merge {
                    this.state.set_merge(merge);
                } else if let Some(diff) = diff {
                    this.state.set_diff(diff);
                }
                this.remember_tab();
            },
        );
        cx.notify();
    }
    pub fn refresh_visible_diff(&mut self, cx: &mut Context<Self>) {
        if self.state.merge.is_some() {
            self.request_refresh(cx);
            return;
        }
        let (Some(repo), Some(file), Some(comparison)) = (
            &self.state.repo,
            self.state.current_file.clone(),
            self.state.comparison.clone(),
        ) else {
            return;
        };
        let root = repo.root.clone();
        let generation = self
            .state
            .begin(mygit_gpui::i18n::text("正在更新已保存 Diff…").into());
        self.pending.cancel();
        self.pending = Default::default();
        tasks::run(
            cx,
            generation,
            self.pending.clone(),
            move || git::compare(&root, &comparison, &file),
            |this, diff, _| {
                this.state.set_diff(diff);
                this.remember_tab();
            },
        );
    }
    pub fn request_restore(&mut self, block: bool, cx: &mut Context<Self>) {
        if self.write_busy
            || !self.state.editable
            || !matches!(
                self.state.mode,
                BrowseMode::Workspace | BrowseMode::Unstaged
            )
        {
            return;
        }
        let (Some(file), Some(comparison)) = (
            self.state.current_file.clone(),
            self.state.comparison.clone(),
        ) else {
            return;
        };
        if comparison.right != Revision::Worktree {
            return;
        }
        if self.is_dirty(&file.path, cx)
            || (file.old_path != file.path && self.is_dirty(&file.old_path, cx))
        {
            self.write_message =
                mygit_gpui::i18n::text("还原涉及未保存文件，请先保存或关闭编辑器修改").into();
            cx.notify();
            return;
        }
        if block && self.state.current_block.is_none() {
            self.write_message = mygit_gpui::i18n::text("请先定位要还原的差异块").into();
            cx.notify();
            return;
        }
        self.confirmation = Some(Confirmation::Restore {
            file,
            comparison,
            diff: Box::new(self.state.diff.clone()),
            block: if block {
                self.state.current_block
            } else {
                None
            },
        });
        cx.notify();
    }
    fn execute_restore(
        &mut self,
        file: FileChange,
        comparison: Comparison,
        diff: Box<Diff>,
        block: Option<usize>,
        cx: &mut Context<Self>,
    ) {
        let Some(repo) = &self.state.repo else {
            return;
        };
        let root = repo.root.clone();
        let store = self
            .settings
            .path
            .parent()
            .unwrap_or(std::path::Path::new("."))
            .join("recovery");
        self.run_write(
            mygit_gpui::i18n::text("正在保存恢复记录并还原…"),
            self.state.mode.clone(),
            false,
            move || {
                let record = if let Some(block) = block {
                    let source = git::version_content(&root, &comparison.left, &file.old_path)?
                        .map(|v| v.bytes)
                        .unwrap_or_default();
                    if source != diff.left_document.text.as_bytes() {
                        anyhow::bail!("还原来源已变化，请刷新 Diff 后重新选择块");
                    }
                    mygit_gpui::recovery::restore_block(&root, &file.path, &diff, block, &store)?
                } else {
                    let mut paths = vec![file.path];
                    if file.old_path != paths[0] {
                        paths.push(file.old_path);
                    }
                    mygit_gpui::recovery::restore_files(&root, &comparison.left, &paths, &store)?
                };
                Ok(mygit_gpui::localized_format!(
                    "已还原，index 保持原样；恢复记录：{}",
                    "Restored; index preserved. Recovery data: {}",
                    record.display()
                ))
            },
            cx,
        );
    }
    pub fn undo_restore(&mut self, cx: &mut Context<Self>) {
        if self.write_busy {
            return;
        }
        if self.editors.values().any(|e| e.read(cx).buffer.dirty()) {
            self.write_message = mygit_gpui::i18n::text("请先保存未保存的编辑，再撤销还原").into();
            cx.notify();
            return;
        }
        let Some(repo) = &self.state.repo else {
            return;
        };
        let root = repo.root.clone();
        let store = self
            .settings
            .path
            .parent()
            .unwrap_or(std::path::Path::new("."))
            .join("recovery");
        self.run_write(
            mygit_gpui::i18n::text("正在撤销最近还原…"),
            self.state.mode.clone(),
            false,
            move || {
                let record = mygit_gpui::recovery::undo_latest(&root, &store)?;
                Ok(mygit_gpui::localized_format!(
                    "已撤销还原：{}",
                    "Restore undone: {}",
                    record.display()
                ))
            },
            cx,
        );
    }
    pub fn request_close(&mut self, cx: &mut Context<Self>) -> bool {
        if self.write_busy {
            self.state.message =
                mygit_gpui::i18n::text("Git 写操作执行中，请等待完成后退出").into();
            cx.notify();
            return false;
        }
        if self.editors.values().any(|e| e.read(cx).buffer.dirty()) {
            self.confirmation = Some(Confirmation::Quit);
            cx.notify();
            false
        } else {
            true
        }
    }
    pub fn confirm_pending(&mut self, save: bool, cx: &mut Context<Self>) {
        let Some(action) = self.confirmation.clone() else {
            return;
        };
        if let Confirmation::Reset {
            target,
            mode,
            expected_head,
            expected_branch,
        } = action.clone()
        {
            self.confirmation = None;
            if save {
                self.execute_reset(target, mode, expected_head, expected_branch, cx);
            }
            return;
        }
        if let Confirmation::Restore {
            file,
            comparison,
            diff,
            block,
        } = action
        {
            self.confirmation = None;
            self.execute_restore(file, comparison, diff, block, cx);
            return;
        }
        let paths: Vec<_> = self
            .editors
            .keys()
            .filter(|path| match &action {
                Confirmation::Close(target) => *path == target,
                Confirmation::CloseOthers(keep) => Some(*path) != keep.as_ref(),
                _ => true,
            })
            .cloned()
            .collect();
        if save {
            for path in &paths {
                if let Some(editor) = self.editors.get(path)
                    && editor.read(cx).buffer.dirty()
                {
                    editor.update(cx, |editor, cx| editor.save(cx));
                }
            }
            if paths.iter().any(|path| self.is_dirty(path, cx)) {
                self.state.message =
                    mygit_gpui::i18n::text("仍有文件未保存，请处理保存错误或取消关闭").into();
                cx.notify();
                return;
            }
        }
        self.confirmation = None;
        for path in paths {
            self.editors.remove(&path);
            self.editor_subscriptions.remove(&path);
        }
        match action {
            Confirmation::Close(path) => {
                if let Some(index) = self.tabs.iter().position(|t| t.file.path == path) {
                    self.close_tab_unchecked(index, cx);
                }
            }
            Confirmation::CloseOthers(keep) => {
                if let Some(path) = keep
                    && let Some(index) = self.tabs.iter().position(|t| t.file.path == path)
                {
                    self.activate_tab(index, cx);
                    self.close_other_tabs_unchecked(false, cx);
                } else {
                    self.close_other_tabs_unchecked(true, cx);
                }
            }
            Confirmation::Load(path) => self.load_unchecked(path, cx),
            Confirmation::Quit => cx.quit(),
            Confirmation::Restore { .. } | Confirmation::Reset { .. } => {
                unreachable!("handled before editor closure")
            }
        }
        cx.notify();
    }
    pub fn toggle_file_selection(&mut self, index: usize, cx: &mut Context<Self>) {
        if let Some(file) = self.state.files.get(index)
            && !self.file_selection.remove(&file.path)
        {
            self.file_selection.insert(file.path.clone());
        }
        cx.notify();
    }
    pub fn change_index(&mut self, stage: bool, all: bool, cx: &mut Context<Self>) {
        if self.write_busy
            || !matches!(
                self.state.mode,
                BrowseMode::Workspace | BrowseMode::Staged | BrowseMode::Unstaged
            )
        {
            return;
        }
        let Some(repo) = &self.state.repo else {
            return;
        };
        let root = repo.root.clone();
        let selected: Vec<_> = self
            .state
            .files
            .iter()
            .filter(|file| {
                if self.file_selection.is_empty() {
                    self.state
                        .active_file()
                        .is_some_and(|active| active.path == file.path)
                } else {
                    self.file_selection.contains(&file.path)
                }
            })
            .collect();
        let mut paths: Vec<String> = selected
            .iter()
            .flat_map(|f| [f.path.clone(), f.old_path.clone()])
            .collect();
        paths.sort();
        paths.dedup();
        if stage
            && self
                .editors
                .iter()
                .any(|(path, e)| (all || paths.contains(path)) && e.read(cx).buffer.dirty())
        {
            self.write_message =
                mygit_gpui::i18n::text("所选文件有未保存修改，请先保存后再暂存").into();
            cx.notify();
            return;
        }
        self.run_write(
            if stage {
                mygit_gpui::i18n::text("正在暂存…")
            } else {
                mygit_gpui::i18n::text("正在取消暂存…")
            },
            if stage {
                BrowseMode::Staged
            } else {
                BrowseMode::Unstaged
            },
            false,
            move || {
                if stage {
                    git::stage(&root, &paths, all)?;
                } else {
                    git::unstage(&root, &paths, all)?;
                }
                Ok(mygit_gpui::i18n::text("index 已更新").into())
            },
            cx,
        );
    }
    pub fn toggle_compare(&mut self, cx: &mut Context<Self>) {
        self.show_compare = !self.show_compare || !self.settings.git_panel_visible;
        if self.show_compare {
            self.reveal_git_panel(cx);
        }
        if self.show_compare {
            self.hide_quick_open();
            self.hide_project_search();
            self.show_branches = false;
            self.show_history_search = false;
        }
        if self.compare_left.is_none() {
            let font = self.state.font_family.clone();
            let size = self.state.font_size;
            self.compare_left = Some(cx.new(|cx| {
                let mut e = Editor::new(
                    mygit_gpui::editor::Buffer::new("HEAD~1"),
                    font.clone(),
                    size,
                    cx,
                );
                e.compact = true;
                e
            }));
            self.compare_right = Some(cx.new(|cx| {
                let mut e = Editor::new(mygit_gpui::editor::Buffer::new("HEAD"), font, size, cx);
                e.compact = true;
                e
            }));
        }
        cx.notify();
    }
    pub fn compare_inputs(&mut self, cx: &mut Context<Self>) {
        let (Some(repo), Some(left), Some(right)) =
            (&self.state.repo, &self.compare_left, &self.compare_right)
        else {
            return;
        };
        let root = repo.root.clone();
        let left = left.read(cx).buffer.text().to_owned();
        let right = right.read(cx).buffer.text().to_owned();
        let generation = self
            .state
            .begin(mygit_gpui::i18n::text("正在解析比较版本…").into());
        self.pending.cancel();
        self.pending = Default::default();
        tasks::run(
            cx,
            generation,
            self.pending.clone(),
            move || {
                Ok(Comparison {
                    left: git::resolve_revision(&root, &left)?,
                    right: git::resolve_revision(&root, &right)?,
                })
            },
            |this, comparison, cx| this.select_mode(BrowseMode::Compare(comparison), cx),
        );
        cx.notify();
    }
    pub fn compare_selected_worktree(&mut self, cx: &mut Context<Self>) {
        let Some(detail) = &self.state.detail else {
            return;
        };
        self.select_mode(
            BrowseMode::Compare(Comparison {
                left: Revision::Commit(detail.sha.clone()),
                right: Revision::Worktree,
            }),
            cx,
        );
    }
    pub fn toggle_commit(&mut self, cx: &mut Context<Self>) {
        if self.show_commit && self.settings.git_panel_visible {
            self.hide_commit();
        } else {
            self.reveal_git_panel(cx);
            self.show_commit = true;
        }
        if self.show_commit {
            self.hide_quick_open();
            self.hide_project_search();
            self.show_branches = false;
            self.show_history_search = false;
        }
        if self.commit_editor.is_none() {
            let font = self.state.font_family.clone();
            let size = self.state.font_size;
            let text = self
                .state
                .repo
                .as_ref()
                .map(|r| self.settings.draft_for(&r.root))
                .unwrap_or_default();
            let editor =
                cx.new(|cx| Editor::new(mygit_gpui::editor::Buffer::new(&text), font, size, cx));
            cx.subscribe(&editor, |this, editor, _: &Changed, cx| {
                if let Some(repo) = &this.state.repo {
                    this.settings.draft = Some((
                        repo.root.to_string_lossy().into(),
                        editor.read(cx).buffer.text().into(),
                    ));
                    this.save_settings();
                }
            })
            .detach();
            self.commit_editor = Some(editor);
        }
        cx.notify();
    }
    pub fn commit(&mut self, cx: &mut Context<Self>) {
        if self.write_busy {
            return;
        }
        let (Some(repo), Some(editor)) = (&self.state.repo, &self.commit_editor) else {
            return;
        };
        let root = repo.root.clone();
        let message = editor.read(cx).buffer.text().to_owned();
        self.run_write(
            mygit_gpui::i18n::text("正在提交暂存内容…"),
            BrowseMode::Workspace,
            true,
            move || git::commit_index(&root, &message),
            cx,
        );
    }
    fn run_write(
        &mut self,
        label: &str,
        mode: BrowseMode,
        clear_message: bool,
        job: impl FnOnce() -> anyhow::Result<String> + Send + 'static,
        cx: &mut Context<Self>,
    ) {
        if self.write_busy {
            return;
        }
        if self.state.repo.is_none() {
            return;
        }
        let submitted_message = self
            .commit_editor
            .as_ref()
            .map(|e| e.read(cx).buffer.text().to_owned());
        let epoch = self.repository_epoch;
        self.refresh_pending.cancel();
        self.refresh_pending = Default::default();
        self.refresh_serial += 1;
        self.refresh_running = false;
        self.pending.cancel();
        self.state.generation += 1;
        self.state.loading = false;
        self.ai.reset();
        self.write_busy = true;
        self.write_message = label.into();
        self.write_progress = Default::default();
        self.write_progress_text.clear();
        let progress = self.write_progress.clone();
        self.write_pending = Default::default();
        let token = self.write_pending.clone();
        let task = cx.background_executor().spawn(async move {
            mygit_gpui::process::with_progress(progress, || mygit_gpui::process::scope(token, job))
        });
        cx.spawn(async move |this, cx| {
            let result = task.await;
            let _ = this.update(cx, |this, cx| {
                this.write_busy = false;
                this.write_progress_text.clear();
                if this.repository_epoch != epoch {
                    cx.notify();
                    return;
                }
                let succeeded = result.is_ok();
                this.write_message = mygit_gpui::process::display_diagnostic(match result {
                    Ok(message) => message,
                    Err(error) => {
                        mygit_gpui::localized_format!(
                            "Git 操作失败：{error:#}",
                            "Git operation failed: {error:#}"
                        )
                    }
                });
                this.notify_result(
                    if succeeded {
                        mygit_gpui::notifications::Kind::Success
                    } else {
                        mygit_gpui::notifications::Kind::Error
                    },
                    this.write_message.clone(),
                    cx,
                );
                if succeeded
                    && clear_message
                    && let Some(editor) = &this.commit_editor
                    && submitted_message.as_deref() == Some(editor.read(cx).buffer.text())
                {
                    editor.update(cx, |e, cx| {
                        e.buffer = mygit_gpui::editor::Buffer::new("");
                        e.refresh(cx);
                    });
                }
                for editor in this.editors.values() {
                    if !editor.read(cx).buffer.dirty() {
                        editor.update(cx, |e, cx| e.reload(cx));
                    }
                }
                if this.state.mode != mode {
                    this.select_mode(mode, cx);
                }
                this.request_refresh(cx);
                cx.notify();
            });
        })
        .detach();
        cx.notify();
    }
    pub fn refresh_tree(&mut self, cx: &mut Context<Self>) {
        let Some(repo) = &self.state.repo else {
            return;
        };
        let root = repo.root.clone();
        let expanded = self.tree.expanded.clone();
        self.tree_pending.cancel();
        self.tree_pending = Default::default();
        let token = self.tree_pending.clone();
        self.tree_epoch += 1;
        let epoch = self.tree_epoch;
        self.tree_loading = true;
        self.tree_error = None;
        let task = cx.background_executor().spawn(async move {
            mygit_gpui::process::scope(token, || mygit_gpui::workspace::read(&root, &expanded))
        });
        cx.spawn(async move |this, cx| {
            let result = task.await;
            let _ = this.update(cx, |this, cx| {
                if this.tree_epoch != epoch {
                    return;
                }
                this.tree_loading = false;
                match result {
                    Ok(children) => {
                        this.tree.children = children;
                        if let Some(path) = this.quick.reveal.take()
                            && this.tree.selected.as_ref() == Some(&path)
                            && let Some(row) = this
                                .tree
                                .rows()
                                .iter()
                                .position(|(entry, _)| entry.path == path)
                        {
                            this.files_scroll
                                .scroll_to_item(row, ScrollStrategy::Center);
                        }
                    }
                    Err(e) => this.tree_error = Some(format!("{e:#}")),
                }
                cx.notify();
            });
        })
        .detach();
        cx.notify();
    }
    pub fn choose_tree(
        &mut self,
        entry: mygit_gpui::workspace::Entry,
        window: &mut Window,
        cx: &mut Context<Self>,
    ) {
        window.focus(if self.settings.files_visible {
            &self.files_focus
        } else {
            &self.focus
        });
        cx.activate(true);
        self.tree.selected = Some(entry.path.clone());
        if entry.directory {
            if !self.tree.expanded.remove(&entry.path) {
                self.tree.expanded.insert(entry.path);
            }
            self.refresh_tree(cx);
        } else {
            self.open_workspace_file(entry.path, cx);
        }
        cx.notify();
    }
    pub fn open_workspace_file(&mut self, path: String, cx: &mut Context<Self>) {
        self.open_workspace_target(path, None, cx);
    }
    pub fn open_workspace_hit(&mut self, hit: mygit_gpui::search::Hit, cx: &mut Context<Self>) {
        self.open_workspace_target(hit.path.clone(), Some(hit), cx);
    }
    fn open_workspace_target(
        &mut self,
        path: String,
        hit: Option<mygit_gpui::search::Hit>,
        cx: &mut Context<Self>,
    ) {
        self.hide_quick_open();
        self.hide_project_search();
        let Some(repo) = &self.state.repo else {
            return;
        };
        let root = repo.root.clone();
        self.capture_tab();
        let previous = self
            .tabs
            .iter()
            .find(|t| t.file.path == path && t.comparison.right == Revision::Worktree)
            .cloned();
        self.active_tab = None;
        self.state.selected = None;
        self.edit_mode = false;
        self.state.detail = None;
        self.state.editable = true;
        self.state.current_file = Some(FileChange {
            path: path.clone(),
            old_path: path.clone(),
            status: "M".into(),
        });
        self.state.clear_diff();
        self.line_layouts.clear();
        self.dragging = false;
        self.diff_scroll = UniformListScrollHandle::new();
        let generation = self.state.begin(mygit_gpui::localized_format!(
            "正在打开 {path}…",
            "Opening {path}…"
        ));
        self.pending.cancel();
        self.pending = Default::default();
        tasks::run(
            cx,
            generation,
            self.pending.clone(),
            move || {
                let (comparison, file) = git::workspace_file(&root, &path)?;
                let diff = git::compare(&root, &comparison, &file)?;
                let location = hit.map(|hit| {
                    let line = hit.line;
                    (
                        line,
                        match &diff.message {
                            Some(message) => Err(mygit_gpui::localized_format!(
                                "{message}；请使用文件预览入口",
                                "{message}; use the file preview action"
                            )),
                            None => hit
                                .locate(&diff.right_document)
                                .map_err(|error| format!("{error:#}")),
                        },
                    )
                });
                Ok((comparison, file, diff, location))
            },
            move |this, (comparison, file, diff, location), cx| {
                this.state.comparison = Some(comparison);
                this.state.current_file = Some(file);
                this.state.set_diff(diff);
                if let Some(previous) = &previous
                    && this.state.restore_positions(previous)
                {
                    this.diff_scroll = this
                        .tab_scroll
                        .get(&previous.file.path)
                        .cloned()
                        .unwrap_or_default();
                }
                let navigate_editor = location.as_ref().is_some_and(|(_, result)| result.is_ok());
                if let Some((line, location)) = location {
                    match location {
                        Ok(range) => {
                            this.state.text_selection = mygit_gpui::text::TextSelection {
                                side: Side::Right,
                                anchor: range.start,
                                head: range.end,
                            };
                            if let Some(row) = this
                                .state
                                .diff
                                .rows
                                .iter()
                                .position(|row| row.right_no == Some(line))
                            {
                                this.diff_scroll.scroll_to_item(
                                    this.state.view_row(row, Side::Right),
                                    ScrollStrategy::Center,
                                );
                            }
                        }
                        Err(error) => {
                            this.state.message = mygit_gpui::localized_format!(
                                "文件已打开，但无法定位：{error}",
                                "File opened, but unable to navigate: {error}"
                            )
                        }
                    }
                }
                this.remember_tab();
                if !this.settings.git_panel_visible && this.state.diff.message.is_none() {
                    this.open_current_editor(cx);
                }
                if !this.settings.git_panel_visible
                    && navigate_editor
                    && let Some(editor) = this.current_editor()
                {
                    let moved = editor.update(cx, |editor, cx| {
                        editor.select_matching_document(
                            &this.state.diff.right_document,
                            &this.state.text_selection,
                            cx,
                        )
                    });
                    if !moved {
                        this.state.message =
                            mygit_gpui::i18n::text("工作区内容已变化或正在输入，保留编辑器位置")
                                .into();
                    }
                }
            },
        );
        cx.notify();
    }
    pub fn load_more_history(&mut self, cx: &mut Context<Self>) {
        if self.history_query.is_some() {
            self.load_more_filtered(cx);
            return;
        }
        let Some(repo) = &self.state.repo else {
            return;
        };
        if self.history_loading || !repo.history_more {
            return;
        }
        let Some(tip) = repo.history_tip.clone() else {
            return;
        };
        let root = repo.root.clone();
        let skip = repo.commits.len();
        let epoch = self.repository_epoch;
        let query_generation = self.history_query_generation;
        self.history_loading = true;
        self.history_failed = false;
        cx.notify();
        let expected_tip = tip.clone();
        let token = self.history_pending.clone();
        let task = cx.background_executor().spawn(async move {
            mygit_gpui::process::scope(token, || git::history_page(&root, &tip, skip))
        });
        cx.spawn(async move |this, cx| {
            let result = task.await;
            let _ = this.update(cx, |this, cx| {
                if this.repository_epoch != epoch
                    || this.history_query_generation != query_generation
                {
                    return;
                }
                if !this.state.repo.as_ref().is_some_and(|repo| {
                    repo.history_tip.as_ref() == Some(&expected_tip) && repo.commits.len() == skip
                }) {
                    return;
                }
                this.history_loading = false;
                match result {
                    Ok(page) => {
                        if let Some(repo) = &mut this.state.repo {
                            repo.commits.extend(page.commits);
                            repo.history_more = page.more;
                        }
                    }
                    Err(e) => {
                        this.history_failed = true;
                        this.state.message = mygit_gpui::localized_format!(
                            "加载历史失败：{e:#}",
                            "Unable to load history: {e:#}"
                        );
                    }
                }
                cx.notify();
            });
        })
        .detach();
    }
    pub fn cancel_task(&mut self, cx: &mut Context<Self>) {
        if self.show_notifications {
            self.show_notifications = false;
            self.restore_main_focus = true;
            cx.notify();
            return;
        }
        if self.write_busy {
            self.state.message = mygit_gpui::i18n::text("Git 写操作执行中，请等待结果").into();
            cx.notify();
            return;
        }
        if self.confirmation.take().is_some() {
            cx.notify();
            return;
        }
        if self.ai.loading || self.ai.applying {
            self.ai.message = mygit_gpui::i18n::text("AI 任务已取消，手动草稿保留").into();
        }
        if self.search.loading {
            self.search.error =
                Some(mygit_gpui::i18n::text("已取消搜索，可修改查询或点击重新搜索重试").into());
        }
        if self.quick.indexing || self.quick.searching {
            self.quick.error =
                Some(mygit_gpui::i18n::text("已取消文件定位任务，可刷新索引重试").into());
        }
        self.ai.cancel();
        self.quick.cancel();
        self.search.cancel();
        self.blame_pending.cancel();
        self.blame_epoch += 1;
        if self.blame_loading {
            self.blame_error = mygit_gpui::i18n::text("已取消 Blame，可隐藏后重新显示重试").into();
        }
        self.blame_loading = false;
        self.blame_detail_pending.cancel();
        self.blame_detail_serial += 1;
        self.blame_detail_loading = None;
        self.pending.cancel();
        self.history_pending.cancel();
        self.history_pending = Default::default();
        self.tree_pending.cancel();
        self.tree_epoch += 1;
        self.tree_loading = false;
        self.refresh_pending.cancel();
        self.refresh_pending = Default::default();
        self.refresh_serial += 1;
        self.refresh_running = false;
        self.refresh_requested = false;
        self.repository_epoch += 1;
        self.history_loading = false;
        self.history_failed = true;
        self.history_search_pending = false;
        self.state.generation += 1;
        self.state.loading = false;
        self.state.message = mygit_gpui::i18n::text("已取消，可刷新或重新选择").into();
        cx.notify();
    }
    pub fn choose_history(&mut self, index: usize, window: &mut Window, cx: &mut Context<Self>) {
        let Some(commit) = self.history_commits().get(index) else {
            return;
        };
        let sha = commit.sha.clone();
        self.history_cursor = Some(index);
        self.reveal_git_panel(cx);
        window.focus(&self.history_focus);
        cx.activate(true);
        self.history_scroll
            .scroll_to_item(index, ScrollStrategy::Center);
        self.select_mode(BrowseMode::History(sha), cx);
    }
    pub fn list_move(&mut self, forward: bool, window: &mut Window, cx: &mut Context<Self>) {
        if self.settings.git_panel_visible
            && self.show_branches
            && self.branch_focus.is_focused(window)
        {
            self.move_branch(forward, cx);
        } else if self.settings.git_panel_visible && self.history_focus.is_focused(window) {
            let count = self.history_commits().len();
            if count == 0 {
                return;
            }
            let index = match self.history_cursor {
                None => 0,
                Some(i) => {
                    if forward {
                        (i + 1).min(count - 1)
                    } else {
                        i.saturating_sub(1)
                    }
                }
            };
            self.choose_history(index, window, cx);
        } else if self.files_focus.is_focused(window) {
            if self.showing_tree() {
                let rows = self.tree.rows();
                if rows.is_empty() {
                    return;
                }
                let current = rows
                    .iter()
                    .position(|(e, _)| Some(&e.path) == self.tree.selected.as_ref())
                    .unwrap_or(0);
                let next = if forward {
                    (current + 1).min(rows.len() - 1)
                } else {
                    current.saturating_sub(1)
                };
                self.tree.selected = Some(rows[next].0.path.clone());
                self.files_scroll
                    .scroll_to_item(next, ScrollStrategy::Center);
                cx.notify();
                return;
            }
            if self.state.files.is_empty() {
                return;
            }
            let index = match self.state.selected {
                None => 0,
                Some(i) => {
                    if forward {
                        (i + 1).min(self.state.files.len() - 1)
                    } else {
                        i.saturating_sub(1)
                    }
                }
            };
            self.files_scroll
                .scroll_to_item(index, ScrollStrategy::Center);
            self.select_file(index, cx);
        }
    }
    pub fn list_enter(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        if self.settings.git_panel_visible
            && self.show_branches
            && self.branch_focus.is_focused(window)
        {
            self.switch_branch(cx);
        } else if self.settings.git_panel_visible && self.history_focus.is_focused(window) {
            window.focus(if self.settings.files_visible {
                &self.files_focus
            } else {
                &self.focus
            });
        } else if self.files_focus.is_focused(window) {
            if self.showing_tree()
                && let Some((entry, _)) = self
                    .tree
                    .rows()
                    .into_iter()
                    .find(|(e, _)| Some(&e.path) == self.tree.selected.as_ref())
            {
                self.choose_tree(entry, window, cx);
                return;
            }
            window.focus(&self.focus);
        }
        cx.notify();
    }
    pub fn cycle_focus(&mut self, reverse: bool, window: &mut Window, cx: &mut Context<Self>) {
        let mut handles = vec![];
        if self.settings.git_panel_visible {
            handles.push(self.history_focus.clone());
        }
        if self.settings.files_visible {
            handles.push(self.files_focus.clone());
        }
        if !self.settings.git_panel_visible
            && let Some(editor) = self.current_editor()
        {
            handles.push(editor.read(cx).focus.clone());
        } else {
            handles.push(self.focus.clone());
        }
        if self.settings.git_panel_visible && self.show_branches {
            handles.push(self.branch_focus.clone());
        }
        let index = handles
            .iter()
            .position(|focus| focus.is_focused(window))
            .unwrap_or(handles.len() - 1);
        let next = (index + if reverse { handles.len() - 1 } else { 1 }) % handles.len();
        window.focus(&handles[next]);
        cx.notify();
    }
    pub fn navigate(&mut self, forward: bool, cx: &mut Context<Self>) {
        if !self.settings.git_panel_visible || self.show_notifications {
            return;
        }
        if let Some(row) = self.state.navigate(forward) {
            self.diff_scroll.scroll_to_item_strict(
                if self.state.merge.is_some() {
                    row
                } else {
                    self.state.view_row(row, Side::Left)
                },
                ScrollStrategy::Center,
            );
            cx.notify();
        }
    }
    pub fn mouse_down(
        &mut self,
        side: Side,
        row: usize,
        event: &MouseDownEvent,
        window: &mut Window,
        cx: &mut Context<Self>,
    ) {
        let Some(hit) = self.line_layouts.get(&(side, row)) else {
            return;
        };
        let offset = hit.offset(event.position.x);
        self.state.text_selection.point(
            side,
            offset,
            event.modifiers.shift,
            self.state.diff.document(side),
        );
        self.dragging = true;
        self.drag_position = Some(event.position);
        self.drag_epoch += 1;
        let epoch = self.drag_epoch;
        let generation = self.state.generation;
        cx.spawn(async move |this, cx| {
            loop {
                cx.background_executor()
                    .timer(std::time::Duration::from_millis(50))
                    .await;
                let keep_running = this.update(cx, |this, cx| {
                    if !this.dragging
                        || this.drag_epoch != epoch
                        || this.state.generation != generation
                    {
                        return false;
                    }
                    let Some(position) = this.drag_position else {
                        return false;
                    };
                    let side = this.state.text_selection.side;
                    let mut visible: Vec<_> = this
                        .line_layouts
                        .values()
                        .filter(|hit| hit.side == side && hit.bounds.size.height > px(0.))
                        .collect();
                    visible.sort_by_key(|hit| hit.view_row);
                    let target = match (visible.first(), visible.last()) {
                        (Some(first), Some(_)) if position.y < first.bounds.top() => first
                            .view_row
                            .checked_sub(1)
                            .map(|row| (row, ScrollStrategy::Top)),
                        (_, Some(last))
                            if position.y > last.bounds.bottom()
                                && last.view_row + 1 < this.state.view_count() =>
                        {
                            Some((last.view_row + 1, ScrollStrategy::Bottom))
                        }
                        _ => None,
                    };
                    if let Some((row, strategy)) = target {
                        this.diff_scroll.scroll_to_item_strict(row, strategy);
                        this.extend_selection(position, cx);
                        cx.notify();
                    }
                    true
                });
                if !keep_running.is_ok_and(|value| value) {
                    break;
                }
            }
        })
        .detach();
        window.focus(&self.focus);
        cx.activate(true);
        cx.notify();
    }
    pub fn mouse_move(
        &mut self,
        event: &MouseMoveEvent,
        _window: &mut Window,
        cx: &mut Context<Self>,
    ) {
        if !self.dragging {
            return;
        }
        if !event.dragging() {
            self.dragging = false;
            return;
        }
        self.drag_position = Some(event.position);
        self.extend_selection(event.position, cx);
    }
    fn extend_selection(&mut self, position: Point<Pixels>, cx: &mut Context<Self>) {
        let side = self.state.text_selection.side;
        let hit = self
            .line_layouts
            .values()
            .filter(|hit| hit.side == side && hit.bounds.size.height > px(0.))
            .min_by(|a, b| {
                fn distance(hit: &LineHit, y: Pixels) -> Pixels {
                    if y < hit.bounds.top() {
                        hit.bounds.top() - y
                    } else if y > hit.bounds.bottom() {
                        y - hit.bounds.bottom()
                    } else {
                        px(0.)
                    }
                }
                distance(a, position.y)
                    .partial_cmp(&distance(b, position.y))
                    .unwrap_or(std::cmp::Ordering::Equal)
            });
        if let Some(hit) = hit {
            let offset = hit.offset(position.x);
            self.state
                .text_selection
                .point(side, offset, true, self.state.diff.document(side));
            cx.notify();
        }
    }
    pub fn copy_text(&mut self, cx: &mut Context<Self>) {
        if self.show_notifications {
            if let Some(notice) = self.notifications.entries().front() {
                self.copy_notification(notice.id, cx);
            }
            return;
        }
        if !self.settings.git_panel_visible || self.show_notifications {
            return;
        }
        if let Some(text) = self
            .state
            .text_selection
            .copy(self.state.diff.document(self.state.text_selection.side))
        {
            cx.write_to_clipboard(ClipboardItem::new_string(text));
        }
    }
    pub fn select_all_text(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        if !self.settings.git_panel_visible || self.show_notifications {
            return;
        }
        self.state
            .text_selection
            .select_all(self.state.diff.document(self.state.text_selection.side));
        window.focus(&self.focus);
        cx.activate(true);
        cx.notify();
    }
    pub fn move_cursor(
        &mut self,
        motion: Motion,
        extend: bool,
        window: &mut Window,
        cx: &mut Context<Self>,
    ) {
        if !self.settings.git_panel_visible || self.show_notifications {
            return;
        }
        let side = self.state.text_selection.side;
        self.state
            .text_selection
            .move_cursor(self.state.diff.document(side), motion, extend);
        let row = self
            .state
            .diff
            .row_for_offset(side, self.state.text_selection.head);
        self.diff_scroll
            .scroll_to_item(self.state.view_row(row, side), ScrollStrategy::Center);
        window.focus(&self.focus);
        cx.notify();
    }
    pub fn save_settings(&mut self) {
        self.settings.font_size = self.state.font_size;
        self.settings.font_family = self.state.font_family.clone();
        if let Err(e) = self.settings.save() {
            self.state.message = mygit_gpui::localized_format!(
                "无法保存设置：{e:#}",
                "Unable to save settings: {e:#}"
            );
        }
    }
    pub fn cycle_font(&mut self, cx: &mut Context<Self>) {
        self.state.font_family = match self.state.font_family.as_str() {
            "Menlo" => "Courier New",
            "Courier New" => "monospace",
            _ => "Menlo",
        }
        .into();
        self.update_editor_fonts(cx);
        self.save_settings();
        cx.notify();
    }
    pub fn resize_panel(&mut self, history: bool, increase: bool, cx: &mut Context<Self>) {
        let width = if history {
            &mut self.settings.history_width
        } else {
            &mut self.settings.files_width
        };
        *width = (*width + if increase { 20. } else { -20. })
            .clamp(if history { 160. } else { 120. }, 600.);
        self.save_settings();
        cx.notify();
    }
    pub fn toggle_unified(&mut self, cx: &mut Context<Self>) {
        self.capture_tab();
        self.state.unified = !self.state.unified;
        self.tab_scroll.clear();
        self.dragging = false;
        self.line_layouts.clear();
        self.diff_scroll = UniformListScrollHandle::new();
        let row = self
            .state
            .current_block
            .and_then(|i| self.state.diff.blocks.get(i))
            .map(|b| b.start)
            .unwrap_or_else(|| {
                self.state.diff.row_for_offset(
                    self.state.text_selection.side,
                    self.state.text_selection.head,
                )
            });
        self.diff_scroll.scroll_to_item_strict(
            self.state.view_row(row, self.state.text_selection.side),
            ScrollStrategy::Center,
        );
        cx.notify();
    }
    pub fn change_font_size(&mut self, increase: bool, cx: &mut Context<Self>) {
        self.state.font_size =
            (self.state.font_size + if increase { 1. } else { -1. }).clamp(10., 22.);
        self.diff_scroll = UniformListScrollHandle::new();
        self.update_editor_fonts(cx);
        self.save_settings();
        cx.notify();
    }
    pub fn horizontal_delta(&mut self, delta: f32, window: &Window, cx: &mut Context<Self>) {
        let width = self
            .diff_bounds
            .map(|b| f32::from(b.size.width))
            .unwrap_or_else(|| {
                f32::from(window.viewport_size().width)
                    - self.visible_history_width
                    - self.visible_files_width
            });
        let visible = if self.state.merge.is_some() {
            width / 3. - 140. - if self.show_blame { 100. } else { 0. }
        } else if self.state.unified {
            width - 122.
        } else {
            width / 2. - 52.
        };
        let limit = ((self.state.panel_width - 68.) * self.state.font_size / 12. - visible).max(0.);
        self.state.horizontal_offset = (self.state.horizontal_offset + delta).clamp(0., limit);
        cx.notify();
    }
    pub fn move_horizontal(&mut self, forward: bool, window: &Window, cx: &mut Context<Self>) {
        self.horizontal_delta(if forward { 200. } else { -200. }, window, cx);
    }
}
impl Render for MyGit {
    fn render(&mut self, window: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        if self.settings.git_panel_visible {
            self.ensure_blame(cx);
        }
        let commits = self.history_commits();
        let graph_key = (
            commits.len(),
            commits.first().map(|c| c.sha.clone()).unwrap_or_default(),
            commits.last().map(|c| c.sha.clone()).unwrap_or_default(),
            self.history_query_generation,
            self.repository_epoch,
        );
        if self.history_graph_key.as_ref() != Some(&graph_key) {
            self.history_graph = mygit_gpui::graph::layout(
                commits,
                self.history_query.as_ref().is_some_and(|q| {
                    !q.text.is_empty()
                        || !q.author.is_empty()
                        || !q.since.is_empty()
                        || !q.until.is_empty()
                        || q.path.is_some()
                }),
            );
            self.history_graph_key = Some(graph_key);
        }
        self.line_layouts.clear();
        let entity = cx.entity().downgrade();
        let scroll_listener = canvas(
            |_, _, _| (),
            move |_, _, window, _| {
                window.on_mouse_event(move |event: &ScrollWheelEvent, phase, window, cx| {
                    if phase != DispatchPhase::Capture {
                        return;
                    }
                    let _ = entity.update(cx, |this, cx| {
                        if !this.settings.git_panel_visible
                            || this.show_notifications
                            || this.confirmation.is_some()
                            || this.current_editor().is_some()
                            || !this
                                .diff_bounds
                                .is_some_and(|bounds| bounds.contains(&event.position))
                        {
                            return;
                        }
                        let delta = event.delta.pixel_delta(px(this.state.font_size + 12.));
                        let horizontal = if event.modifiers.shift && delta.x == px(0.) {
                            delta.y
                        } else {
                            delta.x
                        };
                        if horizontal != px(0.) {
                            this.horizontal_delta(-f32::from(horizontal), window, cx);
                            cx.stop_propagation();
                        }
                    });
                });
            },
        )
        .absolute()
        .size_full();
        if std::mem::take(&mut self.restore_main_focus) || self.confirmation.is_some() {
            window.focus(&self.focus);
        }
        let available = (f32::from(window.viewport_size().width) - 420.).max(280.);
        let requested_width = if self.settings.git_panel_visible {
            self.settings.history_width
        } else {
            0.
        } + if self.settings.files_visible {
            self.settings.files_width
        } else {
            0.
        };
        let factor = (available / requested_width.max(1.)).min(1.);
        self.visible_history_width = (self.settings.history_width * factor).max(160.);
        self.visible_files_width = (self.settings.files_width * factor).max(120.);
        div()
            .relative()
            .child(scroll_listener)
            .key_context("MyGit")
            .on_action(cx.listener(|this, _: &Quit, _, cx| {
                if this.request_close(cx) {
                    cx.quit();
                }
            }))
            .on_action(cx.listener(|this, _: &ViewWorkspace, _, cx| {
                this.reveal_git_panel(cx);
                this.select_mode(BrowseMode::Workspace, cx)
            }))
            .on_action(cx.listener(|this, _: &ViewStaged, _, cx| {
                this.reveal_git_panel(cx);
                this.select_mode(BrowseMode::Staged, cx);
            }))
            .on_action(cx.listener(|this, _: &ViewUnstaged, _, cx| {
                this.reveal_git_panel(cx);
                this.select_mode(BrowseMode::Unstaged, cx)
            }))
            .on_action(cx.listener(|this, _: &StageSelected, _, cx| {
                if this.confirmation.is_none() {
                    this.change_index(true, false, cx);
                }
            }))
            .on_action(cx.listener(|this, _: &UnstageSelected, _, cx| {
                if this.confirmation.is_none() {
                    this.change_index(false, false, cx);
                }
            }))
            .on_action(cx.listener(|this, _: &StageAll, _, cx| {
                if this.confirmation.is_none() {
                    this.change_index(true, true, cx);
                }
            }))
            .on_action(cx.listener(|this, _: &UnstageAll, _, cx| {
                if this.confirmation.is_none() {
                    this.change_index(false, true, cx);
                }
            }))
            .on_action(cx.listener(|this, _: &ToggleCommitPanel, window, cx| {
                if this.confirmation.is_none() {
                    this.toggle_commit(cx);
                    if this.show_commit {
                        if let Some(editor) = &this.commit_editor {
                            window.focus(&editor.read(cx).focus);
                        }
                    } else {
                        window.focus(&this.focus);
                    }
                }
            }))
            .on_action(cx.listener(|this, _: &CopyCommitSha, _, cx| {
                if let Some(detail) = &this.state.detail {
                    cx.write_to_clipboard(ClipboardItem::new_string(detail.sha.clone()));
                }
            }))
            .on_action(cx.listener(|this, _: &OpenRepo, _, cx| this.open(cx)))
            .on_action(cx.listener(|this, _: &RefreshRepo, _, cx| {
                if this.state.repo.is_some() {
                    this.request_refresh(cx);
                } else if let Some(path) = this.last_path.clone() {
                    this.load(path, cx);
                }
            }))
            .on_action(cx.listener(|this, _: &ToggleProjectSearch, window, cx| {
                this.toggle_project_search(window, cx)
            }))
            .on_action(
                cx.listener(|this, _: &ProjectSearchUp, _, cx| this.project_search_move(false, cx)),
            )
            .on_action(
                cx.listener(|this, _: &ProjectSearchDown, _, cx| {
                    this.project_search_move(true, cx)
                }),
            )
            .on_action(cx.listener(|this, _: &ProjectSearchAccept, window, cx| {
                this.accept_project_search(window, cx)
            }))
            .on_action(cx.listener(|this, _: &ProjectSearchDismiss, window, cx| {
                this.close_project_search(window, cx)
            }))
            .on_action(cx.listener(|this, _: &ToggleQuickOpen, window, cx| {
                this.toggle_quick_open(window, cx)
            }))
            .on_action(cx.listener(|this, _: &QuickUp, _, cx| this.quick_move(false, cx)))
            .on_action(cx.listener(|this, _: &QuickDown, _, cx| this.quick_move(true, cx)))
            .on_action(
                cx.listener(|this, _: &QuickAccept, window, cx| this.accept_quick_open(window, cx)),
            )
            .on_action(
                cx.listener(|this, _: &QuickDismiss, window, cx| this.close_quick_open(window, cx)),
            )
            .on_action(cx.listener(|this, _: &ToggleHistorySearch, window, cx| {
                this.toggle_history_search(cx);
                if this.show_history_search
                    && let Some(editor) = this.history_inputs.first()
                {
                    window.focus(&editor.read(cx).focus);
                }
            }))
            .on_action(cx.listener(|this, _: &ToggleBranches, window, cx| {
                this.toggle_branches(cx);
                if this.show_branches {
                    window.focus(&this.branch_focus);
                }
            }))
            .on_action(cx.listener(|this, _: &ToggleSettings, _, cx| {
                this.toggle_settings(cx);
            }))
            .on_action(
                cx.listener(|this, _: &ToggleNotifications, _, cx| this.toggle_notifications(cx)),
            )
            .on_action(cx.listener(|this, _: &ToggleGitPanel, window, cx| {
                this.toggle_git_panel(window, cx);
            }))
            .on_action(cx.listener(|this, _: &ToggleFilesPanel, window, cx| {
                this.toggle_files_panel(cx);
                window.focus(&this.focus);
            }))
            .on_action(cx.listener(|this, _: &CancelTask, _, cx| this.cancel_task(cx)))
            .on_action(
                cx.listener(|this, _: &FocusNext, window, cx| this.cycle_focus(false, window, cx)),
            )
            .on_action(
                cx.listener(|this, _: &FocusPrevious, window, cx| {
                    this.cycle_focus(true, window, cx)
                }),
            )
            .on_action(
                cx.listener(|this, _: &ListUp, window, cx| this.list_move(false, window, cx)),
            )
            .on_action(
                cx.listener(|this, _: &ListDown, window, cx| this.list_move(true, window, cx)),
            )
            .on_action(cx.listener(|this, _: &ListEnter, window, cx| this.list_enter(window, cx)))
            .on_mouse_move(cx.listener(Self::mouse_move))
            .on_mouse_up(
                MouseButton::Left,
                cx.listener(|this, _, _, _| this.dragging = false),
            )
            .on_mouse_up_out(
                MouseButton::Left,
                cx.listener(|this, _, _, _| this.dragging = false),
            )
            .on_action(cx.listener(|this, _: &CopyText, _, cx| this.copy_text(cx)))
            .on_action(
                cx.listener(|this, _: &SelectAllText, window, cx| this.select_all_text(window, cx)),
            )
            .on_action(cx.listener(|this, _: &NextDiff, _, cx| this.navigate(true, cx)))
            .on_action(cx.listener(|this, _: &PreviousDiff, _, cx| this.navigate(false, cx)))
            .on_action(cx.listener(|this, _: &Left, window, cx| {
                this.move_cursor(Motion::Left, false, window, cx)
            }))
            .on_action(cx.listener(|this, _: &SelectLeft, window, cx| {
                this.move_cursor(Motion::Left, true, window, cx)
            }))
            .on_action(cx.listener(|this, _: &Right, window, cx| {
                this.move_cursor(Motion::Right, false, window, cx)
            }))
            .on_action(cx.listener(|this, _: &SelectRight, window, cx| {
                this.move_cursor(Motion::Right, true, window, cx)
            }))
            .on_action(cx.listener(|this, _: &Up, window, cx| {
                this.move_cursor(Motion::Up, false, window, cx)
            }))
            .on_action(cx.listener(|this, _: &SelectUp, window, cx| {
                this.move_cursor(Motion::Up, true, window, cx)
            }))
            .on_action(cx.listener(|this, _: &Down, window, cx| {
                this.move_cursor(Motion::Down, false, window, cx)
            }))
            .on_action(cx.listener(|this, _: &SelectDown, window, cx| {
                this.move_cursor(Motion::Down, true, window, cx)
            }))
            .on_action(cx.listener(|this, _: &Home, window, cx| {
                this.move_cursor(Motion::Home, false, window, cx)
            }))
            .on_action(cx.listener(|this, _: &SelectHome, window, cx| {
                this.move_cursor(Motion::Home, true, window, cx)
            }))
            .on_action(cx.listener(|this, _: &End, window, cx| {
                this.move_cursor(Motion::End, false, window, cx)
            }))
            .on_action(cx.listener(|this, _: &SelectEnd, window, cx| {
                this.move_cursor(Motion::End, true, window, cx)
            }))
            .on_action(cx.listener(|this, _: &Start, window, cx| {
                this.move_cursor(Motion::Start, false, window, cx)
            }))
            .on_action(cx.listener(|this, _: &SelectStart, window, cx| {
                this.move_cursor(Motion::Start, true, window, cx)
            }))
            .on_action(cx.listener(|this, _: &Finish, window, cx| {
                this.move_cursor(Motion::Finish, false, window, cx)
            }))
            .on_action(cx.listener(|this, _: &SelectFinish, window, cx| {
                this.move_cursor(Motion::Finish, true, window, cx)
            }))
            .size_full()
            .flex()
            .flex_col()
            .bg(rgb(0x111722))
            .text_color(rgb(0xdce5f3))
            .text_size(px(13.))
            .child(views::toolbar(self, cx))
            .when(self.search.shown, |s| {
                s.child(views::search::pane(self, cx))
            })
            .when(self.quick.shown, |s| {
                s.child(views::quick_open::pane(self, cx))
            })
            .when(
                self.settings.git_panel_visible && self.show_history_search,
                |s| s.child(views::history::pane(self, cx)),
            )
            .when(self.settings.git_panel_visible && self.show_branches, |s| {
                s.child(views::branches::pane(self, cx))
            })
            .when(self.settings.git_panel_visible && self.show_compare, |s| {
                s.child(views::compare::pane(self, cx))
            })
            .when(self.show_settings, |s| s.child(views::settings(self, cx)))
            .child(
                div()
                    .flex()
                    .flex_1()
                    .min_h_0()
                    .when(self.settings.git_panel_visible, |s| {
                        s.child(views::sidebar::history(self, cx))
                    })
                    .when(self.settings.files_visible, |s| {
                        s.child(if self.showing_tree() {
                            views::tree::pane(self, cx).into_any_element()
                        } else {
                            views::sidebar::files(self, cx).into_any_element()
                        })
                    })
                    .child(if !self.settings.git_panel_visible {
                        views::workspace::pane(self, cx).into_any_element()
                    } else if self.state.merge.is_some() {
                        views::merge::pane(self, cx).into_any_element()
                    } else {
                        views::diff::pane(self, cx).into_any_element()
                    }),
            )
            .child(
                div()
                    .px_3()
                    .py_2()
                    .border_t_1()
                    .border_color(rgb(0x2b3545))
                    .text_color(rgb(0x92a2b9))
                    .child(format!(
                        "{}{}",
                        if self.state.loading { "◌  " } else { "" },
                        self.state.message
                    )),
            )
            .when(self.settings.git_panel_visible && self.show_commit, |s| {
                s.child(views::commit::pane(self, cx))
            })
            .when(
                self.write_busy && !self.write_progress_text.is_empty(),
                |s| {
                    let text = self
                        .write_progress_text
                        .lines()
                        .rev()
                        .take(3)
                        .collect::<Vec<_>>()
                        .into_iter()
                        .rev()
                        .collect::<Vec<_>>()
                        .join("\n");
                    s.child(div().px_3().py_1().text_color(rgb(0x92a2b9)).child(text))
                },
            )
            .when(!self.write_message.is_empty(), |s| {
                s.child(
                    div()
                        .id("operation-result")
                        .max_h(px(90.))
                        .overflow_y_scroll()
                        .flex_shrink_0()
                        .p_2()
                        .text_color(rgb(0xffd479))
                        .child(self.write_message.clone()),
                )
            })
            .when(
                self.confirmation.is_none()
                    && (self.show_notifications || self.notifications.active().is_some()),
                |s| s.child(views::notifications::pane(self, window, cx)),
            )
            .when(self.confirmation.is_some(), |s| {
                s.child(views::confirmation(self, cx))
            })
    }
}

impl Drop for MyGit {
    fn drop(&mut self) {
        self.ai.cancel();
        self.quick.cancel();
        self.search.cancel();
        self.blame_pending.cancel();
        self.blame_detail_pending.cancel();
        self.refresh_pending.cancel();
        self.pending.cancel();
        self.history_pending.cancel();
        self.tree_pending.cancel();
        self.write_pending.cancel();
    }
}
