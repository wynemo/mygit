use crate::{
    app::MyGit,
    views::{button, icons},
};
use gpui::{prelude::*, *};
use mygit_gpui::model::BrowseMode;

fn table_cell(text: impl Into<SharedString>, width: f32) -> Div {
    div()
        .w(px(width))
        .flex_shrink_0()
        .px_1()
        .overflow_hidden()
        .text_ellipsis()
        .child(text.into())
}

pub fn history(this: &MyGit, cx: &mut Context<MyGit>) -> impl IntoElement {
    let count = this.history_commits().len();
    div()
        .key_context("HistoryList")
        .track_focus(&this.history_focus)
        .w(px(this.visible_history_width))
        .flex_shrink_0()
        .flex()
        .flex_col()
        .min_h_0()
        .p(px(10.))
        .child(
            div()
                .h(px(34.))
                .flex_shrink_0()
                .flex()
                .items_center()
                .gap_3()
                .children(
                    [
                        (
                            "fetch-remote",
                            "Fetch",
                            mygit_gpui::operations::RemoteOperation::Fetch,
                        ),
                        (
                            "pull-remote",
                            "Pull",
                            mygit_gpui::operations::RemoteOperation::Pull,
                        ),
                        (
                            "push-remote",
                            "Push",
                            mygit_gpui::operations::RemoteOperation::Push,
                        ),
                    ]
                    .into_iter()
                    .map(|(id, label, operation)| {
                        button(id, label, !this.write_busy && this.state.repo.is_some()).on_click(
                            cx.listener(move |this, _, _, cx| this.remote_operation(operation, cx)),
                        )
                    }),
                ),
        )
        .child(history_tabs(this, cx))
        .when_some(this.active_history_tab, |s, index| {
            let tab = &this.path_history_tabs[index];
            let root = this
                .state
                .repo
                .as_ref()
                .map(|repo| repo.root.join(&tab.path).display().to_string())
                .unwrap_or_else(|| tab.path.clone());
            s.child(
                div()
                    .flex_shrink_0()
                    .py_1()
                    .text_ellipsis()
                    .overflow_hidden()
                    .child(mygit_gpui::localized_format!(
                        "{}：{}",
                        "{}: {}",
                        if tab.directory {
                            mygit_gpui::i18n::text("目录历史")
                        } else {
                            mygit_gpui::i18n::text("文件历史")
                        },
                        root
                    )),
            )
            .when(this.history_loading, |s| {
                s.child(
                    div()
                        .flex_shrink_0()
                        .child(mygit_gpui::i18n::text("正在加载历史…")),
                )
            })
            .when_some(this.history_search_error.clone(), |s, error| {
                s.child(div().flex_shrink_0().text_color(rgb(0xa52a2a)).child(error))
            })
            .when(
                !this.history_loading
                    && !this.history_failed
                    && this.history_query.is_some()
                    && count == 0,
                |s| {
                    s.child(
                        div()
                            .flex_shrink_0()
                            .child(mygit_gpui::i18n::text("暂无文件历史")),
                    )
                },
            )
        })
        .when(this.active_history_tab.is_none(), |s| {
            s.child(
                div()
                    .h(px(48.))
                    .flex_shrink_0()
                    .flex()
                    .items_center()
                    .gap_2()
                    .px_1()
                    .child(
                        div()
                            .flex_1()
                            .max_w(px(124.))
                            .min_w_0()
                            .h(px(24.))
                            .when_some(this.history_inputs.first().cloned(), |s, editor| {
                                s.child(editor)
                            }),
                    )
                    .children(["Branch", "User", "Date"].into_iter().enumerate().map(
                        |(i, label)| {
                            div()
                                .id(("history-filter", i))
                                .flex_shrink_0()
                                .cursor_pointer()
                                .child(format!("{label} ⌄"))
                                .on_click(
                                    cx.listener(|this, _, _, cx| this.toggle_history_search(cx)),
                                )
                        },
                    )),
            )
        })
        .child(
            div()
                .id("history-table-scroll")
                .flex()
                .flex_col()
                .flex_1()
                .min_h_0()
                .overflow_x_scroll()
                // Do not translate an exhausted vertical wheel into horizontal scrolling.
                .map(|mut s| {
                    s.style().restrict_scroll_to_axis = Some(true);
                    s
                })
                .child(
                    div()
                        .w(px(if this.active_history_tab.is_some() {
                            550.
                        } else {
                            720.
                        }))
                        .min_w_full()
                        .flex()
                        .flex_col()
                        .flex_1()
                        .min_h_0()
                        .border_1()
                        .border_color(rgb(0xbcbcbc))
                        .bg(rgb(0xffffff))
                        .child(
                            div()
                                .h(px(20.))
                                .flex_shrink_0()
                                .flex()
                                .bg(rgb(0xececec))
                                .border_b_1()
                                .border_color(rgb(0xc8c8c8))
                                .children(
                                    [
                                        ("DAG", 120.),
                                        (
                                            mygit_gpui::i18n::text("提交信息"),
                                            if this.active_history_tab.is_some() {
                                                300.
                                            } else {
                                                200.
                                            },
                                        ),
                                        ("Branches", 150.),
                                        (mygit_gpui::i18n::text("作者"), 100.),
                                        (mygit_gpui::i18n::text("日期"), 150.),
                                    ]
                                    .into_iter()
                                    .filter(|(label, _)| {
                                        this.active_history_tab.is_none()
                                            || (*label != "DAG" && *label != "Branches")
                                    })
                                    .map(|(label, width)| {
                                        table_cell(label, width)
                                            .border_r_1()
                                            .border_color(rgb(0xc8c8c8))
                                    }),
                                ),
                        )
                        .child(
                            uniform_list(
                                "history",
                                count,
                                cx.processor(|this, range: std::ops::Range<usize>, _, cx| {
                                    if !this.history_failed
                                        && this.history_more()
                                        && range.end >= this.history_commits().len()
                                    {
                                        let entity = cx.entity().downgrade();
                                        cx.defer(move |cx| {
                                            let _ = entity
                                                .update(cx, |this, cx| this.load_more_history(cx));
                                        });
                                    }
                                    range
                                        .map(|i| {
                                            let c = &this.history_commits()[i];
                                            let references = this
                                                .state
                                                .repo
                                                .as_ref()
                                                .and_then(|r| r.references.get(&c.sha))
                                                .cloned()
                                                .unwrap_or_default();
                                            let selected = this.history_cursor == Some(i);
                                            div()
                                                .id(i)
                                                .w_full()
                                                .h(px(18.))
                                                .flex()
                                                .items_center()
                                                .overflow_hidden()
                                                .cursor_pointer()
                                                .bg(rgb(if selected { 0xdceafa } else { 0xffffff }))
                                                .hover(|s| s.bg(rgb(0xedf4fb)))
                                                .tooltip({
                                                    let subject = c.subject.clone();
                                                    move |_, cx| {
                                                        cx.new(|_| {
                                                            crate::views::hints::Hint(
                                                                subject.clone().into(),
                                                            )
                                                        })
                                                        .into()
                                                    }
                                                })
                                                .when(this.active_history_tab.is_none(), |s| {
                                                    s.child(
                                                        div()
                                                            .w(px(120.))
                                                            .h_full()
                                                            .flex_shrink_0()
                                                            .when_some(
                                                                this.history_graph.get(i).cloned(),
                                                                |s, row| {
                                                                    s.child(
                                                                        crate::views::graph::row(
                                                                            row,
                                                                        ),
                                                                    )
                                                                },
                                                            ),
                                                    )
                                                })
                                                .child(table_cell(
                                                    c.subject.clone(),
                                                    if this.active_history_tab.is_some() {
                                                        300.
                                                    } else {
                                                        200.
                                                    },
                                                ))
                                                .when(this.active_history_tab.is_none(), |s| {
                                                    s.child(table_cell(references, 150.))
                                                })
                                                .child(table_cell(c.author.clone(), 100.))
                                                .child(table_cell(
                                                    c.date
                                                        .replace('T', " ")
                                                        .chars()
                                                        .take(19)
                                                        .collect::<String>(),
                                                    150.,
                                                ))
                                                .on_mouse_down(
                                                    MouseButton::Right,
                                                    cx.listener(move |this, _, window, cx| {
                                                        if let Some(commit) =
                                                            this.history_commits().get(i)
                                                        {
                                                            this.show_commit_branches(
                                                                commit.sha.clone(),
                                                                cx,
                                                            );
                                                            window.focus(&this.branch_focus);
                                                        }
                                                        cx.stop_propagation();
                                                    }),
                                                )
                                                .on_click(cx.listener(
                                                    move |this, _, window, cx| {
                                                        this.choose_history(i, window, cx)
                                                    },
                                                ))
                                        })
                                        .collect::<Vec<_>>()
                                }),
                            )
                            .w_full()
                            .with_decoration(crate::views::scrollbar::ListScrollbar(
                                this.history_scroll.clone(),
                                Some(this.visible_history_width - 20.),
                            ))
                            .track_scroll(this.history_scroll.clone())
                            .min_h_0()
                            .flex_1(),
                        ),
                ),
        )
}

#[derive(Clone)]
struct ChangeRow {
    label: String,
    path: String,
    depth: usize,
    index: Option<usize>,
}
fn change_rows(this: &MyGit) -> Vec<ChangeRow> {
    let mut rows = Vec::new();
    let mut seen = std::collections::BTreeSet::new();
    for (index, file) in this.state.files.iter().enumerate() {
        let parts: Vec<_> = file.path.split('/').collect();
        let mut prefix = String::new();
        let mut hidden = false;
        for (depth, part) in parts.iter().enumerate() {
            if !prefix.is_empty() {
                prefix.push('/');
            }
            prefix.push_str(part);
            if depth == parts.len() - 1 {
                rows.push(ChangeRow {
                    label: (*part).into(),
                    path: file.path.clone(),
                    depth,
                    index: Some(index),
                });
            } else {
                if seen.insert(prefix.clone()) {
                    rows.push(ChangeRow {
                        label: (*part).into(),
                        path: prefix.clone(),
                        depth,
                        index: None,
                    });
                }
                if this.change_folders_collapsed.contains(&prefix) {
                    hidden = true;
                    break;
                }
            }
        }
        if hidden {
            continue;
        }
    }
    rows
}

pub fn files(this: &MyGit, workspace: bool, cx: &mut Context<MyGit>) -> impl IntoElement {
    let worktree = matches!(
        this.state.mode,
        BrowseMode::Workspace | BrowseMode::Staged | BrowseMode::Unstaged
    );
    let rows = if workspace || !worktree {
        change_rows(this)
    } else {
        Vec::new()
    };
    let count = rows.len();
    div()
        .key_context("FilesList")
        .track_focus(&this.files_focus)
        .flex()
        .flex_col()
        .flex_1()
        .min_w_0()
        .min_h_0()
        .p(px(5.))
        .child(
            div()
                .h(px(25.))
                .flex_shrink_0()
                .child(mygit_gpui::localized_format!(
                    "文件变化：",
                    "Changed files:"
                )),
        )
        .when(workspace, |s| {
            s.child(
                div().flex().flex_wrap().gap_1().pb_1().children(
                    [
                        (
                            "workspace",
                            mygit_gpui::i18n::text("全部变更"),
                            BrowseMode::Workspace,
                        ),
                        (
                            "staged",
                            mygit_gpui::i18n::text("已暂存"),
                            BrowseMode::Staged,
                        ),
                        (
                            "unstaged",
                            mygit_gpui::i18n::text("未暂存"),
                            BrowseMode::Unstaged,
                        ),
                    ]
                    .into_iter()
                    .map(|(id, label, mode)| {
                        button(id, label, true).on_click(
                            cx.listener(move |this, _, _, cx| this.select_mode(mode.clone(), cx)),
                        )
                    }),
                ),
            )
            .child(
                div().flex().flex_wrap().gap_1().pb_1().children(
                    [
                        (
                            "stage-selected",
                            mygit_gpui::i18n::text("暂存选中"),
                            true,
                            false,
                        ),
                        (
                            "unstage-selected",
                            mygit_gpui::i18n::text("取消暂存"),
                            false,
                            false,
                        ),
                        ("stage-all", mygit_gpui::i18n::text("暂存全部"), true, true),
                        (
                            "unstage-all",
                            mygit_gpui::i18n::text("取消全部"),
                            false,
                            true,
                        ),
                    ]
                    .into_iter()
                    .map(|(id, label, stage, all)| {
                        button(id, label, !this.write_busy).on_click(
                            cx.listener(move |this, _, _, cx| this.change_index(stage, all, cx)),
                        )
                    }),
                ),
            )
        })
        .child(
            div()
                .flex()
                .flex_col()
                .flex_1()
                .min_h_0()
                .border_1()
                .border_color(rgb(0xbcbcbc))
                .bg(rgb(0xffffff))
                .child(
                    div()
                        .h(px(20.))
                        .flex_shrink_0()
                        .flex()
                        .bg(rgb(0xececec))
                        .border_b_1()
                        .border_color(rgb(0xc8c8c8))
                        .child(
                            div()
                                .w(px(100.))
                                .px_1()
                                .border_r_1()
                                .border_color(rgb(0xc8c8c8))
                                .child(mygit_gpui::i18n::text("文件")),
                        )
                        .child(div().px_1().child(mygit_gpui::i18n::text("状态"))),
                )
                .child(
                    uniform_list(
                        if workspace {
                            "workspace-changes"
                        } else {
                            "commit-changes"
                        },
                        count,
                        cx.processor(move |this, range: std::ops::Range<usize>, _, cx| {
                            let rows = change_rows(this);
                            range
                                .filter_map(|i| {
                                    rows.get(i).cloned().map(|row| {
                                        let folder = row.index.is_none();
                                        let expanded =
                                            !this.change_folders_collapsed.contains(&row.path);
                                        let path = row.path.clone();
                                        let status = row
                                            .index
                                            .map(|i| this.state.files[i].status.clone())
                                            .unwrap_or_default();
                                        div()
                                            .id(i)
                                            .w_full()
                                            .h(px(20.))
                                            .flex()
                                            .items_center()
                                            .gap_1()
                                            .pl(px(6. + row.depth as f32 * 14.))
                                            .overflow_hidden()
                                            .whitespace_nowrap()
                                            .cursor_pointer()
                                            .bg(rgb(
                                                if row.index.is_some()
                                                    && row.index == this.state.selected
                                                {
                                                    0xdceafa
                                                } else {
                                                    0xffffff
                                                },
                                            ))
                                            .hover(|s| s.bg(rgb(0xedf4fb)))
                                            .child(if folder {
                                                if expanded { "▾" } else { "▸" }
                                            } else {
                                                " "
                                            })
                                            .when(workspace && !folder, |s| {
                                                s.child(
                                                    div()
                                                        .id(("file-checkbox", i))
                                                        .cursor_pointer()
                                                        .child(
                                                            if this.file_selection.contains(&path) {
                                                                "☑"
                                                            } else {
                                                                "☐"
                                                            },
                                                        )
                                                        .on_click(cx.listener(
                                                            move |this, _, _, cx| {
                                                                cx.stop_propagation();
                                                                if let Some(index) = row.index {
                                                                    this.toggle_file_selection(
                                                                        index, cx,
                                                                    );
                                                                }
                                                            },
                                                        )),
                                                )
                                            })
                                            .child(if folder {
                                                icons::icon("icons/folder.svg").into_any_element()
                                            } else {
                                                icons::file(&path).into_any_element()
                                            })
                                            .child(div().min_w(px(80.)).child(row.label))
                                            .child(div().text_color(rgb(0x666666)).child(status))
                                            .on_click(cx.listener(move |this, _, window, cx| {
                                                window.focus(&this.files_focus);
                                                if let Some(index) = row.index {
                                                    this.select_file(index, cx);
                                                } else {
                                                    if !this.change_folders_collapsed.remove(&path)
                                                    {
                                                        this.change_folders_collapsed
                                                            .insert(path.clone());
                                                    }
                                                    cx.notify();
                                                }
                                            }))
                                    })
                                })
                                .collect::<Vec<_>>()
                        }),
                    )
                    .w_full()
                    .with_decoration(crate::views::scrollbar::ListScrollbar(
                        this.files_scroll.clone(),
                        None,
                    ))
                    .track_scroll(this.files_scroll.clone())
                    .min_h_0()
                    .flex_1(),
                ),
        )
}

pub fn detail(this: &MyGit, cx: &mut Context<MyGit>) -> impl IntoElement {
    div()
        .id("commit-detail")
        .flex()
        .flex_col()
        .flex_1()
        .min_h_0()
        .min_w_0()
        .overflow_y_scroll()
        .bg(rgb(0xffffff))
        .p(px(8.))
        .when_some(this.state.listed_detail.clone(), |s, detail| {
            let sha = detail.sha.clone();
            let message = detail.message.clone();
            s.child(
                div()
                    .flex()
                    .gap_2()
                    .child(
                        button("copy-sha", mygit_gpui::i18n::text("复制 SHA"), true).on_click(
                            cx.listener(move |_, _, _, cx| {
                                cx.write_to_clipboard(ClipboardItem::new_string(sha.clone()))
                            }),
                        ),
                    )
                    .child(
                        button("copy-message", mygit_gpui::i18n::text("复制信息"), true).on_click(
                            cx.listener(move |_, _, _, cx| {
                                cx.write_to_clipboard(ClipboardItem::new_string(message.clone()))
                            }),
                        ),
                    ),
            )
            .child(
                div().font_weight(FontWeight::BOLD).child(
                    detail
                        .message
                        .lines()
                        .next()
                        .unwrap_or_default()
                        .to_string(),
                ),
            )
            .child(div().text_color(rgb(0x666666)).child(format!(
                "{} <{}>  {}",
                detail.author, detail.author_email, detail.author_date
            )))
            .child(div().child(detail.references))
            .children(
                detail
                    .message
                    .lines()
                    .skip(1)
                    .map(|line| div().min_h(px(17.)).child(line.to_string())),
            )
        })
}

fn history_tabs(this: &MyGit, cx: &mut Context<MyGit>) -> impl IntoElement {
    div()
        .id("history-tabs")
        .h(px(29.))
        .flex_shrink_0()
        .overflow_x_scroll()
        .flex()
        .items_end()
        .border_b_1()
        .border_color(rgb(0xc8c8c8))
        .child(
            div()
                .id("ordinary-history-tab")
                .px_2()
                .h(px(23.))
                .flex_shrink_0()
                .cursor_pointer()
                .rounded_t(px(4.))
                .bg(rgb(if this.active_history_tab.is_none() {
                    0x2196f3
                } else {
                    0xe5e5e5
                }))
                .text_color(rgb(if this.active_history_tab.is_none() {
                    0xffffff
                } else {
                    0x202020
                }))
                .child(mygit_gpui::i18n::text("提交历史"))
                .on_click(cx.listener(|this, _, _, cx| this.select_history_tab(None, cx))),
        )
        .children(
            this.path_history_tabs
                .iter()
                .enumerate()
                .map(|(index, tab)| {
                    let name = std::path::Path::new(&tab.path)
                        .file_name()
                        .map(|name| name.to_string_lossy().into_owned())
                        .unwrap_or_else(|| tab.path.clone());
                    let title = mygit_gpui::localized_format!("{} 历史", "{} history", name);
                    let path = tab.path.clone();
                    div()
                        .id(("path-history-tab", index))
                        .px_2()
                        .h(px(23.))
                        .flex_shrink_0()
                        .flex()
                        .items_center()
                        .gap_2()
                        .cursor_pointer()
                        .rounded_t(px(4.))
                        .bg(rgb(if this.active_history_tab == Some(index) {
                            0x2196f3
                        } else {
                            0xe5e5e5
                        }))
                        .text_color(rgb(if this.active_history_tab == Some(index) {
                            0xffffff
                        } else {
                            0x202020
                        }))
                        .child(title)
                        .tooltip(move |_, cx| {
                            cx.new(|_| crate::views::hints::Hint(path.clone().into()))
                                .into()
                        })
                        .child(div().id(("close-history-tab", index)).child("×").on_click(
                            cx.listener(move |this, _, _, cx| {
                                cx.stop_propagation();
                                this.close_history_tab(index, cx);
                            }),
                        ))
                        .on_click(cx.listener(move |this, _, _, cx| {
                            this.select_history_tab(Some(index), cx)
                        }))
                }),
        )
}
