use gpui::{prelude::*, *};
use mygit_gpui::git;
use std::path::PathBuf;

struct MyGit {
    repo: Option<git::Snapshot>,
    files: Vec<git::FileChange>,
    commit: Option<String>,
    selected: Option<usize>,
    diff: git::Diff,
    message: String,
    loading: bool,
    generation: u64,
    panel_width: f32,
    horizontal_offset: f32,
}
impl MyGit {
    fn new() -> Self {
        Self {
            repo: None,
            files: vec![],
            commit: None,
            selected: None,
            diff: git::Diff::default(),
            message: "打开一个 Git 仓库".into(),
            loading: false,
            generation: 0,
            panel_width: 420.,
            horizontal_offset: 0.,
        }
    }
    fn open(&mut self, cx: &mut Context<Self>) {
        let picker = cx.prompt_for_paths(PathPromptOptions {
            files: false,
            directories: true,
            multiple: false,
            prompt: Some("选择 Git 仓库".into()),
        });
        cx.spawn(async move |this, cx| match picker.await {
            Ok(Ok(Some(paths))) => {
                if let Some(path) = paths.into_iter().next() {
                    let _ = this.update(cx, |this, cx| this.load(path, cx));
                }
            }
            Ok(Ok(None)) => {}
            other => {
                let _ = this.update(cx, |this, cx| {
                    this.message = format!("无法打开目录选择器：{other:?}");
                    cx.notify();
                });
            }
        })
        .detach();
    }
    fn load(&mut self, path: PathBuf, cx: &mut Context<Self>) {
        self.generation += 1;
        let generation = self.generation;
        self.loading = true;
        self.repo = None;
        self.files.clear();
        self.commit = None;
        self.selected = None;
        self.diff = git::Diff::default();
        self.message = "正在读取仓库…".into();
        cx.notify();
        let task = cx
            .background_executor()
            .spawn(async move { git::snapshot(&path) });
        cx.spawn(async move |this, cx| {
            let result = task.await;
            let _ = this.update(cx, |this, cx| {
                if this.generation != generation {
                    return;
                }
                this.loading = false;
                match result {
                    Ok(repo) => {
                        this.files = repo.files.clone();
                        this.message = format!(
                            "{} 个工作区变更 · 最近 {} 条提交",
                            this.files.len(),
                            repo.commits.len()
                        );
                        this.repo = Some(repo);
                        if !this.files.is_empty() {
                            this.select_file(0, cx);
                        }
                    }
                    Err(error) => this.message = format!("{error:#}"),
                }
                cx.notify();
            });
        })
        .detach();
    }
    fn select_commit(&mut self, sha: Option<String>, cx: &mut Context<Self>) {
        let Some(repo) = &self.repo else {
            return;
        };
        let root = repo.root.clone();
        let workspace = repo.files.clone();
        self.generation += 1;
        let generation = self.generation;
        self.commit = sha.clone();
        self.selected = None;
        self.files.clear();
        self.diff = git::Diff::default();
        self.loading = true;
        self.message = "正在读取变更…".into();
        cx.notify();
        let task = cx.background_executor().spawn(async move {
            match sha {
                Some(sha) => git::commit_files(&root, &sha),
                None => Ok(workspace),
            }
        });
        cx.spawn(async move |this, cx| {
            let result = task.await;
            let _ = this.update(cx, |this, cx| {
                if this.generation != generation {
                    return;
                }
                this.loading = false;
                match result {
                    Ok(files) => {
                        this.files = files;
                        this.message = format!("{} 个文件", this.files.len());
                        if !this.files.is_empty() {
                            this.select_file(0, cx);
                        }
                    }
                    Err(e) => this.message = format!("{e:#}"),
                }
                cx.notify();
            });
        })
        .detach();
    }
    fn select_file(&mut self, index: usize, cx: &mut Context<Self>) {
        let (Some(repo), Some(file)) = (&self.repo, self.files.get(index)) else {
            return;
        };
        let root = repo.root.clone();
        let file = file.clone();
        let commit = self.commit.clone();
        self.generation += 1;
        let generation = self.generation;
        self.selected = Some(index);
        self.horizontal_offset = 0.;
        self.diff = git::Diff::default();
        self.loading = true;
        self.message = format!("正在比较 {}…", file.path);
        cx.notify();
        let task = cx
            .background_executor()
            .spawn(async move { git::diff(&root, commit.as_deref(), &file) });
        cx.spawn(async move |this, cx| {
            let result = task.await;
            let _ = this.update(cx, |this, cx| {
                if this.generation != generation {
                    return;
                }
                this.loading = false;
                match result {
                    Ok(diff) => {
                        this.message = diff.message.clone().unwrap_or_else(|| {
                            format!(
                                "{} 行 · {} 行差异",
                                diff.rows.len(),
                                diff.rows.iter().filter(|r| r.changed).count()
                            )
                        });
                        this.panel_width = diff
                            .rows
                            .iter()
                            .map(|row| {
                                row.left
                                    .chars()
                                    .map(|c| {
                                        if c == '\t' {
                                            4
                                        } else if c.is_ascii() {
                                            1
                                        } else {
                                            2
                                        }
                                    })
                                    .sum::<usize>()
                                    .max(
                                        row.right
                                            .chars()
                                            .map(|c| {
                                                if c == '\t' {
                                                    4
                                                } else if c.is_ascii() {
                                                    1
                                                } else {
                                                    2
                                                }
                                            })
                                            .sum::<usize>(),
                                    )
                            })
                            .max()
                            .unwrap_or(0)
                            .saturating_mul(8)
                            .saturating_add(68)
                            .max(420) as f32;
                        this.diff = diff;
                    }
                    Err(e) => this.message = format!("{e:#}"),
                }
                cx.notify();
            });
        })
        .detach();
    }
}
fn button(id: &'static str, label: &'static str) -> Stateful<Div> {
    div()
        .id(id)
        .px_3()
        .py_1()
        .rounded_md()
        .bg(rgb(0x263449))
        .hover(|s| s.bg(rgb(0x344962)))
        .cursor_pointer()
        .child(label)
}
fn cell(no: Option<usize>, text: &str, color: u32, offset: f32) -> Div {
    div()
        .flex()
        .flex_1()
        .min_w_0()
        .h(px(24.))
        .overflow_hidden()
        .bg(rgb(color))
        .child(
            div()
                .w(px(52.))
                .flex_shrink_0()
                .text_color(rgb(0x7f8b9c))
                .child(no.map(|n| n.to_string()).unwrap_or_default()),
        )
        .child(
            div()
                .flex_1()
                .min_w_0()
                .h_full()
                .relative()
                .overflow_hidden()
                .child(
                    div()
                        .absolute()
                        .left(px(-offset))
                        .whitespace_nowrap()
                        .child(text.replace('\t', "    ")),
                ),
        )
}
impl Render for MyGit {
    fn render(&mut self, _window: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        let title = self
            .repo
            .as_ref()
            .map(|r| format!("{}   /   {}", r.root.display(), r.branch))
            .unwrap_or_else(|| "MyGit · GPUI".into());
        let commits = self
            .repo
            .as_ref()
            .map(|r| r.commits.clone())
            .unwrap_or_default();
        let file_title = self
            .selected
            .and_then(|i| self.files.get(i))
            .map(|f| f.path.clone())
            .unwrap_or_else(|| "选择文件查看差异".into());
        div()
            .size_full()
            .flex()
            .flex_col()
            .bg(rgb(0x111722))
            .text_color(rgb(0xdce5f3))
            .text_size(px(13.))
            .child(
                div()
                    .flex()
                    .items_center()
                    .gap_3()
                    .p_3()
                    .border_b_1()
                    .border_color(rgb(0x2b3545))
                    .child(div().font_weight(FontWeight::BOLD).child("MyGit"))
                    .child(
                        button("open", "打开仓库")
                            .on_click(cx.listener(|this, _, _, cx| this.open(cx))),
                    )
                    .child(
                        button("refresh", "刷新").on_click(cx.listener(|this, _, _, cx| {
                            if let Some(repo) = &this.repo {
                                this.load(repo.root.clone(), cx);
                            }
                        })),
                    )
                    .child(
                        div()
                            .flex_1()
                            .overflow_hidden()
                            .whitespace_nowrap()
                            .text_color(rgb(0x92a2b9))
                            .child(title),
                    ),
            )
            .child(
                div()
                    .flex()
                    .flex_1()
                    .min_h_0()
                    .child(
                        div()
                            .w(px(300.))
                            .flex_shrink_0()
                            .flex()
                            .flex_col()
                            .border_r_1()
                            .border_color(rgb(0x2b3545))
                            .child(button("workspace", "工作区变更 · HEAD ↔ 工作区").on_click(
                                cx.listener(|this, _, _, cx| this.select_commit(None, cx)),
                            ))
                            .child(
                                div()
                                    .p_3()
                                    .text_color(rgb(0x92a2b9))
                                    .child("提交历史 · 最近 100 条"),
                            )
                            .child(
                                uniform_list(
                                    "history",
                                    commits.len(),
                                    cx.processor(
                                        move |this, range: std::ops::Range<usize>, _, cx| {
                                            range
                                                .map(|i| {
                                                    let c = &commits[i];
                                                    let sha = c.sha.clone();
                                                    div()
                                                        .id(i)
                                                        .h(px(64.))
                                                        .p_2()
                                                        .overflow_hidden()
                                                        .cursor_pointer()
                                                        .bg(rgb(
                                                            if this.commit.as_deref()
                                                                == Some(c.sha.as_str())
                                                            {
                                                                0x263b56
                                                            } else {
                                                                0x151d29
                                                            },
                                                        ))
                                                        .hover(|s| s.bg(rgb(0x253248)))
                                                        .child(
                                                            div()
                                                                .whitespace_nowrap()
                                                                .child(c.subject.clone()),
                                                        )
                                                        .child(
                                                            div().text_color(rgb(0x92a2b9)).child(
                                                                format!(
                                                                    "{}  {}  {}",
                                                                    &c.sha[..8],
                                                                    c.author,
                                                                    c.date
                                                                ),
                                                            ),
                                                        )
                                                        .on_click(cx.listener(
                                                            move |this, _, _, cx| {
                                                                this.select_commit(
                                                                    Some(sha.clone()),
                                                                    cx,
                                                                )
                                                            },
                                                        ))
                                                })
                                                .collect::<Vec<_>>()
                                        },
                                    ),
                                )
                                .flex_1(),
                            ),
                    )
                    .child(
                        div()
                            .w(px(220.))
                            .flex_shrink_0()
                            .flex()
                            .flex_col()
                            .border_r_1()
                            .border_color(rgb(0x2b3545))
                            .child(
                                div()
                                    .p_3()
                                    .child(format!("变更文件 ({})", self.files.len())),
                            )
                            .child(
                                uniform_list(
                                    "files",
                                    self.files.len(),
                                    cx.processor(|this, range: std::ops::Range<usize>, _, cx| {
                                        range
                                            .map(|i| {
                                                let file = &this.files[i];
                                                div()
                                                    .id(i)
                                                    .h(px(36.))
                                                    .px_2()
                                                    .py_1()
                                                    .overflow_hidden()
                                                    .whitespace_nowrap()
                                                    .cursor_pointer()
                                                    .bg(rgb(if this.selected == Some(i) {
                                                        0x263b56
                                                    } else {
                                                        0x111722
                                                    }))
                                                    .hover(|s| s.bg(rgb(0x253248)))
                                                    .child(format!(
                                                        "{}  {}",
                                                        file.status, file.path
                                                    ))
                                                    .on_click(cx.listener(move |this, _, _, cx| {
                                                        this.select_file(i, cx)
                                                    }))
                                            })
                                            .collect::<Vec<_>>()
                                    }),
                                )
                                .flex_1(),
                            ),
                    )
                    .child(
                        div()
                            .flex()
                            .flex_col()
                            .flex_1()
                            .min_w_0()
                            .id("diff-pane")
                            .child(
                                div()
                                    .p_3()
                                    .border_b_1()
                                    .border_color(rgb(0x2b3545))
                                    .flex()
                                    .items_center()
                                    .gap_2()
                                    .child(div().flex_1().overflow_hidden().child(file_title))
                                    .child(button("scroll-left", "←").on_click(cx.listener(
                                        |this, _, _, cx| {
                                            this.horizontal_offset =
                                                (this.horizontal_offset - 200.).max(0.);
                                            cx.notify();
                                        },
                                    )))
                                    .child(button("scroll-right", "→").on_click(cx.listener(
                                        |this, _, window, cx| {
                                            let visible =
                                                ((f32::from(window.viewport_size().width) - 520.)
                                                    / 2.
                                                    - 52.)
                                                    .max(50.);
                                            this.horizontal_offset = (this.horizontal_offset
                                                + 200.)
                                                .min((this.panel_width - visible).max(0.));
                                            cx.notify();
                                        },
                                    ))),
                            )
                            .child(
                                div()
                                    .flex()
                                    .p_2()
                                    .text_color(rgb(0x92a2b9))
                                    .child(div().flex_1().child(if self.commit.is_some() {
                                        "父提交（首个父节点）"
                                    } else {
                                        "HEAD"
                                    }))
                                    .child(div().flex_1().child(if self.commit.is_some() {
                                        "选中提交"
                                    } else {
                                        "工作区（包含暂存和未暂存）"
                                    })),
                            )
                            .child(
                                uniform_list(
                                    ("diff", self.generation as usize),
                                    self.diff.rows.len(),
                                    cx.processor(|this, range: std::ops::Range<usize>, _, _| {
                                        range
                                            .map(|i| {
                                                let r = &this.diff.rows[i];
                                                div()
                                                    .id(i)
                                                    .flex()
                                                    .w_full()
                                                    .h(px(24.))
                                                    .font_family("Menlo")
                                                    .text_size(px(12.))
                                                    .child(cell(
                                                        r.left_no,
                                                        &r.left,
                                                        if r.changed && r.left_no.is_some() {
                                                            0x43262f
                                                        } else {
                                                            0x151d29
                                                        },
                                                        this.horizontal_offset,
                                                    ))
                                                    .child(
                                                        div().w(px(1.)).h_full().bg(rgb(0x354259)),
                                                    )
                                                    .child(cell(
                                                        r.right_no,
                                                        &r.right,
                                                        if r.changed && r.right_no.is_some() {
                                                            0x203c32
                                                        } else {
                                                            0x151d29
                                                        },
                                                        this.horizontal_offset,
                                                    ))
                                            })
                                            .collect::<Vec<_>>()
                                    }),
                                )
                                .flex_1(),
                            ),
                    ),
            )
            .child(
                div()
                    .px_3()
                    .py_2()
                    .border_t_1()
                    .border_color(rgb(0x2b3545))
                    .text_color(rgb(0x92a2b9))
                    .child(format!(
                        "{}{}",
                        if self.loading { "◌  " } else { "" },
                        self.message
                    )),
            )
    }
}
fn main() {
    let path = std::env::args_os()
        .nth(1)
        .map(PathBuf::from)
        .unwrap_or_else(|| std::env::current_dir().unwrap());
    Application::new().run(move |cx: &mut App| {
        cx.on_window_closed(|cx| {
            cx.quit();
        })
        .detach();
        cx.open_window(
            WindowOptions {
                window_bounds: Some(WindowBounds::Windowed(Bounds::centered(
                    None,
                    size(px(1400.), px(860.)),
                    cx,
                ))),
                titlebar: Some(TitlebarOptions {
                    title: Some("MyGit · GPUI Prototype".into()),
                    ..Default::default()
                }),
                ..Default::default()
            },
            |_, cx| {
                cx.new(|cx| {
                    let mut app = MyGit::new();
                    app.load(path, cx);
                    app
                })
            },
        )
        .expect("无法创建窗口");
        cx.activate(true);
    });
}
