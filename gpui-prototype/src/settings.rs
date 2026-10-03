//! Compatible settings with fresh merge-on-save and atomic replacement.
use anyhow::{Context, Result};
use serde_json::{Value, json};
use std::{
    fs,
    io::Write,
    path::{Path, PathBuf},
};
#[derive(Clone)]
pub struct Settings {
    pub path: PathBuf,
    pub font_family: String,
    pub font_size: f32,
    pub history_width: f32,
    pub files_width: f32,
    pub recent: Vec<PathBuf>,
    pub last: Option<PathBuf>,
    pub warning: Option<String>,
    pub draft: Option<(String, String)>,
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
                    Some("配置损坏，已使用默认设置；保存时保留原文件备份".into()),
                ),
            },
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => (json!({}), None),
            Err(_) => (json!({}), Some("无法读取配置，已使用默认设置".into())),
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
            history_width: number("/gpui/history_width", 260., 160., 600.),
            files_width: number("/gpui/files_width", 220., 120., 600.),
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
    pub fn save(&self) -> Result<()> {
        let parent = self.path.parent().context("配置路径缺少目录")?;
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
                    fs::copy(&self.path, backup).context("无法备份损坏配置，未覆盖原文件")?;
                    json!({})
                }
            },
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => json!({}),
            Err(e) => return Err(e.into()),
        };
        data["font_family"] = json!(self.font_family);
        data["font_size"] = json!(self.font_size);
        data["recent_folders"] = json!(self.recent);
        data["last_folder"] = json!(self.last);
        if !data["gpui"].is_object() {
            data["gpui"] = json!({});
        }
        data["gpui"]["history_width"] = json!(self.history_width);
        data["gpui"]["files_width"] = json!(self.files_width);
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
