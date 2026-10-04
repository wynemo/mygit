use crate::{app::MyGit, views::button};
use gpui::{prelude::*, *};
pub fn pane(this: &MyGit, cx: &mut Context<MyGit>) -> impl IntoElement {
    div()
        .id("quick-open-pane")
        .key_context("QuickOpen")
        .flex()
        .flex_col()
        .flex_shrink_0()
        .p_2()
        .gap_1()
        .border_b_1()
        .border_color(rgb(0x2b3545))
        .child(
            div()
                .flex()
                .flex_wrap()
                .gap_2()
                .items_center()
                .child(mygit_gpui::i18n::text(
                    "文件快速定位 · Cmd/Ctrl+P · ↑↓ 选择 · Enter 打开 · Esc 关闭",
                ))
                .child(
                    button(
                        "quick-open-refresh",
                        mygit_gpui::i18n::text("刷新索引"),
                        !this.quick.indexing,
                    )
                    .on_click(cx.listener(|this, _, _, cx| this.refresh_quick_index(cx))),
                )
                .child(
                    button(
                        "quick-open-accept",
                        mygit_gpui::i18n::text("打开"),
                        !this.quick.indexing
                            && !this.quick.searching
                            && !this.quick.matches.paths.is_empty(),
                    )
                    .on_click(
                        cx.listener(|this, _, window, cx| this.accept_quick_open(window, cx)),
                    ),
                )
                .child(
                    button("quick-open-close", mygit_gpui::i18n::text("关闭"), true).on_click(
                        cx.listener(|this, _, window, cx| this.close_quick_open(window, cx)),
                    ),
                ),
        )
        .when_some(this.quick.input.clone(), |s, input| {
            s.child(div().h(px(32.)).child(input))
        })
        .child(
            div()
                .text_xs()
                .text_color(rgb(0x92a2b9))
                .child(if this.quick.indexing {
                    mygit_gpui::i18n::text("正在更新文件索引…").into()
                } else if this.quick.searching {
                    mygit_gpui::i18n::text("正在匹配…").into()
                } else {
                    mygit_gpui::localized_format!(
                        "索引 {} 个文件 · 匹配 {} 项 · 显示 {} 项",
                        "{} indexed files · {} matches · {} displayed",
                        this.quick.count(),
                        this.quick.matches.total,
                        this.quick.matches.paths.len()
                    )
                }),
        )
        .when_some(this.quick.error.clone(), |s, error| {
            s.child(div().text_color(rgb(0xffd479)).child(error))
        })
        .when(
            !this.quick.indexing
                && !this.quick.searching
                && this.quick.matches.paths.is_empty()
                && this.quick.error.is_none(),
            |s| s.child(mygit_gpui::i18n::text("没有匹配文件")),
        )
        .when(!this.quick.matches.paths.is_empty(), |s| {
            s.child(
                uniform_list(
                    "quick-open-results",
                    this.quick.matches.paths.len(),
                    cx.processor(|this, range: std::ops::Range<usize>, _, cx| {
                        range
                            .map(|i| {
                                let path = this.quick.matches.paths[i].clone();
                                div()
                                    .id(i)
                                    .h(px(32.))
                                    .px_2()
                                    .py_1()
                                    .overflow_hidden()
                                    .whitespace_nowrap()
                                    .cursor_pointer()
                                    .bg(rgb(if i == this.quick.selected {
                                        0x263b56
                                    } else {
                                        0x151d29
                                    }))
                                    .hover(|s| s.bg(rgb(0x253248)))
                                    .child(path.clone())
                                    .on_click(cx.listener(move |this, _, window, cx| {
                                        if let Some(index) = this
                                            .quick
                                            .matches
                                            .paths
                                            .iter()
                                            .position(|candidate| candidate == &path)
                                        {
                                            this.quick.selected = index;
                                            this.accept_quick_open(window, cx);
                                        }
                                    }))
                            })
                            .collect::<Vec<_>>()
                    }),
                )
                .track_scroll(this.quick.scroll.clone())
                .h(px((this.quick.matches.paths.len().min(6) * 32) as f32)),
            )
        })
}
