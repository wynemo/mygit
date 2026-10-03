mod app;
mod tasks;
mod views;
use app::*;
use gpui::*;
use std::path::PathBuf;
use views::editor::*;

fn main() {
    let path = std::env::args_os()
        .nth(1)
        .map(PathBuf::from)
        .or_else(|| {
            mygit_gpui::settings::Settings::load(mygit_gpui::settings::Settings::default_path())
                .last
        })
        .unwrap_or_else(|| std::env::current_dir().unwrap_or_else(|_| PathBuf::from(".")));
    Application::new().run(move |cx: &mut App| {
        cx.set_menus(vec![
            Menu {
                name: "MyGit".into(),
                items: vec![
                    MenuItem::action("设置", ToggleSettings),
                    MenuItem::separator(),
                    MenuItem::action("退出", Quit),
                ],
            },
            Menu {
                name: "仓库".into(),
                items: vec![
                    MenuItem::action("打开仓库", OpenRepo),
                    MenuItem::action("刷新", RefreshRepo),
                    MenuItem::action("分支管理", ToggleBranches),
                    MenuItem::action("历史搜索", ToggleHistorySearch),
                    MenuItem::action("取消加载", CancelTask),
                    MenuItem::separator(),
                    MenuItem::action("全部变更", ViewWorkspace),
                    MenuItem::action("已暂存", ViewStaged),
                    MenuItem::action("未暂存", ViewUnstaged),
                    MenuItem::action("复制提交 SHA", CopyCommitSha),
                ],
            },
            Menu {
                name: "编辑".into(),
                items: vec![
                    MenuItem::action("复制", CopyText),
                    MenuItem::action("全选", SelectAllText),
                ],
            },
            Menu {
                name: "差异".into(),
                items: vec![
                    MenuItem::action("上一处", PreviousDiff),
                    MenuItem::action("下一处", NextDiff),
                ],
            },
        ]);
        cx.bind_keys([
            KeyBinding::new("cmd-f", FindText, Some("FileEditor")),
            KeyBinding::new("ctrl-f", FindText, Some("FileEditor")),
            KeyBinding::new("f3", FindNext, Some("FileEditor")),
            KeyBinding::new("shift-f3", FindPrevious, Some("FileEditor")),
            KeyBinding::new("escape", CloseFind, Some("FileEditor")),
            KeyBinding::new("backspace", EditorBackspace, Some("FileEditor")),
            KeyBinding::new("delete", EditorDelete, Some("FileEditor")),
            KeyBinding::new("enter", InsertNewline, Some("FileEditor")),
            KeyBinding::new("tab", InsertTab, Some("FileEditor")),
            KeyBinding::new("cmd-v", EditorPaste, Some("FileEditor")),
            KeyBinding::new("ctrl-v", EditorPaste, Some("FileEditor")),
            KeyBinding::new("cmd-x", EditorCut, Some("FileEditor")),
            KeyBinding::new("ctrl-x", EditorCut, Some("FileEditor")),
            KeyBinding::new("cmd-z", EditorUndo, Some("FileEditor")),
            KeyBinding::new("ctrl-z", EditorUndo, Some("FileEditor")),
            KeyBinding::new("cmd-shift-z", EditorRedo, Some("FileEditor")),
            KeyBinding::new("ctrl-shift-z", EditorRedo, Some("FileEditor")),
            KeyBinding::new("cmd-s", EditorSave, Some("FileEditor")),
            KeyBinding::new("ctrl-s", EditorSave, Some("FileEditor")),
            KeyBinding::new("cmd-1", ViewWorkspace, Some("MyGit")),
            KeyBinding::new("cmd-2", ViewStaged, Some("MyGit")),
            KeyBinding::new("cmd-3", ViewUnstaged, Some("MyGit")),
            KeyBinding::new("ctrl-1", ViewWorkspace, Some("MyGit")),
            KeyBinding::new("ctrl-2", ViewStaged, Some("MyGit")),
            KeyBinding::new("ctrl-3", ViewUnstaged, Some("MyGit")),
            KeyBinding::new("cmd-shift-c", CopyCommitSha, Some("HistoryList")),
            KeyBinding::new("ctrl-shift-c", CopyCommitSha, Some("HistoryList")),
            KeyBinding::new("cmd-q", Quit, None),
            KeyBinding::new("cmd-o", OpenRepo, Some("MyGit")),
            KeyBinding::new("ctrl-o", OpenRepo, Some("MyGit")),
            KeyBinding::new("cmd-r", RefreshRepo, Some("MyGit")),
            KeyBinding::new("ctrl-r", RefreshRepo, Some("MyGit")),
            KeyBinding::new("cmd-,", ToggleSettings, Some("MyGit")),
            KeyBinding::new("escape", CancelTask, Some("MyGit")),
            KeyBinding::new("tab", FocusNext, Some("MyGit")),
            KeyBinding::new("shift-tab", FocusPrevious, Some("MyGit")),
            KeyBinding::new("up", ListUp, Some("HistoryList || FilesList || BranchList")),
            KeyBinding::new(
                "down",
                ListDown,
                Some("HistoryList || FilesList || BranchList"),
            ),
            KeyBinding::new(
                "enter",
                ListEnter,
                Some("HistoryList || FilesList || BranchList"),
            ),
            KeyBinding::new("cmd-c", CopyText, Some("DiffText || FileEditor")),
            KeyBinding::new("ctrl-c", CopyText, Some("DiffText || FileEditor")),
            KeyBinding::new("cmd-a", SelectAllText, Some("DiffText || FileEditor")),
            KeyBinding::new("ctrl-a", SelectAllText, Some("DiffText || FileEditor")),
            KeyBinding::new("alt-down", NextDiff, Some("DiffText || FileEditor")),
            KeyBinding::new("alt-up", PreviousDiff, Some("DiffText || FileEditor")),
            KeyBinding::new("left", Left, Some("DiffText || FileEditor")),
            KeyBinding::new("shift-left", SelectLeft, Some("DiffText || FileEditor")),
            KeyBinding::new("right", Right, Some("DiffText || FileEditor")),
            KeyBinding::new("shift-right", SelectRight, Some("DiffText || FileEditor")),
            KeyBinding::new("up", Up, Some("DiffText || FileEditor")),
            KeyBinding::new("shift-up", SelectUp, Some("DiffText || FileEditor")),
            KeyBinding::new("down", Down, Some("DiffText || FileEditor")),
            KeyBinding::new("shift-down", SelectDown, Some("DiffText || FileEditor")),
            KeyBinding::new("home", Home, Some("DiffText || FileEditor")),
            KeyBinding::new("shift-home", SelectHome, Some("DiffText || FileEditor")),
            KeyBinding::new("end", End, Some("DiffText || FileEditor")),
            KeyBinding::new("shift-end", SelectEnd, Some("DiffText || FileEditor")),
            KeyBinding::new("cmd-up", Start, Some("DiffText || FileEditor")),
            KeyBinding::new("shift-cmd-up", SelectStart, Some("DiffText || FileEditor")),
            KeyBinding::new("cmd-down", Finish, Some("DiffText || FileEditor")),
            KeyBinding::new(
                "shift-cmd-down",
                SelectFinish,
                Some("DiffText || FileEditor"),
            ),
            KeyBinding::new("ctrl-home", Start, Some("DiffText || FileEditor")),
            KeyBinding::new(
                "shift-ctrl-home",
                SelectStart,
                Some("DiffText || FileEditor"),
            ),
            KeyBinding::new("ctrl-end", Finish, Some("DiffText || FileEditor")),
            KeyBinding::new(
                "shift-ctrl-end",
                SelectFinish,
                Some("DiffText || FileEditor"),
            ),
        ]);
        cx.on_window_closed(|cx| cx.quit()).detach();
        cx.open_window(
            WindowOptions {
                window_bounds: Some(WindowBounds::Windowed(Bounds::centered(
                    None,
                    size(px(1400.), px(860.)),
                    cx,
                ))),
                window_min_size: Some(size(px(760.), px(480.))),
                titlebar: Some(TitlebarOptions {
                    title: Some("MyGit · GPUI Prototype".into()),
                    ..Default::default()
                }),
                ..Default::default()
            },
            |window, cx| {
                let entity = cx.new(|cx| {
                    let mut app = MyGit::new(cx);
                    app.observe_activation(window, cx);
                    app.load(path, cx);
                    window.focus(&app.history_focus);
                    app
                });
                let weak = entity.downgrade();
                window.on_window_should_close(cx, move |_, cx| {
                    weak.update(cx, |this, cx| this.request_close(cx))
                        .unwrap_or(true)
                });
                entity
            },
        )
        .expect("无法创建窗口");
        cx.activate(true);
    });
}
