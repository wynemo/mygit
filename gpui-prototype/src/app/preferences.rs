use super::*;

impl MyGit {
    pub fn showing_tree(&self) -> bool {
        self.settings.files_visible
    }
    pub fn reveal_git_panel(&mut self, cx: &mut Context<Self>) {
        if !self.settings.git_panel_visible {
            self.settings.git_panel_visible = true;
            self.save_settings();
            cx.notify();
        }
    }
    pub fn toggle_git_panel(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        if self.confirmation.is_some() {
            return;
        }
        self.settings.git_panel_visible = !self.settings.git_panel_visible;
        self.line_layouts.clear();
        self.diff_bounds = None;
        self.dragging = false;
        self.save_settings();
        // Move focus out of hidden Git inputs, without destroying their entities.
        if let Some(editor) = self.current_editor() {
            window.focus(&editor.read(cx).focus);
        } else {
            window.focus(&self.focus);
        }
        cx.notify();
    }
    pub fn toggle_tree(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        self.toggle_files_panel(cx);
        window.focus(if self.settings.files_visible {
            &self.tree_focus
        } else {
            &self.focus
        });
        cx.notify();
    }

    pub fn select_language(
        &mut self,
        language: mygit_gpui::i18n::Language,
        cx: &mut Context<Self>,
    ) {
        self.settings.language = language;
        self.state.message = mygit_gpui::i18n::text("语言设置已保存，请重启应用生效").into();
        self.save_settings();
        cx.notify();
    }
    pub fn select_code_palette(&mut self, index: usize, cx: &mut Context<Self>) {
        let Some(name) = mygit_gpui::syntax::PALETTES.get(index) else {
            return;
        };
        self.settings.code_theme = (*name).into();
        cx.set_global(crate::views::editor::CodePalette(index));
        self.line_layouts.clear();
        self.update_editor_fonts(cx);
        self.save_settings();
        cx.notify();
    }
    pub fn toggle_settings(&mut self, cx: &mut Context<Self>) {
        self.show_settings = !self.show_settings;
        self.restore_main_focus = true;
        if self.show_settings {
            self.hide_quick_open();
            self.hide_project_search();
            self.font_inputs = [
                self.state.font_family.clone(),
                self.state.font_size.to_string(),
            ]
            .into_iter()
            .map(|text| {
                cx.new(|cx| {
                    let mut editor = Editor::new(
                        mygit_gpui::editor::Buffer::new(&text),
                        self.state.font_family.clone(),
                        self.state.font_size,
                        cx,
                    );
                    editor.compact = true;
                    editor.show_toolbar = false;
                    editor
                })
            })
            .collect();
        }
        cx.notify();
    }
    pub fn apply_font_settings(&mut self, cx: &mut Context<Self>) {
        if self.font_inputs.len() != 2 {
            return;
        }
        if self
            .font_inputs
            .iter()
            .any(|e| e.read(cx).buffer.marked.is_some())
        {
            self.state.message = mygit_gpui::i18n::text("请先完成字体设置输入").into();
            cx.notify();
            return;
        }
        let family = self.font_inputs[0].read(cx).buffer.text().trim().to_owned();
        let size = self.font_inputs[1]
            .read(cx)
            .buffer
            .text()
            .trim()
            .parse::<f32>();
        match mygit_gpui::settings::validate_font(&family, size.ok()) {
            Ok(size) => {
                self.state.font_family = family;
                self.state.font_size = size;
                self.line_layouts.clear();
                self.update_editor_fonts(cx);
                self.state.message = mygit_gpui::i18n::text("字体设置已应用").into();
                self.save_settings();
            }
            Err(error) => self.state.message = error.to_string(),
        }
        cx.notify();
    }
    pub fn update_editor_fonts(&mut self, cx: &mut Context<Self>) {
        let editors: Vec<_> = self
            .editors
            .values()
            .cloned()
            .chain(self.commit_editor.iter().cloned())
            .chain(self.compare_left.iter().cloned())
            .chain(self.compare_right.iter().cloned())
            .chain(self.branch_name.iter().cloned())
            .chain(self.branch_base.iter().cloned())
            .chain(self.remote_name.iter().cloned())
            .chain(self.history_inputs.iter().cloned())
            .chain(self.search.inputs.iter().cloned())
            .chain(self.quick.input.iter().cloned())
            .chain(self.ai.config_inputs.iter().cloned())
            .chain(self.ai.candidate.iter().cloned())
            .chain(self.font_inputs.iter().cloned())
            .collect();
        for editor in editors {
            editor.update(cx, |editor, cx| {
                editor.font_family = self.state.font_family.clone();
                editor.font_size = self.state.font_size;
                cx.notify();
            });
        }
    }
    pub fn clear_recent_repositories(&mut self, cx: &mut Context<Self>) {
        self.settings.clear_recent();
        self.save_settings();
        cx.notify();
    }
    pub fn toggle_files_panel(&mut self, cx: &mut Context<Self>) {
        self.tree_menu = None;
        self.settings.files_visible = !self.settings.files_visible;
        self.save_settings();
        cx.notify();
    }
}
