//! Separate test process: initialize the same locale used by an English app startup.
use mygit_gpui::{
    ai, diff, git,
    i18n::{self, Language},
    model::BrowseMode,
    operations::ResetMode,
    process::{self, Cancellation, Failure},
    settings::Settings,
};
use std::{
    fs,
    path::Path,
    process::Command,
    time::{Duration, SystemTime, UNIX_EPOCH},
};
fn git_command(root: &Path, args: &[&str]) {
    let output = Command::new("git")
        .arg("-C")
        .arg(root)
        .args(args)
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
}
#[test]
fn english_startup_preserves_repository_data_and_task_semantics() {
    i18n::initialize(Language::English);
    assert_eq!(i18n::text("打开仓库"), "Open repository");
    assert_eq!(BrowseMode::Workspace.label(), "All changes");
    assert!(
        ResetMode::Hard
            .description()
            .contains("cannot recover uncommitted content")
    );
    let content = "打开仓库/中文🙂 file.rs";
    let mut evaluations = 0;
    let formatted = mygit_gpui::localized_format!(
        "来源：{} : {}",
        "Source: {} : {}",
        {
            evaluations += 1;
            content
        },
        7
    );
    assert_eq!(evaluations, 1);
    assert_eq!(formatted, format!("Source: {content} : 7"));
    let captured = "中文🙂";
    assert_eq!(
        mygit_gpui::localized_format!("文件 {captured}", "File {captured}"),
        "File 中文🙂"
    );
    let token = Cancellation::default();
    token.cancel();
    let error = process::scope(token.clone(), process::check).unwrap_err();
    assert_eq!(error.downcast_ref::<Failure>(), Some(&Failure::Cancelled));
    assert_eq!(error.to_string(), "Task cancelled");
    let config = ai::Config {
        api_url: "http://127.0.0.1:9/v1".into(),
        api_secret: String::new(),
        model_name: "fixture".into(),
        prompt: "打开仓库".into(),
    };
    // Already cancelled: no API request or child process is started.
    let error = process::scope(token, || ai::generate(&config, "diff fixture")).unwrap_err();
    assert_eq!(error.to_string(), "AI request cancelled");
    assert_eq!(config.prompt, "打开仓库");
    assert!(
        diff::calculate(b"\0", b"data")
            .unwrap()
            .message
            .unwrap()
            .contains("Binary file")
    );
    assert!(
        Settings::load(std::env::temp_dir().join("mygit-locale-nonexistent/settings.json"))
            .language
            == Language::Chinese
    );
    #[cfg(unix)]
    {
        let error = process::output(
            Command::new("sh").args(["-c", "sleep 5"]),
            Duration::from_millis(25),
        )
        .unwrap_err();
        assert_eq!(error.downcast_ref::<Failure>(), Some(&Failure::GitTimeout));
        assert_eq!(error.to_string(), "Git operation timed out; retry");
    }
    let dir = std::env::temp_dir().join(format!(
        "mygit-english-{}-{}",
        std::process::id(),
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    fs::create_dir(&dir).unwrap();
    git_command(&dir, &["init", "-q", "-b", "main"]);
    git_command(&dir, &["config", "user.name", "中文作者"]);
    git_command(&dir, &["config", "user.email", "locale@example.invalid"]);
    fs::write(dir.join("打开仓库.txt"), "打开仓库\n中文🙂\n").unwrap();
    git_command(&dir, &["add", "--", "打开仓库.txt"]);
    git_command(&dir, &["commit", "-q", "-m", "打开仓库"]);
    let snapshot = git::snapshot(&dir).unwrap();
    assert_eq!(snapshot.branch, "main");
    assert_eq!(snapshot.commits[0].subject, "打开仓库");
    assert_eq!(snapshot.commits[0].author, "中文作者");
    let detail = git::commit_detail(&dir, &snapshot.commits[0].sha).unwrap();
    assert_eq!(detail.message.trim(), "打开仓库");
    let (comparison, file) = git::workspace_file(&dir, "打开仓库.txt").unwrap();
    assert_eq!(file.path, "打开仓库.txt");
    let view = git::compare(&dir, &comparison, &file).unwrap();
    assert_eq!(&*view.right_document.text, "打开仓库\n中文🙂\n");
    fs::write(dir.join("large.txt"), "x".repeat(2_000_001)).unwrap();
    let (comparison, file) = git::workspace_file(&dir, "large.txt").unwrap();
    let limited = git::compare(&dir, &comparison, &file).unwrap();
    assert!(limited.can_expand_preview);
    assert!(limited.message.as_ref().unwrap().contains("preview limit"));
    let merge = mygit_gpui::merge::align(&limited, &limited).unwrap();
    assert!(merge.can_expand_preview);
    assert!(merge.pair_diff().can_expand_preview);
    let expanded = git::compare_with_limit(&dir, &comparison, &file, 20_000_000).unwrap();
    assert!(!expanded.can_expand_preview);
    assert!(expanded.message.is_none());
    assert_eq!(expanded.right_document.text.len(), 2_000_001);
    fs::remove_dir_all(dir).unwrap();
}
