//! Repository file index and bounded, deterministic fuzzy ranking.
use anyhow::{Context, Result, bail};
use std::{
    cmp::Reverse,
    collections::{BTreeSet, BinaryHeap, HashMap},
    path::Path,
};
#[derive(Clone, Debug)]
struct Entry {
    path: String,
    name: String,
    folded: String,
}
#[derive(Clone, Debug, Default)]
pub struct Index {
    entries: Vec<Entry>,
}
#[derive(Clone, Debug, Default)]
pub struct Matches {
    pub paths: Vec<String>,
    pub total: usize,
}
impl Index {
    pub fn len(&self) -> usize {
        self.entries.len()
    }
    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }
    pub fn from_paths(paths: impl IntoIterator<Item = String>) -> Result<Self> {
        let paths: BTreeSet<_> = paths.into_iter().collect();
        if paths.len() > 200_000 || paths.iter().map(String::len).sum::<usize>() > 16_000_000 {
            bail!("文件索引超过 200000 项或 16 MB 路径上限");
        }
        crate::git::validate_paths(&paths.iter().cloned().collect::<Vec<_>>())?;
        Ok(Self {
            entries: paths
                .into_iter()
                .map(|path| Entry {
                    name: path.rsplit('/').next().unwrap_or(&path).to_lowercase(),
                    folded: path.to_lowercase(),
                    path,
                })
                .collect(),
        })
    }
    pub fn search(&self, query: &str, limit: usize) -> Result<Matches> {
        let query = query.trim().to_lowercase();
        if query.chars().count() > 256 {
            bail!("文件查询最多支持 256 个字符");
        }
        let limit = limit.min(1000);
        if query.is_empty() {
            return Ok(Matches {
                paths: self
                    .entries
                    .iter()
                    .take(limit.min(20))
                    .map(|e| e.path.clone())
                    .collect(),
                total: self.len(),
            });
        }
        let chars: Vec<_> = query.chars().collect();
        let mut heap: BinaryHeap<Reverse<(i64, Reverse<usize>)>> = BinaryHeap::new();
        let mut total = 0;
        for (index, entry) in self.entries.iter().enumerate() {
            if index % 256 == 0 {
                crate::process::check()?;
            }
            if let Some(score) = score(entry, &query, &chars) {
                total += 1;
                let rank = (score, Reverse(index));
                if heap.len() < limit {
                    heap.push(Reverse(rank));
                } else if heap.peek().is_some_and(|worst| rank > worst.0) {
                    heap.pop();
                    heap.push(Reverse(rank));
                }
            }
        }
        let mut ranks: Vec<_> = heap.into_iter().map(|r| r.0).collect();
        ranks.sort_unstable_by(|a, b| b.cmp(a));
        Ok(Matches {
            paths: ranks
                .into_iter()
                .map(|(_, Reverse(index))| self.entries[index].path.clone())
                .collect(),
            total,
        })
    }
}
pub fn read(root: &Path) -> Result<Index> {
    let bytes = crate::git::git(
        root,
        &[
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "--deduplicate",
            "-z",
        ],
    )?;
    let text = std::str::from_utf8(&bytes).context("文件索引包含非 UTF-8 路径")?;
    let canonical_root = root.canonicalize()?;
    let mut paths = vec![];
    let mut directories = HashMap::new();
    for path in text.split('\0').filter(|p| !p.is_empty()) {
        crate::process::check()?;
        crate::git::validate_paths(&[path.into()])?;
        let full = canonical_root.join(path);
        let parent = full.parent().context("文件缺少父目录")?;
        if !safe_directory(&canonical_root, parent, &mut directories)? {
            continue;
        }
        let metadata = match std::fs::symlink_metadata(&full) {
            Ok(m) => m,
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => continue,
            Err(e) => return Err(e.into()),
        };
        if !metadata.is_file() && !metadata.file_type().is_symlink() {
            continue;
        }
        let parent = full.parent().context("文件缺少父目录")?.canonicalize()?;
        if parent.starts_with(&canonical_root) {
            paths.push(path.into());
        }
    }
    Index::from_paths(paths)
}
fn safe_directory(
    root: &Path,
    directory: &Path,
    cache: &mut HashMap<std::path::PathBuf, bool>,
) -> Result<bool> {
    let mut current = directory;
    let mut pending = vec![];
    let safe = loop {
        if let Some(safe) = cache.get(current) {
            break *safe;
        }
        if current == root {
            break true;
        }
        if !current.starts_with(root) {
            break false;
        }
        pending.push(current.to_path_buf());
        let metadata = match std::fs::symlink_metadata(current) {
            Ok(m) => m,
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => break false,
            Err(error) => return Err(error.into()),
        };
        if !metadata.is_dir() || metadata.file_type().is_symlink() {
            break false;
        }
        let Some(parent) = current.parent() else {
            break false;
        };
        current = parent;
    };
    for directory in pending {
        cache.insert(directory, safe);
    }
    Ok(safe)
}
fn fuzzy(text: &str, query: &[char]) -> Option<i64> {
    let mut matched = 0;
    let mut first = 0;
    let mut last = 0;
    let mut consecutive = 0;
    let mut boundaries = 0;
    let mut previous = '/';
    for (i, c) in text.chars().enumerate() {
        if c == query[matched] {
            if matched == 0 {
                first = i;
            } else if i == last + 1 {
                consecutive += 1;
            }
            if matches!(previous, '/' | '_' | '-' | '.' | ' ') {
                boundaries += 1;
            }
            matched += 1;
            last = i;
            if matched == query.len() {
                return Some(
                    4000 + consecutive * 12 + boundaries * 8
                        - first as i64 * 2
                        - (last + 1 - query.len()) as i64,
                );
            }
        }
        previous = c;
    }
    None
}
fn score(entry: &Entry, query: &str, chars: &[char]) -> Option<i64> {
    let base = if entry.name == query {
        10000
    } else if entry.name.starts_with(query) {
        9000
    } else if entry.name.contains(query) {
        8000
    } else if entry.folded.starts_with(query) {
        7000
    } else if entry.folded.contains(query) {
        6000
    } else {
        fuzzy(&entry.name, chars)
            .map(|s| s + 1000)
            .or_else(|| fuzzy(&entry.folded, chars))?
    };
    Some(base - entry.path.matches('/').count() as i64 * 2)
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn ranks_basename_prefix_path_substring_and_fuzzy_with_stable_full_paths() {
        let index = Index::from_paths(
            [
                "src/main.rs",
                "tests/main.rs",
                "main.rs",
                "src/my_main.rs",
                "src/migration.rs",
            ]
            .map(String::from),
        )
        .unwrap();
        let hits = index.search("MAIN", 50).unwrap();
        assert_eq!(
            hits.paths,
            vec![
                "main.rs",
                "src/main.rs",
                "tests/main.rs",
                "src/my_main.rs",
                "src/migration.rs"
            ]
        );
        assert_eq!(
            index.search("smr", 50).unwrap().paths,
            vec![
                "src/main.rs",
                "src/my_main.rs",
                "src/migration.rs",
                "tests/main.rs"
            ]
        );
        assert_eq!(index.search("src/m", 1).unwrap().total, 3);
        assert_eq!(index.search("missing", 50).unwrap().total, 0);
    }
    #[test]
    fn unicode_spaces_duplicates_limits_and_cancellation() {
        let index = Index::from_paths(
            ["中文/测试 文件.rs", "中文/测试 文件.rs", "other/测试.rs"].map(String::from),
        )
        .unwrap();
        assert_eq!(index.len(), 2);
        assert_eq!(
            index.search("测 文", 50).unwrap().paths,
            vec!["中文/测试 文件.rs"]
        );
        assert_eq!(index.search("测试", 50).unwrap().paths.len(), 2);
        assert!(index.search(&"a".repeat(257), 50).is_err());
        assert!(Index::from_paths(["../outside".into()]).is_err());
        let token = crate::process::Cancellation::default();
        token.cancel();
        assert!(crate::process::scope(token, || index.search("测", 50)).is_err());
        let many = Index::from_paths((0..200).map(|i| format!("file{i:03}"))).unwrap();
        assert_eq!(many.search("", 50).unwrap().paths.len(), 20);
        assert_eq!(
            many.search("file", 5).unwrap().paths,
            (0..5).map(|i| format!("file{i:03}")).collect::<Vec<_>>()
        );
        assert!(many.search("file", 0).unwrap().paths.is_empty());
    }
}
