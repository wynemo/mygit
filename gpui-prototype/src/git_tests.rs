use super::*;
use std::sync::atomic::{AtomicU64, Ordering};
static NEXT_FIXTURE: AtomicU64 = AtomicU64::new(0);
struct Fixture(PathBuf);
impl Fixture {
    fn new() -> Self {
        let path = std::env::temp_dir().join(format!(
            "mygit-gpui-test-{}-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos(),
            NEXT_FIXTURE.fetch_add(1, Ordering::Relaxed)
        ));
        std::fs::create_dir(&path).unwrap();
        git(&path, &["init", "-b", "main"]).unwrap();
        git(&path, &["config", "user.name", "Test"]).unwrap();
        git(&path, &["config", "user.email", "test@example.invalid"]).unwrap();
        Self(path)
    }
    fn commit(&self) -> String {
        git(&self.0, &["add", "-A"]).unwrap();
        git(
            &self.0,
            &["-c", "commit.gpgsign=false", "commit", "-m", "fixture"],
        )
        .unwrap();
        string(git(&self.0, &["rev-parse", "HEAD"]).unwrap())
            .unwrap()
            .trim()
            .into()
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}
fn file_diff(f: &Fixture, mode: BrowseMode, path: &str) -> Diff {
    let selected = selection(&f.0, &mode).unwrap();
    let file = selected
        .files
        .iter()
        .find(|file| file.path == path)
        .unwrap();
    compare(&f.0, &selected.comparison, file).unwrap()
}
#[test]
fn staged_then_modified_uses_three_distinct_versions() {
    let f = Fixture::new();
    std::fs::write(f.0.join("file"), "before\n").unwrap();
    f.commit();
    std::fs::write(f.0.join("file"), "staged\n").unwrap();
    git(&f.0, &["add", "file"]).unwrap();
    std::fs::write(f.0.join("file"), "unstaged\n").unwrap();
    let staged = file_diff(&f, BrowseMode::Staged, "file");
    let unstaged = file_diff(&f, BrowseMode::Unstaged, "file");
    let overall = file_diff(&f, BrowseMode::Workspace, "file");
    assert_eq!(
        (&staged.rows[0].left[..], &staged.rows[0].right[..]),
        ("before", "staged")
    );
    assert_eq!(
        (&unstaged.rows[0].left[..], &unstaged.rows[0].right[..]),
        ("staged", "unstaged")
    );
    assert_eq!(
        (&overall.rows[0].left[..], &overall.rows[0].right[..]),
        ("before", "unstaged")
    );
    let selected = selection(&f.0, &BrowseMode::Staged).unwrap();
    assert!(matches!(selected.comparison.left, Revision::Head(_)));
    assert_eq!(selected.comparison.right, Revision::Index);
}
#[test]
fn unborn_staged_addition_and_untracked_files() {
    let f = Fixture::new();
    assert_eq!(snapshot(&f.0).unwrap().branch, "main");
    assert!(snapshot(&f.0).unwrap().commits.is_empty());
    std::fs::write(f.0.join("new"), "staged\n").unwrap();
    git(&f.0, &["add", "new"]).unwrap();
    std::fs::write(f.0.join("new"), "edited\n").unwrap();
    std::fs::write(f.0.join("untracked"), "untracked\n").unwrap();
    let staged = file_diff(&f, BrowseMode::Staged, "new");
    assert_eq!(staged.rows[0].left_no, None);
    assert_eq!(staged.rows[0].right, "staged");
    let unstaged = file_diff(&f, BrowseMode::Unstaged, "new");
    assert_eq!(
        (&unstaged.rows[0].left[..], &unstaged.rows[0].right[..]),
        ("staged", "edited")
    );
    let untracked = file_diff(&f, BrowseMode::Unstaged, "untracked");
    assert!(untracked.rows.iter().all(|r| r.left_no.is_none()));
    assert_eq!(selection(&f.0, &BrowseMode::Staged).unwrap().files.len(), 1);
    assert_eq!(
        file_diff(&f, BrowseMode::Workspace, "new").rows[0].right,
        "edited"
    );
}
#[test]
fn renamed_index_and_modified_new_path() {
    let f = Fixture::new();
    std::fs::write(f.0.join("old name.txt"), "a\nb\n").unwrap();
    f.commit();
    std::fs::rename(f.0.join("old name.txt"), f.0.join("新 name.txt")).unwrap();
    git(&f.0, &["add", "-A"]).unwrap();
    std::fs::write(f.0.join("新 name.txt"), "a\nc\n").unwrap();
    let staged = selection(&f.0, &BrowseMode::Staged).unwrap();
    assert_eq!(staged.files.len(), 1);
    assert_eq!(staged.files[0].old_path, "old name.txt");
    assert!(
        compare(&f.0, &staged.comparison, &staged.files[0])
            .unwrap()
            .blocks
            .is_empty()
    );
    let unstaged = selection(&f.0, &BrowseMode::Unstaged).unwrap();
    assert_eq!(unstaged.files[0].old_path, "新 name.txt");
    let diff = compare(&f.0, &unstaged.comparison, &unstaged.files[0]).unwrap();
    assert_eq!(
        (&diff.rows[1].left[..], &diff.rows[1].right[..]),
        ("b", "c")
    );
}
#[test]
fn deletion_in_index_and_worktree_and_recreation() {
    let f = Fixture::new();
    std::fs::write(f.0.join("file"), "old\n").unwrap();
    f.commit();
    std::fs::remove_file(f.0.join("file")).unwrap();
    let unstaged = file_diff(&f, BrowseMode::Unstaged, "file");
    assert!(unstaged.rows.iter().all(|r| r.right_no.is_none()));
    git(&f.0, &["add", "-A"]).unwrap();
    assert!(
        selection(&f.0, &BrowseMode::Unstaged)
            .unwrap()
            .files
            .is_empty()
    );
    std::fs::write(f.0.join("file"), "recreated\n").unwrap();
    let staged = file_diff(&f, BrowseMode::Staged, "file");
    assert_eq!(staged.rows[0].left, "old");
    assert_eq!(staged.rows[0].right_no, None);
    let unstaged = file_diff(&f, BrowseMode::Unstaged, "file");
    assert_eq!(unstaged.rows[0].left_no, None);
    assert_eq!(unstaged.rows[0].right, "recreated");
    let overall = file_diff(&f, BrowseMode::Workspace, "file");
    assert_eq!(
        (&overall.rows[0].left[..], &overall.rows[0].right[..]),
        ("old", "recreated")
    );
}
#[test]
fn initial_commit_history_rename_and_binary() {
    let f = Fixture::new();
    std::fs::write(f.0.join("old name.txt"), "a\nb\n").unwrap();
    let initial = f.commit();
    let selected = selection(&f.0, &BrowseMode::History(initial.clone())).unwrap();
    assert_eq!(selected.comparison.left, Revision::Empty);
    assert!(
        compare(&f.0, &selected.comparison, &selected.files[0])
            .unwrap()
            .rows
            .iter()
            .all(|r| r.left_no.is_none())
    );
    std::fs::rename(f.0.join("old name.txt"), f.0.join("new name.txt")).unwrap();
    let renamed = f.commit();
    let selected = selection(&f.0, &BrowseMode::History(renamed)).unwrap();
    assert_eq!(selected.files[0].old_path, "old name.txt");
    assert_eq!(selected.comparison.left, Revision::Commit(initial));
    assert!(
        compare(&f.0, &selected.comparison, &selected.files[0])
            .unwrap()
            .blocks
            .is_empty()
    );
    assert_eq!(snapshot(&f.0).unwrap().commits.len(), 2);
    std::fs::write(f.0.join("binary"), [0, 1, 2]).unwrap();
    assert!(
        file_diff(&f, BrowseMode::Unstaged, "binary")
            .message
            .is_some()
    );
}
#[test]
fn merge_compares_first_parent() {
    let f = Fixture::new();
    std::fs::write(f.0.join("base"), "base\n").unwrap();
    f.commit();
    git(&f.0, &["checkout", "-b", "feature"]).unwrap();
    std::fs::write(f.0.join("feature"), "feature\n").unwrap();
    f.commit();
    git(&f.0, &["checkout", "main"]).unwrap();
    std::fs::write(f.0.join("main"), "main\n").unwrap();
    let first_parent = f.commit();
    git(
        &f.0,
        &[
            "-c",
            "commit.gpgsign=false",
            "merge",
            "--no-ff",
            "feature",
            "-m",
            "merge",
        ],
    )
    .unwrap();
    let sha = string(git(&f.0, &["rev-parse", "HEAD"]).unwrap())
        .unwrap()
        .trim()
        .to_string();
    let selected = selection(&f.0, &BrowseMode::History(sha)).unwrap();
    assert_eq!(selected.files.len(), 1);
    assert_eq!(selected.files[0].path, "feature");
    assert_eq!(selected.comparison.left, Revision::Commit(first_parent));
    assert_eq!(
        compare(&f.0, &selected.comparison, &selected.files[0])
            .unwrap()
            .rows[0]
            .right,
        "feature"
    );
}
#[test]
fn nul_paths_and_conflict_notice() {
    let files = parse_files(b"R100\0old name\0new\tname\n\0M\0other\0").unwrap();
    assert_eq!(files[0].old_path, "old name");
    assert_eq!(files[0].path, "new\tname\n");
    let files = parse_files(b"U\0file\0M\0file\0").unwrap();
    assert_eq!(files.len(), 1);
    let comparison = Comparison {
        left: Revision::Index,
        right: Revision::Worktree,
    };
    assert!(
        compare(Path::new("/unused"), &comparison, &files[0])
            .unwrap()
            .message
            .is_some()
    );
}
#[test]
fn empty_and_detached_repository_browsing() {
    let f = Fixture::new();
    for mode in [
        BrowseMode::Workspace,
        BrowseMode::Staged,
        BrowseMode::Unstaged,
    ] {
        assert!(selection(&f.0, &mode).unwrap().files.is_empty());
    }
    std::fs::write(f.0.join("file"), "base\n").unwrap();
    let sha = f.commit();
    git(&f.0, &["checkout", "--detach", &sha]).unwrap();
    let repo = snapshot(&f.0).unwrap();
    assert_eq!(repo.commits.len(), 1);
    assert!(sha.starts_with(&repo.branch));
    std::fs::create_dir(f.0.join("subdir")).unwrap();
    assert_eq!(snapshot(&f.0.join("subdir")).unwrap().root, repo.root);
}

#[test]
fn history_pages_are_pinned_and_details_preserve_multiline_message() {
    let f = Fixture::new();
    std::fs::write(f.0.join("file"), "text\n").unwrap();
    git(&f.0, &["add", "."]).unwrap();
    let tree = string(git(&f.0, &["write-tree"]).unwrap())
        .unwrap()
        .trim()
        .to_owned();
    let mut parent = String::new();
    for i in 0..105 {
        let message = format!("subject {i}\n\n中文正文\nline two");
        let mut args = vec!["commit-tree", &tree, "-m", &message];
        if !parent.is_empty() {
            args.extend(["-p", &parent]);
        }
        parent = string(git(&f.0, &args).unwrap()).unwrap().trim().into();
    }
    git(&f.0, &["update-ref", "refs/heads/main", &parent]).unwrap();
    let s = snapshot(&f.0).unwrap();
    assert_eq!(s.commits.len(), 100);
    assert!(s.history_more);
    assert_eq!(s.commits[0].subject, "subject 104");
    let second = history_page(&f.0, s.history_tip.as_ref().unwrap(), 100).unwrap();
    assert_eq!(second.commits.len(), 5);
    assert!(!second.more);
    assert_eq!(second.commits[0].subject, "subject 4");
    let detail = commit_detail(&f.0, &parent).unwrap();
    assert_eq!(detail.message, "subject 104\n\n中文正文\nline two\n");
    assert_eq!(detail.author_email, "test@example.invalid");
    assert_eq!(detail.parents.len(), 1);
    let new =
        string(git(&f.0, &["commit-tree", &tree, "-p", &parent, "-m", "new"]).unwrap()).unwrap();
    git(&f.0, &["update-ref", "refs/heads/main", new.trim()]).unwrap();
    assert_eq!(
        history_page(&f.0, s.history_tip.as_ref().unwrap(), 100)
            .unwrap()
            .commits[0]
            .sha,
        second.commits[0].sha
    );
    std::fs::create_dir(f.0.join("nested")).unwrap();
    assert_eq!(snapshot(&f.0.join("nested")).unwrap().root, s.root);
    assert!(snapshot(&f.0.join("missing")).is_err());
}

#[test]
fn lazy_tree_status_rename_ignored_and_symlinks() {
    use crate::workspace::{Tree, read};
    let f = Fixture::new();
    std::fs::create_dir_all(f.0.join("a/deep")).unwrap();
    std::fs::create_dir_all(f.0.join("b")).unwrap();
    std::fs::write(f.0.join("a/same.txt"), "a\n").unwrap();
    std::fs::write(f.0.join("b/same.txt"), "b\n").unwrap();
    std::fs::write(f.0.join(".gitignore"), "ignored/\n").unwrap();
    f.commit();
    git(&f.0, &["mv", "a/same.txt", "a/renamed.txt"]).unwrap();
    std::fs::write(f.0.join("b/same.txt"), "changed\n").unwrap();
    std::fs::create_dir(f.0.join("ignored")).unwrap();
    std::fs::write(f.0.join("ignored/file"), "ignored").unwrap();
    let mut tree = Tree::new();
    tree.children = read(&f.0, &tree.expanded).unwrap();
    assert_eq!(tree.children.len(), 1);
    assert!(!tree.rows().iter().any(|(e, _)| e.name == ".git"));
    assert!(
        tree.rows()
            .iter()
            .any(|(e, _)| e.path == "b" && e.status == "变更")
    );
    assert!(
        tree.rows()
            .iter()
            .any(|(e, _)| e.path == "ignored" && e.status == "!!")
    );
    tree.expanded.insert("a".into());
    tree.expanded.insert("ignored".into());
    tree.children = read(&f.0, &tree.expanded).unwrap();
    assert!(!tree.children.contains_key("a/deep"));
    assert!(
        tree.rows()
            .iter()
            .any(|(e, d)| e.path == "a/renamed.txt" && *d == 1 && e.status.contains('R'))
    );
    assert!(
        tree.rows()
            .iter()
            .any(|(e, _)| e.path == "ignored/file" && e.status == "!!")
    );
    tree.selected = Some("a/renamed.txt".into());
    tree.children = read(&f.0, &tree.expanded).unwrap();
    assert_eq!(tree.selected.as_deref(), Some("a/renamed.txt"));
    let (comparison, file) = workspace_file(&f.0, "b/same.txt").unwrap();
    assert_eq!(file.status, "M");
    assert_eq!(compare(&f.0, &comparison, &file).unwrap().rows[0].left, "b");
    #[cfg(unix)]
    {
        std::os::unix::fs::symlink("b/same.txt", f.0.join("link")).unwrap();
        let (comparison, file) = workspace_file(&f.0, "link").unwrap();
        assert_eq!(
            compare(&f.0, &comparison, &file).unwrap().rows[0].right,
            "b/same.txt"
        );
    }
}

#[test]
fn stage_unstage_and_commit_only_index_including_unborn_and_rename() {
    let f = Fixture::new();
    git(&f.0, &["config", "commit.gpgsign", "false"]).unwrap();
    std::fs::write(f.0.join("space 中文.txt"), "first\n").unwrap();
    let path = vec!["space 中文.txt".into()];
    stage(&f.0, &path, false).unwrap();
    unstage(&f.0, &path, false).unwrap();
    assert!(
        selection(&f.0, &BrowseMode::Staged)
            .unwrap()
            .files
            .is_empty()
    );
    assert!(f.0.join(&path[0]).exists());
    stage(&f.0, &path, false).unwrap();
    assert!(commit_index(&f.0, "").is_err());
    std::fs::write(f.0.join(&path[0]), "not staged\n").unwrap();
    commit_index(&f.0, "title\n\n中文正文").unwrap();
    assert_eq!(
        string(git(&f.0, &["show", "HEAD:space 中文.txt"]).unwrap()).unwrap(),
        "first\n"
    );
    assert_eq!(
        std::fs::read_to_string(f.0.join(&path[0])).unwrap(),
        "not staged\n"
    );
    assert!(commit_index(&f.0, "empty index").is_err());
    stage(&f.0, &[], true).unwrap();
    unstage(&f.0, &[], true).unwrap();
    assert!(
        selection(&f.0, &BrowseMode::Staged)
            .unwrap()
            .files
            .is_empty()
    );
    git(&f.0, &["mv", "space 中文.txt", "renamed.txt"]).unwrap();
    let renamed = vec!["space 中文.txt".into(), "renamed.txt".into()];
    unstage(&f.0, &renamed, false).unwrap();
    assert!(
        selection(&f.0, &BrowseMode::Staged)
            .unwrap()
            .files
            .is_empty()
    );
    stage(&f.0, &renamed, false).unwrap();
    assert!(
        selection(&f.0, &BrowseMode::Staged)
            .unwrap()
            .files
            .iter()
            .any(|f| f.path == "renamed.txt")
    );
    assert!(stage(&f.0, &["../outside".into()], false).is_err());
}
#[test]
#[cfg(unix)]
fn commit_hook_failure_preserves_head_index_and_worktree() {
    use std::os::unix::fs::PermissionsExt;
    let f = Fixture::new();
    git(&f.0, &["config", "commit.gpgsign", "false"]).unwrap();
    std::fs::write(f.0.join("file"), "before\n").unwrap();
    let before = f.commit();
    std::fs::write(f.0.join("file"), "staged\n").unwrap();
    stage(&f.0, &[], true).unwrap();
    let hooks = f.0.join("hooks");
    std::fs::create_dir(&hooks).unwrap();
    let hook = hooks.join("pre-commit");
    std::fs::write(
        &hook,
        "#!/bin/sh\necho 'fixture hook rejected' >&2\nexit 1\n",
    )
    .unwrap();
    std::fs::set_permissions(&hook, std::fs::Permissions::from_mode(0o755)).unwrap();
    git(&f.0, &["config", "core.hooksPath", hooks.to_str().unwrap()]).unwrap();
    assert!(
        commit_index(&f.0, "blocked")
            .unwrap_err()
            .to_string()
            .contains("fixture hook rejected")
    );
    assert_eq!(
        string(git(&f.0, &["rev-parse", "HEAD"]).unwrap())
            .unwrap()
            .trim(),
        before
    );
    assert!(
        !selection(&f.0, &BrowseMode::Staged)
            .unwrap()
            .files
            .is_empty()
    );
    assert_eq!(
        std::fs::read_to_string(f.0.join("file")).unwrap(),
        "staged\n"
    );
}

#[test]
fn arbitrary_commit_and_worktree_comparisons_preserve_rename_targets() {
    let f = Fixture::new();
    std::fs::create_dir(f.0.join("a")).unwrap();
    std::fs::create_dir(f.0.join("b")).unwrap();
    std::fs::write(f.0.join("a/same"), "original\n").unwrap();
    std::fs::write(f.0.join("b/same"), "other\n").unwrap();
    let first = f.commit();
    git(&f.0, &["mv", "a/same", "a/renamed"]).unwrap();
    let second = f.commit();
    let comparison = Comparison {
        left: resolve_revision(&f.0, &first).unwrap(),
        right: resolve_revision(&f.0, &second).unwrap(),
    };
    let selection = comparison_selection(&f.0, &comparison).unwrap();
    assert_eq!(selection.files.len(), 1);
    assert_eq!(selection.files[0].old_path, "a/same");
    assert_eq!(selection.files[0].path, "a/renamed");
    assert!(
        compare(&f.0, &comparison, &selection.files[0])
            .unwrap()
            .blocks
            .is_empty()
    );
    std::fs::write(f.0.join("b/same"), "disk\n").unwrap();
    std::fs::write(f.0.join("untracked"), "new\n").unwrap();
    let comparison = Comparison {
        left: Revision::Commit(second),
        right: Revision::Worktree,
    };
    let selection = comparison_selection(&f.0, &comparison).unwrap();
    let file = selection.files.iter().find(|f| f.path == "b/same").unwrap();
    let d = compare(&f.0, &comparison, file).unwrap();
    assert_eq!(d.rows[0].left, "other");
    assert_eq!(d.rows[0].right, "disk");
    assert!(
        selection
            .files
            .iter()
            .any(|f| f.path == "untracked" && f.status == "??")
    );
    assert!(resolve_revision(&f.0, "--not-a-revision").is_err());
    assert!(resolve_revision(&f.0, "").is_err());
    let empty = comparison_selection(
        &f.0,
        &Comparison {
            left: Revision::Empty,
            right: Revision::Commit(first),
        },
    )
    .unwrap();
    assert_eq!(empty.files.len(), 2);
}

#[test]
fn bounded_preview_binary_encoding_large_file_and_submodule_metadata() {
    let f = Fixture::new();
    std::fs::write(f.0.join("base"), "base\n").unwrap();
    let sha = f.commit();
    std::fs::write(f.0.join("binary"), [1u8, 0, 2]).unwrap();
    let d = file_diff(&f, BrowseMode::Unstaged, "binary");
    assert!(d.message.unwrap().contains("二进制"));
    assert!(d.description.unwrap().contains("3 字节"));
    std::fs::write(f.0.join("encoding"), [0xffu8]).unwrap();
    let s = selection(&f.0, &BrowseMode::Unstaged).unwrap();
    let file = s.files.iter().find(|f| f.path == "encoding").unwrap();
    assert!(
        compare(&f.0, &s.comparison, file)
            .unwrap_err()
            .to_string()
            .contains("UTF-8")
    );
    let large = format!("{}\n", "a".repeat(1000)).repeat(2100);
    std::fs::write(f.0.join("large.txt"), large.as_bytes()).unwrap();
    let s = selection(&f.0, &BrowseMode::Unstaged).unwrap();
    let file = s.files.iter().find(|f| f.path == "large.txt").unwrap();
    let d = compare(&f.0, &s.comparison, file).unwrap();
    assert!(d.message.unwrap().contains("2 MB"));
    assert!(d.rows.is_empty());
    let d = compare_with_limit(&f.0, &s.comparison, file, 20_000_000).unwrap();
    assert_eq!(d.right_document.text.len(), large.len());
    assert_eq!(d.rows.len(), 2100);
    git(
        &f.0,
        &[
            "update-index",
            "--add",
            "--cacheinfo",
            &format!("160000,{sha},module"),
        ],
    )
    .unwrap();
    std::fs::create_dir(f.0.join("module")).unwrap();
    let d = compare(
        &f.0,
        &Comparison {
            left: Revision::Index,
            right: Revision::Worktree,
        },
        &FileChange {
            path: "module".into(),
            old_path: "module".into(),
            status: "M".into(),
        },
    )
    .unwrap();
    let message = d.message.unwrap();
    assert!(message.contains("子模块"));
    assert!(message.contains(&format!("左侧：{sha}")));
    assert!(message.contains("右侧：空/未检出"));
    let d = crate::diff::calculate(b"", &vec![b'\n'; 200_001]).unwrap();
    assert!(d.message.unwrap().contains("200000 行"));
}
