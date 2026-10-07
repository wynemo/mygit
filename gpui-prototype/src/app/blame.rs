use super::*;
use mygit_gpui::blame::Line;
use std::sync::Arc;
// Visibility belongs to a file in a specific repository and comparison.
// Source contents and editor mode are deliberately excluded so edits preserve it.
#[derive(Clone, Debug, PartialEq, Eq)]
pub(super) struct Scope {
    root: PathBuf,
    path: String,
    old_path: String,
    comparison: Comparison,
    mode: BrowseMode,
}

#[derive(Clone)]
pub(super) struct Key {
    file: FileChange,
    comparison: Comparison,
    left: Arc<str>,
    right: Arc<str>,
    editing: bool,
    merge: Option<Arc<mygit_gpui::merge::View>>,
}
impl Key {
    fn matches(&self, other: &Self) -> bool {
        self.file.path == other.file.path
            && self.file.old_path == other.file.old_path
            && self.comparison == other.comparison
            && self.editing == other.editing
            && match (&self.merge, &other.merge) {
                (None, None) => true,
                (Some(a), Some(b)) => {
                    Arc::ptr_eq(a, b)
                        || (a.revisions == b.revisions
                            && a.paths == b.paths
                            && a.documents
                                .iter()
                                .zip(&b.documents)
                                .all(|(a, b)| Arc::ptr_eq(&a.text, &b.text) || a.text == b.text))
                }
                _ => false,
            }
            && (Arc::ptr_eq(&self.left, &other.left) || self.left == other.left)
            && (Arc::ptr_eq(&self.right, &other.right) || self.right == other.right)
    }
}
impl MyGit {
    fn blame_scope(&self) -> Option<Scope> {
        Some(Scope {
            root: self.state.repo.as_ref()?.root.clone(),
            path: self.state.current_file.as_ref()?.path.clone(),
            old_path: self.state.current_file.as_ref()?.old_path.clone(),
            comparison: self.state.comparison.clone()?,
            mode: self.state.mode.clone(),
        })
    }
    pub fn toggle_blame(&mut self, cx: &mut Context<Self>) {
        let Some(scope) = self.blame_scope() else {
            return;
        };
        if let Some(index) = self.blame_scopes.iter().position(|saved| saved == &scope) {
            self.blame_scopes.remove(index);
        } else {
            self.blame_scopes.push(scope);
        }
        self.ensure_blame(cx);
        cx.notify();
    }
    pub(super) fn ensure_blame(&mut self, cx: &mut Context<Self>) {
        let enabled = self
            .blame_scope()
            .is_some_and(|scope| self.blame_scopes.contains(&scope));
        if self.show_blame && !enabled {
            self.reset_blame();
        }
        self.show_blame = enabled;
        if !enabled {
            self.sync_editor_blame(cx);
            return;
        }
        if self.state.loading {
            return;
        }
        let (Some(repo), Some(file), Some(comparison)) = (
            &self.state.repo,
            &self.state.current_file,
            &self.state.comparison,
        ) else {
            return;
        };
        let root = repo.root.clone();
        let editing = self.current_editor().is_some();
        let right = if editing {
            self.current_editor()
                .map(|editor| editor.read(cx).buffer.document.text.clone())
                .unwrap_or_else(|| self.state.diff.right_document.text.clone())
        } else {
            self.state.diff.right_document.text.clone()
        };
        let key = Key {
            file: file.clone(),
            comparison: comparison.clone(),
            left: self.state.diff.left_document.text.clone(),
            right,
            editing,
            merge: self.state.merge.clone(),
        };
        if self
            .blame_key
            .as_ref()
            .is_some_and(|previous| previous.matches(&key))
        {
            self.blame_key = Some(key);
            self.sync_editor_blame(cx);
            return;
        }
        self.blame_key = Some(key.clone());
        self.blame_pending.cancel();
        self.blame_pending = Default::default();
        self.blame_epoch += 1;
        let epoch = self.blame_epoch;
        let repository = self.repository_epoch;
        let token = self.blame_pending.clone();
        self.blame_left = Default::default();
        self.blame_right = Default::default();
        self.blame_third = Default::default();
        self.blame_loading = true;
        self.blame_error.clear();
        self.sync_editor_blame(cx);
        let is_merge = key.merge.is_some();
        let task = cx.background_executor().spawn(async move {
            if key.editing {
                Timer::after(std::time::Duration::from_millis(250)).await;
            }
            mygit_gpui::process::scope(token, || {
                let left = mygit_gpui::blame::annotate(
                    &root,
                    &key.comparison.left,
                    &key.file.old_path,
                    &key.file.old_path,
                    &key.left,
                );
                let right = if key.editing {
                    mygit_gpui::blame::annotate_buffer(&root, &key.file.path, &key.right)
                } else {
                    mygit_gpui::blame::annotate(
                        &root,
                        &key.comparison.right,
                        &key.file.path,
                        &key.file.old_path,
                        &key.right,
                    )
                };
                let third = if let Some(merge) = &key.merge {
                    mygit_gpui::blame::annotate(
                        &root,
                        &Revision::Commit(merge.revisions[2].clone()),
                        &merge.paths[2],
                        &merge.paths[2],
                        &merge.documents[2].text,
                    )
                } else {
                    Ok(vec![])
                };
                (left, right, third)
            })
        });
        cx.spawn(async move |this, cx| {
            let (left, right, third) = task.await;
            let _ = this.update(cx, |this, cx| {
                if this.repository_epoch != repository || this.blame_epoch != epoch {
                    return;
                }
                this.blame_loading = false;
                let mut errors = vec![];
                this.blame_left = match left {
                    Ok(lines) => Arc::new(lines),
                    Err(error) => {
                        errors.push(format!(
                            "{} Blame：{error:#}",
                            if is_merge {
                                mygit_gpui::i18n::text("父提交 1")
                            } else {
                                mygit_gpui::i18n::text("左侧")
                            }
                        ));
                        Default::default()
                    }
                };
                this.blame_right = match right {
                    Ok(lines) => Arc::new(lines),
                    Err(error) => {
                        errors.push(format!(
                            "{} Blame：{error:#}",
                            if is_merge {
                                mygit_gpui::i18n::text("合并结果")
                            } else {
                                mygit_gpui::i18n::text("右侧")
                            }
                        ));
                        Default::default()
                    }
                };
                this.blame_third = match third {
                    Ok(lines) => Arc::new(lines),
                    Err(error) => {
                        errors.push(mygit_gpui::localized_format!(
                            "父提交 2 Blame：{error:#}",
                            "Parent 2 Blame: {error:#}"
                        ));
                        Default::default()
                    }
                };
                this.blame_width = crate::views::blame::column_width(
                    this.blame_left
                        .iter()
                        .chain(this.blame_right.iter())
                        .chain(this.blame_third.iter()),
                    cx,
                );
                this.blame_error = errors.join("；");
                this.sync_editor_blame(cx);
                cx.notify();
            });
        })
        .detach();
    }
    fn sync_editor_blame(&self, cx: &mut Context<Self>) {
        let Some(editor) = self.current_editor() else {
            return;
        };
        let enabled = self.show_blame;
        let current = editor.read(cx);
        if current.blame_width != self.blame_width
            || current.show_blame != enabled
            || !Arc::ptr_eq(&current.blame_lines, &self.blame_right)
            || current.blame_owner.is_none()
        {
            let owner = cx.entity().downgrade();
            editor.update(cx, |editor, cx| {
                editor.show_blame = enabled;
                editor.blame_width = self.blame_width;
                editor.blame_lines = self.blame_right.clone();
                editor.blame_owner = Some(owner);
                cx.notify();
            });
        }
    }
    pub fn blame_line(&self, side: Side, line: usize) -> Option<Line> {
        if !self.show_blame {
            return None;
        }
        match side {
            Side::Left => &self.blame_left,
            Side::Right => &self.blame_right,
            Side::Third => &self.blame_third,
        }
        .get(line)
        .cloned()
    }
    pub fn jump_blame(&mut self, sha: String, cx: &mut Context<Self>) {
        if sha.bytes().all(|b| b == b'0') {
            return;
        }
        self.reveal_git_panel(cx);
        self.history_cursor = self
            .history_commits()
            .iter()
            .position(|commit| commit.sha == sha);
        if self.history_cursor.is_none() {
            self.start_history_filter(
                mygit_gpui::history::Filter {
                    scope: sha.clone(),
                    text: sha.clone(),
                    ..Default::default()
                },
                cx,
            );
        }
        self.select_mode(BrowseMode::History(sha), cx);
    }
    pub fn load_blame_detail(&mut self, sha: String, cx: &mut Context<Self>) {
        if self.blame_details.contains_key(&sha) || self.blame_detail_loading.as_ref() == Some(&sha)
        {
            return;
        }
        let Some(repo) = &self.state.repo else {
            return;
        };
        let root = repo.root.clone();
        let repository = self.repository_epoch;
        self.blame_detail_pending.cancel();
        self.blame_detail_pending = Default::default();
        let token = self.blame_detail_pending.clone();
        self.blame_detail_loading = Some(sha.clone());
        self.blame_detail_serial += 1;
        let serial = self.blame_detail_serial;
        let task = cx.background_executor().spawn(async move {
            mygit_gpui::process::scope(token, || git::commit_detail(&root, &sha))
        });
        cx.spawn(async move |this, cx| {
            let result = task.await;
            let _ = this.update(cx, |this, cx| {
                if this.repository_epoch != repository || this.blame_detail_serial != serial {
                    return;
                }
                this.blame_detail_loading = None;
                if let Ok(detail) = result {
                    let bytes: usize = this
                        .blame_details
                        .values()
                        .map(|detail| detail.message.len())
                        .sum();
                    if this.blame_details.len() >= 128
                        || bytes.saturating_add(detail.message.len()) > 16_000_000
                    {
                        this.blame_details.clear();
                    }
                    this.blame_details.insert(detail.sha.clone(), detail);
                }
                cx.notify();
            });
        })
        .detach();
    }
    pub(super) fn reset_blame(&mut self) {
        self.blame_pending.cancel();
        self.blame_pending = Default::default();
        self.blame_epoch += 1;
        self.blame_key = None;
        self.blame_left = Default::default();
        self.blame_right = Default::default();
        self.blame_third = Default::default();
        self.blame_loading = false;
        self.blame_error.clear();
        self.blame_detail_pending.cancel();
        self.blame_detail_pending = Default::default();
        self.blame_detail_serial += 1;
        self.blame_detail_loading = None;
        self.blame_details.clear();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[::core::prelude::v1::test]
    fn blame_visibility_is_scoped_to_repository_file_and_comparison() {
        let scope = Scope {
            root: PathBuf::from("/repo"),
            path: "a.rs".into(),
            old_path: "a.rs".into(),
            comparison: Comparison {
                left: Revision::Index,
                right: Revision::Worktree,
            },
            mode: BrowseMode::Workspace,
        };
        let mut enabled = vec![scope.clone()];
        let mut other_file = scope.clone();
        other_file.path = "b.rs".into();
        assert!(!enabled.contains(&other_file));
        let mut other_comparison = scope.clone();
        other_comparison.comparison.left = Revision::Commit("abc".into());
        assert!(!enabled.contains(&other_comparison));
        let mut other_repo = scope.clone();
        other_repo.root = PathBuf::from("/other");
        assert!(!enabled.contains(&other_repo));
        enabled.push(other_file.clone());
        enabled.retain(|saved| saved != &scope);
        assert!(!enabled.contains(&scope));
        assert!(enabled.contains(&other_file));
    }
}
