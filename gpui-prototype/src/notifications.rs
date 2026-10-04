//! Bounded, in-memory operation notifications; timer identities cannot dismiss newer results.
use std::{collections::VecDeque, path::PathBuf};
use unicode_segmentation::UnicodeSegmentation;

pub const HISTORY_LIMIT: usize = 16;
pub const TOAST_SECONDS: u64 = 7;
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Kind {
    Success,
    Error,
    Info,
}
#[derive(Clone, Debug)]
pub struct Notice {
    pub id: u64,
    pub kind: Kind,
    pub message: String,
    pub repository: Option<PathBuf>,
}
impl Notice {
    pub fn summary(&self) -> String {
        let first = self
            .message
            .lines()
            .find(|line| !line.is_empty())
            .unwrap_or_default();
        let mut chunks = first.graphemes(true);
        let mut summary = chunks.by_ref().take(180).collect::<String>();
        if chunks.next().is_some() {
            summary.push('…');
        }
        summary
    }
    pub fn copy_text(&self) -> String {
        match &self.repository {
            Some(root) => format!("{}\n{}", root.display(), self.message),
            None => self.message.clone(),
        }
    }
}
#[derive(Default)]
pub struct Notifications {
    next_id: u64,
    active_id: Option<u64>,
    entries: VecDeque<Notice>,
}
impl Notifications {
    pub fn push(&mut self, kind: Kind, message: String, repository: Option<PathBuf>) -> u64 {
        self.next_id = self.next_id.wrapping_add(1);
        let id = self.next_id;
        self.entries.push_front(Notice {
            id,
            kind,
            message: crate::process::display_diagnostic(message),
            repository,
        });
        self.entries.truncate(HISTORY_LIMIT);
        self.active_id = Some(id);
        id
    }
    pub fn entries(&self) -> &VecDeque<Notice> {
        &self.entries
    }
    pub fn active(&self) -> Option<&Notice> {
        self.active_id
            .and_then(|id| self.entries.iter().find(|n| n.id == id))
    }
    pub fn dismiss(&mut self, id: u64) -> bool {
        if self.active_id != Some(id) {
            return false;
        }
        self.active_id = None;
        true
    }
    pub fn clear(&mut self) {
        self.entries.clear();
        self.active_id = None;
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn old_timer_and_close_do_not_dismiss_newer_results_or_erase_history() {
        let mut notices = Notifications::default();
        let old = notices.push(Kind::Error, "old".into(), None);
        let new = notices.push(Kind::Success, "new".into(), None);
        assert!(!notices.dismiss(old));
        assert_eq!(notices.active().unwrap().id, new);
        assert!(notices.dismiss(new));
        assert!(notices.active().is_none());
        assert_eq!(notices.entries().len(), 2);
        notices.clear();
        let later = notices.push(Kind::Info, "later".into(), None);
        assert_ne!(later, new);
        assert!(!notices.dismiss(new));
        assert_eq!(notices.active().unwrap().id, later);
    }
    #[test]
    fn history_bounds_diagnostics_and_keeps_original_repository_association() {
        let mut notices = Notifications::default();
        for i in 0..40 {
            notices.push(
                Kind::Error,
                format!("failure {i}\n{}\nEND🙂", "中文".repeat(10_000)),
                Some(PathBuf::from(format!("/tmp/repo-{i}"))),
            );
        }
        assert_eq!(notices.entries().len(), HISTORY_LIMIT);
        assert_eq!(
            notices.entries().back().unwrap().repository.as_deref(),
            Some(std::path::Path::new("/tmp/repo-24"))
        );
        for entry in notices.entries() {
            assert!(entry.message.len() < 8400);
            assert!(entry.message.ends_with("END🙂"));
        }
        let current = notices.active().unwrap();
        assert_eq!(current.summary(), "failure 39");
        assert!(
            current
                .copy_text()
                .starts_with("/tmp/repo-39\nfailure 39\n")
        );
        let id = notices.push(Kind::Info, "🙂‍↔️".repeat(200), None);
        assert_eq!(notices.active().unwrap().id, id);
        assert_eq!(
            notices.active().unwrap().summary(),
            format!("{}…", "🙂‍↔️".repeat(180))
        );
    }
}
