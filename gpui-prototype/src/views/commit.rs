use crate::{
    app::MyGit,
    views::{button, icons, toolbar_button},
};
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
                .h(px(42.))
                .flex_shrink_0()
                .flex()
                .items_center()
                .px_3()
                .font_weight(FontWeight::SEMIBOLD)
                .child("Commit"),
        )
        .child(
            div()
                .flex()
                .flex_col()
                .map(|mut s| {
                    s.style().flex_grow = Some(1.4);
                    s
                })
                .flex_basis(px(0.))
                .min_h(px(66.
                    + this.state.files.len().clamp(1, 8) as f32 * 28.
                    + 8.))
                .min_h_0()
                .overflow_hidden()
                .child(changes(this, cx)),
        )
        .child(
            div()
                .flex_shrink_0()
                .border_t_1()
                .border_color(rgb(crate::views::theme::BORDER))
                .flex()
                .items_center()
                .gap_2()
                .p_2()
                .child(div().flex_1().child(mygit_gpui::i18n::text("提交信息")))
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
                        !this.write_busy && !this.ai.loading,
                    )
                    .on_click(cx.listener(|this, _, _, cx| this.generate_ai(cx))),
                )
                .when(this.ai.loading, |s| {
                    s.child(
                        button("ai-cancel", mygit_gpui::i18n::text("取消 AI"), true)
                            .on_click(cx.listener(|this, _, _, cx| this.cancel_ai(cx))),
                    )
                }),
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
        .child(
            div()
                .flex()
                .flex_col()
                .flex_1()
                .flex_basis(px(0.))
                .min_h_0()
                .bg(rgb(crate::views::theme::SURFACE))
                .when_some(this.commit_editor.clone(), |s, editor| s.child(editor)),
        )
        .child(
            div()
                .flex_shrink_0()
                .border_t_1()
                .border_color(rgb(crate::views::theme::BORDER))
                .p_3()
                .flex()
                .items_center()
                .gap_2()
                .child(
                    button("commit-selected", "Commit", can_commit(this, cx))
                        .bg(rgb(crate::views::theme::ACCENT))
                        .text_color(rgb(crate::views::theme::SURFACE))
                        .on_click(cx.listener(|this, _, _, cx| this.commit_selected(false, cx))),
                )
                .child(
                    button(
                        "commit-selected-push",
                        "Commit and Push…",
                        can_commit(this, cx),
                    )
                    .on_click(cx.listener(|this, _, _, cx| this.commit_selected(true, cx))),
                ),
        )
}

fn changes(this: &MyGit, cx: &mut Context<MyGit>) -> impl IntoElement {
    let collapsed = this.change_folders_collapsed.contains("@commit-changes");
    let all = !this.state.files.is_empty()
        && this
            .state
            .files
            .iter()
            .all(|f| this.file_selection.contains(&f.path));
    let some = this
        .state
        .files
        .iter()
        .any(|f| this.file_selection.contains(&f.path));
    div()
        .flex()
        .flex_col()
        .flex_1()
        .min_h_0()
        .min_w_0()
        .child(
            div()
                .flex()
                .items_center()
                .gap_2()
                .px_3()
                .h(px(32.))
                .flex_shrink_0()
                .child(
                    toolbar_button("refresh", mygit_gpui::i18n::text("刷新"), !this.write_busy)
                        .on_click(cx.listener(|this, _, _, cx| this.request_refresh(cx))),
                ),
        )
        .child(
            div()
                .h(px(34.))
                .flex_shrink_0()
                .flex()
                .items_center()
                .px_3()
                .gap_2()
                .child(
                    div()
                        .id("commit-changes-toggle")
                        .size(px(16.))
                        .cursor_pointer()
                        .text_color(rgb(crate::views::theme::MUTED))
                        .child(if collapsed { "▸" } else { "▾" })
                        .on_click(cx.listener(|this, _, _, cx| {
                            if !this.change_folders_collapsed.remove("@commit-changes") {
                                this.change_folders_collapsed
                                    .insert("@commit-changes".into());
                            }
                            cx.notify();
                        })),
                )
                .child(
                    div()
                        .id("commit-select-all")
                        .size(px(18.))
                        .flex_shrink_0()
                        .rounded(px(3.))
                        .border_1()
                        .border_color(rgb(0xa8b1c1))
                        .bg(rgb(if some {
                            crate::views::theme::ACCENT
                        } else {
                            crate::views::theme::SURFACE
                        }))
                        .text_color(rgb(crate::views::theme::SURFACE))
                        .flex()
                        .items_center()
                        .justify_center()
                        .cursor_pointer()
                        .child(if all {
                            "✓"
                        } else if some {
                            "−"
                        } else {
                            ""
                        })
                        .on_click(cx.listener(move |this, _, _, cx| {
                            if all {
                                this.file_selection.clear();
                            } else {
                                this.file_selection =
                                    this.state.files.iter().map(|f| f.path.clone()).collect();
                            }
                            cx.notify();
                        })),
                )
                .child(div().font_weight(FontWeight::SEMIBOLD).child("Changes"))
                .child(
                    div()
                        .text_color(rgb(crate::views::theme::MUTED))
                        .child(format!("{} files", this.state.files.len())),
                ),
        )
        .child(
            uniform_list(
                "commit-file-list",
                if collapsed { 0 } else { this.state.files.len() },
                cx.processor(|this, range: std::ops::Range<usize>, _, cx| {
                    let mut order: Vec<_> = (0..this.state.files.len()).collect();
                    order.sort_by_key(|&i| {
                        let path = std::path::Path::new(&this.state.files[i].path);
                        (
                            path.file_name()
                                .unwrap_or_default()
                                .to_string_lossy()
                                .to_lowercase(),
                            this.state.files[i].path.clone(),
                        )
                    });
                    range
                        .map(|position| {
                            let i = order[position];
                            let file = &this.state.files[i];
                            let checked = this.file_selection.contains(&file.path);
                            let path = std::path::Path::new(&file.path);
                            let name = path
                                .file_name()
                                .unwrap_or_default()
                                .to_string_lossy()
                                .into_owned();
                            let directory = path
                                .parent()
                                .map(|p| p.display().to_string())
                                .unwrap_or_default();
                            div()
                                .id(("commit-file", i))
                                .h(px(28.))
                                .w_full()
                                .flex()
                                .items_center()
                                .gap_2()
                                .pl(px(54.))
                                .pr_3()
                                .overflow_hidden()
                                .when(this.state.selected == Some(i), |s| {
                                    s.bg(rgb(crate::views::theme::SELECTED))
                                })
                                .hover(|s| s.bg(rgb(crate::views::theme::HOVER)))
                                .child(
                                    div()
                                        .id(("commit-select", i))
                                        .size(px(18.))
                                        .flex_shrink_0()
                                        .cursor_pointer()
                                        .rounded(px(3.))
                                        .border_1()
                                        .border_color(rgb(if checked {
                                            crate::views::theme::ACCENT
                                        } else {
                                            0xa8b1c1
                                        }))
                                        .bg(rgb(if checked {
                                            crate::views::theme::ACCENT
                                        } else {
                                            crate::views::theme::SURFACE
                                        }))
                                        .text_color(rgb(crate::views::theme::SURFACE))
                                        .flex()
                                        .items_center()
                                        .justify_center()
                                        .child(if checked { "✓" } else { "" })
                                        .on_click(cx.listener(move |this, _, _, cx| {
                                            cx.stop_propagation();
                                            this.toggle_file_selection(i, cx);
                                        })),
                                )
                                .child(icons::file(&file.path))
                                .child(
                                    div()
                                        .flex_shrink_0()
                                        .text_color(rgb(crate::views::theme::ACCENT))
                                        .child(name),
                                )
                                .child(
                                    div()
                                        .flex_1()
                                        .min_w_0()
                                        .truncate()
                                        .text_color(rgb(crate::views::theme::MUTED))
                                        .child(directory),
                                )
                                .child(
                                    div()
                                        .flex_shrink_0()
                                        .text_color(rgb(crate::views::theme::MUTED))
                                        .child(file.status.clone()),
                                )
                                .cursor_pointer()
                                .on_click(cx.listener(move |this, _, window, cx| {
                                    window.focus(&this.files_focus);
                                    this.select_file(i, cx);
                                }))
                        })
                        .collect::<Vec<_>>()
                }),
            )
            .flex_1()
            .min_h_0()
            .w_full()
            .track_scroll(this.commit_files_scroll.clone())
            .with_decoration(crate::views::scrollbar::ListScrollbar(
                this.commit_files_scroll.clone(),
                None,
            )),
        )
}

fn can_commit(this: &MyGit, cx: &Context<MyGit>) -> bool {
    !this.write_busy
        && this.state.repo.is_some()
        && !this.file_selection.is_empty()
        && this
            .commit_editor
            .as_ref()
            .is_some_and(|editor| !editor.read(cx).buffer.text().trim().is_empty())
}
