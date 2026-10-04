//! Worktree editing remains available when the Git history/comparison panel is hidden.
use crate::{
    app::MyGit,
    views::{button, tabs},
};
use gpui::{prelude::*, *};
use mygit_gpui::{i18n, model::Revision};

pub fn pane(this: &MyGit, cx: &mut Context<MyGit>) -> impl IntoElement {
    let editor = this.current_editor();
    let can_edit = this.state.editable
        && this
            .state
            .comparison
            .as_ref()
            .is_some_and(|c| c.right == Revision::Worktree);
    div()
        .id("workspace-editor-pane")
        .key_context("WorkspaceEditor")
        .track_focus(&this.focus)
        .flex()
        .flex_col()
        .flex_1()
        .min_w_0()
        .min_h_0()
        .child(tabs::bar(this, cx))
        .child(
            div()
                .flex()
                .flex_wrap()
                .items_center()
                .gap_2()
                .p_2()
                .border_b_1()
                .border_color(rgb(0x2b3545))
                .child(
                    div()
                        .flex_1()
                        .min_w_0()
                        .overflow_hidden()
                        .whitespace_nowrap()
                        .child(
                            this.state
                                .current_file
                                .as_ref()
                                .map(|f| f.path.clone())
                                .unwrap_or_else(|| i18n::text("工作区编辑器").into()),
                        ),
                )
                .when(editor.is_none() && can_edit, |s| {
                    s.child(
                        button(
                            "workspace-edit-file",
                            i18n::text("编辑工作区"),
                            !this.state.loading,
                        )
                        .on_click(cx.listener(|this, _, window, cx| this.edit_current(window, cx))),
                    )
                })
                .when(can_edit && !this.state.loading, |s| {
                    s.child(
                        button(
                            "workspace-blame",
                            if this.show_blame {
                                i18n::text("隐藏 Blame")
                            } else {
                                "Blame"
                            },
                            true,
                        )
                        .on_click(cx.listener(|this, _, _, cx| this.toggle_blame(cx))),
                    )
                    .child(
                        button(
                            "workspace-history",
                            i18n::text("历史"),
                            this.state.current_file.is_some(),
                        )
                        .on_click(cx.listener(|this, _, _, cx| this.current_file_history(cx))),
                    )
                })
                .child(
                    button("workspace-show-git", i18n::text("显示 Git 面板"), true)
                        .on_click(cx.listener(|this, _, _, cx| this.reveal_git_panel(cx))),
                ),
        )
        .when(this.blame_loading, |s| {
            s.child(
                div()
                    .px_2()
                    .text_xs()
                    .text_color(rgb(0x92a2b9))
                    .child(i18n::text("正在读取两侧 Blame…")),
            )
        })
        .when(!this.blame_error.is_empty() && this.show_blame, |s| {
            s.child(
                div()
                    .px_2()
                    .text_xs()
                    .text_color(rgb(0xffd479))
                    .child(this.blame_error.clone()),
            )
        })
        .when_some(editor.clone(), |s, editor| s.child(editor))
        .when(editor.is_none(), |s| {
            s.child(
                div()
                    .flex_1()
                    .flex()
                    .flex_col()
                    .gap_2()
                    .items_center()
                    .justify_center()
                    .p_3()
                    .text_color(rgb(0x92a2b9))
                    .child(if this.state.repo.is_none() {
                        i18n::text("打开一个 Git 仓库开始浏览")
                    } else if this.state.current_file.is_some() && !can_edit {
                        i18n::text("当前标签是只读比较，显示 Git 面板查看")
                    } else {
                        i18n::text("Git 面板已隐藏，选择工作区文件继续编辑")
                    })
                    .when(
                        this.state.loading || this.state.current_file.is_some(),
                        |s| s.child(this.state.message.clone()),
                    ),
            )
        })
}
