use crate::app::MyGit;
use gpui::{prelude::*, *};

const REPOSITORY: &str = "https://github.com/wynemo/mygit";

fn link(id: &'static str, label: &'static str, url: String) -> Stateful<Div> {
    div()
        .id(id)
        .h(px(34.))
        .px_4()
        .rounded(px(8.))
        .flex()
        .items_center()
        .justify_center()
        .bg(rgb(super::theme::HOVER))
        .cursor_pointer()
        .hover(|s| s.bg(rgb(super::theme::SELECTED)))
        .child(label)
        .on_click(move |_, _, cx| cx.open_url(&url))
}

fn metadata(label: &'static str, value: impl IntoElement) -> Div {
    div()
        .flex()
        .gap_3()
        .items_center()
        .child(div().w(px(100.)).flex().justify_end().child(label))
        .child(div().w(px(130.)).child(value))
}

pub fn pane(window: &Window, cx: &mut Context<MyGit>) -> impl IntoElement {
    let height = (f32::from(window.viewport_size().height) - 32.).max(180.);
    let width = (f32::from(window.viewport_size().width) - 32.).clamp(240., 480.);
    div()
        .id("about-overlay")
        .absolute()
        .inset_0()
        .occlude()
        .flex()
        .items_center()
        .justify_center()
        .bg(rgba(0x00000030))
        .on_mouse_down(MouseButton::Left, |_, _, cx| cx.stop_propagation())
        .child(
            div()
                .id("about-dialog")
                .w(px(width))
                .max_h(px(height))
                .overflow_y_scroll()
                .p_4()
                .flex()
                .flex_col()
                .items_center()
                .rounded(px(14.))
                .border_1()
                .border_color(rgb(super::theme::BORDER))
                .bg(rgb(super::theme::CHROME))
                .shadow_lg()
                .child(
                    div().w_full().flex().justify_end().child(
                        div()
                            .id("close-about")
                            .size(px(26.))
                            .rounded_full()
                            .flex()
                            .items_center()
                            .justify_center()
                            .cursor_pointer()
                            .hover(|s| s.bg(rgb(super::theme::HOVER)))
                            .child("×")
                            .on_click(cx.listener(|this, _, _, cx| this.close_about(cx))),
                    ),
                )
                .child(
                    img(ImageSource::Resource(Resource::Embedded(
                        "icons/mygit.png".into(),
                    )))
                    .size(px(112.))
                    .flex_shrink_0(),
                )
                .child(
                    div()
                        .mt_4()
                        .text_size(px(30.))
                        .font_weight(FontWeight::BOLD)
                        .child("MyGit"),
                )
                .child(
                    div()
                        .mt_3()
                        .text_center()
                        .text_color(rgb(super::theme::MUTED))
                        .child(mygit_gpui::i18n::text(
                            "基于 Rust 与 GPUI 的 Git 桌面客户端。",
                        )),
                )
                .child(
                    div()
                        .mt_6()
                        .flex()
                        .flex_col()
                        .gap_2()
                        .child(metadata(
                            mygit_gpui::i18n::text("版本"),
                            env!("CARGO_PKG_VERSION"),
                        ))
                        .child(metadata(
                            mygit_gpui::i18n::text("构建提交"),
                            div()
                                .id("about-commit")
                                .text_color(rgb(0x2684ff))
                                .cursor_pointer()
                                .child(env!("MYGIT_BUILD_COMMIT"))
                                .on_click(|_, _, cx| {
                                    cx.open_url(&format!(
                                        "{REPOSITORY}/commit/{}",
                                        env!("MYGIT_BUILD_COMMIT")
                                    ))
                                }),
                        )),
                )
                .child(
                    div()
                        .mt_6()
                        .mb_3()
                        .flex()
                        .flex_wrap()
                        .justify_center()
                        .gap_2()
                        .child(link(
                            "about-docs",
                            mygit_gpui::i18n::text("文档"),
                            format!("{REPOSITORY}/blob/HEAD/gpui-prototype/README.md"),
                        ))
                        .child(link("about-github", "GitHub", REPOSITORY.into()))
                        .child(link(
                            "about-license",
                            mygit_gpui::i18n::text("许可证"),
                            format!("{REPOSITORY}/blob/HEAD/LICENSE"),
                        )),
                ),
        )
}
