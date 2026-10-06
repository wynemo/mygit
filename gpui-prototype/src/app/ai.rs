use super::*;
use mygit_gpui::{ai::Fingerprint, process::Cancellation};
#[derive(Default)]
pub struct State {
    pub loading: bool,
    pub applying: bool,
    pub message: String,
    pub candidate: Option<Entity<Editor>>,
    fingerprint: Option<Fingerprint>,
    pending: Cancellation,
    serial: u64,
}
impl State {
    pub fn cancel(&mut self) {
        self.pending.cancel();
        self.serial += 1;
        self.loading = false;
        self.applying = false;
    }
    pub fn reset(&mut self) {
        self.cancel();
        self.candidate = None;
        self.fingerprint = None;
        self.message.clear();
    }
}
impl MyGit {
    pub fn cancel_ai(&mut self, cx: &mut Context<Self>) {
        self.ai.cancel();
        self.ai.message = mygit_gpui::i18n::text("AI 任务已取消，手动草稿保留").into();
        cx.notify();
    }
    pub fn generate_ai(&mut self, cx: &mut Context<Self>) {
        if self.write_busy || self.ai.loading || self.ai.applying {
            return;
        }
        let Some(repo) = &self.state.repo else {
            return;
        };
        let root = repo.root.clone();
        let settings = self.settings.path.clone();
        self.ai.reset();
        self.ai.pending = Default::default();
        self.ai.loading = true;
        self.ai.message = mygit_gpui::i18n::text("正在按当前暂存 Diff 生成…（15 秒超时）").into();
        let serial = self.ai.serial;
        let epoch = self.repository_epoch;
        let token = self.ai.pending.clone();
        let task = cx.background_executor().spawn(async move {
            mygit_gpui::process::scope(token, || {
                let config = mygit_gpui::ai::Config::load(&settings)?;
                mygit_gpui::ai::generate_staged(&root, &config)
            })
        });
        cx.spawn(async move |this, cx| {
            let result = task.await;
            let _ = this.update(cx, |this, cx| {
                if this.repository_epoch != epoch || this.ai.serial != serial {
                    return;
                }
                this.ai.loading = false;
                match result {
                    Ok(generated) => {
                        let font = this.state.font_family.clone();
                        let size = this.state.font_size;
                        this.ai.candidate = Some(cx.new(|cx| {
                            let mut editor = Editor::new(
                                mygit_gpui::editor::Buffer::new(&generated.message),
                                font,
                                size,
                                cx,
                            );
                            editor.show_toolbar = false;
                            editor
                        }));
                        this.ai.fingerprint = Some(generated.fingerprint);
                        this.ai.message = mygit_gpui::i18n::text(
                            "生成草稿可编辑；点击应用将替换手动草稿，可撤销",
                        )
                        .into();
                    }
                    Err(error) => {
                        this.ai.message = mygit_gpui::localized_format!(
                            "AI 生成失败：{error:#}；可继续手动提交",
                            "AI generation failed: {error:#}; you can still commit manually"
                        );
                        this.notify_result(
                            mygit_gpui::notifications::Kind::Error,
                            this.ai.message.clone(),
                            cx,
                        );
                    }
                }
                cx.notify();
            });
        })
        .detach();
        cx.notify();
    }
    pub fn apply_ai(&mut self, cx: &mut Context<Self>) {
        if self.write_busy || self.ai.loading || self.ai.applying {
            return;
        }
        let (Some(repo), Some(candidate), Some(editor), Some(expected)) = (
            &self.state.repo,
            &self.ai.candidate,
            &self.commit_editor,
            &self.ai.fingerprint,
        ) else {
            return;
        };
        if candidate.read(cx).buffer.marked.is_some() || editor.read(cx).buffer.marked.is_some() {
            self.ai.message = mygit_gpui::i18n::text("请先完成输入法组合，再应用草稿").into();
            cx.notify();
            return;
        }
        let root = repo.root.clone();
        let expected = expected.clone();
        let candidate = candidate.clone();
        let editor = editor.clone();
        let message = candidate.read(cx).buffer.text().to_owned();
        let original = editor.read(cx).buffer.text().to_owned();
        self.ai.cancel();
        self.ai.pending = Default::default();
        self.ai.applying = true;
        let serial = self.ai.serial;
        let epoch = self.repository_epoch;
        let token = self.ai.pending.clone();
        let task = cx.background_executor().spawn(async move {
            mygit_gpui::process::scope(token, || mygit_gpui::ai::fingerprint(&root))
        });
        cx.spawn(async move |this, cx| {
            let result = task.await;
            let _ = this.update(cx, |this, cx| {
                if this.repository_epoch != epoch || this.ai.serial != serial {
                    return;
                }
                this.ai.applying = false;
                this.ai.message = match result {
                    Ok(current) if current != expected => {
                        mygit_gpui::i18n::text("暂存区或 HEAD 已改变，请重新生成；当前草稿保留")
                            .into()
                    }
                    Ok(_)
                        if editor.read(cx).buffer.marked.is_some()
                            || candidate.read(cx).buffer.marked.is_some()
                            || editor.read(cx).buffer.text() != original
                            || candidate.read(cx).buffer.text() != message =>
                    {
                        mygit_gpui::i18n::text("校验期间草稿有修改，请再次点击应用").into()
                    }
                    Ok(_) => match editor.update(cx, |editor, cx| editor.replace_all(&message, cx))
                    {
                        Ok(()) => {
                            mygit_gpui::i18n::text("已应用 AI 草稿，可继续编辑或撤销；尚未提交")
                                .into()
                        }
                        Err(error) => {
                            mygit_gpui::localized_format!(
                                "无法应用草稿：{error:#}",
                                "Unable to apply draft: {error:#}"
                            )
                        }
                    },
                    Err(error) => {
                        mygit_gpui::localized_format!(
                            "无法校验暂存区：{error:#}",
                            "Unable to validate index: {error:#}"
                        )
                    }
                };
                cx.notify();
            });
        })
        .detach();
        cx.notify();
    }
}

impl MyGit {
    pub(crate) fn hide_commit(&mut self) {
        self.show_commit = false;
        if self.ai.loading || self.ai.applying {
            self.ai.cancel();
            self.ai.message = mygit_gpui::i18n::text("AI 任务已取消，草稿保留").into();
        }
    }
    pub fn open_ai_settings(&mut self, cx: &mut Context<Self>) {
        self.hide_commit();
        self.hide_quick_open();
        self.hide_project_search();
        if !self.show_settings {
            self.toggle_settings(cx);
        }
        cx.notify();
    }
}
