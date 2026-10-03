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
        .key_context("HistoryList")
        .track_focus(&this.history_focus)
        .w(px(this.visible_history_width))
        .flex_shrink_0()
        .flex()
        .flex_col()
        .min_h_0()
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
                .child(format!("提交历史 · 已加载 {count} 条")),
        )
        .child(
            uniform_list(
                "history",
                count,
                cx.processor(|this, range: std::ops::Range<usize>, _, cx| {
                    if range.end
                        >= this
                            .state
                            .repo
                            .as_ref()
                            .map(|r| r.commits.len())
                            .unwrap_or(0)
                    {
                        let entity = cx.entity().downgrade();
                        cx.defer(move |cx| {
                            let _ = entity.update(cx, |this, cx| this.load_more_history(cx));
                        });
                    }
                    range
                        .map(|i| {
                            let c = &this.state.repo.as_ref().unwrap().commits[i];
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
                                .on_click(cx.listener(move |this, _, window, cx| {
                                    this.choose_history(i, window, cx)
                                }))
                        })
                        .collect::<Vec<_>>()
                }),
            )
            .track_scroll(this.history_scroll.clone())
            .min_h_0()
            .flex_1(),
        )
        .child(
            button(
                "more-history",
                if this.history_loading {
                    "正在加载历史…"
                } else {
                    "加载更多"
                },
                !this.history_loading && this.state.repo.as_ref().is_some_and(|r| r.history_more),
            )
            .on_click(cx.listener(|this, _, _, cx| this.load_more_history(cx))),
        )
        .when_some(this.state.detail.clone(), |s, detail| {
            let sha = detail.sha.clone();
            let message = detail.message.clone();
            s.child(
                div()
                    .id("commit-detail")
                    .h(px(240.))
                    .overflow_y_scroll()
                    .p_2()
                    .border_t_1()
                    .border_color(rgb(0x2b3545))
                    .child(
                        div()
                            .flex()
                            .gap_2()
                            .child(button("copy-sha", "复制 SHA", true).on_click(cx.listener(
                                move |_, _, _, cx| {
                                    cx.write_to_clipboard(ClipboardItem::new_string(sha.clone()));
                                },
                            )))
                            .child(
                                button("copy-message", "复制信息", true).on_click(cx.listener(
                                    move |_, _, _, cx| {
                                        cx.write_to_clipboard(ClipboardItem::new_string(
                                            message.clone(),
                                        ));
                                    },
                                )),
                            ),
                    )
                    .child(div().text_color(rgb(0x92a2b9)).child(format!(
                        "{} <{}>\n{}",
                        detail.author, detail.author_email, detail.author_date
                    )))
                    .child(div().text_color(rgb(0x92a2b9)).child(format!(
                        "提交者：{} <{}>\n{}",
                        detail.committer, detail.committer_email, detail.commit_date
                    )))
                    .child(div().child(detail.references))
                    .child(div().child(format!(
                            "父提交：{}",
                            detail
                                .parents
                                .iter()
                                .map(|p| short_sha(p))
                                .collect::<Vec<_>>()
                                .join(" ")
                        )))
                    .children(
                        detail
                            .message
                            .split('\n')
                            .map(|line| div().min_h(px(18.)).child(line.to_owned()))
                            .collect::<Vec<_>>(),
                    ),
            )
        })
}
pub fn files(this: &MyGit, cx: &mut Context<MyGit>) -> impl IntoElement {
    div()
        .key_context("FilesList")
        .track_focus(&this.files_focus)
        .w(px(this.visible_files_width))
        .flex_shrink_0()
        .flex()
        .flex_col()
        .min_h_0()
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
                                .on_click(cx.listener(move |this, _, window, cx| {
                                    window.focus(&this.files_focus);
                                    cx.activate(true);
                                    this.select_file(i, cx);
                                }))
                        })
                        .collect::<Vec<_>>()
                }),
            )
            .track_scroll(this.files_scroll.clone())
            .min_h_0()
            .flex_1(),
        )
}
