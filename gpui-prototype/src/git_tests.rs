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

#[test]
fn refresh_tracks_external_edits_commits_and_branch_switches() {
    let f = Fixture::new();
    std::fs::write(f.0.join("a"), "original\n").unwrap();
    let original = f.commit();
    std::fs::write(f.0.join("a"), "external\n").unwrap();
    let selected = selection(&f.0, &BrowseMode::Workspace).unwrap();
    let active = (selected.files[0].clone(), selected.comparison.clone());
    let refreshed =
        refresh_snapshot(&f.0, &BrowseMode::Workspace, Some(active.clone()), true).unwrap();
    assert_eq!(
        refreshed.active.unwrap().2.right_document.text.as_ref(),
        "external\n"
    );
    let latest = f.commit();
    let refreshed =
        refresh_snapshot(&f.0, &BrowseMode::Workspace, Some(active.clone()), true).unwrap();
    assert!(refreshed.selection.files.is_empty());
    let (_, comparison, diff) = refreshed.active.unwrap();
    assert_eq!(comparison.left, Revision::Head(latest));
    assert!(diff.blocks.is_empty());
    git(&f.0, &["checkout", "-b", "previous", &original]).unwrap();
    let refreshed = refresh_snapshot(&f.0, &BrowseMode::Workspace, Some(active), true).unwrap();
    assert_eq!(refreshed.repo.branch, "previous");
    assert_eq!(
        refreshed.active.unwrap().2.right_document.text.as_ref(),
        "original\n"
    );
}

#[test]
fn linked_worktree_watches_private_and_shared_metadata() {
    let f = Fixture::new();
    std::fs::write(f.0.join("a"), "original\n").unwrap();
    f.commit();
    let linked = f.0.join("linked");
    git(
        &f.0,
        &["worktree", "add", "-b", "linked", linked.to_str().unwrap()],
    )
    .unwrap();
    let directories = metadata_directories(&linked).unwrap();
    assert_eq!(directories.len(), 2);
    assert!(directories.contains(&f.0.join(".git").canonicalize().unwrap()));
    assert!(directories.iter().all(|p| p.is_absolute() && p.is_dir()));
    assert!(directories.iter().any(|p| p.ends_with("worktrees/linked")));
}

#[test]
fn refresh_after_committed_rename_uses_new_head_path() {
    let f = Fixture::new();
    std::fs::write(f.0.join("old"), "same\n").unwrap();
    f.commit();
    std::fs::rename(f.0.join("old"), f.0.join("new")).unwrap();
    git(&f.0, &["add", "-A"]).unwrap();
    let selected = selection(&f.0, &BrowseMode::Workspace).unwrap();
    let active = (selected.files[0].clone(), selected.comparison.clone());
    assert_eq!(active.0.old_path, "old");
    f.commit();
    let refreshed = refresh_snapshot(&f.0, &BrowseMode::Workspace, Some(active), true).unwrap();
    let (file, _, diff) = refreshed.active.unwrap();
    assert_eq!(file.old_path, "new");
    assert!(diff.blocks.is_empty());
    assert_eq!(diff.left_document.text.as_ref(), "same\n");
}

#[test]
fn branch_create_switch_and_failed_checkout_preserve_worktree() {
    let f = Fixture::new();
    std::fs::write(f.0.join("a"), "original\n").unwrap();
    let original = f.commit();
    crate::branches::create(&f.0, "feature", "HEAD").unwrap();
    std::fs::write(f.0.join("a"), "target\n").unwrap();
    f.commit();
    crate::branches::switch(&f.0, "refs/heads/main", None).unwrap();
    assert_eq!(
        std::fs::read_to_string(f.0.join("a")).unwrap(),
        "original\n"
    );
    std::fs::write(f.0.join("a"), "unsaved-on-disk\n").unwrap();
    let index = git(&f.0, &["write-tree"]).unwrap();
    assert!(crate::branches::switch(&f.0, "refs/heads/feature", None).is_err());
    assert!(crate::branches::create(&f.0, "failed", "feature").is_err());
    let repo = snapshot(&f.0).unwrap();
    assert_eq!(repo.branch, "main");
    assert_eq!(repo.history_tip.as_deref(), Some(original.as_str()));
    assert_eq!(
        std::fs::read_to_string(f.0.join("a")).unwrap(),
        "unsaved-on-disk\n"
    );
    assert_eq!(git(&f.0, &["write-tree"]).unwrap(), index);
    assert!(!repo.branches.iter().any(|b| b.name == "failed"));
    for name in [
        "", "-option", "bad name", "a..b", "HEAD", "@{-1}", "a\nb", "main",
    ] {
        assert!(
            crate::branches::create(&f.0, name, "HEAD").is_err(),
            "{name}"
        );
    }
    // Safe, non-overlapping local changes remain available when Git allows checkout.
    std::fs::write(f.0.join("a"), "original\n").unwrap();
    std::fs::write(f.0.join("untracked"), "keep").unwrap();
    crate::branches::switch(&f.0, "refs/heads/feature", None).unwrap();
    assert_eq!(
        std::fs::read_to_string(f.0.join("untracked")).unwrap(),
        "keep"
    );
}

#[test]
fn branch_list_and_remote_tracking_include_upstream_and_skip_symbolic_head() {
    let f = Fixture::new();
    std::fs::write(f.0.join("a"), "original\n").unwrap();
    f.commit();
    let remote = f.0.join(".git/upstream.git");
    git(&f.0, &["init", "--bare", remote.to_str().unwrap()]).unwrap();
    git(&f.0, &["remote", "add", "origin", remote.to_str().unwrap()]).unwrap();
    git(&f.0, &["push", "-u", "origin", "main"]).unwrap();
    git(
        &f.0,
        &[
            "symbolic-ref",
            "refs/remotes/origin/HEAD",
            "refs/remotes/origin/main",
        ],
    )
    .unwrap();
    let branches = crate::branches::list(&f.0).unwrap();
    let main = branches
        .iter()
        .find(|b| b.reference == "refs/heads/main")
        .unwrap();
    assert!(main.current);
    assert_eq!(main.upstream, "refs/remotes/origin/main");
    assert_eq!(branches.iter().filter(|b| b.remote).count(), 1);
    assert_eq!(
        branches
            .iter()
            .find(|b| b.remote)
            .unwrap()
            .local_name
            .as_deref(),
        Some("main")
    );
    assert!(crate::branches::switch(&f.0, "refs/remotes/origin/main", None).is_err()); // Existing local branch.
    crate::branches::switch(&f.0, "refs/remotes/origin/main", Some("tracking/main")).unwrap();
    let branches = crate::branches::list(&f.0).unwrap();
    let tracked = branches.iter().find(|b| b.current).unwrap();
    assert_eq!(tracked.name, "tracking/main");
    assert_eq!(tracked.upstream, "refs/remotes/origin/main");
    std::fs::write(f.0.join("a"), "ahead\n").unwrap();
    f.commit();
    assert!(
        crate::branches::list(&f.0)
            .unwrap()
            .iter()
            .find(|b| b.current)
            .unwrap()
            .tracking
            .contains("ahead 1")
    );
}

#[test]
fn branch_creation_supports_unborn_and_pinned_base_and_refuses_non_commit() {
    let f = Fixture::new();
    crate::branches::create(&f.0, "first", "HEAD").unwrap();
    assert_eq!(snapshot(&f.0).unwrap().branch, "first");
    std::fs::write(f.0.join("a"), "original\n").unwrap();
    let original = f.commit();
    std::fs::write(f.0.join("a"), "new\n").unwrap();
    f.commit();
    git(&f.0, &["tag", "tagged", &original]).unwrap();
    crate::branches::create(&f.0, "from-tag", "tagged").unwrap();
    assert_eq!(
        snapshot(&f.0).unwrap().history_tip.as_deref(),
        Some(original.as_str())
    );
    for base in ["INDEX", "WORKTREE", "EMPTY", "--option"] {
        assert!(crate::branches::create(&f.0, "invalid-base", base).is_err());
    }
    git(&f.0, &["checkout", "--detach", &original]).unwrap();
    assert!(
        !crate::branches::list(&f.0)
            .unwrap()
            .iter()
            .any(|b| b.current)
    );
    crate::branches::switch(&f.0, "refs/heads/from-tag", None).unwrap();
    assert_eq!(snapshot(&f.0).unwrap().branch, "from-tag");
    assert!(!snapshot(&f.0).unwrap().detached);
}

#[test]
fn reset_modes_match_head_index_and_worktree_and_reject_stale_confirmation() {
    use crate::operations::{self, ResetMode};
    for mode in [ResetMode::Soft, ResetMode::Mixed, ResetMode::Hard] {
        let f = Fixture::new();
        std::fs::write(f.0.join("a"), "original\n").unwrap();
        let original = f.commit();
        std::fs::write(f.0.join("a"), "latest\n").unwrap();
        let latest = f.commit();
        std::fs::write(f.0.join("a"), "staged\n").unwrap();
        git(&f.0, &["add", "a"]).unwrap();
        std::fs::write(f.0.join("a"), "working\n").unwrap();
        std::fs::write(f.0.join("untracked"), "keep").unwrap();
        assert!(operations::reset(&f.0, &original, mode, Some(&original), Some("main")).is_err());
        assert!(operations::reset(&f.0, &original, mode, Some(&latest), Some("other")).is_err());
        assert_eq!(std::fs::read_to_string(f.0.join("a")).unwrap(), "working\n");
        operations::reset(&f.0, &original, mode, Some(&latest), Some("main")).unwrap();
        assert_eq!(
            snapshot(&f.0).unwrap().history_tip.as_deref(),
            Some(original.as_str())
        );
        let expected_index = if mode == ResetMode::Soft {
            b"staged\n".as_slice()
        } else {
            b"original\n".as_slice()
        };
        assert_eq!(git(&f.0, &["show", ":a"]).unwrap(), expected_index);
        assert_eq!(
            std::fs::read_to_string(f.0.join("a")).unwrap(),
            if mode == ResetMode::Hard {
                "original\n"
            } else {
                "working\n"
            }
        );
        assert_eq!(
            std::fs::read_to_string(f.0.join("untracked")).unwrap(),
            "keep"
        );
        assert_eq!(
            string(git(&f.0, &["rev-parse", "ORIG_HEAD"]).unwrap())
                .unwrap()
                .trim(),
            latest
        );
    }
}

#[test]
fn merge_fast_forward_merge_commit_and_conflict_preserve_git_state() {
    use crate::operations;
    let f = Fixture::new();
    std::fs::write(f.0.join("a"), "original\n").unwrap();
    f.commit();
    crate::branches::create(&f.0, "feature", "HEAD").unwrap();
    std::fs::write(f.0.join("a"), "feature\n").unwrap();
    let feature = f.commit();
    crate::branches::switch(&f.0, "refs/heads/main", None).unwrap();
    operations::merge(&f.0, "refs/heads/feature").unwrap();
    assert_eq!(
        snapshot(&f.0).unwrap().history_tip.as_deref(),
        Some(feature.as_str())
    );
    git(
        &f.0,
        &["update-ref", "refs/remotes/origin/feature", &feature],
    )
    .unwrap();
    crate::branches::create(&f.0, "remote-merge", "main~1").unwrap();
    operations::merge(&f.0, "refs/remotes/origin/feature").unwrap();
    assert_eq!(
        snapshot(&f.0).unwrap().history_tip.as_deref(),
        Some(feature.as_str())
    );
    crate::branches::switch(&f.0, "refs/heads/main", None).unwrap();
    std::fs::write(f.0.join("main-only"), "main\n").unwrap();
    f.commit();
    crate::branches::switch(&f.0, "refs/heads/feature", None).unwrap();
    std::fs::write(f.0.join("feature-only"), "feature\n").unwrap();
    f.commit();
    crate::branches::switch(&f.0, "refs/heads/main", None).unwrap();
    operations::merge(&f.0, "refs/heads/feature").unwrap();
    assert_eq!(
        string(git(&f.0, &["rev-list", "--parents", "-n", "1", "HEAD"]).unwrap())
            .unwrap()
            .split_whitespace()
            .count(),
        3
    );
    std::fs::write(f.0.join("a"), "main conflict\n").unwrap();
    let before_conflict = f.commit();
    crate::branches::switch(&f.0, "refs/heads/feature", None).unwrap();
    std::fs::write(f.0.join("a"), "feature conflict\n").unwrap();
    f.commit();
    crate::branches::switch(&f.0, "refs/heads/main", None).unwrap();
    let error = operations::merge(&f.0, "refs/heads/feature")
        .unwrap_err()
        .to_string();
    assert!(error.contains("CONFLICT"), "{error}");
    assert_eq!(
        snapshot(&f.0).unwrap().history_tip.as_deref(),
        Some(before_conflict.as_str())
    );
    assert!(!git(&f.0, &["ls-files", "-u"]).unwrap().is_empty());
    assert!(
        selection(&f.0, &BrowseMode::Workspace)
            .unwrap()
            .files
            .iter()
            .any(|file| file.path == "a")
    );
}

#[test]
fn local_remote_fetch_pull_push_and_rejections() {
    use crate::operations::{self, RemoteOperation};
    let f = Fixture::new();
    std::fs::write(f.0.join("a"), "original\n").unwrap();
    f.commit();
    let remote = f.0.join(".git/upstream.git");
    git(&f.0, &["init", "--bare", remote.to_str().unwrap()]).unwrap();
    git(&f.0, &["remote", "add", "origin", remote.to_str().unwrap()]).unwrap();
    operations::remote(&f.0, RemoteOperation::Push, "origin").unwrap();
    assert_eq!(
        crate::branches::list(&f.0)
            .unwrap()
            .iter()
            .find(|b| b.current)
            .unwrap()
            .upstream,
        "refs/remotes/origin/main"
    );
    let other = f.0.join(".git/other");
    git(
        &f.0,
        &[
            "clone",
            "-b",
            "main",
            remote.to_str().unwrap(),
            other.to_str().unwrap(),
        ],
    )
    .unwrap();
    git(&other, &["config", "user.name", "Test"]).unwrap();
    git(&other, &["config", "user.email", "test@example.invalid"]).unwrap();
    std::fs::write(other.join("a"), "remote change\n").unwrap();
    git(&other, &["add", "a"]).unwrap();
    git(&other, &["commit", "-m", "remote change"]).unwrap();
    git(&other, &["push"]).unwrap();
    operations::remote(&f.0, RemoteOperation::Fetch, "origin").unwrap();
    assert!(
        crate::branches::list(&f.0)
            .unwrap()
            .iter()
            .find(|b| b.current)
            .unwrap()
            .tracking
            .contains("behind 1")
    );
    operations::remote(&f.0, RemoteOperation::Pull, "origin").unwrap();
    assert_eq!(
        std::fs::read_to_string(f.0.join("a")).unwrap(),
        "remote change\n"
    );
    std::fs::write(f.0.join("local"), "local commit\n").unwrap();
    f.commit();
    std::fs::write(other.join("remote"), "other commit\n").unwrap();
    git(&other, &["add", "remote"]).unwrap();
    git(&other, &["commit", "-m", "other"]).unwrap();
    git(&other, &["push"]).unwrap();
    let before = snapshot(&f.0).unwrap().history_tip;
    assert!(operations::remote(&f.0, RemoteOperation::Push, "origin").is_err());
    assert_eq!(snapshot(&f.0).unwrap().history_tip, before);
    assert!(operations::remote(&f.0, RemoteOperation::Fetch, "missing").is_err());
    git(
        &f.0,
        &["remote", "set-url", "origin", "./nonexistent-remote"],
    )
    .unwrap();
    assert!(operations::remote(&f.0, RemoteOperation::Fetch, "origin").is_err());
    assert_eq!(snapshot(&f.0).unwrap().history_tip, before);
}

#[test]
fn pull_conflict_reports_conflict_and_leaves_index_inspectable() {
    use crate::operations::{self, RemoteOperation};
    let f = Fixture::new();
    std::fs::write(f.0.join("a"), "original\n").unwrap();
    f.commit();
    let remote = f.0.join(".git/upstream.git");
    git(&f.0, &["init", "--bare", remote.to_str().unwrap()]).unwrap();
    git(&f.0, &["remote", "add", "origin", remote.to_str().unwrap()]).unwrap();
    operations::remote(&f.0, RemoteOperation::Push, "origin").unwrap();
    let other = f.0.join(".git/other");
    git(
        &f.0,
        &[
            "clone",
            "-b",
            "main",
            remote.to_str().unwrap(),
            other.to_str().unwrap(),
        ],
    )
    .unwrap();
    git(&other, &["config", "user.name", "Test"]).unwrap();
    git(&other, &["config", "user.email", "test@example.invalid"]).unwrap();
    std::fs::write(other.join("a"), "remote\n").unwrap();
    git(&other, &["add", "a"]).unwrap();
    git(&other, &["commit", "-m", "remote"]).unwrap();
    git(&other, &["push"]).unwrap();
    std::fs::write(f.0.join("a"), "local\n").unwrap();
    let local = f.commit();
    git(&f.0, &["config", "pull.rebase", "false"]).unwrap();
    let error = operations::remote(&f.0, RemoteOperation::Pull, "origin")
        .unwrap_err()
        .to_string();
    assert!(error.contains("CONFLICT"), "{error}");
    assert_eq!(
        snapshot(&f.0).unwrap().history_tip.as_deref(),
        Some(local.as_str())
    );
    assert!(!git(&f.0, &["ls-files", "-u"]).unwrap().is_empty());
    assert!(
        std::fs::read_to_string(f.0.join("a"))
            .unwrap()
            .contains("<<<<<<<")
    );
}

#[test]
#[cfg(unix)]
fn remote_honors_configured_ssh_and_reports_authentication_failure() {
    use std::os::unix::fs::PermissionsExt;
    let f = Fixture::new();
    std::fs::write(f.0.join("a"), "original\n").unwrap();
    let before = f.commit();
    let ssh = f.0.join(".git/test-ssh");
    std::fs::write(
        &ssh,
        "#!/bin/sh\necho 'mygit-test-auth-denied: Permission denied (publickey).' >&2\nexit 255\n",
    )
    .unwrap();
    std::fs::set_permissions(&ssh, std::fs::Permissions::from_mode(0o700)).unwrap();
    let command = format!("'{}'", ssh.to_str().unwrap().replace('\'', "'\\''"));
    git(&f.0, &["config", "core.sshCommand", &command]).unwrap();
    git(
        &f.0,
        &[
            "remote",
            "add",
            "origin",
            "ssh://git@example.invalid/repository",
        ],
    )
    .unwrap();
    let error =
        crate::operations::remote(&f.0, crate::operations::RemoteOperation::Fetch, "origin")
            .unwrap_err()
            .to_string();
    assert!(error.contains("mygit-test-auth-denied"), "{error}");
    assert_eq!(
        snapshot(&f.0).unwrap().history_tip.as_deref(),
        Some(before.as_str())
    );
}

#[test]
fn history_search_finds_unloaded_body_author_sha_and_paginates_without_duplicates() {
    use crate::history::{self, Filter};
    let f = Fixture::new();
    std::fs::write(f.0.join("a"), "base").unwrap();
    git(&f.0, &["add", "a"]).unwrap();
    let tree = string(git(&f.0, &["write-tree"]).unwrap())
        .unwrap()
        .trim()
        .to_owned();
    let mut parent = String::new();
    let mut oldest = String::new();
    for i in 0..530 {
        let message = if i == 0 {
            "old subject\n\nUNLOADED 正文 keyword".to_owned()
        } else {
            format!("commit {i}")
        };
        let mut args = vec!["commit-tree", &tree, "-m", &message];
        if !parent.is_empty() {
            args.extend(["-p", &parent]);
        }
        parent = string(git(&f.0, &args).unwrap()).unwrap().trim().to_owned();
        if i == 0 {
            oldest = parent.clone();
        }
    }
    git(&f.0, &["update-ref", "refs/heads/main", &parent]).unwrap();
    let repo = snapshot(&f.0).unwrap();
    assert!(!repo.commits.iter().any(|c| c.sha == oldest));
    for text in ["unloaded 正文", "tEsT", &oldest[..10]] {
        let query = history::prepare(
            &f.0,
            Filter {
                text: text.into(),
                ..Default::default()
            },
        )
        .unwrap();
        let page = history::page(&f.0, &query, 0).unwrap();
        if text != "tEsT" {
            assert_eq!(page.commits.len(), 1);
            assert_eq!(page.commits[0].sha, oldest);
        } else {
            assert_eq!(page.commits.len(), 100);
            assert!(page.more);
        }
    }
    let query = history::prepare(
        &f.0,
        Filter {
            author: "test@example.invalid".into(),
            ..Default::default()
        },
    )
    .unwrap();
    let first = history::page(&f.0, &query, 0).unwrap();
    assert_eq!(first.commits.len(), 100);
    assert!(first.more);
    let new =
        string(git(&f.0, &["commit-tree", &tree, "-p", &parent, "-m", "newer"]).unwrap()).unwrap();
    git(&f.0, &["update-ref", "refs/heads/main", new.trim()]).unwrap();
    let second = history::page(&f.0, &query, first.next).unwrap();
    assert_eq!(second.commits.len(), 100);
    assert!(second.more);
    assert!(
        second
            .commits
            .iter()
            .all(|c| !first.commits.iter().any(|a| a.sha == c.sha))
    );
    let mut all = first.commits;
    let mut next = second.next;
    let mut more = second.more;
    all.extend(second.commits);
    while more {
        let page = history::page(&f.0, &query, next).unwrap();
        next = page.next;
        more = page.more;
        all.extend(page.commits);
    }
    assert_eq!(all.len(), 530);
    assert_eq!(
        all.iter()
            .map(|commit| &commit.sha)
            .collect::<std::collections::HashSet<_>>()
            .len(),
        530
    );
    assert_eq!(all.last().unwrap().sha, oldest);
    let query = history::prepare(
        &f.0,
        Filter {
            text: "[not a regex]".into(),
            ..Default::default()
        },
    )
    .unwrap();
    assert!(history::page(&f.0, &query, 0).unwrap().commits.is_empty());
}

#[test]
fn history_scope_dates_and_renamed_file_directory_paths_are_distinct() {
    use crate::history::{self, Filter};
    let f = Fixture::new();
    std::fs::create_dir(f.0.join("one")).unwrap();
    std::fs::create_dir(f.0.join("two")).unwrap();
    std::fs::write(f.0.join("one/same"), "one\n").unwrap();
    let original = f.commit();
    std::fs::write(f.0.join("two/same"), "two\n").unwrap();
    let two = f.commit();
    std::fs::rename(f.0.join("one/same"), f.0.join("one/moved")).unwrap();
    let moved = f.commit();
    std::fs::write(f.0.join("one/moved"), "changed\n").unwrap();
    let changed = f.commit();
    let query = history::prepare(
        &f.0,
        Filter {
            path: Some("one/moved".into()),
            follow: true,
            ..Default::default()
        },
    )
    .unwrap();
    let page = history::page(&f.0, &query, 0).unwrap();
    assert_eq!(
        page.commits
            .iter()
            .map(|c| c.sha.as_str())
            .collect::<Vec<_>>(),
        vec![changed.as_str(), moved.as_str(), original.as_str()]
    );
    assert!(!page.commits.iter().any(|c| c.sha == two));
    let query = history::prepare(
        &f.0,
        Filter {
            path: Some("two".into()),
            ..Default::default()
        },
    )
    .unwrap();
    assert_eq!(history::page(&f.0, &query, 0).unwrap().commits[0].sha, two);
    crate::branches::create(&f.0, "other", &original).unwrap();
    std::fs::write(f.0.join("other"), "branch-only").unwrap();
    let other = f.commit();
    crate::branches::switch(&f.0, "refs/heads/main", None).unwrap();
    let query = history::prepare(
        &f.0,
        Filter {
            scope: "ALL".into(),
            text: "fixture".into(),
            ..Default::default()
        },
    )
    .unwrap();
    assert!(
        history::page(&f.0, &query, 0)
            .unwrap()
            .commits
            .iter()
            .any(|c| c.sha == other)
    );
    let query = history::prepare(
        &f.0,
        Filter {
            scope: "other".into(),
            ..Default::default()
        },
    )
    .unwrap();
    assert_eq!(history::page(&f.0, &query, 0).unwrap().commits.len(), 2);
    let query = history::prepare(
        &f.0,
        Filter {
            since: "2099-01-01".into(),
            ..Default::default()
        },
    )
    .unwrap();
    assert!(history::page(&f.0, &query, 0).unwrap().commits.is_empty());
    for since in ["2026-02-30", "2026-13-01", "not-date", "2026-+2-01"] {
        assert!(
            history::prepare(
                &f.0,
                Filter {
                    since: since.into(),
                    ..Default::default()
                }
            )
            .is_err()
        );
    }
    assert!(
        history::prepare(
            &f.0,
            Filter {
                path: Some("../outside".into()),
                ..Default::default()
            }
        )
        .is_err()
    );
    assert!(
        history::prepare(
            &f.0,
            Filter {
                scope: "--option".into(),
                ..Default::default()
            }
        )
        .is_err()
    );
}

#[test]
fn file_history_pagination_follows_rename_past_first_page() {
    use crate::history::{self, Filter};
    let f = Fixture::new();
    std::fs::write(f.0.join("old"), "original\n").unwrap();
    let original = f.commit();
    std::fs::rename(f.0.join("old"), f.0.join("new")).unwrap();
    let renamed = f.commit();
    let tree_one = string(git(&f.0, &["write-tree"]).unwrap())
        .unwrap()
        .trim()
        .to_owned();
    std::fs::write(f.0.join("new"), "changed\n").unwrap();
    git(&f.0, &["add", "new"]).unwrap();
    let tree_two = string(git(&f.0, &["write-tree"]).unwrap())
        .unwrap()
        .trim()
        .to_owned();
    let mut parent = renamed.clone();
    for index in 0..105 {
        let tree = if index % 2 == 0 { &tree_two } else { &tree_one };
        parent = string(
            git(
                &f.0,
                &[
                    "commit-tree",
                    tree,
                    "-p",
                    &parent,
                    "-m",
                    &format!("edit {index}"),
                ],
            )
            .unwrap(),
        )
        .unwrap()
        .trim()
        .to_owned();
    }
    git(&f.0, &["update-ref", "refs/heads/main", &parent]).unwrap();
    let query = history::prepare(
        &f.0,
        Filter {
            path: Some("new".into()),
            follow: true,
            ..Default::default()
        },
    )
    .unwrap();
    let first = history::page(&f.0, &query, 0).unwrap();
    assert_eq!(first.commits.len(), 100);
    assert!(first.more);
    let second = history::page(&f.0, &query, first.next).unwrap();
    assert_eq!(second.commits.len(), 7);
    assert!(!second.more);
    assert!(second.commits.iter().any(|commit| commit.sha == renamed));
    assert_eq!(second.commits.last().unwrap().sha, original);
    assert!(
        second
            .commits
            .iter()
            .all(|commit| !first.commits.iter().any(|old| old.sha == commit.sha))
    );
}

#[test]
fn history_date_filter_traverses_out_of_order_commit_dates() {
    use crate::history::{self, Filter};
    let f = Fixture::new();
    std::fs::write(f.0.join("a"), "base").unwrap();
    git(&f.0, &["add", "a"]).unwrap();
    let tree = string(git(&f.0, &["write-tree"]).unwrap())
        .unwrap()
        .trim()
        .to_owned();
    let commit = |date: &str, parent: Option<&str>| {
        let mut command = Command::new("git");
        command
            .arg("-C")
            .arg(&f.0)
            .args(["commit-tree", &tree, "-m", "dated"])
            .env("GIT_AUTHOR_DATE", date)
            .env("GIT_COMMITTER_DATE", date);
        if let Some(parent) = parent {
            command.args(["-p", parent]);
        }
        let output =
            crate::process::output(&mut command, std::time::Duration::from_secs(2)).unwrap();
        assert!(output.status.success());
        string(output.stdout).unwrap().trim().to_owned()
    };
    let future = commit("2030-01-15T00:00:00Z", None);
    let past = commit("2020-01-15T00:00:00Z", Some(&future));
    git(&f.0, &["update-ref", "refs/heads/main", &past]).unwrap();
    let query = history::prepare(
        &f.0,
        Filter {
            since: "2025-01-01".into(),
            until: "2031-01-01".into(),
            ..Default::default()
        },
    )
    .unwrap();
    let page = history::page(&f.0, &query, 0).unwrap();
    assert_eq!(page.commits.len(), 1);
    assert_eq!(page.commits[0].sha, future);
    assert!(
        history::prepare(
            &f.0,
            Filter {
                since: "2031-01-01".into(),
                until: "2025-01-01".into(),
                ..Default::default()
            }
        )
        .is_err()
    );
}

#[test]
fn blame_distinguishes_commit_index_and_worktree_and_preserves_raw_lines() {
    use crate::blame;
    let f = Fixture::new();
    std::fs::write(f.0.join("file"), "a\r\nb\r\nc").unwrap();
    let original = f.commit();
    std::fs::write(f.0.join("file"), "a\r\nnew b\r\nc").unwrap();
    let latest = f.commit();
    let committed = blame::annotate(
        &f.0,
        &Revision::Commit(original.clone()),
        "file",
        "file",
        "a\r\nb\r\nc",
    )
    .unwrap();
    assert_eq!(committed.len(), 3);
    assert!(committed.iter().all(|line| line.commit.sha == original));
    std::fs::write(f.0.join("file"), "a\r\nstaged\r\nnew b\r\nc").unwrap();
    git(&f.0, &["add", "file"]).unwrap();
    std::fs::write(f.0.join("file"), "a\r\nworking\r\nnew b\r\nc\r\nadded\r\n").unwrap();
    let index = blame::annotate(
        &f.0,
        &Revision::Index,
        "file",
        "file",
        "a\r\nstaged\r\nnew b\r\nc",
    )
    .unwrap();
    assert_eq!(index[0].commit.sha, original);
    assert!(index[1].commit.uncommitted());
    assert_eq!(index[2].commit.sha, latest);
    let working = blame::annotate(
        &f.0,
        &Revision::Worktree,
        "file",
        "file",
        "a\r\nworking\r\nnew b\r\nc\r\nadded\r\n",
    )
    .unwrap();
    assert_eq!(working.len(), 5);
    assert!(working[1].commit.uncommitted());
    assert!(working[4].commit.uncommitted());
    assert_eq!(working[2].commit.sha, latest);
    assert!(blame::annotate(&f.0, &Revision::Index, "file", "file", "stale").is_err());
    assert!(blame::annotate(&f.0, &Revision::Worktree, "file", "file", "stale").is_err());
}

#[test]
fn blame_follows_staged_and_committed_rename_and_handles_quoted_paths() {
    use crate::blame;
    let f = Fixture::new();
    let old = "old\tname\nfile";
    let new = "new 中文\tname";
    std::fs::write(f.0.join(old), "original\nsecond\n").unwrap();
    let original = f.commit();
    std::fs::rename(f.0.join(old), f.0.join(new)).unwrap();
    git(&f.0, &["add", "-A"]).unwrap();
    let index = blame::annotate(&f.0, &Revision::Index, new, old, "original\nsecond\n").unwrap();
    assert!(index.iter().all(|line| line.commit.sha == original));
    assert_eq!(index[0].path.as_ref(), old);
    let working =
        blame::annotate(&f.0, &Revision::Worktree, new, new, "original\nsecond\n").unwrap();
    assert!(working.iter().all(|line| line.commit.sha == original));
    let renamed = f.commit();
    let committed = blame::annotate(
        &f.0,
        &Revision::Commit(renamed),
        new,
        new,
        "original\nsecond\n",
    )
    .unwrap();
    assert!(committed.iter().all(|line| line.commit.sha == original));
    assert_eq!(committed[0].path.as_ref(), old);
    assert!(std::sync::Arc::ptr_eq(
        &committed[0].commit,
        &committed[1].commit
    ));
}

#[test]
fn blame_handles_unborn_untracked_and_rejects_special_files() {
    use crate::blame;
    let f = Fixture::new();
    std::fs::write(f.0.join("new"), "🙂new\n\n").unwrap();
    let worktree = blame::annotate(&f.0, &Revision::Worktree, "new", "new", "🙂new\n\n").unwrap();
    assert_eq!(worktree.len(), 2);
    assert!(worktree.iter().all(|line| line.commit.uncommitted()));
    git(&f.0, &["add", "new"]).unwrap();
    assert!(
        blame::annotate(&f.0, &Revision::Index, "new", "new", "🙂new\n\n")
            .unwrap()
            .iter()
            .all(|line| line.commit.uncommitted())
    );
    f.commit();
    std::fs::write(f.0.join("another"), "untracked").unwrap();
    assert!(
        blame::annotate(&f.0, &Revision::Worktree, "another", "another", "untracked").unwrap()[0]
            .commit
            .uncommitted()
    );
    assert!(blame::annotate(&f.0, &Revision::Worktree, "../outside", "new", "text").is_err());
    #[cfg(unix)]
    {
        std::os::unix::fs::symlink("new", f.0.join("link")).unwrap();
        assert!(blame::annotate(&f.0, &Revision::Worktree, "link", "link", "new").is_err());
    }
}

#[test]
fn blame_editor_buffer_marks_unsaved_lines_without_writing_files_or_index() {
    let f = Fixture::new();
    std::fs::write(f.0.join("file"), "original\nsecond\n").unwrap();
    let original = f.commit();
    let index = git(&f.0, &["write-tree"]).unwrap();
    let lines = crate::blame::annotate_buffer(&f.0, "file", "original\nunsaved\nsecond\n").unwrap();
    assert_eq!(lines.len(), 3);
    assert_eq!(lines[0].commit.sha, original);
    assert!(lines[1].commit.uncommitted());
    assert_eq!(lines[2].commit.sha, original);
    assert_eq!(
        std::fs::read_to_string(f.0.join("file")).unwrap(),
        "original\nsecond\n"
    );
    assert_eq!(git(&f.0, &["write-tree"]).unwrap(), index);
}

#[test]
fn blame_accepts_sha256_object_ids() {
    let f = Fixture::new();
    let root = f.0.join(".git/sha256");
    git(
        &f.0,
        &[
            "init",
            "--object-format=sha256",
            "-b",
            "main",
            root.to_str().unwrap(),
        ],
    )
    .unwrap();
    git(&root, &["config", "user.name", "Test"]).unwrap();
    git(&root, &["config", "user.email", "test@example.invalid"]).unwrap();
    std::fs::write(root.join("file"), "sha256\n").unwrap();
    git(&root, &["add", "file"]).unwrap();
    git(&root, &["commit", "-m", "sha256"]).unwrap();
    let sha = string(git(&root, &["rev-parse", "HEAD"]).unwrap())
        .unwrap()
        .trim()
        .to_owned();
    assert_eq!(sha.len(), 64);
    let lines = crate::blame::annotate(
        &root,
        &Revision::Commit(sha.clone()),
        "file",
        "file",
        "sha256\n",
    )
    .unwrap();
    assert_eq!(lines[0].commit.sha, sha);
}

#[test]
fn dag_history_keeps_real_merge_parents_and_refreshes_moved_refs_and_tags() {
    let f = Fixture::new();
    std::fs::write(f.0.join("root"), "root\n").unwrap();
    let root = f.commit();
    git(&f.0, &["switch", "-c", "side"]).unwrap();
    std::fs::write(f.0.join("side"), "side\n").unwrap();
    let side = f.commit();
    git(&f.0, &["switch", "main"]).unwrap();
    std::fs::write(f.0.join("main"), "main\n").unwrap();
    let main = f.commit();
    git(
        &f.0,
        &[
            "-c",
            "commit.gpgsign=false",
            "merge",
            "--no-ff",
            "--no-edit",
            "side",
        ],
    )
    .unwrap();
    let tip = string(git(&f.0, &["rev-parse", "HEAD"]).unwrap())
        .unwrap()
        .trim()
        .to_owned();
    git(
        &f.0,
        &[
            "-c",
            "tag.gpgsign=false",
            "tag",
            "-a",
            "release",
            "-m",
            "release",
            &root,
        ],
    )
    .unwrap();
    let before = snapshot(&f.0).unwrap();
    assert_eq!(before.commits[0].parents, vec![main.clone(), side.clone()]);
    for (i, commit) in before.commits.iter().enumerate() {
        assert_eq!(
            commit.parents,
            commit_detail(&f.0, &commit.sha).unwrap().parents
        );
        for parent in &commit.parents {
            assert!(
                before
                    .commits
                    .iter()
                    .position(|c| &c.sha == parent)
                    .unwrap()
                    > i
            );
        }
    }
    assert!(before.references[&root].contains("tag: release"));
    assert!(before.references[&tip].contains("HEAD"));
    assert!(before.references[&side].contains("side"));
    git(&f.0, &["branch", "-f", "side", &main]).unwrap();
    git(&f.0, &["tag", "-d", "release"]).unwrap();
    let after = snapshot(&f.0).unwrap();
    assert_eq!(before.history_tip, after.history_tip);
    assert!(!after.references.contains_key(&root));
    assert!(!after.references.contains_key(&side));
    assert!(after.references[&main].contains("side"));
    let rows = crate::graph::layout(&after.commits, false);
    assert_eq!(crate::graph::layout(&after.commits[..2], false), rows[..2]);
}

#[test]
fn merge_three_columns_union_both_parents_and_pin_renamed_deleted_and_added_paths() {
    let f = Fixture::new();
    std::fs::write(f.0.join("old name"), "one\ntwo\nthree\nfour\n").unwrap();
    std::fs::write(f.0.join("deleted"), "gone\n").unwrap();
    let initial = f.commit();
    assert!(crate::merge::selection(&f.0, &initial).is_err());
    git(&f.0, &["switch", "-c", "side"]).unwrap();
    std::fs::write(f.0.join("side only"), "side\r\n😀").unwrap();
    let side = f.commit();
    git(&f.0, &["switch", "main"]).unwrap();
    git(&f.0, &["mv", "old name", "new name"]).unwrap();
    std::fs::remove_file(f.0.join("deleted")).unwrap();
    std::fs::write(f.0.join("main only"), "main\n").unwrap();
    let main = f.commit();
    git(
        &f.0,
        &[
            "-c",
            "commit.gpgsign=false",
            "merge",
            "--no-ff",
            "--no-edit",
            "side",
        ],
    )
    .unwrap();
    let sha = string(git(&f.0, &["rev-parse", "HEAD"]).unwrap())
        .unwrap()
        .trim()
        .to_owned();
    let selection = crate::merge::selection(&f.0, &sha).unwrap();
    assert_eq!(selection.detail.parents, vec![main.clone(), side.clone()]);
    let browse = super::selection(&f.0, &BrowseMode::Merge(sha.clone())).unwrap();
    assert_eq!(
        browse
            .files
            .iter()
            .map(|f| f.path.as_str())
            .collect::<Vec<_>>(),
        selection
            .files
            .iter()
            .map(|f| f.path.as_str())
            .collect::<Vec<_>>()
    );
    assert_eq!(
        selection
            .files
            .iter()
            .map(|f| f.path.as_str())
            .collect::<Vec<_>>(),
        vec!["deleted", "main only", "new name", "side only"]
    );
    let load = |path: &str| {
        crate::merge::load(
            &f.0,
            &selection,
            selection
                .files
                .iter()
                .find(|file| file.path == path)
                .unwrap(),
            2_000_000,
        )
        .unwrap()
    };
    for file in &selection.files {
        let view = load(&file.path);
        let diff = view.pair_diff();
        for (column, side) in [
            crate::text::Side::Left,
            crate::text::Side::Right,
            crate::text::Side::Third,
        ]
        .into_iter()
        .enumerate()
        {
            let lines = crate::blame::annotate(
                &f.0,
                &Revision::Commit(view.revisions[column].clone()),
                &view.paths[column],
                &view.paths[column],
                &view.documents[column].text,
            )
            .unwrap();
            assert_eq!(lines.len(), view.documents[column].lines.len());
            assert_eq!(diff.document(side).text, view.documents[column].text);
            for (row, mapped) in view.rows.iter().enumerate() {
                assert_eq!(
                    diff.source_line(side, row),
                    mapped.lines[column].map(|n| n - 1)
                );
            }
        }
    }
    let renamed = load("new name");
    assert_eq!(renamed.paths, ["new name", "new name", "old name"]);
    assert_eq!(renamed.revisions, [main, sha, side]);
    assert!(
        renamed
            .documents
            .iter()
            .all(|d| &*d.text == "one\ntwo\nthree\nfour\n")
    );
    let deleted = load("deleted");
    assert_eq!(deleted.exists, [false, false, true]);
    assert!(deleted.documents[0].text.is_empty());
    assert!(deleted.documents[1].text.is_empty());
    assert_eq!(&*deleted.documents[2].text, "gone\n");
    let main = load("main only");
    assert_eq!(&*main.documents[0].text, "main\n");
    assert_eq!(&*main.documents[1].text, "main\n");
    assert!(main.documents[2].text.is_empty());
    let side = load("side only");
    assert!(side.documents[0].text.is_empty());
    assert_eq!(&*side.documents[1].text, "side\r\n😀");
    assert_eq!(&*side.documents[2].text, "side\r\n😀");
    std::fs::write(f.0.join("side only"), "dirty workspace\n").unwrap();
    git(&f.0, &["add", "side only"]).unwrap();
    assert_eq!(&*load("side only").documents[1].text, "side\r\n😀");
    assert_eq!(
        std::fs::read_to_string(f.0.join("side only")).unwrap(),
        "dirty workspace\n"
    );
    assert_eq!(
        git(&f.0, &["show", ":side only"]).unwrap(),
        b"dirty workspace\n"
    );
}

#[test]
fn merge_three_columns_restricted_contents_return_explicit_notice() {
    let f = Fixture::new();
    std::fs::write(f.0.join("binary"), b"a\0b").unwrap();
    f.commit();
    git(&f.0, &["switch", "-c", "side"]).unwrap();
    std::fs::write(f.0.join("binary"), b"c\0d").unwrap();
    f.commit();
    git(&f.0, &["switch", "main"]).unwrap();
    std::fs::write(f.0.join("text"), "abc\n").unwrap();
    f.commit();
    git(
        &f.0,
        &[
            "-c",
            "commit.gpgsign=false",
            "merge",
            "--no-ff",
            "--no-edit",
            "side",
        ],
    )
    .unwrap();
    let selection = crate::merge::selection(&f.0, "HEAD").unwrap();
    let binary = selection.files.iter().find(|f| f.path == "binary").unwrap();
    let view = crate::merge::load(&f.0, &selection, binary, 2_000_000).unwrap();
    assert!(view.rows.is_empty());
    assert!(view.message.unwrap().contains("二进制"));
    let text = selection.files.iter().find(|f| f.path == "text").unwrap();
    let view = crate::merge::load(&f.0, &selection, text, 1).unwrap();
    assert!(view.rows.is_empty());
    assert!(view.message.unwrap().contains("预览上限"));
}

#[test]
fn merge_three_columns_combined_budget_and_octopus_are_explicit() {
    let f = Fixture::new();
    std::fs::write(f.0.join("file"), "base\n").unwrap();
    let base = f.commit();
    git(&f.0, &["switch", "-c", "side"]).unwrap();
    std::fs::write(f.0.join("file"), "side\n").unwrap();
    let side = f.commit();
    git(&f.0, &["switch", "main"]).unwrap();
    std::fs::write(f.0.join("file"), "main\n").unwrap();
    let main = f.commit();
    assert!(
        git(
            &f.0,
            &[
                "-c",
                "commit.gpgsign=false",
                "merge",
                "--no-ff",
                "--no-edit",
                "side"
            ]
        )
        .is_err()
    );
    std::fs::write(f.0.join("file"), "done\n").unwrap();
    let merged = f.commit();
    let selection = crate::merge::selection(&f.0, &merged).unwrap();
    let view = crate::merge::load(&f.0, &selection, &selection.files[0], 12).unwrap();
    assert!(view.rows.is_empty());
    assert!(view.documents.iter().all(|d| d.text.is_empty()));
    assert!(view.message.unwrap().contains("三侧内容合计"));
    let view = crate::merge::load(&f.0, &selection, &selection.files[0], 15).unwrap();
    assert_eq!(
        view.documents
            .iter()
            .map(|d| d.text.as_ref())
            .collect::<Vec<_>>(),
        vec!["main\n", "done\n", "side\n"]
    );
    let tree = string(git(&f.0, &["rev-parse", "HEAD^{tree}"]).unwrap()).unwrap();
    let octopus = string(
        git(
            &f.0,
            &[
                "-c",
                "commit.gpgsign=false",
                "commit-tree",
                tree.trim(),
                "-p",
                &main,
                "-p",
                &side,
                "-p",
                &base,
                "-m",
                "octopus",
            ],
        )
        .unwrap(),
    )
    .unwrap();
    assert!(
        crate::merge::selection(&f.0, octopus.trim())
            .unwrap_err()
            .to_string()
            .contains("3 个父提交")
    );
}
