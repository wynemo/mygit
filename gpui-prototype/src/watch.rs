//! Bounded event signal and debounce policy shared by filesystem and focus refresh.
use anyhow::Result;
use notify::{EventKind, RecommendedWatcher, RecursiveMode, Watcher};
use std::{
    path::{Path, PathBuf},
    sync::{
        Arc,
        atomic::{AtomicU64, Ordering},
    },
    time::{Duration, Instant},
};

pub struct RepositoryWatch {
    _watcher: RecommendedWatcher,
    revision: Arc<AtomicU64>,
}
impl RepositoryWatch {
    pub fn new(root: &Path, metadata: &[PathBuf]) -> Result<Self> {
        let revision = Arc::new(AtomicU64::new(0));
        let signal = revision.clone();
        let mut watcher =
            notify::recommended_watcher(move |event: notify::Result<notify::Event>| {
                // Reads by Git/preview must not create an endless refresh cycle.
                if !matches!(event.as_ref().map(|e| e.kind), Ok(EventKind::Access(_))) {
                    signal.fetch_add(1, Ordering::Relaxed);
                }
            })?;
        watcher.watch(root, RecursiveMode::Recursive)?;
        for directory in metadata {
            if !directory.starts_with(root) {
                watcher.watch(directory, RecursiveMode::Recursive)?;
            }
        }
        Ok(Self {
            _watcher: watcher,
            revision,
        })
    }
    pub fn revision(&self) -> u64 {
        self.revision.load(Ordering::Relaxed)
    }
}

#[derive(Default)]
pub struct Debounce {
    revision: u64,
    first: Option<Instant>,
    last: Option<Instant>,
}
impl Debounce {
    pub fn observe(&mut self, revision: u64, now: Instant) {
        if self.revision != revision {
            self.revision = revision;
            self.first.get_or_insert(now);
            self.last = Some(now);
        }
    }
    pub fn due(&mut self, now: Instant) -> bool {
        let ready = self
            .last
            .is_some_and(|last| now.duration_since(last) >= Duration::from_millis(300))
            || self
                .first
                .is_some_and(|first| now.duration_since(first) >= Duration::from_secs(2));
        if ready {
            self.first = None;
            self.last = None;
        }
        ready
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn native_watcher_observes_atomic_replacement_and_external_metadata() {
        let base = std::env::temp_dir().join(format!(
            "mygit-watch-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        let root = base.join("repo");
        let metadata = base.join("metadata");
        std::fs::create_dir_all(&root).unwrap();
        std::fs::create_dir_all(&metadata).unwrap();
        let root = root.canonicalize().unwrap();
        let metadata = metadata.canonicalize().unwrap();
        std::fs::write(root.join("a"), "before").unwrap();
        let watcher = RepositoryWatch::new(&root, std::slice::from_ref(&metadata)).unwrap();
        let wait = |revision| {
            let deadline = Instant::now() + Duration::from_secs(6);
            while watcher.revision() == revision && Instant::now() < deadline {
                std::thread::sleep(Duration::from_millis(20));
            }
            assert_ne!(
                watcher.revision(),
                revision,
                "native filesystem event missing"
            );
        };
        let revision = watcher.revision();
        std::fs::write(root.join("tmp"), "after").unwrap();
        std::fs::rename(root.join("tmp"), root.join("a")).unwrap();
        wait(revision);
        let revision = watcher.revision();
        std::fs::write(metadata.join("HEAD"), "refs/heads/other").unwrap();
        wait(revision);
        drop(watcher);
        std::fs::remove_dir_all(base).unwrap();
    }
    #[test]
    fn bursts_coalesce_and_continuous_changes_have_a_deadline() {
        let now = Instant::now();
        let mut d = Debounce::default();
        d.observe(1, now);
        d.observe(2, now + Duration::from_millis(200));
        assert!(!d.due(now + Duration::from_millis(400)));
        assert!(d.due(now + Duration::from_millis(500)));
        assert!(!d.due(now + Duration::from_secs(1)));
        for i in 1..=20 {
            d.observe(
                i + 2,
                now + Duration::from_secs(1) + Duration::from_millis(i * 100),
            );
        }
        assert!(d.due(now + Duration::from_millis(3100)));
    }
}
