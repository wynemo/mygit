use crate::{app::MyGit, views::button};
use gpui::{prelude::*, *};
use mygit_gpui::{i18n, notifications::Kind};
fn color(kind: Kind) -> u32 {
    match kind {
        Kind::Success => 0x86d7a0,
        Kind::Error => 0xffa0a0,
        Kind::Info => 0x9cc7ff,
    }
}
fn label(kind: Kind) -> &'static str {
    i18n::text(match kind {
        Kind::Success => "操作完成",
        Kind::Error => "操作失败",
        Kind::Info => "提示",
    })
}
pub fn pane(this: &MyGit, window: &Window, cx: &mut Context<MyGit>) -> impl IntoElement {
    let width = (f32::from(window.viewport_size().width) - 24.).clamp(0., 420.);
    let height = (f32::from(window.viewport_size().height) - 24.).clamp(0., 480.);
    div()
        .id("notifications-overlay")
        .absolute()
        .right(px(12.))
        .bottom(px(12.))
        .w(px(width))
        .max_h(px(height))
        .occlude()
        .flex()
        .flex_col()
        .p_3()
        .gap_2()
        .rounded_md()
        .border_1()
        .border_color(rgb(0xb9b9b9))
        .bg(rgb(0xffffff))
        .when(this.show_notifications, |s| {
            s.h(px(height))
                .child(
                    div()
                        .flex()
                        .flex_shrink_0()
                        .items_center()
                        .gap_2()
                        .child(div().flex_1().child(i18n::text("最近通知")))
                        .child(
                            button(
                                "clear-notifications",
                                i18n::text("清空"),
                                !this.notifications.entries().is_empty(),
                            )
                            .on_click(cx.listener(|this, _, _, cx| {
                                this.notifications.clear();
                                cx.notify();
                            })),
                        )
                        .child(
                            button("close-notifications", i18n::text("关闭"), true).on_click(
                                cx.listener(|this, _, _, cx| this.toggle_notifications(cx)),
                            ),
                        ),
                )
                .child(
                    div()
                        .id("notification-history")
                        .overflow_y_scroll()
                        .min_h_0()
                        .flex_1()
                        .when(this.notifications.entries().is_empty(), |s| {
                            s.child(i18n::text("暂无通知"))
                        })
                        .children(this.notifications.entries().iter().map(|notice| {
                            let id = notice.id;
                            div()
                                .id(("notice", id))
                                .flex()
                                .flex_col()
                                .gap_1()
                                .py_2()
                                .border_b_1()
                                .border_color(rgb(0x39475b))
                                .child(
                                    div()
                                        .text_color(rgb(color(notice.kind)))
                                        .child(label(notice.kind)),
                                )
                                .when_some(notice.repository.clone(), |s, root| {
                                    s.child(
                                        div()
                                            .text_xs()
                                            .text_color(rgb(0x666666))
                                            .child(root.display().to_string()),
                                    )
                                })
                                .child(div().text_sm().child(notice.message.clone()))
                                .child(
                                    button("copy-notice", i18n::text("复制详情"), true).on_click(
                                        cx.listener(move |this, _, _, cx| {
                                            this.copy_notification(id, cx)
                                        }),
                                    ),
                                )
                        })),
                )
        })
        .when(!this.show_notifications, |s| {
            s.when_some(this.notifications.active().cloned(), |s, notice| {
                let id = notice.id;
                s.child(
                    div()
                        .text_color(rgb(color(notice.kind)))
                        .child(label(notice.kind)),
                )
                .when_some(notice.repository.clone(), |s, root| {
                    s.child(
                        div()
                            .text_xs()
                            .text_color(rgb(0x666666))
                            .child(root.display().to_string()),
                    )
                })
                .child(div().text_sm().child(notice.summary()))
                .child(
                    div()
                        .flex()
                        .gap_2()
                        .child(
                            button("notice-details", i18n::text("查看详情"), true).on_click(
                                cx.listener(|this, _, _, cx| this.toggle_notifications(cx)),
                            ),
                        )
                        .child(
                            button("copy-notice", i18n::text("复制详情"), true).on_click(
                                cx.listener(move |this, _, _, cx| this.copy_notification(id, cx)),
                            ),
                        )
                        .child(button("dismiss-notice", i18n::text("关闭"), true).on_click(
                            cx.listener(move |this, _, _, cx| {
                                this.notifications.dismiss(id);
                                cx.notify();
                            }),
                        )),
                )
            })
        })
}
