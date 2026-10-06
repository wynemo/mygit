use gpui::{prelude::*, *};
use mygit_gpui::graph::Row;
const COLORS: [u32; 8] = [
    0x1f77b4, 0xe4a0ff, 0x277b31, 0xffcb77, 0xff8c9a, 0x71dce8, 0xc0ce77, 0xb1a0ff,
];
pub fn row(row: Row) -> impl IntoElement {
    let width = (row.columns as f32 * 14. + 12.).max(28.);
    canvas(
        |_, _, _| (),
        move |bounds, _, window, _| {
            let x = |lane: usize| bounds.left() + px(12. + lane as f32 * 14.);
            let middle = bounds.top() + bounds.size.height / 2.;
            for edge in &row.edges {
                let (start, end) = if edge.incoming {
                    (point(x(edge.from), bounds.top()), point(x(edge.to), middle))
                } else {
                    (
                        point(x(edge.from), middle),
                        point(x(edge.to), bounds.bottom()),
                    )
                };
                let mut path = PathBuilder::stroke(px(1.5));
                path.move_to(start);
                path.line_to(end);
                if let Ok(path) = path.build() {
                    window.paint_path(path, rgb(COLORS[edge.color % COLORS.len()]));
                }
            }
            if row.omitted > 0 {
                let mut path = PathBuilder::stroke(px(1.));
                path.move_to(point(x(row.lane), middle + px(5.)));
                path.line_to(point(x(row.lane), middle + px(12.)));
                if let Ok(path) = path.build() {
                    window.paint_path(path, rgb(0x888888));
                }
            }
            window.paint_quad(
                fill(
                    Bounds::new(
                        point(x(row.lane) - px(4.), middle - px(4.)),
                        size(px(8.), px(8.)),
                    ),
                    rgb(COLORS[row.color % COLORS.len()]),
                )
                .corner_radii(px(4.)),
            );
        },
    )
    .w(px(width))
    .h_full()
    .flex_shrink_0()
}
