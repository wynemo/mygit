use super::*;
use mygit_gpui::{ai::Fingerprint, process::Cancellation};
#[derive(Default)]
pub struct State {
    pub loading: bool,
    pub applying: bool,
    pub message: String,
    pub candidate: Option<Entity<Editor>>,
    pub config_shown: bool,
    pub config_inputs: Vec<Entity<Editor>>,
    pub config_message: String,
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
        self.ai.message = "AI 任务已取消，手动草稿保留".into();
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
        self.ai.message = "正在按当前暂存 Diff 生成…（15 秒超时）".into();
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
                            Editor::new(
                                mygit_gpui::editor::Buffer::new(&generated.message),
                                font,
                                size,
                                cx,
                            )
                        }));
                        this.ai.fingerprint = Some(generated.fingerprint);
                        this.ai.message = "生成草稿可编辑；点击应用将替换手动草稿，可撤销".into();
                    }
                    Err(error) => {
                        this.ai.message = format!("AI 生成失败：{error:#}；可继续手动提交")
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
            self.ai.message = "请先完成输入法组合，再应用草稿".into();
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
                        "暂存区或 HEAD 已改变，请重新生成；当前草稿保留".into()
                    }
                    Ok(_)
                        if editor.read(cx).buffer.marked.is_some()
                            || candidate.read(cx).buffer.marked.is_some()
                            || editor.read(cx).buffer.text() != original
                            || candidate.read(cx).buffer.text() != message =>
                    {
                        "校验期间草稿有修改，请再次点击应用".into()
                    }
                    Ok(_) => match editor.update(cx, |editor, cx| editor.replace_all(&message, cx))
                    {
                        Ok(()) => "已应用 AI 草稿，可继续编辑或撤销；尚未提交".into(),
                        Err(error) => format!("无法应用草稿：{error:#}"),
                    },
                    Err(error) => format!("无法校验暂存区：{error:#}"),
                };
                cx.notify();
            });
        })
        .detach();
        cx.notify();
    }
}

impl MyGit {
    pub fn toggle_ai_settings(&mut self, cx: &mut Context<Self>) {
        self.ai.config_shown = !self.ai.config_shown;
        if self.ai.config_shown && self.ai.config_inputs.is_empty() {
            match mygit_gpui::ai::Config::load_stored(&self.settings.path) {
                Ok(config) => {
                    for (i, text) in [
                        config.api_url,
                        config.api_secret,
                        config.model_name,
                        config.prompt,
                    ]
                    .iter()
                    .enumerate()
                    {
                        let font = self.state.font_family.clone();
                        let size = self.state.font_size;
                        self.ai.config_inputs.push(cx.new(|cx| {
                            let mut editor =
                                Editor::new(mygit_gpui::editor::Buffer::new(text), font, size, cx);
                            editor.compact = i != 3;
                            editor.sensitive = i == 1;
                            editor
                        }));
                    }
                }
                Err(error) => self.ai.config_message = format!("无法加载 AI 配置：{error:#}"),
            }
        }
        cx.notify();
    }
    pub fn save_ai_settings(&mut self, cx: &mut Context<Self>) {
        if self.ai.config_inputs.len() != 4 {
            return;
        }
        if self
            .ai
            .config_inputs
            .iter()
            .any(|e| e.read(cx).buffer.marked.is_some())
        {
            self.ai.config_message = "请先完成输入法组合，再保存配置".into();
            cx.notify();
            return;
        }
        let text = |i: usize| self.ai.config_inputs[i].read(cx).buffer.text().to_owned();
        let config = mygit_gpui::ai::Config {
            api_url: text(0),
            api_secret: text(1),
            model_name: text(2),
            prompt: text(3),
        };
        if let Err(error) = config.validate() {
            self.ai.config_message = format!("AI 配置无效：{error:#}");
            cx.notify();
            return;
        }
        self.ai.cancel();
        self.ai.candidate = None;
        self.ai.fingerprint = None;
        self.settings.ai_update = Some(config);
        let result = self.settings.save();
        self.settings.ai_update = None;
        self.ai.config_message = match result {
            Ok(()) => "AI 配置已保存；尚未发送请求".into(),
            Err(_) => "无法保存 AI 配置，请检查文件权限；输入保留".into(),
        };
        cx.notify();
    }
}

impl MyGit {
    pub(crate) fn hide_commit(&mut self) {
        self.show_commit = false;
        if self.ai.loading || self.ai.applying {
            self.ai.cancel();
            self.ai.message = "AI 任务已取消，草稿保留".into();
        }
    }
    pub fn open_ai_settings(&mut self, cx: &mut Context<Self>) {
        self.hide_commit();
        self.hide_quick_open();
        self.hide_project_search();
        self.show_settings = true;
        if !self.ai.config_shown {
            self.toggle_ai_settings(cx);
        }
        cx.notify();
    }
}
