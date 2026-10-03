use crate::{app::MyGit, views::button};
use gpui::{prelude::*, *};
pub fn pane(this: &MyGit, cx: &mut Context<MyGit>) -> impl IntoElement {
    div()
        .h(px(220.))
        .flex_shrink_0()
        .flex()
        .flex_col()
        .min_h_0()
        .border_t_1()
        .border_color(rgb(0x2b3545))
        .child(
            div()
                .flex()
                .items_center()
                .gap_2()
                .p_2()
                .child(
                    div()
                        .flex_1()
                        .child("提交信息 · 仅提交暂存区内容，未保存编辑不包含在内"),
                )
                .child(
                    button(
                        "commit-index",
                        if this.write_busy {
                            "执行中…"
                        } else {
                            "提交暂存内容"
                        },
                        !this.write_busy,
                    )
                    .on_click(cx.listener(|this, _, _, cx| this.commit(cx))),
                ),
        )
        .when_some(this.commit_editor.clone(), |s, editor| s.child(editor))
}
