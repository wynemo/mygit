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

    pub fn open_about(&mut self, cx: &mut Context<Self>) {
        if self.confirmation.is_some() {
            return;
        }
        self.cancel_settings(cx);
        self.hide_quick_open();
        self.show_notifications = false;
        self.show_recent = false;
        self.show_branch_dropdown = false;
        self.show_about = true;
        self.restore_main_focus = true;
        cx.notify();
    }
    pub fn close_about(&mut self, cx: &mut Context<Self>) {
        self.show_about = false;
        self.restore_main_focus = true;
        cx.notify();
    }
    pub fn toggle_settings(&mut self, cx: &mut Context<Self>) {
        if self.show_settings {
            self.cancel_settings(cx);
            return;
        }
        self.show_about = false;
        self.hide_quick_open();
        self.hide_project_search();
        self.settings_form = Some(crate::views::settings_dialog::Draft::new(self, cx));
        self.show_settings = true;
        self.restore_main_focus = true;
        cx.notify();
    }
    pub fn cancel_settings(&mut self, cx: &mut Context<Self>) {
        self.show_settings = false;
        self.settings_form = None;
        self.restore_main_focus = true;
        cx.notify();
    }
    pub fn accept_settings(&mut self, cx: &mut Context<Self>) {
        let Some(form) = &self.settings_form else {
            return;
        };
        let result = form.saved_settings(self, cx).and_then(|settings| {
            settings.save()?;
            Ok(settings)
        });
        match result {
            Ok(mut settings) => {
                settings.ai_update = None;
                settings.code_style_update = None;
                self.state.font_family = settings.font_family.clone();
                self.state.font_size = settings.font_size;
                let palette = mygit_gpui::syntax::palette_index(&settings.code_theme);
                self.settings = settings;
                cx.set_global(crate::views::editor::CodePalette(palette));
                self.line_layouts.clear();
                self.update_editor_fonts(cx);
                self.ai.reset();
                self.cancel_settings(cx);
            }
            Err(error) => {
                if let Some(form) = &mut self.settings_form {
                    form.error = error.to_string();
                }
                cx.notify();
            }
        }
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
            .collect();
        for editor in editors {
            editor.update(cx, |editor, cx| {
                editor.font_family = self.state.font_family.clone();
                editor.font_size = self.state.font_size;
                cx.notify();
            });
        }
    }
    pub fn toggle_files_panel(&mut self, cx: &mut Context<Self>) {
        self.tree_menu = None;
        self.settings.files_visible = !self.settings.files_visible;
        self.save_settings();
        cx.notify();
    }
}
