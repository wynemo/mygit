use gpui::{AssetSource, Result, SharedString};
use std::borrow::Cow;

pub struct Embedded;
impl AssetSource for Embedded {
    fn load(&self, path: &str) -> Result<Option<Cow<'static, [u8]>>> {
        Ok(mygit_gpui::resources::load(path).map(Cow::Borrowed))
    }
    fn list(&self, path: &str) -> Result<Vec<SharedString>> {
        let prefix = format!("{}/", path.trim_end_matches('/'));
        Ok(mygit_gpui::resources::ICONS
            .iter()
            .filter(|(key, _)| path.is_empty() || key.starts_with(&prefix))
            .map(|(key, _)| (*key).into())
            .collect())
    }
}
