use crate::{app::MyGit, views::button};
use gpui::{prelude::*, *};
pub fn pane(this: &MyGit, cx: &mut Context<MyGit>) -> impl IntoElement {
    let rows = this.tree.rows();
    div()
        .key_context("FilesList")
        .track_focus(&this.files_focus)
        .w(px(this.visible_files_width))
        .flex_shrink_0()
        .flex()
        .flex_col()
        .min_h_0()
        .border_r_1()
        .border_color(rgb(0x2b3545))
        .child(
            div()
                .p_2()
                .flex()
                .items_center()
                .gap_2()
                .child("工作区文件树")
                .child(
                    button(
                        "selected-tree-history",
                        "历史",
                        this.tree.selected.is_some(),
                    )
                    .on_click(cx.listener(|this, _, _, cx| this.selected_tree_history(cx))),
                )
                .child(
                    button("refresh-tree", "刷新", !this.tree_loading)
                        .on_click(cx.listener(|this, _, _, cx| this.refresh_tree(cx))),
                ),
        )
        .when(this.tree_loading, |s| {
            s.child(div().p_2().child("正在读取目录…"))
        })
        .when_some(this.tree_error.clone(), |s, e| {
            s.child(div().p_2().text_color(rgb(0xffd479)).child(e))
        })
        .child(
            uniform_list(
                "workspace-tree",
                rows.len(),
                cx.processor(|this, range: std::ops::Range<usize>, _, cx| {
                    let rows = this.tree.rows();
                    range
                        .filter_map(|i| {
                            rows.get(i).cloned().map(|(entry, depth)| {
                                let expanded = this.tree.expanded.contains(&entry.path);
                                let history_entry = entry.clone();
                                div()
                                    .id(("tree-entry", i))
                                    .h(px(30.))
                                    .pl(px(8. + depth as f32 * 14.))
                                    .pr_1()
                                    .overflow_hidden()
                                    .whitespace_nowrap()
                                    .cursor_pointer()
                                    .bg(rgb(if Some(&entry.path) == this.tree.selected.as_ref() {
                                        0x263b56
                                    } else {
                                        0x111722
                                    }))
                                    .text_color(rgb(if entry.status == "!!" {
                                        0x7f8b9c
                                    } else {
                                        0xdce5f3
                                    }))
                                    .child(format!(
                                        "{} {}  {}",
                                        if entry.directory {
                                            if expanded { "▾" } else { "▸" }
                                        } else if entry.symlink {
                                            "↗"
                                        } else {
                                            "·"
                                        },
                                        entry.name,
                                        entry.status
                                    ))
                                    .on_mouse_down(
                                        MouseButton::Right,
                                        cx.listener(move |this, _, _, cx| {
                                            this.show_path_history(
                                                history_entry.path.clone(),
                                                history_entry.directory,
                                                cx,
                                            );
                                            cx.stop_propagation();
                                        }),
                                    )
                                    .on_click(cx.listener(move |this, _, window, cx| {
                                        this.choose_tree(entry.clone(), window, cx)
                                    }))
                            })
                        })
                        .collect::<Vec<_>>()
                }),
            )
            .track_scroll(this.files_scroll.clone())
            .min_h_0()
            .flex_1(),
        )
}
