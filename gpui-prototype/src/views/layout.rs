//! The original window hierarchy: workspace above, Git history and details below.
use crate::{
    app::MyGit,
    views::{self, icons},
};
use gpui::{prelude::*, *};

fn splitter(axis: u8, cx: &mut Context<MyGit>) -> Stateful<Div> {
    div()
        .id(("panel-splitter", axis as usize))
        .flex_shrink_0()
        .bg(rgb(0xe9e9e9))
        .hover(|s| s.bg(rgb(0xc7c7c7)))
        .when(axis == 0, |s| {
            s.h(px(6.)).w_full().cursor(CursorStyle::ResizeUpDown)
        })
        .when(axis != 0, |s| {
            s.w(px(6.)).h_full().cursor(CursorStyle::ResizeLeftRight)
        })
        .on_mouse_down(
            MouseButton::Left,
            cx.listener(move |this, event: &MouseDownEvent, _, cx| {
                if this.confirmation.is_some() {
                    return;
                }
                let value = match axis {
                    0 => this.settings.workspace_fraction,
                    1 => this.visible_files_width,
                    _ => this.settings.history_width,
                };
                this.dragging = false;
                this.panel_drag = Some((axis, event.position, value));
                cx.stop_propagation();
            }),
        )
}

fn activity(id: &'static str, path: &'static str, label: &'static str) -> Stateful<Div> {
    div()
        .id(id)
        .size(px(24.))
        .flex()
        .items_center()
        .justify_center()
        .cursor_pointer()
        .rounded_sm()
        .hover(|s| s.bg(rgb(0xe3e3e3)))
        .child(icons::icon(path).size(px(24.)))
        .tooltip(move |_, cx| cx.new(|_| views::hints::Hint(label.into())).into())
}

pub fn body(this: &MyGit, cx: &mut Context<MyGit>) -> impl IntoElement {
    let project = !this.show_commit && !this.search.shown && !this.show_workspace_changes;
    let name = this
        .state
        .repo
        .as_ref()
        .and_then(|r| r.root.file_name())
        .map(|n| n.to_string_lossy().to_string())
        .unwrap_or_default();
    div()
        .id("main-panes")
        .flex()
        .flex_col()
        .flex_1()
        .min_h_0()
        .min_w_0()
        .child(
            div()
                .id("workspace-section")
                .flex()
                .min_h_0()
                .min_w_0()
                .overflow_hidden()
                .map(|mut s| {
                    s.style().flex_grow = Some(if this.settings.git_panel_visible {
                        this.settings.workspace_fraction
                    } else {
                        1.
                    });
                    s
                })
                .flex_basis(px(0.))
                .child(
                    div()
                        .w(px(30.))
                        .flex_shrink_0()
                        .flex()
                        .flex_col()
                        .items_center()
                        .py_2()
                        .gap_2()
                        .bg(rgb(0xf0f0f0))
                        .child(
                            activity(
                                "workspace-tree",
                                "icons/project.svg",
                                mygit_gpui::i18n::text("文件树"),
                            )
                            .when(project, |s| s.bg(rgb(0x2196f3)))
                            .on_click(cx.listener(
                                |this, _, window, cx| {
                                    this.hide_commit();
                                    this.hide_project_search();
                                    this.show_workspace_changes = false;
                                    this.settings.files_visible = true;
                                    this.save_settings();
                                    window.focus(&this.tree_focus);
                                    cx.notify();
                                },
                            )),
                        )
                        .child(
                            activity(
                                "show-commit",
                                "icons/commit_icon.svg",
                                mygit_gpui::i18n::text("提交面板"),
                            )
                            .when(this.show_commit, |s| s.bg(rgb(0x2196f3)))
                            .on_click(cx.listener(|this, _, _, cx| this.toggle_commit(cx))),
                        )
                        .child(
                            activity(
                                "activity-changes",
                                "icons/changes.svg",
                                mygit_gpui::i18n::text("全部变更"),
                            )
                            .when(this.show_workspace_changes, |s| s.bg(rgb(0x2196f3)))
                            .on_click(cx.listener(|this, _, _, cx| {
                                this.hide_commit();
                                this.hide_project_search();
                                this.show_workspace_changes = true;
                                this.settings.files_visible = true;
                                this.select_mode(mygit_gpui::model::BrowseMode::Workspace, cx);
                            })),
                        )
                        .child(
                            activity(
                                "project-search",
                                "icons/search.svg",
                                mygit_gpui::i18n::text("项目搜索"),
                            )
                            .when(this.search.shown, |s| s.bg(rgb(0x2196f3)))
                            .on_click(cx.listener(
                                |this, _, window, cx| {
                                    this.settings.files_visible = true;
                                    this.toggle_project_search(window, cx);
                                },
                            )),
                        ),
                )
                .child(div().w(px(8.)).flex_shrink_0().bg(rgb(0xececec)))
                .child(
                    div()
                        .flex()
                        .flex_col()
                        .flex_1()
                        .min_w_0()
                        .min_h_0()
                        .child(
                            div()
                                .h(px(50.))
                                .flex_shrink_0()
                                .flex()
                                .items_start()
                                .gap_1()
                                .pt_1()
                                .px_1()
                                .child(
                                    views::button("refresh", "", this.state.repo.is_some())
                                        .size(px(30.))
                                        .on_click(
                                            cx.listener(|this, _, _, cx| this.request_refresh(cx)),
                                        ),
                                )
                                .child(
                                    div()
                                        .id("quick-open")
                                        .w(px(300.))
                                        .h(px(25.))
                                        .flex()
                                        .items_center()
                                        .justify_center()
                                        .gap_1()
                                        .bg(rgb(0xd3d3d3))
                                        .cursor_pointer()
                                        .child(icons::icon("icons/search.svg"))
                                        .child(name)
                                        .on_click(cx.listener(|this, _, window, cx| {
                                            this.toggle_quick_open(window, cx)
                                        })),
                                ),
                        )
                        .child(
                            div()
                                .flex()
                                .flex_1()
                                .min_h_0()
                                .min_w_0()
                                .when(this.settings.files_visible, |s| {
                                    s.child(if this.show_commit {
                                        div()
                                            .w(px(this.visible_files_width))
                                            .min_h_0()
                                            .flex_shrink_0()
                                            .flex()
                                            .flex_col()
                                            .child(views::commit::pane(this, cx))
                                            .into_any_element()
                                    } else if this.search.shown {
                                        div()
                                            .w(px(this.visible_files_width.max(300.)))
                                            .min_h_0()
                                            .flex_shrink_0()
                                            .flex()
                                            .flex_col()
                                            .child(views::search::pane(this, cx))
                                            .into_any_element()
                                    } else if this.show_workspace_changes {
                                        div()
                                            .w(px(this.visible_files_width.max(300.)))
                                            .min_h_0()
                                            .flex_shrink_0()
                                            .flex()
                                            .flex_col()
                                            .child(views::sidebar::files(this, true, cx))
                                            .into_any_element()
                                    } else {
                                        views::tree::pane(this, cx).into_any_element()
                                    })
                                    .child(splitter(1, cx))
                                })
                                .child(if this.state.current_file.is_none() {
                                    div()
                                        .flex_1()
                                        .min_w_0()
                                        .bg(rgb(0xe8e8e8))
                                        .into_any_element()
                                } else if this.current_editor().is_some() {
                                    views::workspace::pane(this, cx).into_any_element()
                                } else if this.state.merge.is_some() {
                                    views::merge::pane(this, cx).into_any_element()
                                } else {
                                    views::diff::pane(this, cx).into_any_element()
                                }),
                        ),
                ),
        )
        .when(this.settings.git_panel_visible, |s| {
            s.child(splitter(0, cx)).child(
                div()
                    .id("git-section")
                    .flex()
                    .min_h_0()
                    .min_w_0()
                    .overflow_hidden()
                    .map(|mut s| {
                        s.style().flex_grow = Some(1. - this.settings.workspace_fraction);
                        s
                    })
                    .flex_basis(px(0.))
                    .child(views::sidebar::history(this, cx))
                    .child(splitter(2, cx))
                    .child(
                        div()
                            .flex()
                            .flex_col()
                            .flex_1()
                            .min_w_0()
                            .min_h_0()
                            .child(
                                div()
                                    .flex()
                                    .flex_col()
                                    .min_h_0()
                                    .map(|mut s| {
                                        s.style().flex_grow = Some(1.5);
                                        s
                                    })
                                    .flex_basis(px(0.))
                                    .child(views::sidebar::files(this, false, cx)),
                            )
                            .child(div().h(px(6.)).flex_shrink_0().bg(rgb(0xececec)))
                            .child(
                                div()
                                    .flex()
                                    .flex_col()
                                    .flex_1()
                                    .min_h_0()
                                    .child(views::sidebar::detail(this, cx)),
                            ),
                    ),
            )
        })
}
