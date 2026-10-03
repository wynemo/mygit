use crate::{app::MyGit, views::button};
use gpui::{prelude::*, *};
use mygit_gpui::{
    model::{BrowseMode, short_sha},
    text::Side,
};
fn cell(this: &MyGit, side: usize, row: usize, cx: &mut Context<MyGit>) -> impl IntoElement {
    let view = this.state.merge.as_ref().unwrap();
    let source = view.rows[row].lines[side];
    let ending = source.filter(|_| view.rows[row].changed[side]).map(|line| {
        let raw = &view.documents[side].text[view.documents[side].lines[line - 1].clone()];
        if raw.ends_with("\r\n") {
            "CRLF"
        } else if raw.ends_with('\n') {
            "LF"
        } else {
            "无末尾换行"
        }
    });
    let source_side = [Side::Left, Side::Right, Side::Third][side];
    let raw = source.map(|line| {
        view.documents[side].text[view.documents[side].lines[line - 1].clone()].to_owned()
    });
    let active = this.state.active_row(row);
    let color = if active {
        0x3c435f
    } else if source.is_none() {
        0x1c2533
    } else if view.rows[row].changed[side] {
        if side == 1 {
            match (view.rows[row].changed[0], view.rows[row].changed[2]) {
                (true, true) => 0x443454,
                (true, false) => 0x203c32,
                _ => 0x263b56,
            }
        } else {
            0x43262f
        }
    } else {
        0x151d29
    };
    div()
        .id(("merge-cell", row * 3 + side))
        .flex()
        .flex_1()
        .min_w_0()
        .h_full()
        .overflow_hidden()
        .bg(rgb(color))
        .cursor(CursorStyle::IBeam)
        .on_mouse_down(
            MouseButton::Left,
            cx.listener(move |this, event, window, cx| {
                this.mouse_down(source_side, row, event, window, cx)
            }),
        )
        .on_mouse_down(
            MouseButton::Right,
            cx.listener(move |_, _, _, cx| {
                if let Some(raw) = &raw {
                    cx.write_to_clipboard(ClipboardItem::new_string(raw.clone()));
                }
                cx.stop_propagation();
            }),
        )
        .child(
            div()
                .w(px(42.))
                .flex_shrink_0()
                .text_color(rgb(0x8995a8))
                .child(source.map(|n| n.to_string()).unwrap_or_default()),
        )
        .when(this.show_blame, |s| {
            s.child(crate::views::blame::gutter(
                cx.entity().downgrade(),
                source.and_then(|line| this.blame_line(source_side, line - 1)),
                row * 3 + side,
            ))
        })
        .child(crate::views::text_line::line(this, source_side, row, cx))
        .when_some(ending, |s, ending| {
            s.child(
                div()
                    .px_1()
                    .flex_shrink_0()
                    .text_color(rgb(0xffd479))
                    .child(ending),
            )
        })
}
pub fn pane(this: &MyGit, cx: &mut Context<MyGit>) -> impl IntoElement {
    let view = this.state.merge.as_ref().unwrap();
    let sha = view.revisions[1].clone();
    let counter = format!(
        "{} / {}",
        this.state
            .current_block
            .map(|b| (b + 1).to_string())
            .unwrap_or_else(|| "—".into()),
        view.blocks.len()
    );
    let owner = cx.entity();
    div()
        .id("merge-pane")
        .key_context("MergeHistory")
        .track_focus(&this.focus)
        .flex()
        .flex_col()
        .flex_1()
        .min_w_0()
        .min_h_0()
        .on_mouse_down(
            MouseButton::Left,
            cx.listener(|this, _, window, _| window.focus(&this.focus)),
        )
        .child(crate::views::tabs::bar(this, cx))
        .child(
            button(
                "merge-blame-toggle",
                if this.show_blame {
                    "隐藏 Blame"
                } else {
                    "Blame"
                },
                !this.state.loading,
            )
            .on_click(cx.listener(|this, _, _, cx| this.toggle_blame(cx))),
        )
        .when(this.show_blame && this.blame_loading, |s| {
            s.child(div().px_2().child("正在读取三侧 Blame…"))
        })
        .when(this.show_blame && !this.blame_error.is_empty(), |s| {
            s.child(
                div()
                    .px_2()
                    .text_color(rgb(0xffd479))
                    .child(this.blame_error.clone()),
            )
        })
        .child(
            div()
                .p_2()
                .flex()
                .flex_wrap()
                .gap_2()
                .child(div().child(view.paths[1].clone()))
                .child(
                    button("merge-first-parent", "首父双栏", true).on_click(cx.listener(
                        move |this, _, _, cx| {
                            this.select_mode(BrowseMode::History(sha.clone()), cx)
                        },
                    )),
                )
                .child(
                    button(
                        "merge-prev",
                        "上一处",
                        this.state.navigation_target(false).is_some(),
                    )
                    .on_click(cx.listener(|this, _, _, cx| this.navigate(false, cx))),
                )
                .child(div().child(counter))
                .child(
                    button(
                        "merge-next",
                        "下一处",
                        this.state.navigation_target(true).is_some(),
                    )
                    .on_click(cx.listener(|this, _, _, cx| this.navigate(true, cx))),
                )
                .child(button("merge-left", "←", true).on_click(
                    cx.listener(|this, _, window, cx| this.move_horizontal(false, window, cx)),
                ))
                .child(button("merge-right", "→", true).on_click(
                    cx.listener(|this, _, window, cx| this.move_horizontal(true, window, cx)),
                ))
                .child(
                    button("merge-smaller", "A−", true)
                        .on_click(cx.listener(|this, _, _, cx| this.change_font_size(false, cx))),
                )
                .child(
                    button("merge-larger", "A+", true)
                        .on_click(cx.listener(|this, _, _, cx| this.change_font_size(true, cx))),
                ),
        )
        .child(div().px_2().text_xs().text_color(rgb(0x92a2b9)).child(
            "合并提交历史 · 紫色：结果与双方不同；绿色/蓝色：与父 1/父 2 不同 · 右键复制原始行",
        ))
        .child(
            div().flex().children(
                (0..3)
                    .map(|side| {
                        let text = view.documents[side].text.clone();
                        let full_sha = view.revisions[side].clone();
                        div()
                            .flex_1()
                            .min_w_0()
                            .p_2()
                            .overflow_hidden()
                            .border_r_1()
                            .border_color(rgb(0x354259))
                            .child(div().whitespace_nowrap().child(format!(
                                "{} · {}",
                                ["父提交 1", "合并结果", "父提交 2"][side],
                                short_sha(&full_sha)
                            )))
                            .child(
                                div()
                                    .text_xs()
                                    .whitespace_nowrap()
                                    .child(view.paths[side].clone()),
                            )
                            .when(!view.exists[side], |s| {
                                s.child(
                                    div()
                                        .text_xs()
                                        .text_color(rgb(0xffd479))
                                        .child("该版本中不存在此文件"),
                                )
                            })
                            .child(
                                div()
                                    .flex()
                                    .gap_1()
                                    .child(
                                        button(
                                            ["merge-p1-sha", "merge-result-sha", "merge-p2-sha"]
                                                [side],
                                            "复制 SHA",
                                            true,
                                        )
                                        .on_click(
                                            move |_, _, cx| {
                                                cx.write_to_clipboard(ClipboardItem::new_string(
                                                    full_sha.clone(),
                                                ))
                                            },
                                        ),
                                    )
                                    .child(
                                        button(
                                            ["merge-p1-text", "merge-result-text", "merge-p2-text"]
                                                [side],
                                            "复制内容",
                                            view.message.is_none(),
                                        )
                                        .on_click(
                                            move |_, _, cx| {
                                                cx.write_to_clipboard(ClipboardItem::new_string(
                                                    text.to_string(),
                                                ))
                                            },
                                        ),
                                    ),
                            )
                    })
                    .collect::<Vec<_>>(),
            ),
        )
        .when(view.descriptions.iter().any(|d| !d.is_empty()), |s| {
            s.child(
                div()
                    .px_2()
                    .text_xs()
                    .text_color(rgb(0x8995a8))
                    .child(format!(
                        "父 1 ↔ 结果：{}；父 2 ↔ 结果：{}",
                        view.descriptions[0], view.descriptions[1]
                    )),
            )
        })
        .when(
            view.message
                .as_ref()
                .is_some_and(|message| message.contains("预览上限")),
            |s| {
                s.child(
                    button(
                        "merge-large-preview",
                        "按需查看（最高 20 MB）",
                        !this.state.loading,
                    )
                    .on_click(cx.listener(|this, _, _, cx| this.preview_large_file(cx))),
                )
            },
        )
        .when_some(view.message.clone(), |s, message| {
            s.child(div().p_3().text_color(rgb(0xffd479)).child(message))
        })
        .when(view.message.is_none() && view.rows.is_empty(), |s| {
            s.child(div().p_3().child("三侧文件均为空"))
        })
        .when(!view.rows.is_empty(), |s| {
            s.child(
                div()
                    .relative()
                    .flex()
                    .flex_col()
                    .flex_1()
                    .min_h_0()
                    .child(
                        uniform_list(
                            ("merge-lines", this.state.generation as usize),
                            view.rows.len(),
                            cx.processor(|this, range: std::ops::Range<usize>, _, cx| {
                                range
                                    .map(|row| {
                                        div()
                                            .id(row)
                                            .flex()
                                            .w_full()
                                            .h(px(this.state.font_size + 12.))
                                            .font_family(this.state.font_family.clone())
                                            .text_size(px(this.state.font_size))
                                            .children(
                                                (0..3)
                                                    .map(|side| {
                                                        cell(this, side, row, cx).into_any_element()
                                                    })
                                                    .collect::<Vec<_>>(),
                                            )
                                    })
                                    .collect::<Vec<_>>()
                            }),
                        )
                        .track_scroll(this.diff_scroll.clone())
                        .flex_1()
                        .min_h_0(),
                    )
                    .child(
                        canvas(
                            |_, _, _| (),
                            move |bounds, _, _, cx| {
                                owner.update(cx, |this, _| this.diff_bounds = Some(bounds))
                            },
                        )
                        .absolute()
                        .size_full(),
                    ),
            )
        })
}
