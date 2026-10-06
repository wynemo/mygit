//! Commit message generation through locally installed command-line agents.
use anyhow::{Context, Result, bail};
use serde_json::{Value, json};
use std::{
    hash::{Hash, Hasher},
    path::Path,
    process::Command,
    time::Duration,
};
pub const DEFAULT_PROMPT: &str =
    "直接帮我生成一行commit 信息，用中文, 简洁， 使用 Conventional Commits 格式";
pub const AGENTS: &[(&str, &str)] = &[
    ("pi", "pi -p"),
    ("claude", "claude -p"),
    ("codex", "codex exec"),
];
#[derive(Clone)]
pub struct Config {
    pub agent: String,
    pub agent_args: String,
    pub prompt: String,
}
impl Default for Config {
    fn default() -> Self {
        Self {
            agent: "pi".into(),
            agent_args: String::new(),
            prompt: DEFAULT_PROMPT.into(),
        }
    }
}
impl std::fmt::Debug for Config {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("AiConfig")
            .field("agent", &self.agent)
            .finish_non_exhaustive()
    }
}
impl Config {
    pub fn from_json(data: &Value) -> Self {
        Self {
            agent: data["agent"].as_str().unwrap_or("pi").to_owned(),
            agent_args: data["agent_args"].as_str().unwrap_or_default().to_owned(),
            prompt: data["prompt"].as_str().unwrap_or(DEFAULT_PROMPT).to_owned(),
        }
    }
    pub fn load_stored(path: &Path) -> Result<Self> {
        let data = match std::fs::read(path) {
            Ok(bytes) => serde_json::from_slice(&bytes)
                .context(crate::i18n::text("无法读取 AI 配置 JSON"))?,
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => json!({}),
            Err(_) => bail!(crate::localized_format!(
                "无法读取 AI 配置",
                "Unable to read AI settings"
            )),
        };
        Ok(Self::from_json(&data))
    }
    pub fn load(path: &Path) -> Result<Self> {
        Self::load_stored(path)
    }
    pub fn validate(&self) -> Result<Vec<String>> {
        if !AGENTS.iter().any(|(name, _)| *name == self.agent) {
            bail!(crate::localized_format!(
                "请选择 pi、claude 或 codex",
                "Select pi, claude or codex"
            ));
        }
        if self.agent_args.len() > 8192 || self.prompt.len() > 32768 {
            bail!(crate::localized_format!(
                "AI 配置超过长度上限",
                "AI settings exceed the length limit"
            ));
        }
        if self.agent_args.contains('\0') || self.prompt.contains('\0') {
            bail!(crate::localized_format!(
                "Agent 参数或提示词包含 NUL",
                "Agent arguments or prompt contain NUL"
            ));
        }
        shlex::split(&self.agent_args)
            .context(crate::i18n::text("额外参数格式错误，请检查引号是否配对"))
    }
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Fingerprint {
    head: String,
    index: u64,
    workspace: Option<u64>,
}
#[derive(Clone)]
pub struct Staged {
    pub diff: String,
    pub fingerprint: Fingerprint,
}
impl std::fmt::Debug for Staged {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Staged")
            .field("diff_bytes", &self.diff.len())
            .field("fingerprint", &self.fingerprint)
            .finish()
    }
}
pub fn fingerprint(root: &Path) -> Result<Fingerprint> {
    let head = match crate::git::head(root)? {
        crate::model::Revision::Head(sha) => sha,
        crate::model::Revision::Empty => String::new(),
        _ => unreachable!(),
    };
    let index = crate::git::git(root, &["ls-files", "--stage", "-z"])?;
    let mut hash = std::collections::hash_map::DefaultHasher::new();
    index.hash(&mut hash);
    Ok(Fingerprint {
        head,
        index: hash.finish(),
        workspace: None,
    })
}
pub fn staged(root: &Path) -> Result<Staged> {
    let before = fingerprint(root)?;
    if !crate::git::git(root, &["ls-files", "--unmerged", "-z"])?.is_empty() {
        bail!(crate::localized_format!(
            "暂存区存在未解决冲突，无法生成提交信息",
            "The index has unresolved conflicts; unable to generate a commit message"
        ));
    }
    let diff = crate::git::git(
        root,
        &[
            "diff",
            "--cached",
            "--no-ext-diff",
            "--no-textconv",
            "--no-color",
            "--full-index",
            "--find-renames",
            "--unified=3",
            "--",
        ],
    )?;
    if diff.is_empty() {
        bail!(crate::localized_format!(
            "没有已暂存的变更",
            "No staged changes"
        ));
    }
    if diff.len() > 1_000_000 {
        bail!(crate::localized_format!(
            "暂存 Diff 超过 1 MB，未发送请求；请拆分提交",
            "Staged Diff exceeds 1 MB; no request was sent. Split the commit."
        ));
    }
    let diff = String::from_utf8(diff)
        .context(crate::i18n::text("暂存 Diff 不是 UTF-8，无法生成提交信息"))?;
    if fingerprint(root)? != before {
        bail!(crate::localized_format!(
            "暂存区或 HEAD 在读取期间改变，请重试",
            "The index or HEAD changed while reading; retry"
        ));
    }
    Ok(Staged {
        diff,
        fingerprint: before,
    })
}
/// The request and its result refer to the same staged contents. Callers also
/// guard repository identity and draft edits when applying this message.
pub struct Generated {
    pub message: String,
    pub fingerprint: Fingerprint,
}
pub fn generate_staged(root: &Path, config: &Config) -> Result<Generated> {
    generate_staged_with(root, config, |diff| generate(root, config, diff))
}
fn generate_staged_with(
    root: &Path,
    config: &Config,
    generate: impl FnOnce(&str) -> Result<String>,
) -> Result<Generated> {
    config.validate()?;
    let staged = staged(root)?;
    let message = generate(&staged.diff)?;
    if fingerprint(root)? != staged.fingerprint {
        bail!(crate::localized_format!(
            "暂存区或 HEAD 在生成期间改变，未应用结果，请重试",
            "The index or HEAD changed during generation; the result was not applied. Retry."
        ));
    }
    Ok(Generated {
        message,
        fingerprint: staged.fingerprint,
    })
}
/// Capture every current change without updating the index.
fn changes_snapshot(root: &Path) -> Result<Staged> {
    let before = fingerprint(root)?;
    if !crate::git::git(root, &["ls-files", "--unmerged", "-z"])?.is_empty() {
        bail!(crate::localized_format!(
            "存在未解决冲突，无法生成提交信息",
            "Unresolved conflicts prevent commit message generation"
        ));
    }
    let options = [
        "--no-ext-diff",
        "--no-textconv",
        "--no-color",
        "--binary",
        "--full-index",
        "--find-renames",
        "--unified=3",
    ];
    let mut diff = Vec::new();
    let mut append = |label: &str, bytes: &[u8]| -> Result<()> {
        if bytes.is_empty() {
            return Ok(());
        }
        if diff
            .len()
            .saturating_add(label.len())
            .saturating_add(bytes.len())
            > 1_000_000
        {
            bail!(crate::localized_format!(
                "变更 Diff 超过 1 MB，请拆分变更后重试",
                "Changes Diff exceeds 1 MB; split the changes and retry"
            ));
        }
        diff.extend_from_slice(label.as_bytes());
        diff.extend_from_slice(bytes);
        Ok(())
    };
    let mut args = vec!["diff", "--cached"];
    args.extend(options);
    args.push("--");
    append(
        "\n## Staged changes (HEAD -> index)\n",
        &crate::git::git(root, &args)?,
    )?;
    let mut args = vec!["diff"];
    args.extend(options);
    args.push("--");
    append(
        "\n## Unstaged changes (index -> worktree)\n",
        &crate::git::git(root, &args)?,
    )?;
    let paths = crate::git::git(root, &["ls-files", "--others", "--exclude-standard", "-z"])?;
    for path in paths
        .split(|byte| *byte == 0)
        .filter(|path| !path.is_empty())
    {
        crate::process::check()?;
        let path = std::str::from_utf8(path).context(crate::i18n::text("变更路径不是 UTF-8"))?;
        let metadata = std::fs::symlink_metadata(root.join(path))?;
        if !metadata.is_file() && !metadata.file_type().is_symlink() {
            bail!(crate::localized_format!(
                "无法读取特殊文件变更：{path}",
                "Cannot read changes to special file: {path}"
            ));
        }
        if metadata.len() > 1_000_000 {
            bail!(crate::localized_format!(
                "变更 Diff 超过 1 MB，请拆分变更后重试",
                "Changes Diff exceeds 1 MB; split the changes and retry"
            ));
        }
        let mut command = crate::external::command("git");
        command
            .arg("-C")
            .arg(root)
            .arg("--literal-pathspecs")
            .args(["diff", "--no-index"])
            .args(options)
            .args(["--", "/dev/null", path])
            .env("GIT_OPTIONAL_LOCKS", "0");
        let output = crate::process::output(&mut command, Duration::from_secs(30))?;
        if !output.status.success() && output.status.code() != Some(1) {
            bail!(
                "{}",
                crate::process::display_diagnostic(
                    String::from_utf8_lossy(&output.stderr).into_owned()
                )
            );
        }
        append("\n## Untracked file\n", &output.stdout)?;
    }
    let after = fingerprint(root)?;
    if before != after {
        bail!(crate::localized_format!(
            "仓库变更在读取期间改变，请重试",
            "Repository changes changed while reading; retry"
        ));
    }
    let diff = String::from_utf8(diff)
        .context(crate::i18n::text("变更 Diff 不是 UTF-8，无法生成提交信息"))?;
    let mut hash = std::collections::hash_map::DefaultHasher::new();
    diff.hash(&mut hash);
    let fingerprint = Fingerprint {
        workspace: Some(hash.finish()),
        ..after
    };
    Ok(Staged { diff, fingerprint })
}
pub fn changes(root: &Path) -> Result<Staged> {
    let snapshot = changes_snapshot(root)?;
    if changes_snapshot(root)?.fingerprint != snapshot.fingerprint {
        bail!(crate::localized_format!(
            "仓库变更在读取期间改变，请重试",
            "Repository changes changed while reading; retry"
        ));
    }
    if snapshot.diff.is_empty() {
        bail!(crate::localized_format!("没有文件变更", "No file changes"));
    }
    Ok(snapshot)
}
pub fn changes_fingerprint(root: &Path) -> Result<Fingerprint> {
    Ok(changes_snapshot(root)?.fingerprint)
}
pub fn generate_changes(root: &Path, config: &Config) -> Result<Generated> {
    generate_changes_with(root, config, |diff| generate(root, config, diff))
}
fn generate_changes_with(
    root: &Path,
    config: &Config,
    generate: impl FnOnce(&str) -> Result<String>,
) -> Result<Generated> {
    config.validate()?;
    let changes = changes(root)?;
    let message = generate(&changes.diff)?;
    if changes_fingerprint(root)? != changes.fingerprint {
        bail!(crate::localized_format!(
            "仓库变更在生成期间改变，未应用结果，请重试",
            "Repository changes changed during generation; the result was not applied. Retry."
        ));
    }
    Ok(Generated {
        message,
        fingerprint: changes.fingerprint,
    })
}
fn request_error(error: anyhow::Error) -> anyhow::Error {
    let message = match error.downcast_ref::<crate::process::Failure>() {
        Some(crate::process::Failure::Cancelled) => crate::i18n::text("AI 请求已取消"),
        Some(crate::process::Failure::GitTimeout | crate::process::Failure::SubprocessTimeout) => {
            crate::i18n::text("Agent 生成超时")
        }
        None => crate::i18n::text("无法执行 Agent，请检查命令是否安装且可从 PATH 访问"),
    };
    anyhow::anyhow!(message)
}
pub fn generate(root: &Path, config: &Config, diff: &str) -> Result<String> {
    generate_with_command(
        root,
        config,
        diff,
        Duration::from_secs(300),
        crate::external::command(&config.agent),
    )
}
fn generate_with_command(
    root: &Path,
    config: &Config,
    diff: &str,
    timeout: Duration,
    mut command: Command,
) -> Result<String> {
    crate::process::check().map_err(request_error)?;
    let args = config.validate()?;
    if diff.is_empty() || diff.len() > 1_000_000 {
        bail!(crate::localized_format!(
            "AI 请求需要 1 MB 以内的非空变更 Diff",
            "AI requests require a nonempty changes Diff within 1 MB"
        ));
    }
    let input = format!(
        "{}\n\n只输出提交信息正文，不要 Markdown 代码块或解释，不要执行提交或修改文件。仅根据以下仓库变更生成信息：\n\n{}",
        config.prompt, diff
    );
    command
        .current_dir(root)
        .arg(if config.agent == "codex" {
            "exec"
        } else {
            "-p"
        })
        .args(args);
    // Codex may write execution events to stdout; use its final-response file.
    let output_dir = tempfile::tempdir()?;
    let message_path = output_dir.path().join("message.txt");
    if config.agent == "codex" {
        command
            .arg("--output-last-message")
            .arg(&message_path)
            .arg("-");
    }
    let mut response = Vec::new();
    let output = crate::process::lines_with_input(
        &mut command,
        timeout,
        1_000_000,
        Some(input.as_bytes()),
        |record| {
            if response.len().saturating_add(record.len()) > 1_000_000 {
                return Ok(false);
            }
            response.extend_from_slice(record);
            Ok(true)
        },
    )
    .map_err(request_error)?;
    if output.stopped || output.record_exceeded {
        bail!(crate::localized_format!(
            "AI 响应超过 1 MB 上限",
            "AI response exceeds the 1 MB limit"
        ));
    }
    if !output.status.success() {
        let agent = &config.agent;
        let status = output.status;
        let diagnostic = crate::process::display_diagnostic(
            String::from_utf8_lossy(&output.stderr).into_owned(),
        );
        bail!(crate::localized_format!(
            "{agent} 执行失败（{status}）：{diagnostic}",
            "{agent} failed ({status}): {diagnostic}"
        ));
    }
    let content = if config.agent == "codex" {
        // Bound reads even when custom parameters make the CLI emit huge results.
        use std::io::Read;
        let file = std::fs::File::open(&message_path)
            .context(crate::i18n::text("Codex 未返回最终提交信息"))?;
        let mut bytes = Vec::new();
        file.take(32769).read_to_end(&mut bytes)?;
        String::from_utf8(bytes).context(crate::i18n::text("Agent 提交信息不是 UTF-8"))?
    } else {
        String::from_utf8(response).context(crate::i18n::text("Agent 提交信息不是 UTF-8"))?
    };
    if content.trim().is_empty() || content.len() > 32768 || content.contains('\0') {
        bail!(crate::localized_format!(
            "AI 提交信息为空、过长或包含 NUL",
            "AI commit message is empty, too long or contains NUL"
        ));
    }
    Ok(content.trim().to_owned())
}

#[cfg(all(test, unix))]
mod tests {
    use super::*;
    use std::os::unix::fs::PermissionsExt;

    fn script(directory: &Path, body: &str) -> Command {
        let path = directory.join("mock-agent");
        std::fs::write(&path, format!("#!/bin/sh\nset -eu\n{body}\n")).unwrap();
        std::fs::set_permissions(&path, std::fs::Permissions::from_mode(0o700)).unwrap();
        Command::new(path)
    }
    fn run(root: &Path, config: &Config, body: &str) -> Result<String> {
        generate_with_command(
            root,
            config,
            "diff --git fixture\n+暂存内容",
            Duration::from_secs(2),
            script(root, body),
        )
    }
    #[test]
    fn all_agents_receive_arguments_stdin_and_repository_and_codex_returns_only_final_message() {
        for (agent, _) in AGENTS {
            let directory = tempfile::tempdir().unwrap();
            let root = directory.path();
            let config = Config {
                agent: (*agent).into(),
                agent_args: "--model 'model with spaces' --flag '$(touch injected)'".into(),
                prompt: "中文规则".into(),
            };
            let base = if *agent == "codex" { "exec" } else { "-p" };
            let body = format!(
                r#"
test "$1" = '{base}'
test "$2" = '--model'
test "$3" = 'model with spaces'
test "$4" = '--flag'
test "$5" = '$(touch injected)'
pwd > cwd.txt
cat > request.txt
if [ "$1" = exec ]; then
    test "$6" = '--output-last-message'
    test "$8" = '-'
    printf 'feat: 中文提交\n' > "$7"
    printf 'execution logs must not become commit text'
else
    printf 'feat: 中文提交\n'
fi
"#
            );
            assert_eq!(run(root, &config, &body).unwrap(), "feat: 中文提交");
            let cwd = std::fs::read_to_string(root.join("cwd.txt")).unwrap();
            assert_eq!(
                std::fs::canonicalize(cwd.trim()).unwrap(),
                root.canonicalize().unwrap()
            );
            let request = std::fs::read_to_string(root.join("request.txt")).unwrap();
            assert!(request.contains("中文规则"));
            assert!(request.contains("+暂存内容"));
            assert!(!root.join("injected").exists());
        }
    }
    #[test]
    fn old_configuration_preserves_prompt_and_defaults_to_pi() {
        let config = Config::from_json(
            &json!({"api_url":"old", "api_secret":"secret", "model_name":"old", "prompt":"保持原提示"}),
        );
        assert_eq!(config.agent, "pi");
        assert!(config.agent_args.is_empty());
        assert_eq!(config.prompt, "保持原提示");
        let config = Config {
            agent_args: "--api-key fixture-secret".into(),
            ..config
        };
        assert!(!format!("{config:?}").contains("fixture-secret"));
    }
    #[test]
    fn invalid_configuration_and_diff_are_rejected_before_launch() {
        let directory = tempfile::tempdir().unwrap();
        for config in [
            Config {
                agent: "unknown".into(),
                ..Config::default()
            },
            Config {
                agent_args: "'unclosed".into(),
                ..Config::default()
            },
            Config {
                agent_args: "nul\0".into(),
                ..Config::default()
            },
        ] {
            assert!(run(directory.path(), &config, "touch launched; cat").is_err());
            assert!(!directory.path().join("launched").exists());
        }
        for diff in [String::new(), "x".repeat(1_000_001)] {
            assert!(
                generate_with_command(
                    directory.path(),
                    &Config::default(),
                    &diff,
                    Duration::from_secs(2),
                    script(directory.path(), "touch launched; cat")
                )
                .is_err()
            );
            assert!(!directory.path().join("launched").exists());
        }
    }
    #[test]
    fn failures_empty_invalid_and_oversized_results_are_reported() {
        let directory = tempfile::tempdir().unwrap();
        for body in [
            "cat >/dev/null; printf 'login required' >&2; exit 3",
            "cat >/dev/null",
            "cat >/dev/null; printf '\\377'",
            "cat >/dev/null; printf '\\000'",
            "cat >/dev/null; head -c 32769 /dev/zero | tr '\\000' x",
            "cat >/dev/null; head -c 1000001 /dev/zero | tr '\\000' x",
        ] {
            assert!(run(directory.path(), &Config::default(), body).is_err());
        }
        let error = run(
            directory.path(),
            &Config::default(),
            "cat >/dev/null; echo 'login required' >&2; exit 3",
        )
        .unwrap_err();
        assert!(error.to_string().contains("login required"));
        let codex = Config {
            agent: "codex".into(),
            ..Config::default()
        };
        assert!(
            run(directory.path(), &codex, "cat >/dev/null; echo logs")
                .unwrap_err()
                .to_string()
                .contains("Codex")
        );
        assert!(
            run(
                directory.path(),
                &codex,
                "cat >/dev/null; head -c 32769 /dev/zero | tr '\\000' x > \"$3\""
            )
            .is_err()
        );
    }
    #[test]
    fn timeout_missing_command_and_cancellation_reap_processes() {
        let directory = tempfile::tempdir().unwrap();
        let root = directory.path();
        let error = generate_with_command(
            root,
            &Config::default(),
            "diff",
            Duration::from_millis(30),
            script(root, "sleep 20"),
        )
        .unwrap_err();
        assert_eq!(error.to_string(), crate::i18n::text("Agent 生成超时"));
        let error = generate_with_command(
            root,
            &Config::default(),
            "diff",
            Duration::from_secs(1),
            Command::new(root.join("missing")),
        )
        .unwrap_err();
        assert_eq!(
            error.to_string(),
            crate::i18n::text("无法执行 Agent，请检查命令是否安装且可从 PATH 访问")
        );
        let token = crate::process::Cancellation::default();
        let trigger = token.clone();
        let cancel = std::thread::spawn(move || {
            std::thread::sleep(Duration::from_millis(30));
            trigger.cancel();
        });
        let error =
            crate::process::scope(token, || run(root, &Config::default(), "sleep 20")).unwrap_err();
        cancel.join().unwrap();
        assert_eq!(error.to_string(), crate::i18n::text("AI 请求已取消"));
        let token = crate::process::Cancellation::default();
        token.cancel();
        assert!(
            crate::process::scope(token, || run(root, &Config::default(), "touch launched"))
                .is_err()
        );
        assert!(!root.join("launched").exists());
    }
    #[test]
    fn staged_generation_handles_initial_commit_and_rejects_index_changes() {
        let directory = tempfile::tempdir().unwrap();
        let root = directory.path();
        crate::git::git(root, &["init", "-b", "main"]).unwrap();
        std::fs::write(root.join("file.txt"), "暂存内容\n").unwrap();
        crate::git::git(root, &["add", "file.txt"]).unwrap();
        let config = Config::default();
        let generated = generate_staged_with(root, &config, |diff| {
            assert!(diff.contains("+暂存内容"));
            generate_with_command(
                root,
                &config,
                diff,
                Duration::from_secs(2),
                script(root, "cat >/dev/null; printf 'feat: test'"),
            )
        })
        .unwrap();
        assert_eq!(generated.message, "feat: test");
        assert_eq!(generated.fingerprint, fingerprint(root).unwrap());
        let error = generate_staged_with(root, &config, |diff| {
            generate_with_command(root, &config, diff, Duration::from_secs(2), script(root, "cat >/dev/null; printf 'changed' > file.txt; git add file.txt; printf 'feat: test'"))
        }).err().unwrap();
        assert!(error.to_string().contains("在生成期间改变"));
    }
}
