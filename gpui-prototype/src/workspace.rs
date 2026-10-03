//! Lazy filesystem tree: only expanded directories are read, symlinks are leaves.
use crate::git;
use anyhow::{Context, Result};
use std::{
    collections::{BTreeMap, BTreeSet},
    path::Path,
};
#[derive(Clone, Debug)]
pub struct Entry {
    pub path: String,
    pub name: String,
    pub directory: bool,
    pub symlink: bool,
    pub status: String,
}
#[derive(Clone, Debug, Default)]
pub struct Tree {
    pub children: BTreeMap<String, Vec<Entry>>,
    pub expanded: BTreeSet<String>,
    pub selected: Option<String>,
}
impl Tree {
    pub fn new() -> Self {
        Self {
            expanded: BTreeSet::from([String::new()]),
            ..Default::default()
        }
    }
    pub fn reveal(&mut self, path: &str) -> Result<()> {
        git::validate_paths(&[path.into()])?;
        self.expanded.insert(String::new());
        let mut parent = String::new();
        let parts: Vec<_> = path.split('/').collect();
        for part in parts.iter().take(parts.len().saturating_sub(1)) {
            if !parent.is_empty() {
                parent.push('/');
            }
            parent.push_str(part);
            self.expanded.insert(parent.clone());
        }
        self.selected = Some(path.into());
        Ok(())
    }
    pub fn rows(&self) -> Vec<(Entry, usize)> {
        fn visit(tree: &Tree, parent: &str, depth: usize, result: &mut Vec<(Entry, usize)>) {
            if let Some(children) = tree.children.get(parent) {
                for entry in children {
                    result.push((entry.clone(), depth));
                    if entry.directory && tree.expanded.contains(&entry.path) {
                        visit(tree, &entry.path, depth + 1, result);
                    }
                }
            }
        }
        let mut rows = vec![];
        visit(self, "", 0, &mut rows);
        rows
    }
}
pub fn read(root: &Path, expanded: &BTreeSet<String>) -> Result<BTreeMap<String, Vec<Entry>>> {
    let statuses = git::workspace_status(root)?;
    let mut result = BTreeMap::new();
    for parent in expanded {
        crate::process::check()?;
        let mut entries = vec![];
        let directory = root.join(parent);
        if !directory.exists()
            || std::fs::symlink_metadata(&directory)?
                .file_type()
                .is_symlink()
        {
            continue;
        }
        // Do not follow an externally replaced directory symlink outside the repository.
        let canonical = directory.canonicalize()?;
        if !canonical.starts_with(root.canonicalize()?) {
            continue;
        }
        for entry in
            std::fs::read_dir(&directory).with_context(|| format!("无法读取目录 {parent}"))?
        {
            let entry = entry?;
            let name = entry
                .file_name()
                .into_string()
                .map_err(|_| anyhow::anyhow!("目录存在非 UTF-8 文件名"))?;
            if parent.is_empty() && name == ".git" {
                continue;
            }
            let path = if parent.is_empty() {
                name.clone()
            } else {
                format!("{parent}/{name}")
            };
            let kind = entry.file_type()?;
            let prefix = format!("{path}/");
            let mut status = statuses.get(&path).cloned().unwrap_or_default();
            if status.is_empty() {
                let nested: Vec<_> = statuses
                    .iter()
                    .filter(|(p, _)| p.starts_with(&prefix))
                    .map(|(_, s)| s.as_str())
                    .collect();
                if !nested.is_empty() {
                    status = if nested.iter().all(|s| *s == "!!") {
                        "!!"
                    } else {
                        "变更"
                    }
                    .into();
                }
            }
            if status.is_empty()
                && statuses.iter().any(|(p, s)| {
                    s == "!!" && path.starts_with(&format!("{}/", p.trim_end_matches('/')))
                })
            {
                status = "!!".into();
            }
            entries.push(Entry {
                path,
                name,
                directory: kind.is_dir(),
                symlink: kind.is_symlink(),
                status,
            });
        }
        entries.sort_by(|a, b| a.name.cmp(&b.name));
        result.insert(parent.clone(), entries);
    }
    Ok(result)
}
