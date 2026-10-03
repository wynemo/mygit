pub mod diff;
pub mod sidebar;
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
            button("refresh", "刷新", this.state.repo.is_some()).on_click(cx.listener(
                |this, _, _, cx| {
                    if let Some(repo) = &this.state.repo {
                        this.load(repo.root.clone(), cx);
                    }
                },
            )),
        )
        .child(
            div()
                .flex_1()
                .overflow_hidden()
                .whitespace_nowrap()
                .text_color(rgb(0x92a2b9))
                .child(title),
        )
}
