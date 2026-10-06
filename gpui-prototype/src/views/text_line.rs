use crate::app::MyGit;
use gpui::{prelude::*, *};
use mygit_gpui::text::{DisplayLine, Side};

pub struct LineHit {
    pub side: Side,
    pub view_row: usize,
    pub bounds: Bounds<Pixels>,
    pub origin: Point<Pixels>,
    pub line: ShapedLine,
    pub display: DisplayLine,
    pub start: usize,
}
impl LineHit {
    pub fn offset(&self, x: Pixels) -> usize {
        self.start
            + self
                .display
                .source_offset(self.line.closest_index_for_x(x - self.origin.x))
    }
}

pub fn line(this: &MyGit, side: Side, row: usize, cx: &mut Context<MyGit>) -> impl IntoElement {
    let palette = mygit_gpui::syntax::palette_index(&this.settings.code_theme);
    let view_row = this.state.view_row(row, side);
    let document = this.state.diff.document(side).clone();
    let source_line = this.state.diff.source_line(side, row);
    let range = source_line
        .map(|i| document.display_range(i))
        .unwrap_or_else(|| {
            let offset = this.state.diff.padding_offset(side, row);
            offset..offset
        });
    let display = DisplayLine::new(&document.text[range.clone()]);
    let tokens = source_line
        .and_then(|i| this.state.diff.syntax(side).lines.get(i))
        .cloned()
        .unwrap_or_default();
    let inline = match side {
        Side::Left => this.state.diff.rows[row].left_inline.clone(),
        Side::Right => this.state.diff.rows[row].right_inline.clone(),
        Side::Third => vec![],
    };
    let selection = this.state.text_selection.clone();
    let horizontal = this.state.horizontal_offset;
    let entity = cx.entity();
    let start = range.start;
    canvas(
        move |_, window, _| {
            let font = window.text_style().font();
            let mut runs: Vec<TextRun> = tokens
                .iter()
                .filter_map(|token| {
                    let len = display.display_offset(token.range.end)
                        - display.display_offset(token.range.start);
                    (len > 0).then(|| TextRun {
                        len,
                        font: font.clone(),
                        color: rgb(token.color_for(palette)).into(),
                        background_color: None,
                        underline: None,
                        strikethrough: None,
                    })
                })
                .collect();
            if runs.is_empty() {
                runs.push(TextRun {
                    len: display.text.len(),
                    font,
                    color: rgb(0x202020).into(),
                    background_color: None,
                    underline: None,
                    strikethrough: None,
                });
            }
            let style = window.text_style();
            let line = window.text_system().shape_line(
                display.text.clone().into(),
                style.font_size.to_pixels(window.rem_size()),
                &runs,
                None,
            );
            (line, display)
        },
        move |bounds, (line, display), window, cx| {
            let origin = point(bounds.left() - px(horizontal), bounds.top());
            let visible = window.content_mask().bounds.intersect(&bounds);
            window.with_content_mask(Some(ContentMask { bounds }), |window| {
                for changed in &inline {
                    let x1 = line.x_for_index(display.display_offset(changed.start));
                    let x2 = line.x_for_index(display.display_offset(changed.end));
                    window.paint_quad(fill(
                        Bounds::new(
                            point(origin.x + x1, bounds.top()),
                            size((x2 - x1).max(px(1.)), bounds.size.height),
                        ),
                        rgb(if side == Side::Left {
                            0xf5b6b6
                        } else {
                            0xb5dfb5
                        }),
                    ));
                }
                if selection.side == side
                    && let Some(source_line) = source_line
                {
                    let selected = selection.range();
                    if selected.start < document.lines[source_line].end
                        && selected.end > range.start
                    {
                        let a = selected.start.saturating_sub(start).min(range.len());
                        let b = selected.end.saturating_sub(start).min(range.len());
                        let x1 = line.x_for_index(display.display_offset(a));
                        let mut x2 = line.x_for_index(display.display_offset(b));
                        if selected.end > range.end {
                            x2 += px(8.);
                        }
                        window.paint_quad(fill(
                            Bounds::new(
                                point(origin.x + x1, bounds.top()),
                                size((x2 - x1).max(px(0.)), bounds.size.height),
                            ),
                            rgb(0xb5d6fa),
                        ));
                    }
                    if selection.range().is_empty()
                        && selection.head >= range.start
                        && selection.head <= range.end
                        && entity.read(cx).focus.is_focused(window)
                    {
                        let x = line.x_for_index(display.display_offset(selection.head - start));
                        window.paint_quad(fill(
                            Bounds::new(
                                point(origin.x + x, bounds.top() + px(3.)),
                                size(px(1.), bounds.size.height - px(6.)),
                            ),
                            rgb(0x202020),
                        ));
                    }
                }
                let _ = line.paint(origin, bounds.size.height, window, cx);
            });
            entity.update(cx, |this, _| {
                this.line_layouts.insert(
                    (side, row),
                    LineHit {
                        side,
                        view_row,
                        bounds: visible,
                        origin,
                        line,
                        display,
                        start,
                    },
                );
            });
        },
    )
    .w_full()
    .h_full()
}
