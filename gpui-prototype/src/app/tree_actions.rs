use super::*;
use mygit_gpui::workspace::Entry;

#[derive(Clone)]
pub struct Menu {
    pub entry: Entry,
    pub root: PathBuf,
    pub position: Point<Pixels>,
    pub selected: usize,
}
#[derive(Clone, Copy, PartialEq)]
pub enum Action {
    Open,
    History,
    CopyRelative,
    CopyFull,
    Reveal,
    Blame,
    Restore,
}
impl Action {
    pub fn label(self) -> &'static str {
        mygit_gpui::i18n::text(match self {
            Self::Open => "打开文件",
            Self::History => "历史",
            Self::CopyRelative => "复制相对路径",
            Self::CopyFull => "复制完整路径",
            Self::Reveal => "在文件管理器中显示",
            Self::Blame => "显示 / 隐藏 Blame",
            Self::Restore => "还原到 HEAD",
        })
    }
}
impl MyGit {
    pub fn show_tree_menu(
        &mut self,
        entry: Entry,
        position: Point<Pixels>,
        window: &mut Window,
        cx: &mut Context<Self>,
    ) {
        if self.confirmation.is_some() {
            return;
        }
        let Some(repo) = &self.state.repo else {
            return;
        };
        self.show_notifications = false;
        self.tree.selected = Some(entry.path.clone());
        self.tree_menu = Some(Menu {
            entry,
            root: repo.root.clone(),
            position,
            selected: 0,
        });
        self.restore_main_focus = false;
        window.focus(&self.tree_menu_focus);
        cx.notify();
    }
    pub fn selected_tree_menu(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        if let Some((entry, _)) = self
            .tree
            .rows()
            .into_iter()
            .find(|(entry, _)| Some(&entry.path) == self.tree.selected.as_ref())
        {
            self.show_tree_menu(entry, point(px(12.), px(100.)), window, cx);
        }
    }
    pub fn tree_menu_actions(&self) -> Vec<Action> {
        let Some(menu) = &self.tree_menu else {
            return vec![];
        };
        let mut actions = vec![];
        if !menu.entry.directory {
            actions.push(Action::Open);
        }
        actions.extend([
            Action::History,
            Action::CopyRelative,
            Action::CopyFull,
            Action::Reveal,
        ]);
        if !menu.entry.directory {
            if self
                .state
                .current_file
                .as_ref()
                .is_some_and(|file| file.path == menu.entry.path)
                && self
                    .state
                    .comparison
                    .as_ref()
                    .is_some_and(|comparison| comparison.right == Revision::Worktree)
                && !self.state.loading
            {
                actions.push(Action::Blame);
            }
            if !menu.entry.status.is_empty() && menu.entry.status != "!!" && !self.write_busy {
                actions.push(Action::Restore);
            }
        }
        actions
    }
    pub fn move_tree_menu(&mut self, forward: bool, cx: &mut Context<Self>) {
        let count = self.tree_menu_actions().len();
        if count > 0
            && let Some(menu) = &mut self.tree_menu
        {
            menu.selected = (menu.selected + if forward { 1 } else { count - 1 }) % count;
            cx.notify();
        }
    }
    pub fn accept_tree_menu(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        if let Some(action) = self
            .tree_menu
            .as_ref()
            .and_then(|menu| self.tree_menu_actions().get(menu.selected).copied())
        {
            self.tree_menu_action(action, window, cx);
        }
    }
    pub fn dismiss_tree_menu(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        if self.tree_menu.take().is_some() {
            self.restore_main_focus = false;
            window.focus(if self.settings.files_visible && self.showing_tree() {
                &self.files_focus
            } else {
                &self.focus
            });
            cx.notify();
        }
    }
    pub fn tree_menu_action(
        &mut self,
        action: Action,
        window: &mut Window,
        cx: &mut Context<Self>,
    ) {
        if self.confirmation.is_some() || !self.tree_menu_actions().contains(&action) {
            return;
        }
        let Some(menu) = self.tree_menu.take() else {
            return;
        };
        self.restore_main_focus = false;
        window.focus(if self.settings.files_visible && self.showing_tree() {
            &self.files_focus
        } else {
            &self.focus
        });
        if !self
            .state
            .repo
            .as_ref()
            .is_some_and(|repo| repo.root == menu.root)
        {
            cx.notify();
            return;
        }
        match action {
            Action::Open => self.choose_tree(menu.entry, window, cx),
            Action::History => self.show_path_history(menu.entry.path, menu.entry.directory, cx),
            Action::CopyRelative => {
                cx.write_to_clipboard(ClipboardItem::new_string(menu.entry.path))
            }
            Action::CopyFull => cx.write_to_clipboard(ClipboardItem::new_string(
                menu.root.join(menu.entry.path).display().to_string(),
            )),
            Action::Reveal => cx.reveal_path(&menu.root.join(menu.entry.path)),
            Action::Blame => self.toggle_blame(cx),
            Action::Restore => self.request_tree_restore(menu.entry.path, cx),
        }
        cx.notify();
    }
    fn request_tree_restore(&mut self, path: String, cx: &mut Context<Self>) {
        if self.write_busy || self.confirmation.is_some() {
            return;
        }
        if self.is_dirty(&path, cx)
            || self
                .editors
                .get(&path)
                .is_some_and(|editor| editor.read(cx).buffer.marked.is_some())
        {
            self.notify_result(
                mygit_gpui::notifications::Kind::Error,
                mygit_gpui::i18n::text("还原涉及未保存文件，请先保存或关闭编辑器修改").into(),
                cx,
            );
            return;
        }
        let Some(repo) = &self.state.repo else {
            return;
        };
        let root = repo.root.clone();
        let generation = self
            .state
            .begin(mygit_gpui::i18n::text("正在准备文件还原…").into());
        self.pending.cancel();
        self.pending = Default::default();
        tasks::run(
            cx,
            generation,
            self.pending.clone(),
            move || {
                let (comparison, file) = git::workspace_file(&root, &path)?;
                let diff = git::compare(&root, &comparison, &file)?;
                Ok((comparison, file, diff))
            },
            |this, (comparison, file, diff), cx| {
                if this.is_dirty(&file.path, cx)
                    || this
                        .editors
                        .get(&file.path)
                        .is_some_and(|editor| editor.read(cx).buffer.marked.is_some())
                    || this.write_busy
                    || this.confirmation.is_some()
                {
                    return;
                }
                this.confirmation = Some(Confirmation::Restore {
                    file,
                    comparison,
                    diff: Box::new(diff),
                    block: None,
                });
            },
        );
        cx.notify();
    }
    pub fn drop_tree_file(
        &mut self,
        file: &crate::views::tree::DraggedFile,
        window: &mut Window,
        cx: &mut Context<Self>,
    ) {
        if self.confirmation.is_some()
            || file.entry.directory
            || !self
                .state
                .repo
                .as_ref()
                .is_some_and(|repo| repo.root == file.root)
        {
            return;
        }
        if self.tree.reveal(&file.entry.path).is_err() {
            return;
        }
        self.dismiss_tree_menu(window, cx);
        self.refresh_tree(cx);
        self.choose_tree(file.entry.clone(), window, cx);
    }
}
