use super::*;
use mygit_gpui::blame::Line;
use std::sync::Arc;
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
    pub fn toggle_blame(&mut self, cx: &mut Context<Self>) {
        if self.state.current_file.is_none() {
            return;
        }
        self.show_blame = !self.show_blame;
        if !self.show_blame {
            self.blame_pending.cancel();
            self.blame_epoch += 1;
            self.blame_key = None;
            self.blame_loading = false;
        }
        self.ensure_blame(cx);
        cx.notify();
    }
    pub(super) fn ensure_blame(&mut self, cx: &mut Context<Self>) {
        if !self.show_blame {
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
        let right = if self.edit_mode {
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
            editing: self.edit_mode,
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
                            if is_merge { "父提交 1" } else { "左侧" }
                        ));
                        Default::default()
                    }
                };
                this.blame_right = match right {
                    Ok(lines) => Arc::new(lines),
                    Err(error) => {
                        errors.push(format!(
                            "{} Blame：{error:#}",
                            if is_merge { "合并结果" } else { "右侧" }
                        ));
                        Default::default()
                    }
                };
                this.blame_third = match third {
                    Ok(lines) => Arc::new(lines),
                    Err(error) => {
                        errors.push(format!("父提交 2 Blame：{error:#}"));
                        Default::default()
                    }
                };
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
        let enabled = self.show_blame && self.edit_mode;
        let current = editor.read(cx);
        if current.show_blame != enabled
            || !Arc::ptr_eq(&current.blame_lines, &self.blame_right)
            || current.blame_owner.is_none()
        {
            let owner = cx.entity().downgrade();
            editor.update(cx, |editor, cx| {
                editor.show_blame = enabled;
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
