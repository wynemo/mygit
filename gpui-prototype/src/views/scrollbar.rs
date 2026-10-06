//! Visible scrollbar for the native-sized virtual lists.
use gpui::{prelude::*, *};
use std::ops::Range;

pub struct ListScrollbar(pub UniformListScrollHandle, pub Option<f32>);
impl UniformListDecoration for ListScrollbar {
    fn compute(
        &self,
        _: Range<usize>,
        bounds: Bounds<Pixels>,
        offset: Point<Pixels>,
        item_height: Pixels,
        count: usize,
        _: &mut Window,
        _: &mut App,
    ) -> AnyElement {
        let height = f32::from(bounds.size.height);
        let content = f32::from(item_height) * count as f32;
        let maximum = (content - height).max(0.);
        let thumb = (height * height / content.max(height)).max(24.).min(height);
        let travel = (height - thumb).max(0.);
        let top = if maximum > 0. {
            (-f32::from(offset.y) / maximum).clamp(0., 1.) * travel
        } else {
            0.
        };
        let handle = self.0.0.borrow().base_handle.clone();
        let down_handle = handle.clone();
        let move_handle = handle;
        let update = move |position: Point<Pixels>, handle: &ScrollHandle| {
            let ratio = if travel > 0. {
                ((f32::from(position.y - bounds.top()) - thumb / 2.) / travel).clamp(0., 1.)
            } else {
                0.
            };
            handle.set_offset(point(handle.offset().x, px(-ratio * maximum)));
        };
        div()
            .w(px(self.1.unwrap_or(f32::from(bounds.size.width))))
            .h(bounds.size.height)
            .child(
                div()
                    .id("list-scrollbar")
                    .absolute()
                    .right_0()
                    .top_0()
                    .w(px(12.))
                    .h(bounds.size.height)
                    .bg(rgb(0xf1f1f1))
                    .when(maximum > 0., |s| {
                        s.child(
                            div()
                                .absolute()
                                .top(px(top))
                                .left(px(3.))
                                .w(px(6.))
                                .h(px(thumb))
                                .rounded(px(3.))
                                .bg(rgb(0xb6b6b6)),
                        )
                    })
                    .on_mouse_down(MouseButton::Left, move |event, window, cx| {
                        update(event.position, &down_handle);
                        cx.stop_propagation();
                        window.refresh();
                    })
                    .on_mouse_move(move |event, window, cx| {
                        if event.pressed_button == Some(MouseButton::Left) {
                            update(event.position, &move_handle);
                            cx.stop_propagation();
                            window.refresh();
                        }
                    }),
            )
            .into_any_element()
    }
}
