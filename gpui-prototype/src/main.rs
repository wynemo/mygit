mod app;
mod assets;
mod tasks;
mod views;
use app::*;
use gpui::*;
use std::path::PathBuf;
use views::editor::*;

fn main() {
    let startup_settings =
        mygit_gpui::settings::Settings::load(mygit_gpui::settings::Settings::default_path());
    mygit_gpui::i18n::initialize(startup_settings.language);
    let path = std::env::args_os()
        .nth(1)
        .map(PathBuf::from)
        .or(startup_settings.last)
        .unwrap_or_else(|| std::env::current_dir().unwrap_or_else(|_| PathBuf::from(".")));
    let application = Application::new().with_assets(assets::Embedded);
    application.run(move |cx: &mut App| {
        cx.set_menus(vec![
            Menu {
                name: "MyGit".into(),
                items: vec![
                    MenuItem::action(mygit_gpui::i18n::text("设置"), ToggleSettings),
                    MenuItem::action(mygit_gpui::i18n::text("通知"), ToggleNotifications),
                    MenuItem::separator(),
                    MenuItem::action(mygit_gpui::i18n::text("退出"), Quit),
                ],
            },
            Menu {
                name: mygit_gpui::i18n::text("仓库").into(),
                items: vec![
                    MenuItem::action(mygit_gpui::i18n::text("打开仓库"), OpenRepo),
                    MenuItem::action(mygit_gpui::i18n::text("刷新"), RefreshRepo),
                    MenuItem::action(mygit_gpui::i18n::text("分支管理"), ToggleBranches),
                    MenuItem::action(mygit_gpui::i18n::text("历史搜索"), ToggleHistorySearch),
                    MenuItem::action(mygit_gpui::i18n::text("项目内容搜索"), ToggleProjectSearch),
                    MenuItem::action(mygit_gpui::i18n::text("文件快速定位"), ToggleQuickOpen),
                    MenuItem::action(mygit_gpui::i18n::text("取消加载"), CancelTask),
                    MenuItem::action(
                        mygit_gpui::i18n::text("显示 / 隐藏文件栏"),
                        ToggleFilesPanel,
                    ),
                    MenuItem::action(
                        mygit_gpui::i18n::text("显示 / 隐藏 Git 面板"),
                        ToggleGitPanel,
                    ),
                    MenuItem::separator(),
                    MenuItem::action(mygit_gpui::i18n::text("全部变更"), ViewWorkspace),
                    MenuItem::action(mygit_gpui::i18n::text("已暂存"), ViewStaged),
                    MenuItem::action(mygit_gpui::i18n::text("未暂存"), ViewUnstaged),
                    MenuItem::action(mygit_gpui::i18n::text("复制提交 SHA"), CopyCommitSha),
                ],
            },
            Menu {
                name: mygit_gpui::i18n::text("工作区").into(),
                items: vec![
                    MenuItem::action(mygit_gpui::i18n::text("暂存选中文件"), StageSelected),
                    MenuItem::action(mygit_gpui::i18n::text("取消暂存选中文件"), UnstageSelected),
                    MenuItem::separator(),
                    MenuItem::action(mygit_gpui::i18n::text("暂存全部文件"), StageAll),
                    MenuItem::action(mygit_gpui::i18n::text("取消全部暂存"), UnstageAll),
                    MenuItem::separator(),
                    MenuItem::action(mygit_gpui::i18n::text("提交面板"), ToggleCommitPanel),
                ],
            },
            Menu {
                name: mygit_gpui::i18n::text("编辑").into(),
                items: vec![
                    MenuItem::action(mygit_gpui::i18n::text("撤销"), EditorUndo),
                    MenuItem::action(mygit_gpui::i18n::text("重做"), EditorRedo),
                    MenuItem::separator(),
                    MenuItem::action(mygit_gpui::i18n::text("剪切"), EditorCut),
                    MenuItem::action(mygit_gpui::i18n::text("粘贴"), EditorPaste),
                    MenuItem::action(mygit_gpui::i18n::text("复制"), CopyText),
                    MenuItem::action(mygit_gpui::i18n::text("全选"), SelectAllText),
                    MenuItem::action(mygit_gpui::i18n::text("查找"), FindText),
                ],
            },
            Menu {
                name: mygit_gpui::i18n::text("差异").into(),
                items: vec![
                    MenuItem::action(mygit_gpui::i18n::text("上一处"), PreviousDiff),
                    MenuItem::action(mygit_gpui::i18n::text("下一处"), NextDiff),
                ],
            },
        ]);
        cx.bind_keys([
            KeyBinding::new("cmd-shift-m", ToggleNotifications, Some("MyGit")),
            KeyBinding::new("ctrl-shift-m", ToggleNotifications, Some("MyGit")),
            KeyBinding::new("cmd-j", ToggleGitPanel, Some("MyGit")),
            KeyBinding::new("ctrl-j", ToggleGitPanel, Some("MyGit")),
            KeyBinding::new("cmd-b", ToggleFilesPanel, Some("MyGit")),
            KeyBinding::new("ctrl-b", ToggleFilesPanel, Some("MyGit")),
            KeyBinding::new("cmd-k", ToggleCommitPanel, Some("MyGit")),
            KeyBinding::new("ctrl-k", ToggleCommitPanel, Some("MyGit")),
            KeyBinding::new("cmd-shift-f", ToggleProjectSearch, Some("MyGit")),
            KeyBinding::new("ctrl-shift-f", ToggleProjectSearch, Some("MyGit")),
            KeyBinding::new("cmd-p", ToggleQuickOpen, Some("MyGit")),
            KeyBinding::new("ctrl-p", ToggleQuickOpen, Some("MyGit")),
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
            KeyBinding::new("shift-f10", OpenTreeMenu, Some("FilesList")),
            KeyBinding::new("up", TreeMenuUp, Some("TreeMenu")),
            KeyBinding::new("down", TreeMenuDown, Some("TreeMenu")),
            KeyBinding::new("enter", TreeMenuAccept, Some("TreeMenu")),
            KeyBinding::new("escape", DismissTreeMenu, Some("TreeMenu")),
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
            KeyBinding::new(
                "cmd-c",
                CopyText,
                Some("DiffText || FileEditor || MergeHistory"),
            ),
            KeyBinding::new(
                "ctrl-c",
                CopyText,
                Some("DiffText || FileEditor || MergeHistory"),
            ),
            KeyBinding::new(
                "cmd-a",
                SelectAllText,
                Some("DiffText || FileEditor || MergeHistory"),
            ),
            KeyBinding::new(
                "ctrl-a",
                SelectAllText,
                Some("DiffText || FileEditor || MergeHistory"),
            ),
            KeyBinding::new(
                "alt-down",
                NextDiff,
                Some("DiffText || FileEditor || MergeHistory"),
            ),
            KeyBinding::new(
                "alt-up",
                PreviousDiff,
                Some("DiffText || FileEditor || MergeHistory"),
            ),
            KeyBinding::new("left", Left, Some("DiffText || FileEditor || MergeHistory")),
            KeyBinding::new(
                "shift-left",
                SelectLeft,
                Some("DiffText || FileEditor || MergeHistory"),
            ),
            KeyBinding::new(
                "right",
                Right,
                Some("DiffText || FileEditor || MergeHistory"),
            ),
            KeyBinding::new(
                "shift-right",
                SelectRight,
                Some("DiffText || FileEditor || MergeHistory"),
            ),
            KeyBinding::new("up", Up, Some("DiffText || FileEditor || MergeHistory")),
            KeyBinding::new(
                "shift-up",
                SelectUp,
                Some("DiffText || FileEditor || MergeHistory"),
            ),
            KeyBinding::new("down", Down, Some("DiffText || FileEditor || MergeHistory")),
            KeyBinding::new(
                "shift-down",
                SelectDown,
                Some("DiffText || FileEditor || MergeHistory"),
            ),
            KeyBinding::new("home", Home, Some("DiffText || FileEditor || MergeHistory")),
            KeyBinding::new(
                "shift-home",
                SelectHome,
                Some("DiffText || FileEditor || MergeHistory"),
            ),
            KeyBinding::new("end", End, Some("DiffText || FileEditor || MergeHistory")),
            KeyBinding::new(
                "shift-end",
                SelectEnd,
                Some("DiffText || FileEditor || MergeHistory"),
            ),
            KeyBinding::new(
                "cmd-up",
                Start,
                Some("DiffText || FileEditor || MergeHistory"),
            ),
            KeyBinding::new(
                "shift-cmd-up",
                SelectStart,
                Some("DiffText || FileEditor || MergeHistory"),
            ),
            KeyBinding::new(
                "cmd-down",
                Finish,
                Some("DiffText || FileEditor || MergeHistory"),
            ),
            KeyBinding::new(
                "shift-cmd-down",
                SelectFinish,
                Some("DiffText || FileEditor || MergeHistory"),
            ),
            KeyBinding::new(
                "ctrl-home",
                Start,
                Some("DiffText || FileEditor || MergeHistory"),
            ),
            KeyBinding::new(
                "shift-ctrl-home",
                SelectStart,
                Some("DiffText || FileEditor || MergeHistory"),
            ),
            KeyBinding::new(
                "ctrl-end",
                Finish,
                Some("DiffText || FileEditor || MergeHistory"),
            ),
            KeyBinding::new(
                "shift-ctrl-end",
                SelectFinish,
                Some("DiffText || FileEditor || MergeHistory"),
            ),
            KeyBinding::new("up", ProjectSearchUp, Some("ProjectSearch > FileEditor")),
            KeyBinding::new(
                "down",
                ProjectSearchDown,
                Some("ProjectSearch > FileEditor"),
            ),
            KeyBinding::new(
                "enter",
                ProjectSearchAccept,
                Some("ProjectSearch > FileEditor"),
            ),
            KeyBinding::new(
                "escape",
                ProjectSearchDismiss,
                Some("ProjectSearch > FileEditor"),
            ),
            KeyBinding::new("up", QuickUp, Some("QuickOpen > FileEditor")),
            KeyBinding::new("down", QuickDown, Some("QuickOpen > FileEditor")),
            KeyBinding::new("enter", QuickAccept, Some("QuickOpen > FileEditor")),
            KeyBinding::new("escape", QuickDismiss, Some("QuickOpen > FileEditor")),
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
        .expect("Unable to create window");
        cx.activate(true);
    });
}
