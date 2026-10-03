use crate::{app::MyGit, views::button};
use gpui::{prelude::*, *};
use mygit_gpui::model::short_sha;

pub fn pane(this: &MyGit, cx: &mut Context<MyGit>) -> impl IntoElement {
    let rows = this.branch_rows();
    let selected = this
        .branch_selected
        .as_ref()
        .and_then(|reference| rows.iter().find(|b| &b.reference == reference));
    div()
        .flex()
        .flex_col()
        .p_2()
        .gap_2()
        .flex_shrink_0()
        .border_b_1()
        .border_color(rgb(0x2b3545))
        .child(
            div()
                .flex()
                .gap_2()
                .items_center()
                .child(format!("分支 · {} 个引用", rows.len()))
                .when(this.branch_filter_sha.is_some(), |s| {
                    s.child(
                        button("all-branches", "显示所有分支", true).on_click(cx.listener(
                            |this, _, _, cx| {
                                this.branch_filter_sha = None;
                                cx.notify();
                            },
                        )),
                    )
                })
                .child(
                    button(
                        "switch-branch",
                        if selected.is_some_and(|b| b.remote) {
                            "建立跟踪并切换"
                        } else {
                            "切换选中分支"
                        },
                        !this.write_busy && selected.is_some(),
                    )
                    .on_click(cx.listener(|this, _, _, cx| this.switch_branch(cx))),
                )
                .child(button("close-branches", "关闭", true).on_click(cx.listener(
                    |this, _, _, cx| {
                        this.show_branches = false;
                        cx.notify();
                    },
                ))),
        )
        .child(
            div()
                .key_context("BranchList")
                .track_focus(&this.branch_focus)
                .child(
                    uniform_list(
                        "branch-list",
                        rows.len(),
                        cx.processor(|this, range: std::ops::Range<usize>, _, cx| {
                            let rows = this.branch_rows();
                            range
                                .filter_map(|index| {
                                    rows.get(index).map(|branch| {
                                        let reference = branch.reference.clone();
                                        div()
                                            .id(index)
                                            .h(px(28.))
                                            .px_2()
                                            .flex()
                                            .items_center()
                                            .gap_2()
                                            .overflow_hidden()
                                            .whitespace_nowrap()
                                            .when(
                                                this.branch_selected.as_ref() == Some(&reference),
                                                |s| s.bg(rgb(0x263b56)),
                                            )
                                            .cursor_pointer()
                                            .hover(|s| s.bg(rgb(0x253248)))
                                            .child(format!(
                                                "{}{} · {}",
                                                if branch.current {
                                                    "● "
                                                } else if branch.remote {
                                                    "远程 "
                                                } else {
                                                    "本地 "
                                                },
                                                branch.name,
                                                short_sha(&branch.sha)
                                            ))
                                            .child(div().text_color(rgb(0x92a2b9)).child(format!(
                                                "{} {}",
                                                branch.upstream, branch.tracking
                                            )))
                                            .on_click(cx.listener(move |this, _, window, cx| {
                                                window.focus(&this.branch_focus);
                                                this.choose_branch(reference.clone(), cx)
                                            }))
                                    })
                                })
                                .collect::<Vec<_>>()
                        }),
                    )
                    .track_scroll(this.branch_scroll.clone())
                    .h(px(112.))
                    .min_h_0(),
                ),
        )
        .when(rows.is_empty(), |s| {
            s.child("没有分支引用；空仓库可输入新分支名，起点用 HEAD。")
        })
        .child(
            div()
                .flex()
                .gap_2()
                .items_center()
                .child("新分支名 / 远程本地名")
                .when_some(this.branch_name.clone(), |s, e| {
                    s.child(div().flex_1().min_w_0().h(px(32.)).child(e))
                }),
        )
        .child(
            div()
                .flex()
                .gap_2()
                .items_center()
                .child("新分支起点")
                .when_some(this.branch_base.clone(), |s, e| {
                    s.child(div().flex_1().min_w_0().h(px(32.)).child(e))
                })
                .child(
                    button("create-branch", "创建并切换", !this.write_busy)
                        .on_click(cx.listener(|this, _, _, cx| this.create_branch(cx))),
                ),
        )
        .child(div().text_color(rgb(0x92a2b9)).child(
            "选择引用可设为新分支起点。切换沿用 Git 对未提交内容的保护；远程检出建立本地跟踪分支。",
        ))
}
