use crate::{app::MyGit, views::button};
use gpui::{prelude::*, *};
pub fn pane(this: &MyGit, cx: &mut Context<MyGit>) -> impl IntoElement {
    div()
        .id("history-filter-pane")
        .max_h(px(210.))
        .overflow_y_scroll()
        .flex()
        .flex_col()
        .flex_shrink_0()
        .p_2()
        .gap_2()
        .border_b_1()
        .border_color(rgb(0x2b3545))
        .child(
            div()
                .flex()
                .flex_wrap()
                .gap_2()
                .items_center()
                .child("历史搜索 · 消息全文 / SHA / 作者")
                .child(
                    button("apply-history-filter", "搜索", !this.history_loading)
                        .on_click(cx.listener(|this, _, _, cx| this.search_history_inputs(cx))),
                )
                .child(
                    button("clear-history-filter", "恢复普通历史", true)
                        .on_click(cx.listener(|this, _, _, cx| this.clear_history_filter(cx))),
                )
                .child(
                    button("close-history-filter", "关闭面板", true).on_click(cx.listener(
                        |this, _, _, cx| {
                            this.show_history_search = false;
                            cx.notify();
                        },
                    )),
                ),
        )
        .children(
            [
                "查询",
                "范围（HEAD / 分支 / 标签 / ALL）",
                "作者过滤",
                "开始日期 YYYY-MM-DD",
                "结束日期 YYYY-MM-DD",
            ]
            .into_iter()
            .enumerate()
            .filter_map(|(index, label)| {
                this.history_inputs.get(index).map(|editor| {
                    div()
                        .flex()
                        .gap_2()
                        .items_center()
                        .child(div().w(px(240.)).child(label))
                        .child(div().flex_1().min_w_0().h(px(32.)).child(editor.clone()))
                })
            }),
        )
        .when_some(this.history_path.clone(), |s, (path, directory)| {
            s.child(format!(
                "{}历史：{}",
                if directory {
                    "目录"
                } else {
                    "跟随重命名的文件"
                },
                path
            ))
        })
        .when_some(this.history_search_error.clone(), |s, error| {
            s.child(div().text_color(rgb(0xffd479)).child(error))
        })
}
