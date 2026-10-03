use crate::{app::MyGit, views::button};
use gpui::{prelude::*, *};
use mygit_gpui::model::{BrowseMode, short_sha};

fn mode_button(
    this: &MyGit,
    cx: &mut Context<MyGit>,
    id: &'static str,
    label: &'static str,
    mode: BrowseMode,
) -> impl IntoElement {
    button(id, label, this.state.repo.is_some())
        .mb_1()
        .when(this.state.mode == mode, |s| s.bg(rgb(0x263b56)))
        .on_click(cx.listener(move |this, _, _, cx| this.select_mode(mode.clone(), cx)))
}
pub fn history(this: &MyGit, cx: &mut Context<MyGit>) -> impl IntoElement {
    let count = this
        .state
        .repo
        .as_ref()
        .map(|r| r.commits.len())
        .unwrap_or(0);
    div()
        .w(px(300.))
        .flex_shrink_0()
        .flex()
        .flex_col()
        .border_r_1()
        .border_color(rgb(0x2b3545))
        .child(
            div()
                .p_2()
                .flex()
                .flex_col()
                .child(mode_button(
                    this,
                    cx,
                    "workspace",
                    "全部变更 · HEAD ↔ 工作区",
                    BrowseMode::Workspace,
                ))
                .child(mode_button(
                    this,
                    cx,
                    "staged",
                    "已暂存 · HEAD ↔ index",
                    BrowseMode::Staged,
                ))
                .child(mode_button(
                    this,
                    cx,
                    "unstaged",
                    "未暂存 · index ↔ 工作区",
                    BrowseMode::Unstaged,
                )),
        )
        .child(
            div()
                .p_3()
                .text_color(rgb(0x92a2b9))
                .child("提交历史 · 最近 100 条"),
        )
        .child(
            uniform_list(
                "history",
                count,
                cx.processor(|this, range: std::ops::Range<usize>, _, cx| {
                    range
                        .map(|i| {
                            let c = &this.state.repo.as_ref().unwrap().commits[i];
                            let sha = c.sha.clone();
                            div()
                                .id(i)
                                .h(px(64.))
                                .p_2()
                                .overflow_hidden()
                                .cursor_pointer()
                                .bg(rgb(
                                    if this.state.mode == BrowseMode::History(c.sha.clone()) {
                                        0x263b56
                                    } else {
                                        0x151d29
                                    },
                                ))
                                .hover(|s| s.bg(rgb(0x253248)))
                                .child(div().whitespace_nowrap().child(c.subject.clone()))
                                .child(div().text_color(rgb(0x92a2b9)).child(format!(
                                    "{}  {}  {}",
                                    short_sha(&c.sha),
                                    c.author,
                                    c.date
                                )))
                                .on_click(cx.listener(move |this, _, _, cx| {
                                    this.select_mode(BrowseMode::History(sha.clone()), cx)
                                }))
                        })
                        .collect::<Vec<_>>()
                }),
            )
            .flex_1(),
        )
}
pub fn files(this: &MyGit, cx: &mut Context<MyGit>) -> impl IntoElement {
    div()
        .w(px(220.))
        .flex_shrink_0()
        .flex()
        .flex_col()
        .border_r_1()
        .border_color(rgb(0x2b3545))
        .child(div().p_3().child(format!(
            "{} ({})",
            this.state.mode.label(),
            this.state.files.len()
        )))
        .child(
            uniform_list(
                ("files", this.state.generation as usize),
                this.state.files.len(),
                cx.processor(|this, range: std::ops::Range<usize>, _, cx| {
                    range
                        .map(|i| {
                            let file = &this.state.files[i];
                            div()
                                .id(i)
                                .h(px(36.))
                                .px_2()
                                .py_1()
                                .overflow_hidden()
                                .whitespace_nowrap()
                                .cursor_pointer()
                                .bg(rgb(if this.state.selected == Some(i) {
                                    0x263b56
                                } else {
                                    0x111722
                                }))
                                .hover(|s| s.bg(rgb(0x253248)))
                                .child(format!("{}  {}", file.status, file.path))
                                .on_click(
                                    cx.listener(move |this, _, _, cx| this.select_file(i, cx)),
                                )
                        })
                        .collect::<Vec<_>>()
                }),
            )
            .flex_1(),
        )
}
