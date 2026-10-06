pub mod blame;
pub mod branches;
pub mod commit;
pub mod compare;
pub mod diff;
pub mod editor;
pub mod hints;
pub mod history;
pub mod icons;
pub mod layout;
pub mod notifications;
pub mod scrollbar;
pub mod sidebar;
pub mod tabs;
pub mod text_line;
pub mod tree;
pub mod workspace;
use crate::app::MyGit;
use gpui::{prelude::*, *};

pub fn button(id: &'static str, label: &'static str, enabled: bool) -> Stateful<Div> {
    div()
        .id(id)
        .flex_shrink_0()
        .whitespace_nowrap()
        .h(px(24.))
        .px_2()
        .rounded(px(3.))
        .border_1()
        .border_color(rgb(0xbcbcbc))
        .bg(rgb(0xf8f8f8))
        .flex()
        .items_center()
        .gap_1()
        .when(enabled, |s| {
            s.cursor_pointer().hover(|s| s.bg(rgb(0xe5e5e5)))
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
        .h(px(24.))
        .min_w(px(24.))
        .px_1()
        .flex_shrink_0()
        .flex()
        .items_center()
        .justify_center()
        .when(enabled, |s| {
            s.cursor_pointer().hover(|s| s.bg(rgb(0xe3e3e3)))
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
        .h(px(50.))
        .flex_shrink_0()
        .flex()
        .items_center()
        .gap(px(10.))
        .px(px(10.))
        .bg(rgb(0xececec))
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
        .child(mygit_gpui::i18n::text("分支："))
        .child(icons::icon("icons/git_branch.svg"))
        .child(
            div()
                .id("show-branches")
                .w(px(280.))
                .h(px(24.))
                .flex()
                .items_center()
                .px_2()
                .gap_2()
                .bg(rgb(0xffffff))
                .border_1()
                .border_color(rgb(0xbcbcbc))
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
            button(
                "toggle-git-panel",
                if this.settings.git_panel_visible {
                    "⌄"
                } else {
                    "⌃"
                },
                true,
            )
            .on_click(cx.listener(|this, _, window, cx| this.toggle_git_panel(window, cx))),
        )
        .child(
            button(
                "toggle-files-panel",
                if this.settings.files_visible {
                    "‹"
                } else {
                    "›"
                },
                true,
            )
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
        .top(px(45.))
        .left(px(if this.show_recent { 135. } else { 285. }))
        .w(px(if this.show_recent { 450. } else { 280. }))
        .max_h(px(300.))
        .overflow_y_scroll()
        .occlude()
        .p_1()
        .bg(rgb(0xffffff))
        .border_1()
        .border_color(rgb(0xbcbcbc))
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
                    .h(px(24.))
                    .px_2()
                    .cursor_pointer()
                    .hover(|s| s.bg(rgb(0xdceafa)))
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
                            .h(px(24.))
                            .px_2()
                            .cursor_pointer()
                            .hover(|s| s.bg(rgb(0xdceafa)))
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

pub fn settings(this: &MyGit, cx: &mut Context<MyGit>) -> impl IntoElement {
    div()
        .id("settings-pane")
        .max_h(px(400.))
        .overflow_y_scroll()
        .flex_shrink_0()
        .flex()
        .flex_col()
        .p_2()
        .gap_2()
        .border_b_1()
        .border_color(rgb(0xc8c8c8))
        .child(
            div()
                .flex()
                .gap_2()
                .items_center()
                .child(mygit_gpui::i18n::text("界面语言"))
                .child(
                    button("language-zh", "中文", true)
                        .when(
                            this.settings.language == mygit_gpui::i18n::Language::Chinese,
                            |s| s.border_1().border_color(rgb(0x2196f3)),
                        )
                        .on_click(cx.listener(|this, _, _, cx| {
                            this.select_language(mygit_gpui::i18n::Language::Chinese, cx)
                        })),
                )
                .child(
                    button("language-en", "English", true)
                        .when(
                            this.settings.language == mygit_gpui::i18n::Language::English,
                            |s| s.border_1().border_color(rgb(0x2196f3)),
                        )
                        .on_click(cx.listener(|this, _, _, cx| {
                            this.select_language(mygit_gpui::i18n::Language::English, cx)
                        })),
                )
                .child(mygit_gpui::i18n::text("保存后重启生效")),
        )
        .child(
            div()
                .flex()
                .gap_2()
                .items_center()
                .child(div().child(mygit_gpui::localized_format!(
                    "字体：{} · {}",
                    "Font: {} · {}",
                    this.state.font_family,
                    this.state.font_size
                )))
                .child(
                    button("font-family", mygit_gpui::i18n::text("切换字体"), true)
                        .on_click(cx.listener(|this, _, _, cx| this.cycle_font(cx))),
                )
                .child(
                    button("history-narrower", mygit_gpui::i18n::text("历史 −"), true)
                        .on_click(cx.listener(|this, _, _, cx| this.resize_panel(true, false, cx))),
                )
                .child(
                    button("history-wider", mygit_gpui::i18n::text("历史 +"), true)
                        .on_click(cx.listener(|this, _, _, cx| this.resize_panel(true, true, cx))),
                )
                .child(
                    button("files-narrower", mygit_gpui::i18n::text("文件 −"), true).on_click(
                        cx.listener(|this, _, _, cx| this.resize_panel(false, false, cx)),
                    ),
                )
                .child(
                    button("files-wider", mygit_gpui::i18n::text("文件 +"), true)
                        .on_click(cx.listener(|this, _, _, cx| this.resize_panel(false, true, cx))),
                ),
        )
        .child(
            button(
                "ai-config-toggle",
                mygit_gpui::i18n::text("AI API 配置"),
                true,
            )
            .on_click(cx.listener(|this, _, _, cx| this.toggle_ai_settings(cx))),
        )
        .child(
            div()
                .flex()
                .gap_2()
                .items_center()
                .child(mygit_gpui::i18n::text("代码配色"))
                .children(
                    mygit_gpui::syntax::PALETTES
                        .iter()
                        .enumerate()
                        .map(|(index, name)| {
                            button(
                                [
                                    "palette-friendly",
                                    "palette-ocean",
                                    "palette-eighties",
                                    "palette-solarized",
                                ][index],
                                name,
                                true,
                            )
                            .when(this.settings.code_theme == *name, |s| {
                                s.border_1().border_color(rgb(0x2196f3))
                            })
                            .on_click(cx.listener(
                                move |this, _, _, cx| this.select_code_palette(index, cx),
                            ))
                        }),
                ),
        )
        .when(this.font_inputs.len() == 2, |s| {
            s.child(
                div()
                    .flex()
                    .gap_2()
                    .items_center()
                    .child(mygit_gpui::i18n::text("字体名称"))
                    .child(div().w(px(240.)).child(this.font_inputs[0].clone()))
                    .child(mygit_gpui::i18n::text("字号"))
                    .child(div().w(px(90.)).child(this.font_inputs[1].clone()))
                    .child(
                        button("apply-font", mygit_gpui::i18n::text("应用字体"), true)
                            .on_click(cx.listener(|this, _, _, cx| this.apply_font_settings(cx))),
                    ),
            )
        })
        .child(
            div()
                .flex()
                .gap_2()
                .flex_wrap()
                .child(
                    button(
                        "clear-recent",
                        mygit_gpui::i18n::text("清空最近仓库"),
                        !this.settings.recent.is_empty(),
                    )
                    .on_click(cx.listener(|this, _, _, cx| this.clear_recent_repositories(cx))),
                )
                .child(
                    button(
                        "toggle-files-panel",
                        if this.settings.files_visible {
                            mygit_gpui::i18n::text("隐藏文件栏")
                        } else {
                            mygit_gpui::i18n::text("显示文件栏")
                        },
                        true,
                    )
                    .on_click(cx.listener(|this, _, window, cx| {
                        this.toggle_files_panel(cx);
                        window.focus(&this.focus);
                    })),
                )
                .child(
                    button(
                        "settings-toggle-git",
                        if this.settings.git_panel_visible {
                            mygit_gpui::i18n::text("隐藏 Git 面板")
                        } else {
                            mygit_gpui::i18n::text("显示 Git 面板")
                        },
                        true,
                    )
                    .on_click(cx.listener(|this, _, window, cx| this.toggle_git_panel(window, cx))),
                ),
        )
        .when(this.ai.config_shown, |s| s.child(ai_settings(this, cx)))
        .when_some(this.settings.warning.clone(), |s, warning| {
            s.child(div().text_color(rgb(0x946200)).child(warning))
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
                        .hover(|s| s.bg(rgb(0xf4f4f4)))
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
                .bg(rgb(0xf5f5f5))
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

fn ai_settings(this: &MyGit, cx: &mut Context<MyGit>) -> impl IntoElement {
    let mut pane = div()
        .flex()
        .flex_col()
        .gap_1()
        .child(mygit_gpui::i18n::text(
            "AI API 配置 · 基础 URL 自动追加 /chat/completions",
        ));
    for (i, label) in [
        "API URL",
        mygit_gpui::i18n::text("API 密钥"),
        mygit_gpui::i18n::text("模型名称"),
        mygit_gpui::i18n::text("提示词"),
    ]
    .iter()
    .enumerate()
    {
        if let Some(input) = this.ai.config_inputs.get(i) {
            pane = pane.child(
                div().flex().gap_2().items_center().child(*label).child(
                    div()
                        .flex_1()
                        .flex()
                        .flex_col()
                        .h(px(if i == 3 { 85. } else { 32. }))
                        .child(input.clone()),
                ),
            );
        }
    }
    pane.child(div().text_xs().child(mygit_gpui::i18n::text("密钥保存在兼容 JSON 中；Unix 文件权限 0600。MYGIT_AI_API_SECRET 可覆盖密钥且无需写入配置。")))
        .child(button("ai-config-save", mygit_gpui::i18n::text("保存 AI 配置"), this.ai.config_inputs.len() == 4).on_click(cx.listener(|this, _, _, cx| this.save_ai_settings(cx))))
        .when(!this.ai.config_message.is_empty(), |s| s.child(div().text_color(rgb(0x946200)).child(this.ai.config_message.clone())))
}

pub fn popover(content: AnyElement) -> impl IntoElement {
    div()
        .absolute()
        .top(px(55.))
        .right(px(12.))
        .w(px(650.))
        .max_h(px(600.))
        .occlude()
        .bg(rgb(0xf5f5f5))
        .border_1()
        .border_color(rgb(0xbcbcbc))
        .shadow_md()
        .child(content)
}
