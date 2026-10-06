use crate::{app::MyGit, views::button};
use gpui::{prelude::*, *};
pub fn bar(this: &MyGit, cx: &mut Context<MyGit>) -> impl IntoElement {
    div()
        .flex()
        .items_center()
        .flex_shrink_0()
        .min_w_0()
        .overflow_hidden()
        .h(px(27.))
        .drag_over::<crate::views::tree::DraggedFile>(|s, _, _, _| s.bg(rgb(0xdceafa)))
        .on_drop(
            cx.listener(|this, file: &crate::views::tree::DraggedFile, window, cx| {
                this.drop_tree_file(file, window, cx)
            }),
        )
        .border_b_1()
        .border_color(rgb(0xc8c8c8))
        .when(!this.tabs.is_empty(), |s| {
            s.child(
                div()
                    .id("file-tabs")
                    .flex()
                    .flex_1()
                    .min_w_0()
                    .overflow_x_scroll()
                    .children(
                        this.tabs
                            .iter()
                            .enumerate()
                            .map(|(i, tab)| {
                                div()
                                    .id(("file-tab", i))
                                    .flex()
                                    .flex_shrink_0()
                                    .items_center()
                                    .whitespace_nowrap()
                                    .gap_2()
                                    .px_2()
                                    .h(px(26.))
                                    .border_r_1()
                                    .border_color(rgb(0xc8c8c8))
                                    .bg(rgb(if this.active_tab == Some(i) {
                                        0xdceafa
                                    } else {
                                        0xffffff
                                    }))
                                    .tooltip({
                                        let path = tab.file.path.clone();
                                        move |_, cx| {
                                            cx.new(|_| {
                                                crate::views::hints::Hint(path.clone().into())
                                            })
                                            .into()
                                        }
                                    })
                                    .on_mouse_down(
                                        MouseButton::Right,
                                        cx.listener(move |this, event: &MouseDownEvent, _, cx| {
                                            this.tab_menu = Some(event.position);
                                            cx.stop_propagation();
                                            cx.notify();
                                        }),
                                    )
                                    .child(
                                        div()
                                            .id(("activate-tab", i))
                                            .cursor_pointer()
                                            .flex()
                                            .items_center()
                                            .gap_2()
                                            .child(crate::views::icons::file(&tab.file.path))
                                            .child(format!(
                                                "{}{}",
                                                if this.is_dirty(&tab.file.path, cx) {
                                                    "● "
                                                } else {
                                                    ""
                                                },
                                                std::path::Path::new(&tab.file.path)
                                                    .file_name()
                                                    .unwrap_or_default()
                                                    .to_string_lossy()
                                            ))
                                            .on_click(cx.listener(move |this, _, _, cx| {
                                                this.activate_tab(i, cx)
                                            })),
                                    )
                                    .child(
                                        div()
                                            .id(("close-tab", i))
                                            .cursor_pointer()
                                            .child("×")
                                            .on_click(cx.listener(move |this, _, _, cx| {
                                                this.close_tab(i, cx)
                                            })),
                                    )
                            })
                            .collect::<Vec<_>>(),
                    ),
            )
        })
}

pub fn menu(this: &MyGit, cx: &mut Context<MyGit>) -> impl IntoElement {
    let position = this.tab_menu.unwrap_or_default();
    div()
        .id("tab-context-menu")
        .absolute()
        .left(position.x)
        .top(position.y)
        .occlude()
        .w(px(160.))
        .p_1()
        .bg(rgb(0xffffff))
        .border_1()
        .border_color(rgb(0xbcbcbc))
        .on_mouse_down_out(cx.listener(|this, _, _, cx| {
            this.tab_menu = None;
            cx.notify();
        }))
        .child(
            button(
                "close-other-tabs",
                mygit_gpui::i18n::text("关闭其他"),
                this.active_tab.is_some(),
            )
            .on_click(cx.listener(|this, _, _, cx| {
                this.tab_menu = None;
                this.close_other_tabs(false, cx);
            })),
        )
        .child(
            button("close-all-tabs", mygit_gpui::i18n::text("关闭全部"), true).on_click(
                cx.listener(|this, _, _, cx| {
                    this.tab_menu = None;
                    this.close_other_tabs(true, cx);
                }),
            ),
        )
}
