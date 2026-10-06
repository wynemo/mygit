pub mod blame;
pub mod branches;
pub mod commit;
pub mod compare;
pub mod diff;
pub mod editor;
pub mod hints;
pub mod history;
pub mod history_branch_menu;
pub mod history_menu;
pub mod icons;
pub mod layout;
pub mod notifications;
pub mod scrollbar;
pub mod settings_dialog;
pub mod sidebar;
pub mod tabs;
pub mod text_line;
pub mod theme;
pub mod tree;
pub mod workspace;
use crate::app::MyGit;
use gpui::{prelude::*, *};

pub fn button(id: &'static str, label: &'static str, enabled: bool) -> Stateful<Div> {
    div()
        .id(id)
        .flex_shrink_0()
        .whitespace_nowrap()
        .h(px(30.))
        .px_2()
        .rounded(px(6.))
        .border_1()
        .border_color(rgb(crate::views::theme::BORDER))
        .bg(rgb(crate::views::theme::SURFACE))
        .flex()
        .items_center()
        .gap_1()
        .when(enabled, |s| {
            s.cursor_pointer()
                .hover(|s| s.bg(rgb(crate::views::theme::HOVER)))
        })
        .when(!enabled, |s| s.opacity(0.4))
        .when_some(icons::button_icon(id), |s, path| s.child(icons::icon(path)))
        .child(label)
        .when_some(hints::button_hint(id), |s, text| {
            s.tooltip(move |_, cx| cx.new(|_| hints::Hint(text.into())).into())
        })
}

pub fn toolbar_button(id: &'static str, label: &'static str, enabled: bool) -> Stateful<Div> {
    let path = icons::button_icon(id);
    div()
        .id(id)
        .h(px(30.))
        .min_w(px(24.))
        .px_1()
        .flex_shrink_0()
        .flex()
        .items_center()
        .justify_center()
        .when(enabled, |s| {
            s.cursor_pointer()
                .hover(|s| s.bg(rgb(crate::views::theme::HOVER)))
        })
        .when(!enabled, |s| s.opacity(0.35))
        .when_some(path, |s, path| s.child(icons::icon(path)))
        .when(path.is_none(), |s| s.child(label))
        .tooltip(move |_, cx| cx.new(|_| hints::Hint(label.into())).into())
}

pub fn toolbar(this: &MyGit, cx: &mut Context<MyGit>) -> impl IntoElement {
    let branch = this
        .state
        .repo
        .as_ref()
        .map(|r| r.branch.clone())
        .unwrap_or_default();
    div()
        .h(px(56.))
        .flex_shrink_0()
        .flex()
        .items_center()
        .gap(px(10.))
        .px(px(16.))
        .bg(rgb(crate::views::theme::CHROME))
        .child(
            button("open", mygit_gpui::i18n::text("打开文件夹"), true)
                .w(px(114.))
                .on_click(cx.listener(|this, _, _, cx| this.open(cx))),
        )
        .child(
            button(
                "recent",
                mygit_gpui::i18n::text("最近"),
                !this.settings.recent.is_empty(),
            )
            .w(px(62.))
            .child(" ▾")
            .on_click(cx.listener(|this, _, _, cx| {
                this.show_recent = !this.show_recent;
                this.show_branch_dropdown = false;
                cx.notify();
            })),
        )
        .child(
            div()
                .id("show-branches")
                .w(px(240.))
                .h(px(32.))
                .flex()
                .items_center()
                .px_2()
                .gap_2()
                .child(icons::icon("icons/git_branch.svg"))
                .bg(rgb(crate::views::theme::SURFACE))
                .border_1()
                .border_color(rgb(crate::views::theme::BORDER))
                .rounded(px(4.))
                .cursor_pointer()
                .child(
                    div()
                        .flex_1()
                        .min_w_0()
                        .overflow_hidden()
                        .whitespace_nowrap()
                        .child(branch),
                )
                .child("▾")
                .on_click(cx.listener(|this, _, _, cx| {
                    this.show_branch_dropdown = !this.show_branch_dropdown;
                    this.show_recent = false;
                    cx.notify();
                })),
        )
        .child(
            button("new-branch", "+", this.state.repo.is_some())
                .w(px(38.))
                .on_click(cx.listener(|this, _, window, cx| {
                    this.toggle_branches(cx);
                    if let Some(editor) = &this.branch_name {
                        window.focus(&editor.read(cx).focus);
                    }
                })),
        )
        .child(div().flex_1())
        .child(
            button("settings", mygit_gpui::i18n::text("设置"), true)
                .on_click(cx.listener(|this, _, _, cx| this.toggle_settings(cx))),
        )
        .child(
            button("toggle-git-panel", "", true)
            .w(px(30.))
            .px_0()
            .gap_0()
            .justify_center()
            .child(icons::icon(if this.settings.git_panel_visible {
                "icons/panel-chevron-down.svg"
            } else {
                "icons/panel-chevron-up.svg"
            }))
            .on_click(cx.listener(|this, _, window, cx| this.toggle_git_panel(window, cx))),
        )
        .child(
            button("toggle-files-panel", "", true)
            .w(px(30.))
            .px_0()
            .gap_0()
            .justify_center()
            .child(icons::icon(if this.settings.files_visible {
                "icons/panel-chevron-left.svg"
            } else {
                "icons/panel-chevron-right.svg"
            }))
            .on_click(cx.listener(|this, _, window, cx| {
                this.toggle_files_panel(cx);
                window.focus(&this.focus);
            })),
        )
}

pub fn toolbar_menu(this: &MyGit, cx: &mut Context<MyGit>) -> impl IntoElement {
    div()
        .id("toolbar-menu")
        .absolute()
        .top(px(50.))
        .left(px(if this.show_recent { 140. } else { 212. }))
        .w(px(if this.show_recent { 450. } else { 280. }))
        .max_h(px(300.))
        .overflow_y_scroll()
        .occlude()
        .p_1()
        .bg(rgb(crate::views::theme::SURFACE))
        .border_1()
        .border_color(rgb(crate::views::theme::BORDER))
        .rounded(px(4.))
        .on_mouse_down_out(cx.listener(|this, _, _, cx| {
            this.show_recent = false;
            this.show_branch_dropdown = false;
            cx.notify();
        }))
        .when(this.show_recent, |s| {
            s.children(this.settings.recent.iter().enumerate().map(|(i, path)| {
                let path = path.clone();
                div()
                    .id(("recent-menu", i))
                    .h(px(30.))
                    .px_2()
                    .cursor_pointer()
                    .hover(|s| s.bg(rgb(crate::views::theme::SELECTED)))
                    .child(path.display().to_string())
                    .on_click(cx.listener(move |this, _, _, cx| {
                        this.show_recent = false;
                        this.load(path.clone(), cx);
                    }))
            }))
        })
        .when(this.show_branch_dropdown, |s| {
            s.children(
                this.state
                    .repo
                    .as_ref()
                    .into_iter()
                    .flat_map(|r| r.branches.iter())
                    .enumerate()
                    .map(|(i, branch)| {
                        let reference = branch.reference.clone();
                        div()
                            .id(("branch-menu", i))
                            .h(px(30.))
                            .px_2()
                            .cursor_pointer()
                            .hover(|s| s.bg(rgb(crate::views::theme::SELECTED)))
                            .child(format!(
                                "{}{}",
                                if branch.current { "✓ " } else { "  " },
                                branch.name
                            ))
                            .on_click(cx.listener(move |this, _, _, cx| {
                                this.show_branch_dropdown = false;
                                this.branch_selected = Some(reference.clone());
                                this.switch_branch(cx);
                            }))
                    }),
            )
        })
}

pub fn confirmation(this: &MyGit, cx: &mut Context<MyGit>) -> impl IntoElement {
    let restore = match &this.confirmation {
        Some(crate::app::Confirmation::Restore {
            file,
            comparison,
            block,
            ..
        }) => Some(mygit_gpui::localized_format!(
            "{}：{} → 工作区磁盘\n目标：{}{}{}\nindex 保持原样；先保存恢复记录，可用“撤销还原”恢复。",
            "{}: {} → worktree on disk\nTarget: {}{}{}\nThe index is preserved. Recovery data is saved first; use Undo restore to recover.",
            if block.is_some() {
                mygit_gpui::i18n::text("还原当前差异块")
            } else {
                mygit_gpui::i18n::text("还原整文件")
            },
            comparison.left.label(),
            file.path,
            if file.old_path != file.path {
                format!("、{}", file.old_path)
            } else {
                String::new()
            },
            if block.is_none()
                && comparison.targets(file).0.revision == mygit_gpui::model::Revision::Empty
            {
                mygit_gpui::i18n::text("\n来源中不存在该文件，确认后将删除磁盘文件。")
            } else {
                ""
            }
        )),
        Some(crate::app::Confirmation::Reset {
            target,
            mode,
            expected_head,
            expected_branch,
        }) => Some(mygit_gpui::localized_format!(
            "{}\n目标提交：{}\n当前 HEAD：{}\n当前分支：{}\n这是本地操作，不会推送远程。已提交内容可从 reflog 查找。",
            "{}\nTarget commit: {}\nCurrent HEAD: {}\nCurrent branch: {}\nThis is a local operation; it does not push. Committed content can be found in the reflog.",
            mode.description(),
            target,
            expected_head
                .as_deref()
                .unwrap_or(mygit_gpui::i18n::text("空仓库")),
            expected_branch.as_deref().unwrap_or("detached HEAD")
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
                .bg(rgb(crate::views::theme::CHROME))
                .flex()
                .flex_col()
                .gap_3()
                .child(if restore.is_some() {
                    if matches!(
                        this.confirmation,
                        Some(crate::app::Confirmation::Reset { .. })
                    ) {
                        mygit_gpui::i18n::text("确认 Reset")
                    } else {
                        mygit_gpui::i18n::text("确认还原")
                    }
                } else {
                    mygit_gpui::i18n::text("存在未保存内容")
                })
                .when_some(restore.clone(), |s, text| s.child(text))
                .children(
                    paths
                        .into_iter()
                        .filter(|_| restore.is_none())
                        .map(|path| div().child(path)),
                )
                .when(restore.is_none(), |s| {
                    s.child(mygit_gpui::i18n::text(
                        "保存失败时会保留编辑器内容，并停止关闭或切换。",
                    ))
                })
                .child(
                    div()
                        .flex()
                        .gap_2()
                        .child(
                            button(
                                "save-and-continue",
                                if restore.is_some() {
                                    if matches!(
                                        this.confirmation,
                                        Some(crate::app::Confirmation::Reset { .. })
                                    ) {
                                        mygit_gpui::i18n::text("确认 Reset")
                                    } else {
                                        mygit_gpui::i18n::text("确认还原")
                                    }
                                } else {
                                    mygit_gpui::i18n::text("保存并继续")
                                },
                                true,
                            )
                            .on_click(cx.listener(|this, _, _, cx| this.confirm_pending(true, cx))),
                        )
                        .when(restore.is_none(), |s| {
                            s.child(
                                button(
                                    "discard-and-continue",
                                    mygit_gpui::i18n::text("放弃修改并继续"),
                                    true,
                                )
                                .on_click(
                                    cx.listener(|this, _, _, cx| this.confirm_pending(false, cx)),
                                ),
                            )
                        })
                        .child(
                            button("cancel-confirmation", mygit_gpui::i18n::text("取消"), true)
                                .on_click(cx.listener(|this, _, _, cx| {
                                    this.confirmation = None;
                                    cx.notify();
                                })),
                        ),
                ),
        )
}

pub mod graph;

pub mod merge;

pub mod quick_open;
pub mod search;

pub fn popover(content: AnyElement) -> impl IntoElement {
    div()
        .absolute()
        .top(px(55.))
        .right(px(12.))
        .w(px(650.))
        .max_h(px(600.))
        .occlude()
        .bg(rgb(crate::views::theme::CHROME))
        .border_1()
        .border_color(rgb(crate::views::theme::BORDER))
        .shadow_md()
        .child(content)
}
