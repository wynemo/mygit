//! Shared Python-compatible settings, edited as a draft until OK is pressed.
use crate::{app::MyGit, views::editor::Editor};
use gpui::{prelude::*, *};
use mygit_gpui::{ai::Config, i18n::Language, settings::Settings};

pub const CODE_STYLES: &[&str] = &[
    "abap",
    "algol",
    "algol_nu",
    "arduino",
    "autumn",
    "bw",
    "borland",
    "coffee",
    "colorful",
    "default",
    "dracula",
    "emacs",
    "friendly_grayscale",
    "friendly",
    "fruity",
    "github-dark",
    "gruvbox-dark",
    "gruvbox-light",
    "igor",
    "inkpot",
    "lightbulb",
    "lilypond",
    "lovelace",
    "manni",
    "material",
    "monokai",
    "murphy",
    "native",
    "nord-darker",
    "nord",
    "one-dark",
    "paraiso-dark",
    "paraiso-light",
    "pastie",
    "perldoc",
    "rainbow_dash",
    "rrt",
    "sas",
    "solarized-dark",
    "solarized-light",
    "staroffice",
    "stata-dark",
    "stata-light",
    "tango",
    "trac",
    "vim",
    "vs",
    "xcode",
    "zenburn",
];

pub struct Draft {
    pub inputs: Vec<Entity<Editor>>,
    pub language: Language,
    pub original_language: Language,
    pub code_style: String,
    pub agent: String,
    original_style: String,
    pub dropdown: Option<usize>,
    pub error: String,
    load_failed: bool,
}
impl Draft {
    pub fn new(this: &MyGit, cx: &mut Context<MyGit>) -> Self {
        let data = match std::fs::read(&this.settings.path) {
            Ok(bytes) => {
                serde_json::from_slice::<serde_json::Value>(&bytes).map_err(|_| "无法读取设置")
            }
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(serde_json::json!({})),
            Err(_) => Err("无法读取设置"),
        };
        let load_failed = data.is_err();
        let data = data.unwrap_or_else(|_| serde_json::json!({}));
        let config = Config::from_json(&data);
        let language = Language::from_saved(
            data["language"]
                .as_str()
                .unwrap_or(this.settings.language.saved()),
        );
        let code_style = data["code_style"].as_str().unwrap_or("friendly").to_owned();
        let family = data["font_family"]
            .as_str()
            .unwrap_or(&this.state.font_family)
            .to_owned();
        let size = data["font_size"]
            .as_f64()
            .unwrap_or(this.state.font_size as f64)
            .round()
            .to_string();
        let inputs = [family, size, config.agent_args, config.prompt]
            .into_iter()
            .enumerate()
            .map(|(i, text)| {
                cx.new(|cx| {
                    let mut editor = Editor::new(
                        mygit_gpui::editor::Buffer::new(&text),
                        "Helvetica".into(),
                        13.,
                        cx,
                    );
                    editor.compact = i != 3;
                    editor.form_input = true;
                    editor
                })
            })
            .collect();
        Self {
            inputs,
            language,
            original_language: language,
            original_style: code_style.clone(),
            code_style,
            agent: config.agent,
            dropdown: None,
            error: if load_failed {
                mygit_gpui::i18n::text("无法读取设置").into()
            } else {
                String::new()
            },
            load_failed,
        }
    }
    pub fn saved_settings(&self, this: &MyGit, cx: &App) -> anyhow::Result<Settings> {
        anyhow::ensure!(!self.load_failed, mygit_gpui::i18n::text("无法读取设置"));
        anyhow::ensure!(
            !self
                .inputs
                .iter()
                .any(|input| input.read(cx).buffer.marked.is_some()),
            mygit_gpui::i18n::text("请先完成输入法组合，再保存配置")
        );
        let text = |i: usize| self.inputs[i].read(cx).buffer.text().to_owned();
        let family = text(0).trim().to_owned();
        let size = text(1)
            .trim()
            .parse::<u32>()
            .map_err(|_| anyhow::anyhow!(mygit_gpui::i18n::text("字号必须为整数")))?
            as f32;
        let size = mygit_gpui::settings::validate_font(&family, Some(size))?;
        let mut settings = this.settings.clone();
        settings.font_family = family;
        settings.font_size = size;
        settings.language = self.language;
        settings.code_style_update = Some(self.code_style.clone());
        if self.code_style != self.original_style {
            settings.code_theme = match self.code_style.as_str() {
                "solarized-dark" => "Solarized (dark)",
                "monokai" | "dracula" | "gruvbox-dark" => "base16-eighties.dark",
                "native" | "vim" | "github-dark" | "nord" | "one-dark" => "base16-ocean.dark",
                _ => "InspiredGitHub",
            }
            .into();
        }
        settings.ai_update = Some(Config {
            agent: self.agent.clone(),
            agent_args: text(2),
            prompt: text(3),
        });
        settings.ai_update.as_ref().unwrap().validate()?;
        Ok(settings)
    }
}

fn row(label: &'static str, content: impl IntoElement) -> Div {
    div()
        .flex()
        .items_center()
        .gap(px(10.))
        .flex_shrink_0()
        .child(
            div()
                .w(px(70.))
                .flex_shrink_0()
                .flex()
                .items_center()
                .gap_1()
                .when(label == "语言：", |s| {
                    s.child(super::icons::icon("icons/globe.svg"))
                })
                .child(mygit_gpui::i18n::text(label)),
        )
        .child(div().min_w_0().flex_1().child(content))
}
fn dropdown(this: &MyGit, index: usize, cx: &mut Context<MyGit>) -> impl IntoElement {
    let form = this.settings_form.as_ref().unwrap();
    let value = match index {
        0 => form.language.saved().to_owned(),
        1 => form.code_style.clone(),
        _ => mygit_gpui::ai::AGENTS
            .iter()
            .find(|(name, _)| *name == form.agent)
            .map(|(_, label)| *label)
            .unwrap_or(&form.agent)
            .to_owned(),
    };
    let choices = match index {
        0 => vec!["中文", "English"],
        1 => CODE_STYLES.to_vec(),
        _ => mygit_gpui::ai::AGENTS
            .iter()
            .map(|(_, label)| *label)
            .collect(),
    };
    div()
        .relative()
        .w_full()
        .child(
            div()
                .id(("settings-select", index))
                .h(px(24.))
                .px_2()
                .w_full()
                .rounded(px(4.))
                .border_1()
                .border_color(rgb(crate::views::theme::BORDER))
                .bg(rgb(crate::views::theme::SURFACE))
                .flex()
                .items_center()
                .justify_between()
                .cursor_pointer()
                .child(value)
                .child("▾")
                .on_click(cx.listener(move |this, _, _, cx| {
                    if let Some(form) = &mut this.settings_form {
                        form.dropdown = if form.dropdown == Some(index) {
                            None
                        } else {
                            Some(index)
                        };
                    }
                    cx.notify();
                })),
        )
        .when(form.dropdown == Some(index), |s| {
            s.child(
                deferred(
                    div()
                        .id(("settings-options", index))
                        .absolute()
                        .top(px(25.))
                        .w_full()
                        .max_h(px(190.))
                        .overflow_y_scroll()
                        .occlude()
                        .border_1()
                        .border_color(rgb(crate::views::theme::BORDER))
                        .bg(rgb(crate::views::theme::SURFACE))
                        .shadow_md()
                        .children(choices.into_iter().enumerate().map(|(i, value)| {
                            div()
                                .id(("settings-option", i))
                                .h(px(24.))
                                .px_2()
                                .cursor_pointer()
                                .hover(|s| {
                                    s.bg(rgb(crate::views::theme::ACCENT))
                                        .text_color(rgb(crate::views::theme::SURFACE))
                                })
                                .child(value)
                                .on_click(cx.listener(move |this, _, _, cx| {
                                    if let Some(form) = &mut this.settings_form {
                                        if index == 0 {
                                            form.language = Language::from_saved(value);
                                        } else if index == 1 {
                                            form.code_style = value.into();
                                        } else {
                                            form.agent = mygit_gpui::ai::AGENTS[i].0.into();
                                        }
                                        form.dropdown = None;
                                    }
                                    cx.notify();
                                }))
                        })),
                )
                .with_priority(1),
            )
        })
}

pub fn pane(this: &MyGit, window: &Window, cx: &mut Context<MyGit>) -> impl IntoElement {
    let Some(form) = &this.settings_form else {
        return div();
    };
    let height = (f32::from(window.viewport_size().height) - 40.).clamp(180., 530.);
    let width = (f32::from(window.viewport_size().width) - 32.).clamp(240., 360.);
    div()
        .absolute()
        .inset_0()
        .occlude()
        .flex()
        .items_center()
        .justify_center()
        .bg(rgba(0x00000010))
        .on_action(
            cx.listener(|this, _: &super::editor::InsertTab, window, cx| {
                this.cycle_focus(false, window, cx)
            }),
        )
        .child(
            div()
                .w(px(width))
                .max_h(px(height))
                .flex()
                .flex_col()
                .overflow_hidden()
                .rounded(px(10.))
                .border_1()
                .border_color(rgb(0xc6c6c6))
                .bg(rgb(crate::views::theme::CHROME))
                .shadow_lg()
                .child(
                    div()
                        .h(px(30.))
                        .flex_shrink_0()
                        .border_b_1()
                        .border_color(rgb(0xc6c6c6))
                        .flex()
                        .items_center()
                        .justify_center()
                        .font_weight(FontWeight::SEMIBOLD)
                        .child(mygit_gpui::i18n::text("设置")),
                )
                .child(
                    div()
                        .id("settings-form")
                        .min_h_0()
                        .overflow_y_scroll()
                        .p_4()
                        .flex()
                        .flex_col()
                        .gap(px(10.))
                        .child(row("语言：", dropdown(this, 0, cx)))
                        .when(form.language != form.original_language, |s| {
                            s.child(
                                div()
                                    .text_xs()
                                    .text_color(rgb(crate::views::theme::MUTED))
                                    .child(mygit_gpui::i18n::text("保存后重启生效")),
                            )
                        })
                        .child(row("字体：", form.inputs[0].clone()))
                        .child(row("字体大小：", form.inputs[1].clone()))
                        .child(row("代码风格：", dropdown(this, 1, cx)))
                        .child(row("Agent：", dropdown(this, 2, cx)))
                        .child(row("额外参数：", form.inputs[2].clone()))
                        .child(
                            div()
                                .text_xs()
                                .text_color(rgb(crate::views::theme::MUTED))
                                .child(mygit_gpui::i18n::text("例如：--model \"模型名称\"")),
                        )
                        .child(row(
                            "提示词：",
                            div()
                                .h(px(180.))
                                .flex()
                                .flex_col()
                                .border_1()
                                .border_color(rgb(crate::views::theme::BORDER))
                                .child(form.inputs[3].clone()),
                        ))
                        .when(!form.error.is_empty(), |s| {
                            s.child(div().text_color(rgb(0xa52a2a)).child(form.error.clone()))
                        }),
                )
                .child(
                    div()
                        .px_4()
                        .pb_4()
                        .flex_shrink_0()
                        .flex()
                        .justify_end()
                        .gap_3()
                        .child(
                            super::button("settings-cancel", "Cancel", true)
                                .w(px(68.))
                                .justify_center()
                                .on_click(cx.listener(|this, _, _, cx| this.cancel_settings(cx))),
                        )
                        .child(
                            super::button("settings-ok", "OK", true)
                                .w(px(68.))
                                .justify_center()
                                .on_click(cx.listener(|this, _, _, cx| this.accept_settings(cx))),
                        ),
                ),
        )
}
