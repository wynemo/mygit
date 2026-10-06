use crate::app::MyGit;
use gpui::{prelude::*, *};

pub fn menu(this: &MyGit, window: &Window, cx: &mut Context<MyGit>) -> impl IntoElement {
    let position = this.history_menu.as_ref().unwrap().0;
    div()
        .id("history-context-menu")
        .absolute()
        .occlude()
        .left(
            position
                .x
                .min(window.viewport_size().width - px(300.))
                .max(px(0.)),
        )
        .top(
            position
                .y
                .min(window.viewport_size().height - px(310.))
                .max(px(0.)),
        )
        .w(px(300.))
        .p_1()
        .rounded(px(8.))
        .shadow_md()
        .bg(rgb(super::theme::SURFACE))
        .border_1()
        .border_color(rgb(super::theme::BORDER))
        .on_mouse_down_out(cx.listener(|this, _, _, cx| {
            this.history_menu = None;
            cx.notify();
        }))
        .children(
            [
                "Copy Commit SHA",
                "Copy Commit Message",
                "Compare with Working Tree",
                "Reset Current Branch · Soft…",
                "Reset Current Branch · Mixed…",
                "Reset Current Branch · Hard…",
                "Checkout Commit (Detached HEAD)",
                "Branches at This Commit…",
            ]
            .into_iter()
            .enumerate()
            .map(|(action, label)| {
                div()
                    .id(("history-context-action", action))
                    .h(px(36.))
                    .px_3()
                    .flex()
                    .items_center()
                    .rounded(px(4.))
                    .cursor_pointer()
                    .when(action >= 3, |s| s.when(this.write_busy, |s| s.opacity(0.4)))
                    .hover(|s| s.bg(rgb(super::theme::SELECTED)))
                    .child(label)
                    .on_click(
                        cx.listener(move |this, _, _, cx| this.history_context_action(action, cx)),
                    )
            }),
        )
}
