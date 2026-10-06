use crate::app::MyGit;
use gpui::{prelude::*, *};
use mygit_gpui::{blame::Line, model::short_sha};
pub fn gutter(owner: WeakEntity<MyGit>, line: Option<Line>, index: usize) -> Div {
    div()
        .w(px(100.))
        .h_full()
        .flex_shrink_0()
        .when_some(line, |s, line| s.child(annotation(owner, line, index)))
}
pub fn annotation(owner: WeakEntity<MyGit>, line: Line, index: usize) -> Stateful<Div> {
    let pending = line.commit.uncommitted();
    let label = if pending {
        mygit_gpui::i18n::text("未提交").into()
    } else {
        format!("{} {}", short_sha(&line.commit.sha), line.commit.author)
    };
    let tooltip_owner = owner.clone();
    let tooltip_line = line.clone();
    let click_owner = owner.clone();
    let sha = line.commit.sha.clone();
    div()
        .id(("blame-annotation", index))
        .w(px(100.))
        .flex_shrink_0()
        .h_full()
        .px_1()
        .text_size(px(11.))
        .text_color(rgb(if pending {
            0x946200
        } else {
            crate::views::theme::MUTED
        }))
        .overflow_hidden()
        .whitespace_nowrap()
        .when(!pending, |s| s.cursor_pointer())
        .child(label)
        .on_mouse_down(MouseButton::Left, |_, _, cx| cx.stop_propagation())
        .on_mouse_down(MouseButton::Right, move |_, _, cx| {
            if !pending {
                cx.write_to_clipboard(ClipboardItem::new_string(sha.clone()));
            }
            cx.stop_propagation();
        })
        .on_click(move |_, window, cx| {
            if !pending {
                let sha = line.commit.sha.clone();
                let _ = click_owner.update(cx, |this, cx| {
                    this.jump_blame(sha, cx);
                    window.focus(&this.history_focus);
                });
            }
            cx.stop_propagation();
        })
        .tooltip(move |_, cx| {
            if !pending {
                let sha = tooltip_line.commit.sha.clone();
                let _ = tooltip_owner.update(cx, |this, cx| this.load_blame_detail(sha, cx));
            }
            cx.new(|cx| {
                if let Some(entity) = tooltip_owner.upgrade() {
                    cx.observe(&entity, |_, _, cx| cx.notify()).detach();
                }
                Tooltip {
                    owner: tooltip_owner.clone(),
                    line: tooltip_line.clone(),
                }
            })
            .into()
        })
}
struct Tooltip {
    owner: WeakEntity<MyGit>,
    line: Line,
}
impl Render for Tooltip {
    fn render(&mut self, _: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        let detail = self.owner.upgrade().and_then(|owner| {
            owner
                .read(cx)
                .blame_details
                .get(&self.line.commit.sha)
                .cloned()
        });
        let message = detail
            .map(|detail| {
                format!(
                    "{} <{}>\n{}\n{}",
                    detail.author, detail.author_email, detail.author_date, detail.message
                )
            })
            .unwrap_or_else(|| {
                format!(
                    "{} {}\n{}",
                    self.line.commit.author, self.line.commit.email, self.line.commit.summary
                )
            });
        let message = mygit_gpui::process::display_diagnostic(message);
        div()
            .id("blame-tooltip")
            .max_w(px(560.))
            .max_h(px(280.))
            .overflow_y_scroll()
            .p_3()
            .rounded_md()
            .bg(rgb(crate::views::theme::CHROME))
            .text_color(rgb(crate::views::theme::TEXT))
            .text_size(px(13.))
            .child(if self.line.commit.uncommitted() {
                mygit_gpui::i18n::text("未提交").to_owned()
            } else {
                self.line.commit.sha.clone()
            })
            .child(mygit_gpui::localized_format!(
                "来源：{} : {}",
                "Source: {} : {}",
                self.line.path,
                self.line.original_line
            ))
            .child(message)
            .child(if self.line.commit.uncommitted() {
                mygit_gpui::i18n::text("该行尚无提交归属")
            } else {
                mygit_gpui::i18n::text("单击查看历史，右击复制 SHA")
            })
    }
}
