use crate::app::MyGit;
use gpui::{prelude::*, *};

fn row(id: usize, label: String) -> Stateful<Div> {
    let star = label.starts_with('★');
    let submenu = label.ends_with('›');
    let text = label
        .trim()
        .trim_start_matches('★')
        .trim_end_matches('›')
        .trim()
        .to_string();
    div()
        .id(("branch-menu-row", id))
        .h(px(28.))
        .px_2()
        .flex()
        .items_center()
        .rounded(px(4.))
        .cursor_pointer()
        .hover(|s| s.bg(rgb(super::theme::SELECTED)))
        .child(
            div()
                .w(px(22.))
                .flex_shrink_0()
                .text_color(rgb(0xffa500))
                .child(if star { "★" } else { "" }),
        )
        .child(div().flex_1().min_w_0().truncate().child(text))
        .when(submenu, |s| {
            s.child(div().text_color(rgb(super::theme::MUTED)).child("›"))
        })
}

pub fn menu(this: &MyGit, window: &Window, cx: &mut Context<MyGit>) -> impl IntoElement {
    let position = this.history_branch_menu.unwrap();
    let branches = this
        .state
        .repo
        .as_ref()
        .map(|r| r.branches.as_slice())
        .unwrap_or(&[]);
    let mut favorites = vec![("HEAD".to_string(), "HEAD".to_string())];
    if let Some(repo) = &this.state.repo {
        if let Some(branch) = branches.iter().find(|b| b.current) {
            favorites.push((branch.name.clone(), branch.reference.clone()));
            if let Some(upstream) = branches.iter().find(|b| b.reference == branch.upstream) {
                favorites.push((upstream.name.clone(), upstream.reference.clone()));
            }
        } else if let Some(branch) = branches.iter().find(|b| b.name == repo.branch) {
            favorites.push((branch.name.clone(), branch.reference.clone()));
        }
    }
    let mut groups = vec!["Recent".to_string(), "Local".to_string()];
    for branch in branches.iter().filter(|b| b.remote) {
        if let Some((remote, _)) = branch.name.split_once('/') {
            if !groups.iter().any(|g| g == remote) {
                groups.push(remote.to_string());
            }
        }
    }
    let group = this.history_branch_group.as_deref();
    let items: Vec<(String, String)> = match group {
        Some("Recent") => this
            .history_branch_recent
            .iter()
            .map(|s| {
                (
                    s.strip_prefix("refs/heads/")
                        .or_else(|| s.strip_prefix("refs/remotes/"))
                        .unwrap_or(s)
                        .to_string(),
                    s.clone(),
                )
            })
            .collect(),
        Some(name) => branches
            .iter()
            .filter(|b| {
                if name == "Local" {
                    !b.remote
                } else {
                    b.remote && b.name.starts_with(&format!("{name}/"))
                }
            })
            .map(|b| (b.name.clone(), b.reference.clone()))
            .collect(),
        None => vec![],
    };
    let panel = |id| {
        div()
            .id(id)
            .w(px(250.))
            .p_2()
            .flex()
            .flex_col()
            .rounded(px(8.))
            .shadow_md()
            .bg(rgb(super::theme::SURFACE))
            .border_1()
            .border_color(rgb(super::theme::BORDER))
    };
    div()
        .id("history-branch-popup")
        .absolute()
        .occlude()
        .left(
            position
                .x
                .min((window.viewport_size().width - px(508.)).max(px(0.)))
                .max(px(0.)),
        )
        .top((position.y + px(12.)).min((window.viewport_size().height - px(330.)).max(px(0.))))
        .flex()
        .items_start()
        .gap_1()
        .on_mouse_down_out(cx.listener(|this, _, _, cx| {
            this.history_branch_menu = None;
            this.history_branch_group = None;
            cx.notify();
        }))
        .on_key_down(cx.listener(|this, event: &KeyDownEvent, _, cx| {
            if event.keystroke.key == "escape" {
                this.history_branch_menu = None;
                this.history_branch_group = None;
                cx.notify();
            }
        }))
        .child(
            panel("branch-main-menu")
                .child(
                    row(0, "     Select…".into()).on_click(cx.listener(|this, _, _, cx| {
                        this.history_branch_menu = None;
                        this.toggle_history_search(cx);
                    })),
                )
                .child(
                    row(1, "     Recent                         ›".into())
                        .on_mouse_move(cx.listener(|this, _, _, cx| {
                            if this.history_branch_group.as_deref() != Some("Recent") {
                                this.history_branch_group = Some("Recent".into());
                                cx.notify();
                            }
                        }))
                        .on_click(cx.listener(|this, _, _, cx| {
                            this.history_branch_group = Some("Recent".into());
                            cx.notify();
                        })),
                )
                .child(
                    div()
                        .h(px(28.))
                        .px_2()
                        .flex()
                        .items_center()
                        .child("     Favorites"),
                )
                .children(
                    favorites
                        .into_iter()
                        .enumerate()
                        .map(|(i, (label, scope))| {
                            row(10 + i, format!("★   {label}"))
                                .on_mouse_move(cx.listener(|this, _, _, cx| {
                                    if this.history_branch_group.take().is_some() {
                                        cx.notify();
                                    }
                                }))
                                .on_click(cx.listener(move |this, _, _, cx| {
                                    this.select_history_branch(scope.clone(), cx)
                                }))
                        }),
                )
                .child(
                    div()
                        .my_1()
                        .border_t_1()
                        .border_color(rgb(super::theme::BORDER)),
                )
                .children(
                    groups
                        .into_iter()
                        .filter(|g| g != "Recent")
                        .enumerate()
                        .map(|(i, name)| {
                            let hover = name.clone();
                            row(
                                30 + i,
                                format!(
                                    "     {name}{}                         ›",
                                    if name == "Local" { "" } else { "/…" }
                                ),
                            )
                            .when(group == Some(name.as_str()), |s| {
                                s.bg(rgb(super::theme::SELECTED))
                            })
                            .on_mouse_move(cx.listener(move |this, _, _, cx| {
                                if this.history_branch_group.as_ref() != Some(&hover) {
                                    this.history_branch_group = Some(hover.clone());
                                    cx.notify();
                                }
                            }))
                            .on_click(cx.listener(
                                move |this, _, _, cx| {
                                    this.history_branch_group = Some(name.clone());
                                    cx.notify();
                                },
                            ))
                        }),
                ),
        )
        .when(group.is_some(), |s| {
            s.child(
                panel("branch-submenu")
                    .max_h(px(320.))
                    .overflow_y_scroll()
                    .when(items.is_empty(), |s| {
                        s.child(
                            div()
                                .px_2()
                                .py_1()
                                .text_color(rgb(super::theme::MUTED))
                                .child("—"),
                        )
                    })
                    .children(items.into_iter().enumerate().map(|(i, (label, scope))| {
                        row(100 + i, label).on_click(cx.listener(move |this, _, _, cx| {
                            this.select_history_branch(scope.clone(), cx)
                        }))
                    })),
            )
        })
}
