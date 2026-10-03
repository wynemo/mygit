use crate::{app::MyGit, views::button};
use gpui::{prelude::*, *};

fn cell(no: Option<usize>, text: &str, color: u32, offset: f32, active: bool) -> Div {
    div()
        .flex()
        .flex_1()
        .min_w_0()
        .h(px(24.))
        .overflow_hidden()
        .bg(rgb(color))
        .child(
            div()
                .w(px(52.))
                .flex_shrink_0()
                .text_color(rgb(if active { 0xffd479 } else { 0x7f8b9c }))
                .child(no.map(|n| n.to_string()).unwrap_or_default()),
        )
        .child(
            div()
                .flex_1()
                .min_w_0()
                .h_full()
                .relative()
                .overflow_hidden()
                .child(
                    div()
                        .absolute()
                        .left(px(-offset))
                        .whitespace_nowrap()
                        .child(text.replace('\t', "    ")),
                ),
        )
}
pub fn pane(this: &MyGit, cx: &mut Context<MyGit>) -> impl IntoElement {
    let title = this
        .state
        .selected
        .and_then(|i| this.state.files.get(i))
        .map(|f| {
            if f.old_path != f.path {
                format!("{} → {}", f.old_path, f.path)
            } else {
                f.path.clone()
            }
        })
        .unwrap_or_else(|| "选择文件查看差异".into());
    let (left, right) = this.state.labels();
    let previous = this.state.navigation_target(false).is_some();
    let next = this.state.navigation_target(true).is_some();
    let counter = format!(
        "{} / {}",
        this.state
            .current_block
            .map(|i| (i + 1).to_string())
            .unwrap_or_else(|| "—".into()),
        this.state.diff.blocks.len()
    );
    div()
        .id("diff-pane")
        .flex()
        .flex_col()
        .flex_1()
        .min_w_0()
        .min_h_0()
        .child(
            div()
                .p_3()
                .border_b_1()
                .border_color(rgb(0x2b3545))
                .flex()
                .items_center()
                .gap_2()
                .child(
                    div()
                        .flex_1()
                        .overflow_hidden()
                        .whitespace_nowrap()
                        .child(title),
                )
                .child(
                    button("previous-diff", "上一处", previous)
                        .on_click(cx.listener(|this, _, _, cx| this.navigate(false, cx))),
                )
                .child(div().text_color(rgb(0x92a2b9)).child(counter))
                .child(
                    button("next-diff", "下一处", next)
                        .on_click(cx.listener(|this, _, _, cx| this.navigate(true, cx))),
                )
                .child(button("scroll-left", "←", true).on_click(
                    cx.listener(|this, _, window, cx| this.move_horizontal(false, window, cx)),
                ))
                .child(button("scroll-right", "→", true).on_click(
                    cx.listener(|this, _, window, cx| this.move_horizontal(true, window, cx)),
                )),
        )
        .child(
            div()
                .flex()
                .p_2()
                .text_color(rgb(0x92a2b9))
                .child(
                    div()
                        .flex_1()
                        .min_w_0()
                        .overflow_hidden()
                        .whitespace_nowrap()
                        .child(left),
                )
                .child(
                    div()
                        .flex_1()
                        .min_w_0()
                        .overflow_hidden()
                        .whitespace_nowrap()
                        .child(right),
                ),
        )
        .when(this.state.diff.rows.is_empty(), |s| {
            s.child(
                div()
                    .flex_1()
                    .flex()
                    .items_center()
                    .justify_center()
                    .p_3()
                    .text_color(rgb(0x92a2b9))
                    .child(if this.state.loading {
                        "正在加载…".into()
                    } else if this.state.selected.is_some() || this.state.comparison.is_none() {
                        this.state.message.clone()
                    } else if this.state.repo.is_some() {
                        format!("{}：没有变更文件", this.state.mode.label())
                    } else {
                        "打开一个 Git 仓库开始浏览".into()
                    }),
            )
        })
        .when(!this.state.diff.rows.is_empty(), |s| {
            s.child(
                uniform_list(
                    ("diff", this.state.generation as usize),
                    this.state.diff.rows.len(),
                    cx.processor(|this, range: std::ops::Range<usize>, _, _| {
                        range
                            .map(|i| {
                                let r = &this.state.diff.rows[i];
                                let active = this.state.active_row(i);
                                div()
                                    .id(i)
                                    .flex()
                                    .w_full()
                                    .h(px(24.))
                                    .font_family("Menlo")
                                    .text_size(px(12.))
                                    .child(cell(
                                        r.left_no,
                                        &r.left,
                                        if active {
                                            0x624233
                                        } else if r.changed && r.left_no.is_some() {
                                            0x43262f
                                        } else {
                                            0x151d29
                                        },
                                        this.state.horizontal_offset,
                                        active,
                                    ))
                                    .child(div().w(px(1.)).h_full().bg(rgb(0x354259)))
                                    .child(cell(
                                        r.right_no,
                                        &r.right,
                                        if active {
                                            0x365245
                                        } else if r.changed && r.right_no.is_some() {
                                            0x203c32
                                        } else {
                                            0x151d29
                                        },
                                        this.state.horizontal_offset,
                                        active,
                                    ))
                            })
                            .collect::<Vec<_>>()
                    }),
                )
                .track_scroll(this.diff_scroll.clone())
                .flex_1(),
            )
        })
}
