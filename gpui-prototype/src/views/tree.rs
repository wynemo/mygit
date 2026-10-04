use crate::{
    app::{DismissTreeMenu, MyGit, TreeMenuAccept, TreeMenuDown, TreeMenuUp, tree_actions::Action},
    views::button,
};
use gpui::{prelude::*, *};
#[derive(Clone)]
pub struct DraggedFile {
    pub root: std::path::PathBuf,
    pub entry: mygit_gpui::workspace::Entry,
}
impl Render for DraggedFile {
    fn render(&mut self, _: &mut Window, _: &mut Context<Self>) -> impl IntoElement {
        div()
            .p_2()
            .rounded_md()
            .bg(rgb(0x263449))
            .text_color(rgb(0xdce5f3))
            .flex()
            .items_center()
            .gap_2()
            .child(crate::views::icons::file(&self.entry.path))
            .child(self.entry.path.clone())
    }
}
pub fn menu(this: &MyGit, window: &Window, cx: &mut Context<MyGit>) -> impl IntoElement {
    let menu = this.tree_menu.as_ref().expect("visible tree menu");
    let width = (f32::from(window.viewport_size().width) - 24.).clamp(0., 270.);
    let height = (f32::from(window.viewport_size().height) - 24.).clamp(0., 360.);
    let left = f32::from(menu.position.x).clamp(
        12.,
        (f32::from(window.viewport_size().width) - width - 12.).max(12.),
    );
    let top = f32::from(menu.position.y).clamp(
        12.,
        (f32::from(window.viewport_size().height) - height - 12.).max(12.),
    );
    div()
        .id("tree-menu")
        .absolute()
        .left(px(left))
        .top(px(top))
        .w(px(width))
        .max_h(px(height))
        .overflow_y_scroll()
        .occlude()
        .p_2()
        .rounded_md()
        .bg(rgb(0x1d293b))
        .border_1()
        .border_color(rgb(0x44546c))
        .key_context("TreeMenu")
        .track_focus(&this.tree_menu_focus)
        .on_action(cx.listener(|this, _: &TreeMenuUp, _, cx| this.move_tree_menu(false, cx)))
        .on_action(cx.listener(|this, _: &TreeMenuDown, _, cx| this.move_tree_menu(true, cx)))
        .on_action(
            cx.listener(|this, _: &TreeMenuAccept, window, cx| this.accept_tree_menu(window, cx)),
        )
        .on_action(cx.listener(|this, _: &DismissTreeMenu, window, cx| this.dismiss_tree_menu(window, cx)))
        .on_mouse_down_out(cx.listener(|this, _, window, cx| this.dismiss_tree_menu(window, cx)))
        .child(
            div()
                .text_xs()
                .text_color(rgb(0x92a2b9))
                .child(menu.entry.path.clone()),
        )
        .children(
            this.tree_menu_actions()
                .into_iter()
                .enumerate()
                .map(|(i, action)| {
                    div()
                        .id(("tree-menu-action", i))
                        .px_2()
                        .py_1()
                        .rounded_md()
                        .cursor_pointer()
                        .bg(rgb(if i == menu.selected {
                            0x344962
                        } else {
                            0x1d293b
                        }))
                        .hover(|s| s.bg(rgb(0x344962)))
                        .child(action.label())
                        .when(action == Action::Restore, |s| {
                            s.tooltip(|_, cx| {
                                cx.new(|_| {
                                    crate::views::hints::Hint(mygit_gpui::i18n::text("还原磁盘文件到 HEAD；index 保持原样；新文件将删除，先保存恢复记录，可撤销").into())
                                })
                                .into()
                            })
                        })
                        .on_click(cx.listener(move |this, _, window, cx| {
                            this.tree_menu_action(action, window, cx)
                        }))
                }),
        )
}
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
                .child(mygit_gpui::i18n::text("工作区文件树"))
                .child(
                    button(
                        "tree-actions",
                        mygit_gpui::i18n::text("文件操作"),
                        this.tree.selected.is_some(),
                    )
                    .on_click(
                        cx.listener(|this, _, window, cx| this.selected_tree_menu(window, cx)),
                    ),
                )
                .child(
                    button(
                        "selected-tree-history",
                        mygit_gpui::i18n::text("历史"),
                        this.tree.selected.is_some(),
                    )
                    .on_click(cx.listener(|this, _, _, cx| this.selected_tree_history(cx))),
                )
                .child(
                    button(
                        "refresh-tree",
                        mygit_gpui::i18n::text("刷新"),
                        !this.tree_loading,
                    )
                    .on_click(cx.listener(|this, _, _, cx| this.refresh_tree(cx))),
                ),
        )
        .when(this.tree_loading, |s| {
            s.child(div().p_2().child(mygit_gpui::i18n::text("正在读取目录…")))
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
                                let full_path = this
                                    .state
                                    .repo
                                    .as_ref()
                                    .map(|repo| repo.root.join(&entry.path).display().to_string())
                                    .unwrap_or_else(|| entry.path.clone());
                                let menu_entry = entry.clone();
                                let dragged =
                                    this.state.repo.as_ref().filter(|_| !entry.directory).map(
                                        |repo| DraggedFile {
                                            root: repo.root.clone(),
                                            entry: entry.clone(),
                                        },
                                    );
                                div()
                                    .id(("tree-entry", i))
                                    .h(px(30.))
                                    .pl(px(8. + depth as f32 * 14.))
                                    .pr_1()
                                    .flex()
                                    .items_center()
                                    .gap_1()
                                    .overflow_hidden()
                                    .whitespace_nowrap()
                                    .cursor_pointer()
                                    .tooltip(move |_, cx| {
                                        cx.new(|_| {
                                            crate::views::hints::Hint(full_path.clone().into())
                                        })
                                        .into()
                                    })
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
                                    .child(if entry.directory {
                                        if expanded { "▾" } else { "▸" }
                                    } else if entry.symlink {
                                        "↗"
                                    } else {
                                        " "
                                    })
                                    .child(if entry.directory {
                                        crate::views::icons::icon("icons/folder.svg")
                                            .into_any_element()
                                    } else {
                                        crate::views::icons::file(&entry.path).into_any_element()
                                    })
                                    .child(format!("{}  {}", entry.name, entry.status))
                                    .when_some(dragged, |s, file| {
                                        s.on_drag(file, |file, _, _, cx| cx.new(|_| file.clone()))
                                    })
                                    .on_mouse_down(
                                        MouseButton::Right,
                                        cx.listener(
                                            move |this, event: &MouseDownEvent, window, cx| {
                                                this.show_tree_menu(
                                                    menu_entry.clone(),
                                                    event.position,
                                                    window,
                                                    cx,
                                                );
                                                cx.stop_propagation();
                                            },
                                        ),
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
