//! Commit message generation through locally installed command-line agents.
use anyhow::{Context, Result, bail};
use serde_json::{Value, json};
use std::{path::Path, process::Command, time::Duration};
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
pub fn generate(root: &Path, config: &Config) -> Result<String> {
    generate_with_command(
        root,
        config,
        Duration::from_secs(300),
        crate::external::command(&config.agent),
    )
}
fn generate_with_command(
    root: &Path,
    config: &Config,
    timeout: Duration,
    mut command: Command,
) -> Result<String> {
    crate::process::check().map_err(request_error)?;
    let args = config.validate()?;
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
        Some(config.prompt.as_bytes()),
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
        generate_with_command(root, config, Duration::from_secs(2), script(root, body))
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
            assert_eq!(request, config.prompt);
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
    fn invalid_configuration_is_rejected_before_launch() {
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
            Duration::from_millis(30),
            script(root, "sleep 20"),
        )
        .unwrap_err();
        assert_eq!(error.to_string(), crate::i18n::text("Agent 生成超时"));
        let error = generate_with_command(
            root,
            &Config::default(),
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
    fn large_repository_files_do_not_block_prompt_only_generation() {
        let directory = tempfile::tempdir().unwrap();
        let root = directory.path();
        crate::git::git(root, &["init", "-b", "main"]).unwrap();
        std::fs::write(root.join("large.txt"), "x".repeat(1_000_100)).unwrap();
        crate::git::git(root, &["add", "large.txt"]).unwrap();
        std::fs::write(root.join("untracked.bin"), vec![0; 1_000_100]).unwrap();
        let config = Config::default();
        let message = run(root, &config, "cat > request.txt; printf 'feat: test'").unwrap();
        assert_eq!(message, "feat: test");
        assert_eq!(
            std::fs::read_to_string(root.join("request.txt")).unwrap(),
            config.prompt
        );
    }
}
