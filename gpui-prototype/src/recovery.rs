//! Reversible file/block restore. The Git index is never modified by this module.
use crate::{
    git,
    model::{Diff, Revision},
    text::Side,
};
use anyhow::{Context, Result, bail};
use serde::{Deserialize, Serialize};
use std::{
    fs,
    io::{Read, Write},
    path::{Path, PathBuf},
};
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
enum Kind {
    Missing,
    Regular,
    Symlink,
}
#[derive(Clone, Debug, PartialEq, Eq)]
struct State {
    kind: Kind,
    data: Vec<u8>,
    mode: u32,
}
#[derive(Serialize, Deserialize)]
struct Stored {
    kind: Kind,
    blob: String,
    mode: u32,
}
#[derive(Serialize, Deserialize)]
struct Record {
    path: String,
    before: Stored,
    after: Stored,
}
#[derive(Serialize, Deserialize)]
struct Manifest {
    root: PathBuf,
    records: Vec<Record>,
}
fn inside(root: &Path, path: &str) -> Result<PathBuf> {
    git::validate_paths(&[path.into()])?;
    let result = root.join(path);
    let mut ancestor = result.parent().context(crate::i18n::text("缺少父目录"))?;
    while !ancestor.exists() {
        ancestor = ancestor
            .parent()
            .context(crate::i18n::text("缺少有效父目录"))?;
    }
    if !ancestor.canonicalize()?.starts_with(root.canonicalize()?) {
        bail!(crate::localized_format!(
            "路径的父目录位于仓库外，停止还原",
            "The parent directory is outside the repository; restore stopped"
        ));
    }
    Ok(result)
}
fn capture(root: &Path, path: &str) -> Result<State> {
    let path = inside(root, path)?;
    let metadata = match fs::symlink_metadata(&path) {
        Ok(m) => m,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
            return Ok(State {
                kind: Kind::Missing,
                data: vec![],
                mode: 0,
            });
        }
        Err(e) => return Err(e.into()),
    };
    if metadata.file_type().is_symlink() {
        let target = fs::read_link(path)?;
        #[cfg(unix)]
        let data = {
            use std::os::unix::ffi::OsStrExt;
            target.as_os_str().as_bytes().to_vec()
        };
        #[cfg(not(unix))]
        let data = target
            .to_str()
            .context(crate::i18n::text("链接目标不是 UTF-8"))?
            .as_bytes()
            .to_vec();
        return Ok(State {
            kind: Kind::Symlink,
            data,
            mode: 0,
        });
    }
    if !metadata.is_file() {
        bail!(crate::localized_format!(
            "目录/特殊文件不能使用文件还原操作",
            "Directories and special files cannot be restored as files"
        ));
    }
    if metadata.len() > 20_000_000 {
        bail!(crate::localized_format!(
            "文件超过 20 MB 恢复记录上限",
            "File exceeds the 20 MB recovery limit"
        ));
    }
    let mut options = fs::OpenOptions::new();
    options.read(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.custom_flags(libc::O_NOFOLLOW | libc::O_NONBLOCK);
    }
    let mut data = vec![];
    let file = options.open(path)?;
    if !file.metadata()?.is_file() {
        bail!(crate::localized_format!(
            "特殊文件不能还原",
            "Special files cannot be restored"
        ));
    }
    file.take(20_000_001).read_to_end(&mut data)?;
    if data.len() > 20_000_000 {
        bail!(crate::localized_format!(
            "文件在读取期间超过上限",
            "File exceeded the size limit while reading"
        ));
    }
    #[cfg(unix)]
    let mode = {
        use std::os::unix::fs::PermissionsExt;
        metadata.permissions().mode() & 0o777
    };
    #[cfg(not(unix))]
    let mode = if metadata.permissions().readonly() {
        0o444
    } else {
        0o644
    };
    Ok(State {
        kind: Kind::Regular,
        data,
        mode,
    })
}
fn stamp() -> Result<String> {
    Ok(format!(
        "{}-{}",
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)?
            .as_nanos(),
        std::process::id()
    ))
}
fn write_state(root: &Path, path: &str, state: &State) -> Result<()> {
    let path = inside(root, path)?;
    if state.kind == Kind::Missing {
        match fs::remove_file(path) {
            Ok(()) => {}
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => {}
            Err(e) => return Err(e.into()),
        };
        return Ok(());
    }
    let parent = path.parent().context(crate::i18n::text("缺少父目录"))?;
    fs::create_dir_all(parent)?;
    let temp = parent.join(format!(".mygit-restore-{}", stamp()?));
    let result = (|| -> Result<()> {
        if state.kind == Kind::Regular {
            let mut file = fs::OpenOptions::new()
                .write(true)
                .create_new(true)
                .open(&temp)?;
            #[cfg(unix)]
            {
                use std::os::unix::fs::PermissionsExt;
                file.set_permissions(fs::Permissions::from_mode(state.mode))?;
            }
            file.write_all(&state.data)?;
            file.sync_all()?;
            #[cfg(not(unix))]
            {
                let mut p = file.metadata()?.permissions();
                p.set_readonly(state.mode == 0o444);
                file.set_permissions(p)?;
            }
        } else {
            #[cfg(unix)]
            {
                use std::os::unix::ffi::OsStringExt;
                std::os::unix::fs::symlink(
                    std::ffi::OsString::from_vec(state.data.clone()),
                    &temp,
                )?;
            }
            #[cfg(windows)]
            std::os::windows::fs::symlink_file(std::str::from_utf8(&state.data)?, &temp)?;
            #[cfg(not(any(unix, windows)))]
            bail!(crate::localized_format!(
                "此平台不能恢复符号链接",
                "This platform cannot restore symbolic links"
            ));
        }
        fs::rename(&temp, &path)?;
        Ok(())
    })();
    if result.is_err() {
        let _ = fs::remove_file(temp);
    }
    result
}
fn store_state(dir: &Path, name: &str, state: &State) -> Result<Stored> {
    let path = dir.join(name);
    let mut file = fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(path)?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        file.set_permissions(fs::Permissions::from_mode(0o600))?;
    }
    file.write_all(&state.data)?;
    file.sync_all()?;
    Ok(Stored {
        kind: state.kind.clone(),
        blob: name.into(),
        mode: state.mode,
    })
}
fn load_state(dir: &Path, stored: &Stored) -> Result<State> {
    if stored.blob.contains('/') || stored.blob.contains('\\') || stored.blob.starts_with('.') {
        bail!(crate::localized_format!(
            "恢复记录数据路径无效",
            "Invalid recovery data path"
        ));
    }
    let path = dir.join(&stored.blob);
    let metadata = fs::symlink_metadata(&path)?;
    if !metadata.is_file() || metadata.file_type().is_symlink() || metadata.len() > 20_000_000 {
        bail!(crate::localized_format!(
            "恢复记录数据无效或超过上限",
            "Recovery data is invalid or exceeds the size limit"
        ));
    }
    Ok(State {
        kind: stored.kind.clone(),
        data: fs::read(path)?,
        mode: stored.mode,
    })
}
fn apply(root: &Path, actions: Vec<(String, State)>, store: &Path) -> Result<PathBuf> {
    let mut states = vec![];
    let mut bytes = 0;
    for (path, after) in actions {
        let before = capture(root, &path)?;
        bytes += before.data.len() + after.data.len();
        if bytes > 64_000_000 {
            bail!(crate::localized_format!(
                "本次还原超过 64 MB 恢复记录上限，请分批操作",
                "Restore exceeds the 64 MB recovery limit; restore in smaller batches"
            ));
        }
        states.push((path, before, after));
    }
    fs::create_dir_all(store)?;
    let dir = store.join(stamp()?);
    fs::create_dir(&dir)?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        fs::set_permissions(&dir, fs::Permissions::from_mode(0o700))?;
    }
    let mut records = vec![];
    for (i, (path, before, after)) in states.iter().enumerate() {
        records.push(Record {
            path: path.clone(),
            before: store_state(&dir, &format!("before-{i}"), before)?,
            after: store_state(&dir, &format!("after-{i}"), after)?,
        });
    }
    let manifest = Manifest {
        root: root.canonicalize()?,
        records,
    };
    let mut file = fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(dir.join("manifest.json"))?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        file.set_permissions(fs::Permissions::from_mode(0o600))?;
    }
    file.write_all(&serde_json::to_vec_pretty(&manifest)?)?;
    file.sync_all()?;
    for (path, before, _) in &states {
        if capture(root, path)? != *before {
            fs::write(dir.join("undone"), b"stale")?;
            bail!(crate::localized_format!(
                "磁盘文件在准备还原时变化，未执行还原",
                "The disk file changed while preparing; restore was not performed"
            ));
        }
    }
    for (index, (path, before, after)) in states.iter().enumerate() {
        let result = (|| -> Result<()> {
            if capture(root, path)? != *before {
                bail!(crate::localized_format!(
                    "磁盘文件在还原期间变化",
                    "The disk file changed during restore"
                ));
            }
            write_state(root, path, after)
        })();
        if let Err(error) = result {
            let mut failures = vec![];
            for (p, b, a) in states.iter().take(index).rev() {
                if capture(root, p).ok().as_ref() == Some(a) {
                    if let Err(e) = write_state(root, p, b) {
                        failures.push(e.to_string());
                    }
                } else {
                    failures.push(crate::localized_format!(
                        "{p} 已变化，保留现场",
                        "{p} changed; its current state is preserved"
                    ));
                }
            }
            fs::write(dir.join("undone"), b"failed")?;
            bail!(crate::localized_format!(
                "{error:#}；恢复记录位于 {}；回退结果：{}",
                "{error:#}; recovery data: {}; rollback result: {}",
                dir.display(),
                if failures.is_empty() {
                    "已回退".into()
                } else {
                    failures.join("；")
                }
            ));
        }
    }
    Ok(dir)
}
pub fn restore_files(
    root: &Path,
    source: &Revision,
    paths: &[String],
    store: &Path,
) -> Result<PathBuf> {
    if paths.is_empty() {
        bail!(crate::localized_format!(
            "请选择还原文件",
            "Select a file to restore"
        ));
    }
    let mut actions = vec![];
    for path in paths {
        let after = match git::version_content(root, source, path)? {
            None => State {
                kind: Kind::Missing,
                data: vec![],
                mode: 0,
            },
            Some(v) => State {
                kind: if v.symlink {
                    Kind::Symlink
                } else {
                    Kind::Regular
                },
                data: v.bytes,
                mode: if v.executable { 0o755 } else { 0o644 },
            },
        };
        actions.push((path.clone(), after));
    }
    apply(root, actions, store)
}
pub fn restore_block(
    root: &Path,
    path: &str,
    diff: &Diff,
    block: usize,
    store: &Path,
) -> Result<PathBuf> {
    let block = diff
        .blocks
        .get(block)
        .context(crate::i18n::text("请先选择差异块"))?;
    let mut before = capture(root, path)?;
    if before.kind != Kind::Regular {
        bail!(crate::localized_format!(
            "差异块还原仅支持已存在的普通文本文件",
            "Change block restore requires an existing regular text file"
        ));
    }
    if before.data != diff.right_document.text.as_bytes() {
        bail!(crate::localized_format!(
            "磁盘内容已偏离当前 Diff，请刷新后再还原",
            "Disk content no longer matches the Diff; refresh before restoring"
        ));
    }
    fn span(diff: &Diff, side: Side, block: &std::ops::Range<usize>) -> std::ops::Range<usize> {
        let lines: Vec<_> = block
            .clone()
            .filter_map(|r| diff.source_line(side, r))
            .collect();
        let document = diff.document(side);
        match (lines.first(), lines.last()) {
            (Some(a), Some(b)) => document.lines[*a].start..document.lines[*b].end,
            _ => {
                let offset = diff.padding_offset(side, block.start);
                offset..offset
            }
        }
    }
    let left = span(diff, Side::Left, block);
    let right = span(diff, Side::Right, block);
    let mut text =
        String::from_utf8(before.data).context(crate::i18n::text("当前文件不是 UTF-8"))?;
    text.replace_range(right, &diff.left_document.text[left]);
    before.data = text.into_bytes();
    apply(root, vec![(path.into(), before)], store)
}
pub fn undo_latest(root: &Path, store: &Path) -> Result<PathBuf> {
    let mut dirs = match fs::read_dir(store) {
        Ok(d) => d
            .filter_map(|e| e.ok().map(|e| e.path()))
            .filter(|p| p.is_dir() && !p.join("undone").exists())
            .collect::<Vec<_>>(),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => bail!(crate::localized_format!(
            "没有可撤销的还原记录",
            "No restore record to undo"
        )),
        Err(e) => return Err(e.into()),
    };
    dirs.sort();
    dirs.reverse();
    let canonical = root.canonicalize()?;
    for dir in dirs {
        let Ok(bytes) = fs::read(dir.join("manifest.json")) else {
            continue;
        };
        let manifest: Manifest = serde_json::from_slice(&bytes)?;
        if manifest.root != canonical {
            continue;
        }
        let mut states = vec![];
        for record in manifest.records {
            let before = load_state(&dir, &record.before)?;
            let after = load_state(&dir, &record.after)?;
            if capture(root, &record.path)? != after {
                bail!(crate::localized_format!(
                    "{} 已在还原后改变，撤销不会覆盖新内容",
                    "{} changed after restore; undo will not overwrite new content",
                    record.path
                ));
            }
            states.push((record.path, before, after));
        }
        for (index, (path, before, after)) in states.iter().enumerate() {
            let result = (|| -> Result<()> {
                if capture(root, path)? != *after {
                    bail!(crate::localized_format!(
                        "文件在撤销期间变化，停止操作",
                        "The file changed during undo; operation stopped"
                    ));
                }
                write_state(root, path, before)
            })();
            if let Err(error) = result {
                let mut failures = vec![];
                for (p, b, a) in states.iter().take(index).rev() {
                    if capture(root, p).ok().as_ref() == Some(b) {
                        if let Err(e) = write_state(root, p, a) {
                            failures.push(e.to_string());
                        }
                    } else {
                        failures.push(crate::localized_format!(
                            "{p} 已变化，保留现场",
                            "{p} changed; its current state is preserved"
                        ));
                    }
                }
                bail!(crate::localized_format!(
                    "{error:#}；恢复记录位于 {}；回退结果：{}",
                    "{error:#}; recovery data: {}; rollback result: {}",
                    dir.display(),
                    if failures.is_empty() {
                        "已回退".into()
                    } else {
                        failures.join("；")
                    }
                ));
            }
        }
        fs::write(dir.join("undone"), b"undone")?;
        return Ok(dir);
    }
    bail!(crate::localized_format!(
        "当前仓库没有可撤销的还原记录",
        "This repository has no restore record to undo"
    ))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::process::Command;
    struct Fixture {
        root: PathBuf,
        store: PathBuf,
    }
    impl Fixture {
        fn new() -> Self {
            let base = std::env::temp_dir().join(format!(
                "mygit-recovery-{}-{}",
                std::process::id(),
                std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .unwrap()
                    .as_nanos()
            ));
            let root = base.join("repo");
            fs::create_dir_all(&root).unwrap();
            let fixture = Self {
                root,
                store: base.join("records"),
            };
            fixture.git(&["init", "-q"]);
            fixture.git(&["config", "user.name", "Test"]);
            fixture.git(&["config", "user.email", "test@example.invalid"]);
            fixture
        }
        fn git(&self, args: &[&str]) -> Vec<u8> {
            let result = Command::new("git")
                .current_dir(&self.root)
                .args(args)
                .output()
                .unwrap();
            assert!(
                result.status.success(),
                "{}",
                String::from_utf8_lossy(&result.stderr)
            );
            result.stdout
        }
    }
    impl Drop for Fixture {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(self.root.parent().unwrap());
        }
    }
    #[test]
    fn whole_restore_and_undo_preserve_index_and_added_files() {
        let f = Fixture::new();
        fs::write(f.root.join("a"), b"original\n").unwrap();
        f.git(&["add", "a"]);
        f.git(&["commit", "-qm", "initial"]);
        fs::write(f.root.join("a"), b"staged\n").unwrap();
        f.git(&["add", "a"]);
        fs::write(f.root.join("a"), b"working\n").unwrap();
        fs::write(f.root.join("new"), b"untracked\n").unwrap();
        let index = f.git(&["write-tree"]);
        restore_files(
            &f.root,
            &Revision::Index,
            &["a".into(), "new".into()],
            &f.store,
        )
        .unwrap();
        assert_eq!(fs::read(f.root.join("a")).unwrap(), b"staged\n");
        assert!(!f.root.join("new").exists());
        assert_eq!(f.git(&["write-tree"]), index);
        undo_latest(&f.root, &f.store).unwrap();
        assert_eq!(fs::read(f.root.join("a")).unwrap(), b"working\n");
        assert_eq!(fs::read(f.root.join("new")).unwrap(), b"untracked\n");
        assert_eq!(f.git(&["write-tree"]), index);
        assert!(undo_latest(&f.root, &f.store).is_err());
    }
    #[test]
    fn rename_restore_and_undo_recreate_both_paths() {
        let f = Fixture::new();
        fs::write(f.root.join("old"), "original").unwrap();
        f.git(&["add", "old"]);
        f.git(&["commit", "-qm", "initial"]);
        let source = git::resolve_revision(&f.root, "HEAD").unwrap();
        fs::rename(f.root.join("old"), f.root.join("new")).unwrap();
        f.git(&["add", "-A"]);
        fs::write(f.root.join("new"), "modified").unwrap();
        let index = f.git(&["write-tree"]);
        restore_files(&f.root, &source, &["old".into(), "new".into()], &f.store).unwrap();
        assert_eq!(fs::read(f.root.join("old")).unwrap(), b"original");
        assert!(!f.root.join("new").exists());
        undo_latest(&f.root, &f.store).unwrap();
        assert!(!f.root.join("old").exists());
        assert_eq!(fs::read(f.root.join("new")).unwrap(), b"modified");
        assert_eq!(f.git(&["write-tree"]), index);
    }
    #[cfg(unix)]
    #[test]
    fn undo_preserves_executable_permissions() {
        use std::os::unix::fs::PermissionsExt;
        let f = Fixture::new();
        fs::write(f.root.join("a"), "script").unwrap();
        fs::set_permissions(f.root.join("a"), fs::Permissions::from_mode(0o751)).unwrap();
        restore_files(&f.root, &Revision::Empty, &["a".into()], &f.store).unwrap();
        undo_latest(&f.root, &f.store).unwrap();
        assert_eq!(
            fs::metadata(f.root.join("a")).unwrap().permissions().mode() & 0o777,
            0o751
        );
    }
    #[test]
    fn blocks_preserve_raw_newlines_and_reject_stale_disk() {
        for (left, right) in [
            ("a\r\nb\r\n", "a\r\nchanged\r\n"),
            ("a\n", "a\nb\n"),
            ("a\nb\n", "a\n"),
            ("old", "new"),
        ] {
            let f = Fixture::new();
            fs::write(f.root.join("a"), right).unwrap();
            let diff = crate::diff::calculate(left.as_bytes(), right.as_bytes()).unwrap();
            restore_block(&f.root, "a", &diff, 0, &f.store).unwrap();
            assert_eq!(fs::read(f.root.join("a")).unwrap(), left.as_bytes());
            undo_latest(&f.root, &f.store).unwrap();
            assert_eq!(fs::read(f.root.join("a")).unwrap(), right.as_bytes());
            fs::write(f.root.join("a"), "external").unwrap();
            assert!(restore_block(&f.root, "a", &diff, 0, &f.store).is_err());
            assert_eq!(fs::read(f.root.join("a")).unwrap(), b"external");
        }
    }
    #[test]
    fn undo_refuses_external_changes_before_touching_any_file() {
        let f = Fixture::new();
        fs::write(f.root.join("a"), "one").unwrap();
        fs::write(f.root.join("b"), "two").unwrap();
        restore_files(
            &f.root,
            &Revision::Empty,
            &["a".into(), "b".into()],
            &f.store,
        )
        .unwrap();
        fs::write(f.root.join("b"), "external").unwrap();
        assert!(undo_latest(&f.root, &f.store).is_err());
        assert!(!f.root.join("a").exists());
        assert_eq!(fs::read(f.root.join("b")).unwrap(), b"external");
    }
    #[cfg(unix)]
    #[test]
    fn symlink_restore_does_not_follow_target_or_escape_repository() {
        let f = Fixture::new();
        let outside = f.root.parent().unwrap().join("outside");
        fs::write(&outside, "untouched").unwrap();
        std::os::unix::fs::symlink(&outside, f.root.join("link")).unwrap();
        restore_files(&f.root, &Revision::Empty, &["link".into()], &f.store).unwrap();
        assert_eq!(fs::read(&outside).unwrap(), b"untouched");
        undo_latest(&f.root, &f.store).unwrap();
        assert_eq!(fs::read_link(f.root.join("link")).unwrap(), outside);
        std::os::unix::fs::symlink(f.root.parent().unwrap(), f.root.join("escape")).unwrap();
        assert!(
            restore_files(
                &f.root,
                &Revision::Empty,
                &["escape/outside".into()],
                &f.store
            )
            .is_err()
        );
        assert!(
            restore_files(&f.root, &Revision::Empty, &["../outside".into()], &f.store).is_err()
        );
        assert_eq!(fs::read(&outside).unwrap(), b"untouched");
    }
}
