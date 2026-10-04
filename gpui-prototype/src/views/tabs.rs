use crate::{app::MyGit, views::button};
use gpui::{prelude::*, *};
pub fn bar(this: &MyGit, cx: &mut Context<MyGit>) -> impl IntoElement {
    div()
        .flex()
        .flex_col()
        .border_b_1()
        .border_color(rgb(0x2b3545))
        .when(!this.tabs.is_empty(), |s| {
            s.child(
                div().id("file-tabs").flex().overflow_x_scroll().children(
                    this.tabs
                        .iter()
                        .enumerate()
                        .map(|(i, tab)| {
                            div()
                                .id(("file-tab", i))
                                .flex()
                                .flex_shrink_0()
                                .items_center()
                                .gap_2()
                                .p_2()
                                .bg(rgb(if this.active_tab == Some(i) {
                                    0x263b56
                                } else {
                                    0x151d29
                                }))
                                .child(
                                    div()
                                        .id(("activate-tab", i))
                                        .cursor_pointer()
                                        .child(format!(
                                            "{}{}",
                                            if this.is_dirty(&tab.file.path, cx) {
                                                "● "
                                            } else {
                                                ""
                                            },
                                            tab.file.path
                                        ))
                                        .on_click(cx.listener(move |this, _, _, cx| {
                                            this.activate_tab(i, cx)
                                        })),
                                )
                                .child(
                                    div()
                                        .id(("close-tab", i))
                                        .cursor_pointer()
                                        .child("×")
                                        .on_click(
                                            cx.listener(move |this, _, _, cx| {
                                                this.close_tab(i, cx)
                                            }),
                                        ),
                                )
                        })
                        .collect::<Vec<_>>(),
                ),
            )
            .child(
                div()
                    .flex()
                    .gap_2()
                    .px_2()
                    .py_1()
                    .child(
                        button(
                            "close-other-tabs",
                            mygit_gpui::i18n::text("关闭其他"),
                            this.active_tab.is_some(),
                        )
                        .on_click(cx.listener(|this, _, _, cx| this.close_other_tabs(false, cx))),
                    )
                    .child(
                        button("close-all-tabs", mygit_gpui::i18n::text("关闭全部"), true)
                            .on_click(
                                cx.listener(|this, _, _, cx| this.close_other_tabs(true, cx)),
                            ),
                    ),
            )
        })
}
