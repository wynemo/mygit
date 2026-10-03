use crate::{tasks, views};
use gpui::{prelude::*, *};
use mygit_gpui::{git, model::*, state::AppState};
use std::path::PathBuf;

pub struct MyGit {
    pub state: AppState,
    pub diff_scroll: UniformListScrollHandle,
}
impl MyGit {
    pub fn new() -> Self {
        Self {
            state: AppState::default(),
            diff_scroll: UniformListScrollHandle::new(),
        }
    }
    pub fn open(&mut self, cx: &mut Context<Self>) {
        let picker = cx.prompt_for_paths(PathPromptOptions {
            files: false,
            directories: true,
            multiple: false,
            prompt: Some("选择 Git 仓库".into()),
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
                    this.state.message = format!("无法打开目录选择器：{other:?}");
                    cx.notify();
                });
            }
        })
        .detach();
    }
    pub fn load(&mut self, path: PathBuf, cx: &mut Context<Self>) {
        self.state.repo = None;
        self.state.comparison = None;
        self.state.files.clear();
        self.state.selected = None;
        self.state.mode = BrowseMode::Workspace;
        self.state.clear_diff();
        self.diff_scroll = UniformListScrollHandle::new();
        let generation = self.state.begin("正在读取仓库…".into());
        cx.notify();
        tasks::run(
            cx,
            generation,
            move || git::snapshot(&path),
            |this, repo, cx| {
                this.state.repo = Some(repo);
                this.select_mode(BrowseMode::Workspace, cx);
            },
        );
    }
    pub fn select_mode(&mut self, mode: BrowseMode, cx: &mut Context<Self>) {
        let Some(repo) = &self.state.repo else {
            return;
        };
        let root = repo.root.clone();
        self.state.mode = mode.clone();
        self.state.comparison = None;
        self.state.files.clear();
        self.state.selected = None;
        self.state.clear_diff();
        let generation = self.state.begin(format!("正在读取{}…", mode.label()));
        cx.notify();
        tasks::run(
            cx,
            generation,
            move || git::selection(&root, &mode),
            |this, selection, cx| {
                this.state.comparison = Some(selection.comparison);
                this.state.files = selection.files;
                this.state.message = format!(
                    "{} · {} 个文件",
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
            &self.state.comparison,
            self.state.files.get(index),
        ) else {
            return;
        };
        let root = repo.root.clone();
        let comparison = comparison.clone();
        let file = file.clone();
        self.state.selected = Some(index);
        self.state.clear_diff();
        self.diff_scroll = UniformListScrollHandle::new();
        let generation = self.state.begin(format!("正在比较 {}…", file.path));
        cx.notify();
        tasks::run(
            cx,
            generation,
            move || git::compare(&root, &comparison, &file),
            |this, diff, _| this.state.set_diff(diff),
        );
    }
    pub fn navigate(&mut self, forward: bool, cx: &mut Context<Self>) {
        if let Some(row) = self.state.navigate(forward) {
            self.diff_scroll
                .scroll_to_item_strict(row, ScrollStrategy::Center);
            cx.notify();
        }
    }
    pub fn move_horizontal(&mut self, forward: bool, window: &Window, cx: &mut Context<Self>) {
        let visible = ((f32::from(window.viewport_size().width) - 520.) / 2. - 52.).max(50.);
        self.state.horizontal_offset = (self.state.horizontal_offset
            + if forward { 200. } else { -200. })
        .clamp(0., (self.state.panel_width - visible).max(0.));
        cx.notify();
    }
}
impl Render for MyGit {
    fn render(&mut self, _window: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        div()
            .size_full()
            .flex()
            .flex_col()
            .bg(rgb(0x111722))
            .text_color(rgb(0xdce5f3))
            .text_size(px(13.))
            .child(views::toolbar(self, cx))
            .child(
                div()
                    .flex()
                    .flex_1()
                    .min_h_0()
                    .child(views::sidebar::history(self, cx))
                    .child(views::sidebar::files(self, cx))
                    .child(views::diff::pane(self, cx)),
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
    }
}
