use crate::{app::MyGit, views::button};
use gpui::{prelude::*, *};
pub fn pane(this: &MyGit, cx: &mut Context<MyGit>) -> impl IntoElement {
    div()
        .flex()
        .flex_col()
        .p_2()
        .gap_2()
        .border_b_1()
        .border_color(rgb(0xc8c8c8))
        .child(mygit_gpui::i18n::text(
            "输入提交 SHA/分支/标签；EMPTY 表示空内容，右侧可用 WORKTREE。比较视图只读。",
        ))
        .child(
            div()
                .flex()
                .gap_2()
                .items_center()
                .child(mygit_gpui::i18n::text("左侧"))
                .when_some(this.compare_left.clone(), |s, e| {
                    s.child(div().flex_1().min_w_0().h(px(32.)).child(e))
                })
                .child(mygit_gpui::i18n::text("右侧"))
                .when_some(this.compare_right.clone(), |s, e| {
                    s.child(div().flex_1().min_w_0().h(px(32.)).child(e))
                })
                .child(
                    button(
                        "compare-revisions",
                        mygit_gpui::i18n::text("开始比较"),
                        !this.state.loading,
                    )
                    .on_click(cx.listener(|this, _, _, cx| this.compare_inputs(cx))),
                ),
        )
}
