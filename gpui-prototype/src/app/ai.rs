use super::*;
use mygit_gpui::process::Cancellation;
#[derive(Default)]
pub struct State {
    pub loading: bool,
    pub message: String,
    pending: Cancellation,
    serial: u64,
}
impl State {
    pub fn cancel(&mut self) {
        self.pending.cancel();
        self.serial += 1;
        self.loading = false;
    }
    pub fn reset(&mut self) {
        self.cancel();
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
        if self.write_busy || self.ai.loading {
            return;
        }
        let Some(repo) = &self.state.repo else {
            return;
        };
        let Some(editor) = self.commit_editor.clone() else {
            return;
        };
        let original = editor.read(cx).buffer.text().to_owned();
        let root = repo.root.clone();
        let settings = self.settings.path.clone();
        self.ai.reset();
        self.ai.pending = Default::default();
        self.ai.loading = true;
        self.ai.message = mygit_gpui::i18n::text("正在按当前文件变更生成…（5 分钟超时）").into();
        let serial = self.ai.serial;
        let epoch = self.repository_epoch;
        let token = self.ai.pending.clone();
        let task = cx.background_executor().spawn(async move {
            mygit_gpui::process::scope(token, || {
                let config = mygit_gpui::ai::Config::load(&settings)?;
                mygit_gpui::ai::generate_changes(&root, &config)
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
                        this.ai.message = if editor.read(cx).buffer.marked.is_some()
                            || editor.read(cx).buffer.text() != original
                        {
                            mygit_gpui::i18n::text("生成期间提交信息有修改，请重新生成；当前输入保留").into()
                        } else {
                            match editor.update(cx, |editor, cx| editor.replace_all(&generated.message, cx)) {
                                Ok(()) => String::new(),
                                Err(error) => mygit_gpui::localized_format!(
                                    "无法填入提交信息：{error:#}",
                                    "Unable to fill commit message: {error:#}"
                                ),
                            }
                        };
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

}

impl MyGit {
    pub(crate) fn hide_commit(&mut self) {
        self.show_commit = false;
        if self.ai.loading {
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
