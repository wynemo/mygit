use crate::views::text_line;
use crate::{app::MyGit, views::button};
use gpui::{prelude::*, *};
use mygit_gpui::text::Side;

fn cell(
    this: &MyGit,
    side: Side,
    row: usize,
    color: u32,
    active: bool,
    cx: &mut Context<MyGit>,
) -> impl IntoElement {
    let no = this.state.diff.source_line(side, row).map(|i| i + 1);
    let ending = match side {
        Side::Left => this.state.diff.rows[row].left_ending,
        Side::Right => this.state.diff.rows[row].right_ending,
    };
    div()
        .id((
            if side == Side::Left {
                "left-text"
            } else {
                "right-text"
            },
            row,
        ))
        .flex()
        .flex_1()
        .min_w_0()
        .h(px(this.state.font_size + 12.))
        .overflow_hidden()
        .bg(rgb(color))
        .cursor(CursorStyle::IBeam)
        .on_mouse_down(
            MouseButton::Left,
            cx.listener(move |this, event, window, cx| {
                this.mouse_down(side, row, event, window, cx)
            }),
        )
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
                .overflow_hidden()
                .child(text_line::line(this, side, row, cx)),
        )
        .when_some(ending, |s, label| {
            s.child(
                div()
                    .px_1()
                    .flex_shrink_0()
                    .text_color(rgb(0xffd479))
                    .bg(rgb(0x283346))
                    .child(label),
            )
        })
}
pub fn pane(this: &MyGit, cx: &mut Context<MyGit>) -> impl IntoElement {
    let title = this
        .state
        .active_file()
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
        .key_context("DiffText")
        .track_focus(&this.focus)
        .flex()
        .flex_col()
        .flex_1()
        .min_w_0()
        .min_h_0()
        .child(crate::views::tabs::bar(this, cx))
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
                .when(
                    this.state
                        .comparison
                        .as_ref()
                        .is_some_and(|c| c.right == mygit_gpui::model::Revision::Worktree),
                    |s| {
                        s.child(
                            button(
                                "edit-file",
                                if this.edit_mode {
                                    "查看 Diff"
                                } else {
                                    "编辑工作区"
                                },
                                !this.state.loading,
                            )
                            .on_click(cx.listener(
                                |this, _, window, cx| {
                                    if this.edit_mode {
                                        this.edit_mode = false;
                                        cx.notify();
                                    } else {
                                        this.edit_current(window, cx);
                                    }
                                },
                            )),
                        )
                    },
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
                .items_center()
                .gap_2()
                .px_2()
                .py_1()
                .child(
                    button("select-all-text", "全选", !this.state.diff.rows.is_empty()).on_click(
                        cx.listener(|this, _, window, cx| this.select_all_text(window, cx)),
                    ),
                )
                .child(
                    button(
                        "copy-text",
                        "复制",
                        !this.state.text_selection.range().is_empty(),
                    )
                    .on_click(cx.listener(|this, _, _, cx| this.copy_text(cx))),
                )
                .child(
                    div()
                        .flex_1()
                        .min_w_0()
                        .overflow_hidden()
                        .whitespace_nowrap()
                        .text_color(rgb(0x92a2b9))
                        .child(format!(
                            "{} · {} · 选区 {} 字节",
                            this.state.diff.right_syntax.language,
                            if this.state.text_selection.side == Side::Left {
                                "左侧"
                            } else {
                                "右侧"
                            },
                            this.state.text_selection.range().len()
                        )),
                )
                .child(
                    button("font-smaller", "字号 −", this.state.font_size > 10.)
                        .on_click(cx.listener(|this, _, _, cx| this.change_font_size(false, cx))),
                )
                .child(div().child(format!("{}", this.state.font_size)))
                .child(
                    button("font-larger", "字号 +", this.state.font_size < 22.)
                        .on_click(cx.listener(|this, _, _, cx| this.change_font_size(true, cx))),
                ),
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
        .when_some(this.current_editor(), |s, editor| s.child(editor))
        .when(
            this.current_editor().is_none() && this.state.diff.rows.is_empty(),
            |s| {
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
                        } else if this.state.active_file().is_some()
                            || this.state.comparison.is_none()
                        {
                            this.state.message.clone()
                        } else if this.state.repo.is_some() {
                            format!("{}：没有变更文件", this.state.mode.label())
                        } else {
                            "打开一个 Git 仓库开始浏览".into()
                        }),
                )
            },
        )
        .when(
            this.current_editor().is_none() && !this.state.diff.rows.is_empty(),
            |s| {
                s.child(
                    uniform_list(
                        ("diff", this.state.generation as usize),
                        this.state.diff.rows.len(),
                        cx.processor(|this, range: std::ops::Range<usize>, _, cx| {
                            range
                                .map(|i| {
                                    let r = &this.state.diff.rows[i];
                                    let active = this.state.active_row(i);
                                    div()
                                        .id(i)
                                        .flex()
                                        .w_full()
                                        .h(px(this.state.font_size + 12.))
                                        .font_family(this.state.font_family.clone())
                                        .text_size(px(this.state.font_size))
                                        .child(cell(
                                            this,
                                            Side::Left,
                                            i,
                                            if active {
                                                0x624233
                                            } else if r.changed && r.left_no.is_some() {
                                                0x43262f
                                            } else {
                                                0x151d29
                                            },
                                            active,
                                            cx,
                                        ))
                                        .child(div().w(px(1.)).h_full().bg(rgb(0x354259)))
                                        .child(cell(
                                            this,
                                            Side::Right,
                                            i,
                                            if active {
                                                0x365245
                                            } else if r.changed && r.right_no.is_some() {
                                                0x203c32
                                            } else {
                                                0x151d29
                                            },
                                            active,
                                            cx,
                                        ))
                                })
                                .collect::<Vec<_>>()
                        }),
                    )
                    .track_scroll(this.diff_scroll.clone())
                    .flex_1(),
                )
            },
        )
}
