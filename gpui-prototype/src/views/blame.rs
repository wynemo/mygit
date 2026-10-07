use crate::app::MyGit;
use gpui::{prelude::*, *};
use mygit_gpui::{blame::Line, model::short_sha};
// Stable commit colors: scrolling, refreshes and opposite diff sides agree.
// Use pale backgrounds with dark ink so annotations remain readable.
fn commit_colors(sha: &str, pending: bool) -> (u32, u32, u32) {
    if pending {
        return (0xfff3d6, 0x805b14, 0xd8a438);
    }
    const COLORS: [(u32, u32, u32); 12] = [
        (0xe4edfc, 0x365789, 0x7a9ed5),
        (0xe9e5f7, 0x594687, 0xa08cc9),
        (0xe0f0e9, 0x326650, 0x7ab29a),
        (0xf9e6e5, 0x874c49, 0xd49893),
        (0xe0f0f4, 0x356574, 0x80b4c3),
        (0xf5eadb, 0x7b5b32, 0xc4a070),
        (0xeee5f2, 0x735381, 0xb397c0),
        (0xeaf0dc, 0x586735, 0xa6b67b),
        (0xf7e4ed, 0x854963, 0xcf93ad),
        (0xe3eaf2, 0x455c77, 0x8da5c0),
        (0xe0efef, 0x366c69, 0x7ab3af),
        (0xf8ebdf, 0x865b3b, 0xd0a27d),
    ];
    let hash = sha.bytes().fold(2166136261u32, |hash, byte| {
        (hash ^ u32::from(byte)).wrapping_mul(16777619)
    });
    COLORS[hash as usize % COLORS.len()]
}

const FONT_FAMILY: &str = ".AppleSystemUIFont";

fn label(line: &Line) -> String {
    if line.commit.uncommitted() {
        mygit_gpui::i18n::text("未提交").into()
    } else {
        format!("{} {}", short_sha(&line.commit.sha), line.commit.author)
    }
}

// Measure unique labels once when annotations load, keeping every row aligned.
pub fn column_width<'a>(lines: impl Iterator<Item = &'a Line>, cx: &App) -> f32 {
    let mut labels = std::collections::HashSet::new();
    lines.fold(100.0_f32, |width, line| {
        let label = label(line);
        if !labels.insert(label.clone()) {
            return width;
        }
        let text_system = cx.text_system();
        let font_id = text_system.resolve_font(&font(FONT_FAMILY));
        let text_width: f32 = label
            .chars()
            .map(|ch| {
                text_system
                    .advance(font_id, px(11.), ch)
                    .map(|size| f32::from(size.width))
                    .unwrap_or(11.)
            })
            .sum();
        // Padding, left border and a little breathing room.
        width.max(text_width.ceil() + 16.)
    })
}

pub fn gutter(owner: WeakEntity<MyGit>, line: Option<Line>, index: usize, width: f32) -> Div {
    div()
        .w(px(width))
        .h_full()
        .flex_shrink_0()
        .when_some(line, |s, line| s.child(annotation(owner, line, index)))
}
pub fn annotation(owner: WeakEntity<MyGit>, line: Line, index: usize) -> Stateful<Div> {
    let pending = line.commit.uncommitted();
    let (background, foreground, edge) = commit_colors(&line.commit.sha, pending);
    let label = label(&line);
    let tooltip_owner = owner.clone();
    let tooltip_line = line.clone();
    let click_owner = owner.clone();
    let sha = line.commit.sha.clone();
    div()
        .id(("blame-annotation", index))
        .w_full()
        .flex_shrink_0()
        .h_full()
        .px_1()
        .font_family(FONT_FAMILY)
        .text_size(px(11.))
        .bg(rgb(background))
        .text_color(rgb(foreground))
        .border_l_2()
        .border_color(rgb(edge))
        .hover(|s| s.bg(rgb(edge)).text_color(rgb(0x182333)))
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
