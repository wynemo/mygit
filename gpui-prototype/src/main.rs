mod app;
mod tasks;
mod views;
use app::*;
use gpui::*;
use std::path::PathBuf;

fn main() {
    let path = std::env::args_os()
        .nth(1)
        .map(PathBuf::from)
        .unwrap_or_else(|| std::env::current_dir().unwrap());
    Application::new().run(move |cx: &mut App| {
        cx.bind_keys([
            KeyBinding::new("cmd-c", CopyText, Some("DiffText")),
            KeyBinding::new("ctrl-c", CopyText, Some("DiffText")),
            KeyBinding::new("cmd-a", SelectAllText, Some("DiffText")),
            KeyBinding::new("ctrl-a", SelectAllText, Some("DiffText")),
            KeyBinding::new("alt-down", NextDiff, Some("DiffText")),
            KeyBinding::new("alt-up", PreviousDiff, Some("DiffText")),
            KeyBinding::new("left", Left, Some("DiffText")),
            KeyBinding::new("shift-left", SelectLeft, Some("DiffText")),
            KeyBinding::new("right", Right, Some("DiffText")),
            KeyBinding::new("shift-right", SelectRight, Some("DiffText")),
            KeyBinding::new("up", Up, Some("DiffText")),
            KeyBinding::new("shift-up", SelectUp, Some("DiffText")),
            KeyBinding::new("down", Down, Some("DiffText")),
            KeyBinding::new("shift-down", SelectDown, Some("DiffText")),
            KeyBinding::new("home", Home, Some("DiffText")),
            KeyBinding::new("shift-home", SelectHome, Some("DiffText")),
            KeyBinding::new("end", End, Some("DiffText")),
            KeyBinding::new("shift-end", SelectEnd, Some("DiffText")),
            KeyBinding::new("cmd-up", Start, Some("DiffText")),
            KeyBinding::new("shift-cmd-up", SelectStart, Some("DiffText")),
            KeyBinding::new("cmd-down", Finish, Some("DiffText")),
            KeyBinding::new("shift-cmd-down", SelectFinish, Some("DiffText")),
            KeyBinding::new("ctrl-home", Start, Some("DiffText")),
            KeyBinding::new("shift-ctrl-home", SelectStart, Some("DiffText")),
            KeyBinding::new("ctrl-end", Finish, Some("DiffText")),
            KeyBinding::new("shift-ctrl-end", SelectFinish, Some("DiffText")),
        ]);
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
                    let mut app = MyGit::new(cx);
                    app.load(path, cx);
                    app
                })
            },
        )
        .expect("无法创建窗口");
        cx.activate(true);
    });
}
