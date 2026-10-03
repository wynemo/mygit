pub mod commit;
pub mod compare;
pub mod diff;
pub mod editor;
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
            button(
                "undo-restore",
                "撤销还原",
                !this.write_busy && this.state.repo.is_some(),
            )
            .on_click(cx.listener(|this, _, _, cx| this.undo_restore(cx))),
        )
        .child(
            button("show-compare", "比较版本", this.state.repo.is_some())
                .on_click(cx.listener(|this, _, _, cx| this.toggle_compare(cx))),
        )
        .child(
            button("show-commit", "提交面板", this.state.repo.is_some())
                .on_click(cx.listener(|this, _, _, cx| this.toggle_commit(cx))),
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

pub fn confirmation(this: &MyGit, cx: &mut Context<MyGit>) -> impl IntoElement {
    let restore = match &this.confirmation {
        Some(crate::app::Confirmation::Restore {
            file,
            comparison,
            block,
            ..
        }) => Some(format!(
            "{}：{} → 工作区磁盘\n目标：{}{}\nindex 保持原样；先保存恢复记录，可用“撤销还原”恢复。",
            if block.is_some() {
                "还原当前差异块"
            } else {
                "还原整文件"
            },
            comparison.left.label(),
            file.path,
            if file.old_path != file.path {
                format!("、{}", file.old_path)
            } else {
                String::new()
            }
        )),
        _ => None,
    };
    let paths = this
        .editors
        .iter()
        .filter(|(_, e)| e.read(cx).buffer.dirty())
        .map(|(path, _)| path.clone())
        .collect::<Vec<_>>();
    div()
        .absolute()
        .inset_0()
        .flex()
        .items_center()
        .justify_center()
        .bg(rgba(0x000000bb))
        .child(
            div()
                .w(px(520.))
                .p_4()
                .rounded_lg()
                .bg(rgb(0x1b2637))
                .flex()
                .flex_col()
                .gap_3()
                .child(if restore.is_some() {
                    "确认还原"
                } else {
                    "存在未保存内容"
                })
                .when_some(restore.clone(), |s, text| s.child(text))
                .children(
                    paths
                        .into_iter()
                        .filter(|_| restore.is_none())
                        .map(|path| div().child(path)),
                )
                .when(restore.is_none(), |s| {
                    s.child("保存失败时会保留编辑器内容，并停止关闭或切换。")
                })
                .child(
                    div()
                        .flex()
                        .gap_2()
                        .child(
                            button(
                                "save-and-continue",
                                if restore.is_some() {
                                    "确认还原"
                                } else {
                                    "保存并继续"
                                },
                                true,
                            )
                            .on_click(cx.listener(|this, _, _, cx| this.confirm_pending(true, cx))),
                        )
                        .when(restore.is_none(), |s| {
                            s.child(
                                button("discard-and-continue", "放弃修改并继续", true).on_click(
                                    cx.listener(|this, _, _, cx| this.confirm_pending(false, cx)),
                                ),
                            )
                        })
                        .child(
                            button("cancel-confirmation", "取消", true).on_click(cx.listener(
                                |this, _, _, cx| {
                                    this.confirmation = None;
                                    cx.notify();
                                },
                            )),
                        ),
                ),
        )
}
