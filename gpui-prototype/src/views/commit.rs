use crate::{app::MyGit, views::button};
use gpui::{prelude::*, *};
pub fn pane(this: &MyGit, cx: &mut Context<MyGit>) -> impl IntoElement {
    div()
        .flex_1()
        .flex()
        .flex_col()
        .min_h_0()
        .border_t_1()
        .border_color(rgb(crate::views::theme::BORDER))
        .child(
            div()
                .flex()
                .flex_wrap()
                .items_center()
                .gap_2()
                .p_2()
                .child(div().flex_1().child(mygit_gpui::i18n::text(
                    "提交信息 · 仅提交暂存区内容，未保存编辑不包含在内",
                )))
                .child(
                    button("ai-config-open", mygit_gpui::i18n::text("AI 配置"), true)
                        .on_click(cx.listener(|this, _, _, cx| this.open_ai_settings(cx))),
                )
                .child(
                    button(
                        "ai-generate",
                        if this.ai.loading {
                            mygit_gpui::i18n::text("生成中…")
                        } else {
                            mygit_gpui::i18n::text("AI 生成")
                        },
                        !this.write_busy && !this.ai.loading && !this.ai.applying,
                    )
                    .on_click(cx.listener(|this, _, _, cx| this.generate_ai(cx))),
                )
                .when(this.ai.loading || this.ai.applying, |s| {
                    s.child(
                        button("ai-cancel", mygit_gpui::i18n::text("取消 AI"), true)
                            .on_click(cx.listener(|this, _, _, cx| this.cancel_ai(cx))),
                    )
                })
                .child(
                    button(
                        "commit-index",
                        if this.write_busy {
                            mygit_gpui::i18n::text("执行中…")
                        } else {
                            mygit_gpui::i18n::text("提交暂存内容")
                        },
                        !this.write_busy,
                    )
                    .on_click(cx.listener(|this, _, _, cx| this.commit(cx))),
                ),
        )
        .when(!this.ai.message.is_empty(), |s| {
            s.child(
                div()
                    .px_2()
                    .text_xs()
                    .text_color(rgb(0x946200))
                    .child(this.ai.message.clone()),
            )
        })
        .when_some(this.ai.candidate.clone(), |s, candidate| {
            s.child(
                div()
                    .flex()
                    .flex_col()
                    .h(px(135.))
                    .flex_shrink_0()
                    .min_h_0()
                    .child(
                        div()
                            .flex()
                            .gap_2()
                            .items_center()
                            .px_2()
                            .child(mygit_gpui::i18n::text("AI 生成草稿（可编辑）"))
                            .child(
                                button(
                                    "ai-apply",
                                    mygit_gpui::i18n::text("应用到提交信息（替换）"),
                                    !this.write_busy && !this.ai.loading && !this.ai.applying,
                                )
                                .on_click(cx.listener(|this, _, _, cx| this.apply_ai(cx))),
                            ),
                    )
                    .child(candidate),
            )
        })
        .child(
            div()
                .px_2()
                .text_xs()
                .child(mygit_gpui::i18n::text("提交信息（手动草稿）")),
        )
        .when_some(this.commit_editor.clone(), |s, editor| s.child(editor))
}
