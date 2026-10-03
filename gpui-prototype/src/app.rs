use crate::views::text_line::LineHit;
use crate::{tasks, views};
use gpui::{prelude::*, *};
use mygit_gpui::text::{Motion, Side};
use mygit_gpui::{git, model::*, state::AppState};
use std::{collections::HashMap, path::PathBuf};

actions!(
    mygit,
    [
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

pub struct MyGit {
    pub state: AppState,
    pub diff_scroll: UniformListScrollHandle,
    pub focus: FocusHandle,
    pub line_layouts: HashMap<(Side, usize), LineHit>,
    pub dragging: bool,
    pub drag_position: Option<Point<Pixels>>,
    pub drag_epoch: u64,
}
impl MyGit {
    pub fn new(cx: &mut Context<Self>) -> Self {
        Self {
            state: AppState::default(),
            diff_scroll: UniformListScrollHandle::new(),
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
        self.line_layouts.clear();
        self.dragging = false;
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
        self.line_layouts.clear();
        self.dragging = false;
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
        self.line_layouts.clear();
        self.dragging = false;
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
                    visible.sort_by_key(|hit| hit.row);
                    let target = match (visible.first(), visible.last()) {
                        (Some(first), Some(_)) if position.y < first.bounds.top() => first
                            .row
                            .checked_sub(1)
                            .map(|row| (row, ScrollStrategy::Top)),
                        (_, Some(last))
                            if position.y > last.bounds.bottom()
                                && last.row + 1 < this.state.diff.rows.len() =>
                        {
                            Some((last.row + 1, ScrollStrategy::Bottom))
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
        if let Some(text) = self
            .state
            .text_selection
            .copy(self.state.diff.document(self.state.text_selection.side))
        {
            cx.write_to_clipboard(ClipboardItem::new_string(text));
        }
    }
    pub fn select_all_text(&mut self, window: &mut Window, cx: &mut Context<Self>) {
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
        let side = self.state.text_selection.side;
        self.state
            .text_selection
            .move_cursor(self.state.diff.document(side), motion, extend);
        let row = self
            .state
            .diff
            .row_for_offset(side, self.state.text_selection.head);
        self.diff_scroll.scroll_to_item(row, ScrollStrategy::Center);
        window.focus(&self.focus);
        cx.notify();
    }
    pub fn change_font_size(&mut self, increase: bool, cx: &mut Context<Self>) {
        self.state.font_size =
            (self.state.font_size + if increase { 1. } else { -1. }).clamp(10., 22.);
        self.diff_scroll = UniformListScrollHandle::new();
        cx.notify();
    }
    pub fn move_horizontal(&mut self, forward: bool, window: &Window, cx: &mut Context<Self>) {
        let visible = ((f32::from(window.viewport_size().width) - 520.) / 2. - 52.).max(50.);
        self.state.horizontal_offset = (self.state.horizontal_offset
            + if forward { 200. } else { -200. })
        .clamp(
            0.,
            ((self.state.panel_width - 68.) * self.state.font_size / 12. + 68. - visible).max(0.),
        );
        cx.notify();
    }
}
impl Render for MyGit {
    fn render(&mut self, _window: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        self.line_layouts.clear();
        div()
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
