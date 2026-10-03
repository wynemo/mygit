pub mod diff;
pub mod sidebar;
pub mod tabs;
pub mod text_line;
pub mod tree;
use crate::app::MyGit;
use gpui::{prelude::*, *};

pub fn button(id: &'static str, label: &'static str, enabled: bool) -> Stateful<Div> {
    div()
        .id(id)
        .px_3()
        .py_1()
        .rounded_md()
        .bg(rgb(0x263449))
        .when(enabled, |s| {
            s.hover(|s| s.bg(rgb(0x344962))).cursor_pointer()
        })
        .when(!enabled, |s| s.opacity(0.35))
        .child(label)
}
pub fn toolbar(this: &MyGit, cx: &mut Context<MyGit>) -> impl IntoElement {
    let title = this
        .state
        .repo
        .as_ref()
        .map(|r| format!("{}   /   {}", r.root.display(), r.branch))
        .unwrap_or_else(|| "MyGit · GPUI".into());
    div()
        .flex()
        .items_center()
        .gap_3()
        .p_3()
        .border_b_1()
        .border_color(rgb(0x2b3545))
        .child(div().font_weight(FontWeight::BOLD).child("MyGit"))
        .child(
            button("open", "打开仓库", true).on_click(cx.listener(|this, _, _, cx| this.open(cx))),
        )
        .child(
            button("refresh", "刷新", this.last_path.is_some()).on_click(cx.listener(
                |this, _, _, cx| {
                    if let Some(path) = this.last_path.clone() {
                        this.load(path, cx);
                    }
                },
            )),
        )
        .child(
            button("workspace-tree", "文件树", this.state.repo.is_some()).on_click(cx.listener(
                |this, _, window, cx| {
                    this.show_tree = !this.show_tree;
                    window.focus(&this.files_focus);
                    cx.notify();
                },
            )),
        )
        .child(
            button("settings", "设置 / 最近仓库", true).on_click(cx.listener(|this, _, _, cx| {
                this.show_settings = !this.show_settings;
                cx.notify();
            })),
        )
        .when(this.state.loading || this.history_loading, |s| {
            s.child(
                button("cancel-task", "取消加载", true)
                    .on_click(cx.listener(|this, _, _, cx| this.cancel_task(cx))),
            )
        })
        .child(
            div()
                .flex_1()
                .overflow_hidden()
                .whitespace_nowrap()
                .text_color(rgb(0x92a2b9))
                .child(title),
        )
}

pub fn settings(this: &MyGit, cx: &mut Context<MyGit>) -> impl IntoElement {
    div()
        .flex()
        .flex_col()
        .p_2()
        .gap_2()
        .border_b_1()
        .border_color(rgb(0x2b3545))
        .child(
            div()
                .flex()
                .gap_2()
                .items_center()
                .child(div().child(format!(
                    "字体：{} · {}",
                    this.state.font_family, this.state.font_size
                )))
                .child(
                    button("font-family", "切换字体", true)
                        .on_click(cx.listener(|this, _, _, cx| this.cycle_font(cx))),
                )
                .child(
                    button("history-narrower", "历史 −", true)
                        .on_click(cx.listener(|this, _, _, cx| this.resize_panel(true, false, cx))),
                )
                .child(
                    button("history-wider", "历史 +", true)
                        .on_click(cx.listener(|this, _, _, cx| this.resize_panel(true, true, cx))),
                )
                .child(
                    button("files-narrower", "文件 −", true).on_click(
                        cx.listener(|this, _, _, cx| this.resize_panel(false, false, cx)),
                    ),
                )
                .child(
                    button("files-wider", "文件 +", true)
                        .on_click(cx.listener(|this, _, _, cx| this.resize_panel(false, true, cx))),
                ),
        )
        .when_some(this.settings.warning.clone(), |s, warning| {
            s.child(div().text_color(rgb(0xffd479)).child(warning))
        })
        .children(
            this.settings
                .recent
                .iter()
                .enumerate()
                .map(|(i, path)| {
                    let path = path.clone();
                    div()
                        .id(("recent-repo", i))
                        .cursor_pointer()
                        .hover(|s| s.bg(rgb(0x263449)))
                        .child(path.display().to_string())
                        .on_click(cx.listener(move |this, _, _, cx| {
                            this.show_settings = false;
                            this.load(path.clone(), cx);
                        }))
                })
                .collect::<Vec<_>>(),
        )
}
