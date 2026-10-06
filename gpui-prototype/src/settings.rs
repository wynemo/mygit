//! Compatible settings with fresh merge-on-save and atomic replacement.
use anyhow::{Context, Result};
use serde_json::{Value, json};
use std::{
    fs,
    io::Write,
    path::{Path, PathBuf},
};
pub fn validate_font(family: &str, size: Option<f32>) -> Result<f32> {
    anyhow::ensure!(
        !family.is_empty() && family.len() < 256 && !family.chars().any(char::is_control),
        crate::localized_format!(
            "字体名称必须为 1–255 字节且不含控制字符",
            "Font family must be 1–255 bytes without control characters"
        )
    );
    let size = size.context(crate::i18n::text("字号必须为数字"))?;
    anyhow::ensure!(
        size.is_finite() && (10.0..=22.0).contains(&size),
        crate::localized_format!("字号必须为 10–22", "Font size must be between 10 and 22")
    );
    Ok(size)
}
#[derive(Clone)]
pub struct Settings {
    pub path: PathBuf,
    pub font_family: String,
    pub font_size: f32,
    pub history_width: f32,
    pub workspace_fraction: f32,
    pub files_width: f32,
    pub files_visible: bool,
    pub git_panel_visible: bool,
    pub code_theme: String,
    pub language: crate::i18n::Language,
    pub recent: Vec<PathBuf>,
    pub last: Option<PathBuf>,
    pub warning: Option<String>,
    pub draft: Option<(String, String)>,
    pub ai_update: Option<crate::ai::Config>,
}
impl Settings {
    pub fn default_path() -> PathBuf {
        if let Some(dir) = std::env::var_os("MYGIT_CONFIG_DIR") {
            return PathBuf::from(dir).join("settings.json");
        }
        PathBuf::from(
            std::env::var_os("HOME")
                .or_else(|| std::env::var_os("USERPROFILE"))
                .unwrap_or_default(),
        )
        .join(".git_manager/settings.json")
    }
    pub fn load(path: PathBuf) -> Self {
        let (data, warning) = match fs::read(&path) {
            Ok(bytes) => match serde_json::from_slice::<Value>(&bytes) {
                Ok(value) if value.is_object() => (value, None),
                _ => (
                    json!({}),
                    Some(
                        crate::i18n::text("配置损坏，已使用默认设置；保存时保留原文件备份").into(),
                    ),
                ),
            },
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => (json!({}), None),
            Err(_) => (
                json!({}),
                Some(crate::i18n::text("无法读取配置，已使用默认设置").into()),
            ),
        };
        let number = |key: &str, default: f32, min: f32, max: f32| {
            data.pointer(key)
                .and_then(Value::as_f64)
                .map(|v| v as f32)
                .filter(|v| v.is_finite())
                .unwrap_or(default)
                .clamp(min, max)
        };
        Self {
            path,
            font_family: data["font_family"]
                .as_str()
                .filter(|s| !s.is_empty() && s.len() < 256)
                .unwrap_or("Menlo")
                .into(),
            font_size: number("/font_size", 12., 10., 22.),
            workspace_fraction: number("/gpui/workspace_fraction", 0.625, 0.25, 0.85),
            history_width: number("/gpui/history_width", 260., 160., 600.),
            files_width: if data
                .pointer("/gpui/layout_version")
                .and_then(Value::as_u64)
                .unwrap_or(0)
                < 2
                && data
                    .pointer("/gpui/files_width")
                    .and_then(Value::as_f64)
                    .is_none_or(|w| w == 220.)
            {
                number("/panel_widths/file_tree", 250., 120., 600.)
            } else {
                number("/gpui/files_width", 250., 120., 600.)
            },
            language: crate::i18n::Language::from_saved(
                data["language"].as_str().unwrap_or("中文"),
            ),
            code_theme: crate::syntax::PALETTES[crate::syntax::palette_index(
                if data
                    .pointer("/gpui/layout_version")
                    .and_then(Value::as_u64)
                    .unwrap_or(0)
                    >= 2
                {
                    data.pointer("/gpui/code_theme")
                        .and_then(Value::as_str)
                        .unwrap_or("")
                } else {
                    match data.pointer("/gpui/code_theme").and_then(Value::as_str) {
                        Some("base16-ocean.dark") | None => "InspiredGitHub",
                        Some(name) => name,
                    }
                },
            )]
            .into(),
            files_visible: data
                .pointer("/gpui/files_visible")
                .and_then(Value::as_bool)
                .or_else(|| data["left_panel_visible"].as_bool())
                .unwrap_or(true),
            git_panel_visible: data
                .pointer("/gpui/git_panel_visible")
                .and_then(Value::as_bool)
                .or_else(|| data["bottom_widget_visible"].as_bool())
                .unwrap_or(true),
            recent: data["recent_folders"]
                .as_array()
                .map(|a| {
                    a.iter()
                        .filter_map(Value::as_str)
                        .take(10)
                        .map(PathBuf::from)
                        .collect()
                })
                .unwrap_or_default(),
            last: data["last_folder"].as_str().map(PathBuf::from),
            warning,
            draft: None,
            ai_update: None,
        }
    }
    pub fn draft_for(&self, root: &Path) -> String {
        let Ok(bytes) = fs::read(&self.path) else {
            return String::new();
        };
        let Ok(data) = serde_json::from_slice::<Value>(&bytes) else {
            return String::new();
        };
        data["gpui"]["commit_drafts"][root.to_string_lossy().as_ref()]
            .as_str()
            .unwrap_or("")
            .into()
    }
    pub fn opened(&mut self, path: &Path) {
        self.last = Some(path.to_owned());
        self.recent.retain(|p| p != path);
        self.recent.insert(0, path.to_owned());
        self.recent.truncate(10);
    }
    pub fn clear_recent(&mut self) {
        self.recent.clear();
        self.last = None;
    }
    pub fn save(&self) -> Result<()> {
        let parent = self
            .path
            .parent()
            .context(crate::i18n::text("配置路径缺少目录"))?;
        fs::create_dir_all(parent)?;
        let mut data = match fs::read(&self.path) {
            Ok(bytes) => match serde_json::from_slice::<Value>(&bytes) {
                Ok(value) if value.is_object() => value,
                _ => {
                    let backup = self.path.with_extension(format!(
                        "corrupt-{}.json",
                        std::time::SystemTime::now()
                            .duration_since(std::time::UNIX_EPOCH)?
                            .as_nanos()
                    ));
                    fs::copy(&self.path, backup)
                        .context(crate::i18n::text("无法备份损坏配置，未覆盖原文件"))?;
                    json!({})
                }
            },
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => json!({}),
            Err(e) => return Err(e.into()),
        };
        if let Some(config) = &self.ai_update {
            data["api_url"] = json!(config.api_url);
            data["api_secret"] = json!(config.api_secret);
            data["model_name"] = json!(config.model_name);
            data["prompt"] = json!(config.prompt);
        }
        data["language"] = json!(self.language.saved());
        data["font_family"] = json!(self.font_family);
        // Python passes this shared setting to QFont's integer point-size argument.
        data["font_size"] = json!(self.font_size.round() as u32);
        data["recent_folders"] = json!(self.recent);
        data["last_folder"] = json!(self.last);
        if !data["gpui"].is_object() {
            data["gpui"] = json!({});
        }
        data["gpui"]["history_width"] = json!(self.history_width);
        data["gpui"]["files_width"] = json!(self.files_width);
        data["gpui"]["code_theme"] = json!(self.code_theme);
        data["gpui"]["files_visible"] = json!(self.files_visible);
        data["gpui"]["layout_version"] = json!(2);
        data["gpui"]["workspace_fraction"] = json!(self.workspace_fraction);
        data["gpui"]["git_panel_visible"] = json!(self.git_panel_visible);
        if let Some((root, text)) = &self.draft {
            if !data["gpui"]["commit_drafts"].is_object() {
                data["gpui"]["commit_drafts"] = json!({});
            }
            data["gpui"]["commit_drafts"][root] = json!(text);
        }
        let temp = parent.join(format!(
            ".settings-{}-{}.tmp",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)?
                .as_nanos()
        ));
        let result = (|| -> Result<()> {
            let mut file = fs::OpenOptions::new()
                .write(true)
                .create_new(true)
                .open(&temp)?;
            #[cfg(unix)]
            {
                use std::os::unix::fs::PermissionsExt;
                file.set_permissions(fs::Permissions::from_mode(0o600))?;
            }
            file.write_all(&serde_json::to_vec_pretty(&data)?)?;
            file.sync_all()?;
            fs::rename(&temp, &self.path)?;
            Ok(())
        })();
        if result.is_err() {
            let _ = fs::remove_file(temp);
        }
        result
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn shared_font_size_is_saved_as_an_integer() {
        let dir = std::env::temp_dir().join(format!("mygit-font-compat-{}", std::process::id()));
        fs::create_dir_all(&dir).unwrap();
        let path = dir.join("settings.json");
        fs::write(&path, r#"{"font_size":13.0,"code_style":"friendly"}"#).unwrap();
        let mut settings = Settings::load(path.clone());
        for (size, expected) in [(13., 13), (16.5, 17), (22., 22)] {
            settings.font_size = size;
            settings.save().unwrap();
            let data: Value = serde_json::from_slice(&fs::read(&path).unwrap()).unwrap();
            assert_eq!(data["font_size"].as_u64(), Some(expected));
            assert_eq!(data["code_style"], "friendly");
        }
        fs::remove_dir_all(dir).unwrap();
    }
    #[test]
    fn git_panel_visibility_restores_legacy_state_and_preserves_other_preferences() {
        let dir = std::env::temp_dir().join(format!("mygit-git-panel-{}", std::process::id()));
        fs::create_dir_all(&dir).unwrap();
        let path = dir.join("settings.json");
        for (data, visible) in [
            (json!({}), true),
            (json!({"bottom_widget_visible": false}), false),
            (json!({"bottom_widget_visible": true}), true),
            (
                json!({"bottom_widget_visible": false, "gpui": {"git_panel_visible": true}}),
                true,
            ),
            (
                json!({"bottom_widget_visible": true, "gpui": {"git_panel_visible": false}}),
                false,
            ),
            (
                json!({"bottom_widget_visible": false, "gpui": {"git_panel_visible": "invalid"}}),
                false,
            ),
        ] {
            fs::write(&path, serde_json::to_vec(&data).unwrap()).unwrap();
            assert_eq!(Settings::load(path.clone()).git_panel_visible, visible);
        }
        fs::write(
            &path,
            serde_json::to_vec(&json!({
                "bottom_widget_visible": false, "left_panel_visible": true,
                "language": "English", "prompt": "KEEP 提示词", "code_style": "friendly",
                "recent_folders": ["/tmp/repo"], "last_folder": "/tmp/repo",
                "gpui": {"history_width": 320, "files_width": 240,
                    "files_visible": false, "code_theme": "Solarized (dark)",
                    "commit_drafts": {"/tmp/repo": "KEEP 草稿"}}
            }))
            .unwrap(),
        )
        .unwrap();
        let mut settings = Settings::load(path.clone());
        assert!(!settings.git_panel_visible);
        for visible in [true, false, true] {
            settings.git_panel_visible = visible;
            settings.save().unwrap();
            let loaded = Settings::load(path.clone());
            assert_eq!(loaded.git_panel_visible, visible);
            assert!(!loaded.files_visible);
            assert_eq!(loaded.history_width, 320.);
            assert_eq!(loaded.files_width, 240.);
            assert_eq!(loaded.code_theme, "Solarized (dark)");
            assert_eq!(loaded.language, crate::i18n::Language::English);
            assert_eq!(loaded.draft_for(Path::new("/tmp/repo")), "KEEP 草稿");
            assert_eq!(loaded.last.as_deref(), Some(Path::new("/tmp/repo")));
            let data: Value = serde_json::from_slice(&fs::read(&path).unwrap()).unwrap();
            assert_eq!(data["bottom_widget_visible"], false);
            assert_eq!(data["left_panel_visible"], true);
            assert_eq!(data["prompt"], "KEEP 提示词");
            assert_eq!(data["code_style"], "friendly");
        }
        fs::remove_dir_all(dir).unwrap();
    }
    #[test]
    fn language_preferences_round_trip_without_changing_drafts_or_prompt() {
        let dir = std::env::temp_dir().join(format!("mygit-language-{}", std::process::id()));
        fs::create_dir_all(&dir).unwrap();
        let path = dir.join("settings.json");
        fs::write(
            &path,
            serde_json::to_vec(&json!({
                "language": "English", "prompt": "打开仓库",
                "code_style": "friendly", "custom": {"keep": true},
                "gpui": {"commit_drafts": {"/tmp/中文": "打开仓库"}}
            }))
            .unwrap(),
        )
        .unwrap();
        let mut settings = Settings::load(path.clone());
        assert_eq!(settings.language, crate::i18n::Language::English);
        settings.language = crate::i18n::Language::Chinese;
        settings.save().unwrap();
        let data: Value = serde_json::from_slice(&fs::read(&path).unwrap()).unwrap();
        assert_eq!(data["language"], "中文");
        assert_eq!(data["prompt"], "打开仓库");
        assert_eq!(data["custom"]["keep"], true);
        assert_eq!(data["code_style"], "friendly");
        assert_eq!(
            Settings::load(path.clone()).draft_for(Path::new("/tmp/中文")),
            "打开仓库"
        );
        fs::write(&path, br#"{"language":"unknown"}"#).unwrap();
        assert_eq!(
            Settings::load(path).language,
            crate::i18n::Language::Chinese
        );
        fs::remove_dir_all(dir).unwrap();
    }
    #[test]
    fn code_palette_round_trips_and_preserves_legacy_style() {
        let dir = std::env::temp_dir().join(format!("mygit-palette-{}", std::process::id()));
        fs::create_dir_all(&dir).unwrap();
        let path = dir.join("settings.json");
        fs::write(
            &path,
            br#"{"code_style":"friendly","gpui":{"code_theme":"unknown"}}"#,
        )
        .unwrap();
        let mut settings = Settings::load(path.clone());
        assert_eq!(settings.code_theme, crate::syntax::THEME);
        settings.code_theme = crate::syntax::PALETTES[2].into();
        settings.save().unwrap();
        assert_eq!(
            Settings::load(path.clone()).code_theme,
            crate::syntax::PALETTES[2]
        );
        let data: Value = serde_json::from_slice(&fs::read(path).unwrap()).unwrap();
        assert_eq!(data["code_style"], "friendly");
        fs::remove_dir_all(dir).unwrap();
    }
    #[test]
    fn font_validation_and_legacy_visibility_preserve_settings_and_drafts() {
        assert_eq!(validate_font("自定义字体", Some(16.5)).unwrap(), 16.5);
        for size in [
            None,
            Some(f32::NAN),
            Some(f32::INFINITY),
            Some(9.0),
            Some(23.0),
        ] {
            assert!(validate_font("Menlo", size).is_err());
        }
        assert!(validate_font("", Some(12.0)).is_err());
        assert!(validate_font("bad\nfont", Some(12.0)).is_err());
        let dir = std::env::temp_dir().join(format!(
            "mygit-preferences-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        fs::create_dir(&dir).unwrap();
        let path = dir.join("settings.json");
        fs::write(&path, br#"{"left_panel_visible":false,"recent_folders":["/tmp/a"],"last_folder":"/tmp/a","code_style":"friendly","gpui":{"commit_drafts":{"/tmp/a":"KEEP"}}}"#).unwrap();
        let mut settings = Settings::load(path.clone());
        assert!(!settings.files_visible);
        settings.clear_recent();
        settings.files_visible = true;
        settings.save().unwrap();
        let loaded = Settings::load(path.clone());
        assert!(loaded.files_visible);
        assert!(loaded.recent.is_empty());
        assert!(loaded.last.is_none());
        assert_eq!(loaded.draft_for(Path::new("/tmp/a")), "KEEP");
        let data: Value = serde_json::from_slice(&fs::read(path).unwrap()).unwrap();
        assert_eq!(data["code_style"], "friendly");
        assert_eq!(data["left_panel_visible"], false);
        fs::remove_dir_all(dir).unwrap();
    }
    #[test]
    fn ai_configuration_updates_are_explicit_private_and_preserve_legacy_fields() {
        let dir = std::env::temp_dir().join(format!(
            "mygit-ai-settings-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        fs::create_dir(&dir).unwrap();
        let path = dir.join("settings.json");
        fs::write(&path, r#"{"api_url":"https://example.com/v1","api_secret":"fixture-old","model_name":"old","prompt":"old","future":42}"#).unwrap();
        let mut settings = Settings::load(path.clone());
        settings.save().unwrap();
        let data: Value = serde_json::from_slice(&fs::read(&path).unwrap()).unwrap();
        assert_eq!(data["api_secret"], "fixture-old");
        settings.ai_update = Some(crate::ai::Config {
            api_url: "https://example.com/new".into(),
            api_secret: "fixture-new".into(),
            model_name: "new".into(),
            prompt: "中文提示".into(),
        });
        settings.save().unwrap();
        let data: Value = serde_json::from_slice(&fs::read(&path).unwrap()).unwrap();
        assert_eq!(data["api_secret"], "fixture-new");
        assert_eq!(data["prompt"], "中文提示");
        assert_eq!(data["future"], 42);
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            assert_eq!(
                fs::metadata(&path).unwrap().permissions().mode() & 0o777,
                0o600
            );
        }
        fs::remove_dir_all(dir).unwrap();
    }
    #[test]
    fn preserves_unknown_fresh_fields_and_backs_up_corrupt_settings() {
        let dir = std::env::temp_dir().join(format!(
            "mygit-settings-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        fs::create_dir(&dir).unwrap();
        let path = dir.join("settings.json");
        fs::write(&path,r#"{"font_size":16,"unknown":{"keep":true},"gpui":{"future":1},"last_folder":"/tmp/repo"}"#).unwrap();
        let mut settings = Settings::load(path.clone());
        assert_eq!(settings.font_size, 16.);
        assert_eq!(settings.last, Some(PathBuf::from("/tmp/repo")));
        fs::write(
            &path,
            r#"{"unknown":{"keep":true},"gpui":{"future":2},"other":"new"}"#,
        )
        .unwrap();
        settings.font_size = 18.;
        settings.opened(Path::new("/tmp/中文 repo"));
        settings.save().unwrap();
        let value: Value = serde_json::from_slice(&fs::read(&path).unwrap()).unwrap();
        assert_eq!(value["unknown"]["keep"], true);
        assert_eq!(value["gpui"]["future"], 2);
        assert_eq!(value["other"], "new");
        assert_eq!(Settings::load(path.clone()).font_size, 18.);
        settings.draft = Some(("/tmp/repo-a".into(), "draft a\n正文".into()));
        settings.save().unwrap();
        settings.draft = Some(("/tmp/repo-b".into(), "draft b".into()));
        settings.save().unwrap();
        assert_eq!(
            settings.draft_for(Path::new("/tmp/repo-a")),
            "draft a\n正文"
        );
        assert_eq!(settings.draft_for(Path::new("/tmp/repo-b")), "draft b");
        fs::write(&path, b"{broken").unwrap();
        settings = Settings::load(path.clone());
        assert!(settings.warning.is_some());
        assert_eq!(settings.font_size, 12.);
        settings.save().unwrap();
        assert!(fs::read_dir(&dir).unwrap().any(|e| {
            e.unwrap()
                .file_name()
                .to_string_lossy()
                .contains("corrupt-")
        }));
        fs::remove_dir_all(dir).unwrap();
    }
}
