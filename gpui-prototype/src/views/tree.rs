use crate::app::{
    DismissTreeMenu, MyGit, TreeMenuAccept, TreeMenuDown, TreeMenuUp, tree_actions::Action,
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
            .bg(rgb(crate::views::theme::CHROME))
            .text_color(rgb(crate::views::theme::TEXT))
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
        .bg(rgb(crate::views::theme::SURFACE))
        .border_1()
        .border_color(rgb(crate::views::theme::BORDER))
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
                .text_color(rgb(crate::views::theme::MUTED))
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
                            crate::views::theme::HOVER
                        } else {
                            crate::views::theme::SURFACE
                        }))
                        .hover(|s| s.bg(rgb(crate::views::theme::HOVER)))
                        .child(if action == Action::History && menu.entry.directory { mygit_gpui::i18n::text("目录历史") } else { action.label() })
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
        .track_focus(&this.tree_focus)
        .w(px(this.visible_files_width))
        .flex_shrink_0()
        .flex()
        .flex_col()
        .min_h_0()
        .border_r_1()
        .border_color(rgb(crate::views::theme::BORDER))
        .child(
            div()
                .h(px(32.))
                .flex()
                .items_center()
                .flex_shrink_0()
                .px_1()
                .bg(rgb(crate::views::theme::CHROME))
                .border_b_1()
                .border_color(rgb(crate::views::theme::BORDER))
                .child(mygit_gpui::i18n::text("工作区文件")),
        )
        .when(this.tree_loading, |s| {
            s.child(div().p_2().child(mygit_gpui::i18n::text("正在读取目录…")))
        })
        .when_some(this.tree_error.clone(), |s, e| {
            s.child(div().p_2().text_color(rgb(0x946200)).child(e))
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
                                    .w_full()
                                    .h(px(28.))
                                    .pl(px(8. + depth as f32 * 14.))
                                    .pr_1()
                                    .flex()
                                    .items_center()
                                    .gap_1()
                                    .overflow_hidden()
                                    .whitespace_nowrap()
                                    .cursor_pointer()
                                    .when(this.tree_menu.is_none(), |s| {
                                        s.tooltip(move |_, cx| {
                                            cx.new(|_| {
                                                crate::views::hints::Hint(full_path.clone().into())
                                            })
                                            .into()
                                        })
                                    })
                                    .bg(rgb(if Some(&entry.path) == this.tree.selected.as_ref() {
                                        crate::views::theme::SELECTED
                                    } else {
                                        crate::views::theme::SURFACE
                                    }))
                                    .text_color(rgb(if entry.status == "!!" {
                                        0x888888
                                    } else if !entry.status.is_empty() {
                                        0xa52a2a
                                    } else {
                                        crate::views::theme::TEXT
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
                                    .child(entry.name.clone())
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
            .w_full()
            .with_decoration(crate::views::scrollbar::ListScrollbar(
                this.tree_scroll.clone(),
                None,
            ))
            .bg(rgb(crate::views::theme::SURFACE))
            .track_scroll(this.tree_scroll.clone())
            .min_h_0()
            .flex_1(),
        )
}
