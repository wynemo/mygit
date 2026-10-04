use crate::{app::MyGit, views::button};
use gpui::{prelude::*, *};
pub fn pane(this: &MyGit, cx: &mut Context<MyGit>) -> impl IntoElement {
    let results = &this.search.results;
    let mut pane = div()
        .id("project-search-pane")
        .key_context("ProjectSearch")
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
                .items_center()
                .gap_2()
                .child(mygit_gpui::i18n::text(
                    "项目内容搜索 · Cmd/Ctrl+Shift+F · ↑↓ 选择 · Enter 打开",
                ))
                .child(
                    button(
                        "project-search-run",
                        mygit_gpui::i18n::text("重新搜索"),
                        true,
                    )
                    .on_click(cx.listener(|this, _, _, cx| this.search_project(cx))),
                )
                .child(
                    button("project-search-close", mygit_gpui::i18n::text("关闭"), true).on_click(
                        cx.listener(|this, _, window, cx| this.close_project_search(window, cx)),
                    ),
                ),
        );
    for (index, label) in [
        mygit_gpui::i18n::text("查询"),
        mygit_gpui::i18n::text("包含 glob（例如 *.rs）"),
        mygit_gpui::i18n::text("排除 glob（例如 target/**）"),
    ]
    .iter()
    .enumerate()
    {
        if let Some(input) = this.search.inputs.get(index) {
            pane = pane.child(
                div()
                    .flex()
                    .gap_2()
                    .items_center()
                    .child(*label)
                    .child(div().flex_1().h(px(32.)).child(input.clone())),
            );
        }
    }
    let mut options = div().flex().flex_wrap().gap_2();
    for (index, id, label, active_label, enabled) in [
        (
            0,
            "search-case",
            mygit_gpui::i18n::text("大小写"),
            mygit_gpui::i18n::text("✓ 大小写"),
            this.search.options.case_sensitive,
        ),
        (
            1,
            "search-regex",
            mygit_gpui::i18n::text("正则"),
            mygit_gpui::i18n::text("✓ 正则"),
            this.search.options.regex,
        ),
        (
            2,
            "search-word",
            mygit_gpui::i18n::text("整词"),
            mygit_gpui::i18n::text("✓ 整词"),
            this.search.options.whole_word,
        ),
        (
            3,
            "search-hidden",
            mygit_gpui::i18n::text("隐藏文件"),
            mygit_gpui::i18n::text("✓ 隐藏文件"),
            this.search.options.hidden,
        ),
    ] {
        options = options.child(
            button(id, if enabled { active_label } else { label }, true).on_click(cx.listener(
                move |this, _, _, cx| {
                    let option = match index {
                        0 => &mut this.search.options.case_sensitive,
                        1 => &mut this.search.options.regex,
                        2 => &mut this.search.options.whole_word,
                        _ => &mut this.search.options.hidden,
                    };
                    *option = !*option;
                    this.search_project(cx);
                },
            )),
        );
    }
    pane.child(options)
        .child(
            div()
                .text_xs()
                .text_color(rgb(0x92a2b9))
                .child(if this.search.loading {
                    mygit_gpui::i18n::text("正在搜索磁盘内容…").into()
                } else {
                    mygit_gpui::localized_format!(
                        "显示 {} 个文件 / {} 个匹配行 / {} 处匹配{} · 跳过编码 {} 项",
                        "{} files / {} matching lines / {} matches{} · {} skipped for encoding",
                        results.files,
                        results.hits.len(),
                        results.occurrences,
                        if results.truncated {
                            mygit_gpui::i18n::text("（已达上限，请缩小范围）")
                        } else {
                            ""
                        },
                        results.skipped_encoding
                    )
                }),
        )
        .child(
            div()
                .text_xs()
                .text_color(rgb(0x92a2b9))
                .child(mygit_gpui::i18n::text(
                    "遵循 rg 忽略规则 · 单文件 ≤20 MB · 最多 2,000 行 · 搜索磁盘内容",
                )),
        )
        .when_some(this.search.error.clone(), |s, error| {
            s.child(div().text_color(rgb(0xffd479)).child(error))
        })
        .when(!results.diagnostic.is_empty(), |s| {
            s.child(
                div()
                    .text_color(rgb(0xffd479))
                    .child(results.diagnostic.clone()),
            )
        })
        .when(
            !this.search.loading && results.hits.is_empty() && this.search.error.is_none(),
            |s| s.child(mygit_gpui::i18n::text("请输入查询；没有匹配结果")),
        )
        .when(!results.hits.is_empty(), |s| {
            s.child(
                uniform_list(
                    "project-search-results",
                    results.hits.len(),
                    cx.processor(|this, range: std::ops::Range<usize>, _, cx| {
                        range
                            .map(|i| {
                                let hit = &this.search.results.hits[i];
                                let serial = this.search.serial;
                                let epoch = this.repository_epoch;
                                div()
                                    .id(i)
                                    .h(px(48.))
                                    .px_2()
                                    .flex()
                                    .flex_col()
                                    .overflow_hidden()
                                    .whitespace_nowrap()
                                    .cursor_pointer()
                                    .bg(rgb(if i == this.search.selected {
                                        0x263b56
                                    } else {
                                        0x151d29
                                    }))
                                    .hover(|s| s.bg(rgb(0x253248)))
                                    .child(mygit_gpui::localized_format!(
                                        "{}:{} · {} 处",
                                        "{}:{} · {} matches",
                                        hit.path,
                                        hit.line,
                                        hit.occurrences
                                    ))
                                    .child(
                                        div()
                                            .text_xs()
                                            .text_color(rgb(0x92a2b9))
                                            .child(hit.preview.clone()),
                                    )
                                    .on_click(cx.listener(move |this, _, window, cx| {
                                        if this.repository_epoch == epoch
                                            && this.search.serial == serial
                                            && i < this.search.results.hits.len()
                                        {
                                            this.search.selected = i;
                                            this.accept_project_search(window, cx);
                                        }
                                    }))
                            })
                            .collect::<Vec<_>>()
                    }),
                )
                .track_scroll(this.search.scroll.clone())
                .h(px((results.hits.len().min(5) * 48) as f32)),
            )
        })
}
