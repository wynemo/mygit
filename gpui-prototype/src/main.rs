mod app;
mod tasks;
mod views;
use app::MyGit;
use gpui::*;
use std::path::PathBuf;

fn main() {
    let path = std::env::args_os()
        .nth(1)
        .map(PathBuf::from)
        .unwrap_or_else(|| std::env::current_dir().unwrap());
    Application::new().run(move |cx: &mut App| {
        cx.on_window_closed(|cx| cx.quit()).detach();
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
