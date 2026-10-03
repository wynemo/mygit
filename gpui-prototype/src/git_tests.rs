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
