use crate::views::text_line;
use crate::{app::MyGit, views::button};
use gpui::{prelude::*, *};
use mygit_gpui::{model::BrowseMode, text::Side};

fn scroll_area(content: AnyElement, cx: &mut Context<MyGit>) -> Div {
    let entity = cx.entity();
    div()
        .relative()
        .flex()
        .flex_col()
        .flex_1()
        .min_h_0()
        .child(content)
        .child(
            canvas(
                |_, _, _| (),
                move |bounds, _, _, cx| {
                    entity.update(cx, |this, _| this.diff_bounds = Some(bounds))
                },
            )
            .absolute()
            .size_full(),
        )
}
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
        Side::Third => None,
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
        .when(this.show_blame, |s| {
            s.child(crate::views::blame::gutter(
                cx.entity().downgrade(),
                no.and_then(|n| this.blame_line(side, n - 1)),
                row,
            ))
        })
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
                    .child(mygit_gpui::i18n::text(label)),
            )
        })
}
fn unified_cell(this: &MyGit, index: usize, cx: &mut Context<MyGit>) -> Stateful<Div> {
    let item = &this.state.diff.unified[index];
    let row = item.row;
    let source = &this.state.diff.rows[row];
    let side = if source.changed {
        item.side
    } else {
        this.state.text_selection.side
    };
    let changed = source.changed;
    let active = this.state.active_row(row);
    let left = if !changed || side == Side::Left {
        source.left_no
    } else {
        None
    };
    let right = if !changed || side == Side::Right {
        source.right_no
    } else {
        None
    };
    let ending = if side == Side::Left {
        source.left_ending
    } else {
        source.right_ending
    };
    div()
        .id(("unified-row", index))
        .flex()
        .w_full()
        .h(px(this.state.font_size + 12.))
        .font_family(this.state.font_family.clone())
        .text_size(px(this.state.font_size))
        .overflow_hidden()
        .cursor(CursorStyle::IBeam)
        .bg(rgb(if active {
            0x624233
        } else if changed {
            if side == Side::Left {
                0x43262f
            } else {
                0x203c32
            }
        } else {
            0x151d29
        }))
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
                .text_color(rgb(0x7f8b9c))
                .child(left.map(|n| n.to_string()).unwrap_or_default()),
        )
        .child(
            div()
                .w(px(52.))
                .flex_shrink_0()
                .text_color(rgb(0x7f8b9c))
                .child(right.map(|n| n.to_string()).unwrap_or_default()),
        )
        .when(this.show_blame, |s| {
            s.child(crate::views::blame::gutter(
                cx.entity().downgrade(),
                this.state
                    .diff
                    .source_line(side, row)
                    .and_then(|line| this.blame_line(side, line)),
                index,
            ))
        })
        .child(div().w(px(18.)).flex_shrink_0().child(if !changed {
            " "
        } else if side == Side::Left {
            "−"
        } else {
            "+"
        }))
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
                    .child(mygit_gpui::i18n::text(label)),
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
        .unwrap_or_else(|| mygit_gpui::i18n::text("选择文件查看差异").into());
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
                .flex_wrap()
                .items_center()
                .gap_2()
                .child(
                    div()
                        .flex_1()
                        .overflow_hidden()
                        .whitespace_nowrap()
                        .child(title),
                )
                .when(this.state.current_file.is_some(), |s| {
                    s.child(
                        button(
                            "current-file-history",
                            mygit_gpui::i18n::text("文件历史"),
                            !this.state.loading,
                        )
                        .on_click(cx.listener(|this, _, _, cx| this.current_file_history(cx))),
                    )
                })
                .when(
                    !this.state.editable && this.state.current_file.is_some(),
                    |s| {
                        s.child(
                            button(
                                "edit-current-worktree",
                                mygit_gpui::i18n::text("编辑工作区文件"),
                                !this.state.loading,
                            )
                            .on_click(cx.listener(|this, _, _, cx| this.edit_current_worktree(cx))),
                        )
                    },
                )
                .when(
                    this.state.comparison.as_ref().is_some_and(|c| {
                        matches!(
                            c.right,
                            mygit_gpui::model::Revision::Commit(_)
                                | mygit_gpui::model::Revision::Head(_)
                        )
                    }),
                    |s| {
                        s.child(
                            button(
                                "compare-current-worktree",
                                mygit_gpui::i18n::text("当前文件与工作区比较"),
                                !this.state.loading,
                            )
                            .on_click(
                                cx.listener(|this, _, _, cx| this.compare_current_worktree(cx)),
                            ),
                        )
                    },
                )
                .when(
                    this.state.editable
                        && this
                            .state
                            .comparison
                            .as_ref()
                            .is_some_and(|c| c.right == mygit_gpui::model::Revision::Worktree),
                    |s| {
                        s.child(
                            button(
                                "edit-file",
                                if this.edit_mode {
                                    mygit_gpui::i18n::text("查看 Diff")
                                } else {
                                    mygit_gpui::i18n::text("编辑工作区")
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
                .when(
                    this.state.editable
                        && matches!(
                            this.state.mode,
                            BrowseMode::Workspace | BrowseMode::Unstaged
                        ),
                    |s| {
                        s.child(
                            button(
                                "restore-file",
                                mygit_gpui::i18n::text("还原文件"),
                                !this.write_busy,
                            )
                            .on_click(
                                cx.listener(|this, _, _, cx| this.request_restore(false, cx)),
                            ),
                        )
                        .child(
                            button(
                                "restore-block",
                                mygit_gpui::i18n::text("还原当前块"),
                                !this.write_busy && this.state.current_block.is_some(),
                            )
                            .on_click(cx.listener(|this, _, _, cx| this.request_restore(true, cx))),
                        )
                    },
                )
                .child(
                    button(
                        "diff-layout",
                        if this.state.unified {
                            mygit_gpui::i18n::text("双栏")
                        } else {
                            mygit_gpui::i18n::text("统一视图")
                        },
                        true,
                    )
                    .on_click(cx.listener(|this, _, _, cx| this.toggle_unified(cx))),
                )
                .child(
                    button(
                        "toggle-blame",
                        if this.show_blame {
                            mygit_gpui::i18n::text("隐藏 Blame")
                        } else {
                            "Blame"
                        },
                        this.state.current_file.is_some(),
                    )
                    .on_click(cx.listener(|this, _, _, cx| this.toggle_blame(cx))),
                )
                .child(
                    button("previous-diff", mygit_gpui::i18n::text("上一处"), previous)
                        .on_click(cx.listener(|this, _, _, cx| this.navigate(false, cx))),
                )
                .child(div().text_color(rgb(0x92a2b9)).child(counter))
                .child(
                    button("next-diff", mygit_gpui::i18n::text("下一处"), next)
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
                    button(
                        "select-all-text",
                        mygit_gpui::i18n::text("全选"),
                        !this.state.diff.rows.is_empty(),
                    )
                    .on_click(cx.listener(|this, _, window, cx| this.select_all_text(window, cx))),
                )
                .child(
                    button(
                        "copy-text",
                        mygit_gpui::i18n::text("复制"),
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
                        .child(mygit_gpui::localized_format!(
                            "{} · {} · 选区 {} 字节",
                            "{} · {} · {} selected bytes",
                            this.state.diff.right_syntax.language,
                            if this.state.text_selection.side == Side::Left {
                                mygit_gpui::i18n::text("左侧")
                            } else {
                                mygit_gpui::i18n::text("右侧")
                            },
                            this.state.text_selection.range().len()
                        )),
                )
                .child(
                    button(
                        "font-smaller",
                        mygit_gpui::i18n::text("字号 −"),
                        this.state.font_size > 10.,
                    )
                    .on_click(cx.listener(|this, _, _, cx| this.change_font_size(false, cx))),
                )
                .child(div().child(format!("{}", this.state.font_size)))
                .child(
                    button(
                        "font-larger",
                        mygit_gpui::i18n::text("字号 +"),
                        this.state.font_size < 22.,
                    )
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
        .when_some(this.state.diff.description.clone(), |s, description| {
            s.child(
                div()
                    .px_2()
                    .py_1()
                    .text_color(rgb(0x92a2b9))
                    .child(description),
            )
        })
        .when(this.state.diff.can_expand_preview, |s| {
            s.child(
                button(
                    "preview-large-file",
                    mygit_gpui::i18n::text("按需预览（最高 20 MB）"),
                    !this.state.loading,
                )
                .on_click(cx.listener(|this, _, _, cx| this.preview_large_file(cx))),
            )
        })
        .when(this.show_blame && this.blame_loading, |s| {
            s.child(
                div()
                    .px_2()
                    .child(mygit_gpui::i18n::text("正在读取两侧 Blame…")),
            )
        })
        .when(this.show_blame && !this.blame_error.is_empty(), |s| {
            s.child(
                div()
                    .px_2()
                    .text_color(rgb(0xffd479))
                    .child(this.blame_error.clone()),
            )
        })
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
                            mygit_gpui::i18n::text("正在加载…").into()
                        } else if this.state.active_file().is_some()
                            || this.state.comparison.is_none()
                        {
                            this.state.message.clone()
                        } else if this.state.repo.is_some() {
                            mygit_gpui::localized_format!(
                                "{}：没有变更文件",
                                "{}: no changed files",
                                this.state.mode.label()
                            )
                        } else {
                            mygit_gpui::i18n::text("打开一个 Git 仓库开始浏览").into()
                        }),
                )
            },
        )
        .when(
            this.current_editor().is_none()
                && !this.state.unified
                && !this.state.diff.rows.is_empty(),
            |s| {
                let list = uniform_list(
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
                .flex_1();
                s.child(scroll_area(list.into_any_element(), cx))
            },
        )
        .when(
            this.current_editor().is_none()
                && this.state.unified
                && !this.state.diff.rows.is_empty(),
            |s| {
                let list = uniform_list(
                    ("unified-diff", this.state.generation as usize),
                    this.state.diff.unified.len(),
                    cx.processor(|this, range: std::ops::Range<usize>, _, cx| {
                        range.map(|i| unified_cell(this, i, cx)).collect::<Vec<_>>()
                    }),
                )
                .track_scroll(this.diff_scroll.clone())
                .flex_1();
                s.child(scroll_area(list.into_any_element(), cx))
            },
        )
}
