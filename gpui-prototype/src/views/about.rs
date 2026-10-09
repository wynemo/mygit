use crate::app::MyGit;
use gpui::{prelude::*, *};

pub fn pane(cx: &mut Context<MyGit>) -> impl IntoElement {
    div()
        .id("about-overlay")
        .absolute()
        .inset_0()
        .occlude()
        .flex()
        .items_center()
        .justify_center()
        .bg(rgba(0x00000088))
        .on_mouse_down(MouseButton::Left, |_, _, cx| cx.stop_propagation())
        .child(
            div()
                .id("about-dialog")
                .w(px(340.))
                .p_4()
                .flex()
                .flex_col()
                .gap_3()
                .rounded(px(10.))
                .border_1()
                .border_color(rgb(super::theme::BORDER))
                .bg(rgb(super::theme::CHROME))
                .shadow_lg()
                .child(mygit_gpui::i18n::text("关于"))
                .child(
                    div()
                        .text_xl()
                        .font_weight(FontWeight::SEMIBOLD)
                        .child("MyGit GPUI"),
                )
                // Cargo.toml's package.version is the single source of truth.
                .child(format!(
                    "{} {}",
                    mygit_gpui::i18n::text("版本"),
                    env!("CARGO_PKG_VERSION")
                ))
                .child(
                    div().flex().justify_end().child(
                        super::button("close-about", mygit_gpui::i18n::text("关闭"), true)
                            .on_click(cx.listener(|this, _, _, cx| this.close_about(cx))),
                    ),
                ),
        )
}
