//! Optional staged-diff generation through legacy Chat Completions settings.
//! Transport configuration and bearer credentials travel only through stdin.
use anyhow::{Context, Result, bail};
use serde_json::{Value, json};
use std::{
    hash::{Hash, Hasher},
    path::Path,
    process::Command,
    time::Duration,
};
pub const DEFAULT_PROMPT: &str =
    "帮我生成 commit 信息，用中文，简洁，使用 Conventional Commits 格式";
#[derive(Clone)]
pub struct Config {
    pub api_url: String,
    pub api_secret: String,
    pub model_name: String,
    pub prompt: String,
}
impl Default for Config {
    fn default() -> Self {
        Self {
            api_url: String::new(),
            api_secret: String::new(),
            model_name: String::new(),
            prompt: DEFAULT_PROMPT.into(),
        }
    }
}
impl std::fmt::Debug for Config {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("AiConfig")
            .field("api_secret", &"[redacted]")
            .finish_non_exhaustive()
    }
}
impl Config {
    pub fn from_json(data: &Value) -> Self {
        let value = |key: &str| data[key].as_str().unwrap_or_default().to_owned();
        Self {
            api_url: value("api_url"),
            api_secret: value("api_secret"),
            model_name: value("model_name"),
            prompt: data["prompt"].as_str().unwrap_or(DEFAULT_PROMPT).to_owned(),
        }
    }
    pub fn load(path: &Path) -> Result<Self> {
        let data = match std::fs::read(path) {
            Ok(bytes) => serde_json::from_slice(&bytes).context("无法读取 AI 配置 JSON")?,
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => json!({}),
            Err(_) => bail!("无法读取 AI 配置"),
        };
        let mut config = Self::from_json(&data);
        if let Ok(secret) = std::env::var("MYGIT_AI_API_SECRET") {
            config.api_secret = secret;
        }
        Ok(config)
    }
    pub fn validate(&self) -> Result<url::Url> {
        if self.api_url.len() > 4096
            || self.model_name.len() > 256
            || self.prompt.len() > 32768
            || self.api_secret.len() > 8192
        {
            bail!("AI 配置超过长度上限");
        }
        if self.api_secret.chars().any(char::is_control)
            || self.model_name.chars().any(char::is_control)
        {
            bail!("AI 密钥或模型名称含不支持的控制字符");
        }
        if self.model_name.trim().is_empty() {
            bail!("请先配置 AI 模型名称");
        }
        let mut endpoint = url::Url::parse(self.api_url.trim())
            .map_err(|_| anyhow::anyhow!("请配置有效的 AI API 基础 URL"))?;
        if !matches!(endpoint.scheme(), "http" | "https")
            || endpoint.host_str().is_none()
            || !endpoint.username().is_empty()
            || endpoint.password().is_some()
            || endpoint.query().is_some()
            || endpoint.fragment().is_some()
        {
            bail!("AI API URL 需为 HTTP/HTTPS 基础地址，不能包含登录信息、查询或片段");
        }
        let path = format!("{}/chat/completions", endpoint.path().trim_end_matches('/'));
        endpoint.set_path(&path);
        Ok(endpoint)
    }
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Fingerprint {
    head: String,
    index: u64,
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
    })
}
pub fn staged(root: &Path) -> Result<Staged> {
    let before = fingerprint(root)?;
    if !crate::git::git(root, &["ls-files", "--unmerged", "-z"])?.is_empty() {
        bail!("暂存区存在未解决冲突，无法生成提交信息");
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
        bail!("没有已暂存的变更");
    }
    if diff.len() > 1_000_000 {
        bail!("暂存 Diff 超过 1 MB，未发送请求；请拆分提交");
    }
    let diff = String::from_utf8(diff).context("暂存 Diff 不是 UTF-8，无法生成提交信息")?;
    if fingerprint(root)? != before {
        bail!("暂存区或 HEAD 在读取期间改变，请重试");
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
    config.validate()?;
    let staged = staged(root)?;
    let message = generate(config, &staged.diff)?;
    if fingerprint(root)? != staged.fingerprint {
        bail!("暂存区或 HEAD 在生成期间改变，未应用结果，请重试");
    }
    Ok(Generated {
        message,
        fingerprint: staged.fingerprint,
    })
}
fn quote(value: &str) -> String {
    format!(
        "\"{}\"",
        value
            .replace('\\', "\\\\")
            .replace('"', "\\\"")
            .replace('\n', "\\n")
            .replace('\r', "\\r")
            .replace('\t', "\\t")
    )
}
/// Uses curl's config-on-stdin support, with no default curlrc or redirects.
/// HTTP errors deliberately omit server bodies which may echo credentials.
pub fn generate(config: &Config, diff: &str) -> Result<String> {
    generate_with_timeout(config, diff, Duration::from_secs(15))
}
fn generate_with_timeout(config: &Config, diff: &str, timeout: Duration) -> Result<String> {
    crate::process::check()?;
    let endpoint = config.validate()?;
    if diff.is_empty() || diff.len() > 1_000_000 {
        bail!("AI 请求需要 1 MB 以内的非空暂存 Diff");
    }
    let body = serde_json::to_string(
        &json!({"model": config.model_name, "messages": [{"role":"system", "content":config.prompt}, {"role":"user", "content":diff}]}),
    )?;
    let mut input = format!(
        "url = {}\nheader = {}\nheader = {}\ndata-binary = {}\n",
        quote(endpoint.as_str()),
        quote("Content-Type: application/json"),
        quote(&format!("Authorization: Bearer {}", config.api_secret)),
        quote(&body)
    );
    input.push_str("request = POST\nsilent\nproto = \"=http,https\"\nconnect-timeout = 5\nmax-time = 15\nwrite-out = \"\\n%{http_code}\"\n");
    let mut response = Vec::new();
    let output = crate::process::lines_with_input(
        Command::new("curl")
            .args(["--disable", "--config", "-"])
            .env_remove("MYGIT_AI_API_SECRET"),
        timeout,
        1_000_010,
        Some(input.as_bytes()),
        |record| {
            if response.len().saturating_add(record.len()) > 1_000_010 {
                return Ok(false);
            }
            response.extend_from_slice(record);
            Ok(true)
        },
    )
    .map_err(|error| {
        let text = error.to_string();
        if text.contains("已取消") {
            anyhow::anyhow!("AI 请求已取消")
        } else if text.contains("超时") {
            anyhow::anyhow!("AI 请求超时")
        } else {
            anyhow::anyhow!("无法执行 AI 请求，请检查 curl 安装与网络")
        }
    })?;
    if output.stopped || output.record_exceeded {
        bail!("AI 响应超过 1 MB 上限");
    }
    if !output.status.success() {
        if output.status.code() == Some(28) {
            bail!("AI 请求超时（15 秒）");
        }
        bail!("AI 请求失败，请检查网络、证书与 API 配置");
    }
    let split = response
        .iter()
        .rposition(|byte| *byte == b'\n')
        .context("AI 响应缺少 HTTP 状态")?;
    let status = std::str::from_utf8(&response[split + 1..]).unwrap_or("");
    if status != "200" {
        bail!("AI API 调用失败：HTTP {status}");
    }
    let data: Value = serde_json::from_slice(&response[..split])
        .map_err(|_| anyhow::anyhow!("AI API 返回无效 JSON"))?;
    let content = data["choices"][0]["message"]["content"]
        .as_str()
        .context("AI API 未返回文本提交信息")?;
    if content.trim().is_empty() || content.len() > 32768 || content.contains('\0') {
        bail!("AI 提交信息为空、过长或包含 NUL");
    }
    Ok(content.to_owned())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{
        io::{Read, Write},
        net::TcpListener,
        thread,
    };
    fn config(url: String) -> Config {
        Config {
            api_url: url,
            api_secret: "fixture-token-with-quote\"and-slash\\".into(),
            model_name: "test-model".into(),
            prompt: "中文规则\n第二行".into(),
        }
    }
    fn server(status: u16, body: String, delay: Duration) -> (String, thread::JoinHandle<Vec<u8>>) {
        server_with_action(status, body, delay, || {})
    }
    fn server_with_action(
        status: u16,
        body: String,
        delay: Duration,
        action: impl FnOnce() + Send + 'static,
    ) -> (String, thread::JoinHandle<Vec<u8>>) {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let url = format!("http://{}/v1/", listener.local_addr().unwrap());
        listener.set_nonblocking(true).unwrap();
        let task = thread::spawn(move || {
            let started = std::time::Instant::now();
            let mut stream = loop {
                match listener.accept() {
                    Ok((stream, _)) => break stream,
                    Err(error)
                        if error.kind() == std::io::ErrorKind::WouldBlock
                            && started.elapsed() < Duration::from_secs(5) =>
                    {
                        thread::sleep(Duration::from_millis(5))
                    }
                    Err(error) => panic!("mock server accept failed: {error}"),
                }
            };
            stream.set_nonblocking(false).unwrap();
            stream
                .set_read_timeout(Some(Duration::from_secs(2)))
                .unwrap();
            let mut request = Vec::new();
            let mut buffer = [0u8; 8192];
            loop {
                let count = stream.read(&mut buffer).unwrap();
                assert!(count > 0);
                request.extend_from_slice(&buffer[..count]);
                if let Some(end) = request.windows(4).position(|bytes| bytes == b"\r\n\r\n") {
                    let headers = String::from_utf8_lossy(&request[..end]);
                    let length: usize = headers
                        .lines()
                        .find_map(|line| {
                            line.to_ascii_lowercase()
                                .strip_prefix("content-length:")
                                .map(|v| v.trim().parse().unwrap())
                        })
                        .unwrap();
                    if request.len() >= end + 4 + length {
                        break;
                    }
                }
                assert!(request.len() <= 2_100_000);
            }
            action();
            thread::sleep(delay);
            let redirect = if status == 302 {
                "Location: http://127.0.0.1:1/credential-target\r\n"
            } else {
                ""
            };
            let header = format!(
                "HTTP/1.1 {status} Test\r\n{redirect}Content-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
                body.len()
            );
            let _ = stream.write_all(header.as_bytes());
            let _ = stream.write_all(body.as_bytes());
            request
        });
        (url, task)
    }
    #[test]
    fn generated_message_belongs_to_current_index_and_rejects_changes_during_request() {
        struct Repo(std::path::PathBuf);
        impl Drop for Repo {
            fn drop(&mut self) {
                let _ = std::fs::remove_dir_all(&self.0);
            }
        }
        let root = Repo(std::env::temp_dir().join(format!(
                "mygit-ai-request-{}-{}",
                std::process::id(),
                std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .unwrap()
                    .as_nanos()
            )));
        std::fs::create_dir(&root.0).unwrap();
        crate::git::git(&root.0, &["init", "-b", "main"]).unwrap();
        std::fs::write(root.0.join("file.txt"), "暂存内容\n").unwrap();
        crate::git::git(&root.0, &["add", "file.txt"]).unwrap();
        let response = json!({"choices":[{"message":{"content":"feat: test"}}]}).to_string();
        let (url, task) = server(200, response.clone(), Duration::ZERO);
        let generated = generate_staged(&root.0, &config(url)).unwrap();
        assert_eq!(generated.message, "feat: test");
        assert_eq!(generated.fingerprint, fingerprint(&root.0).unwrap());
        task.join().unwrap();
        let changed = root.0.clone();
        let (url, task) = server_with_action(200, response, Duration::ZERO, move || {
            std::fs::write(changed.join("file.txt"), "不同暂存内容\n").unwrap();
            crate::git::git(&changed, &["add", "file.txt"]).unwrap();
        });
        let error = generate_staged(&root.0, &config(url)).err().unwrap();
        assert!(error.to_string().contains("在生成期间改变"));
        task.join().unwrap();
    }
    #[test]
    fn legacy_settings_url_validation_and_debug_do_not_reveal_credentials() {
        let value = json!({"api_url":"https://example.com/v1/", "api_secret":"fixture-secret", "model_name":"m", "prompt":"保持原提示"});
        let config = Config::from_json(&value);
        assert_eq!(
            config.validate().unwrap().as_str(),
            "https://example.com/v1/chat/completions"
        );
        assert_eq!(config.prompt, "保持原提示");
        assert!(!format!("{config:?}").contains("fixture-secret"));
        for url in [
            "file:///tmp/test",
            "ftp://example.com",
            "https://name:secret@example.com/v1",
            "https://example.com/v1?token=secret",
            "https://example.com/#x",
        ] {
            let mut invalid = config.clone();
            invalid.api_url = url.into();
            let error = invalid.validate().unwrap_err().to_string();
            assert!(!error.contains("secret"));
        }
        let mut invalid = config.clone();
        invalid.api_secret = "secret\r\nInjected: value".into();
        assert!(invalid.validate().is_err());
        assert_eq!(Config::from_json(&json!({})).prompt, DEFAULT_PROMPT);
    }
    #[test]
    fn local_transport_preserves_json_unicode_headers_and_editable_multiline_response() {
        let message = "feat: 中文提交\n\n保留详细说明 🙂";
        let body = json!({"choices":[{"message":{"content":message}}]}).to_string();
        let (url, server) = server(200, body, Duration::ZERO);
        let config = config(url);
        let diff = "diff --git a/空 格.rs b/空 格.rs\n+\tprintln!(\"🙂\\path\");\n";
        assert_eq!(generate(&config, diff).unwrap(), message);
        let request = server.join().unwrap();
        let end = request
            .windows(4)
            .position(|bytes| bytes == b"\r\n\r\n")
            .unwrap();
        let headers = String::from_utf8_lossy(&request[..end]);
        assert!(headers.starts_with("POST /v1/chat/completions HTTP/1.1\r\n"));
        assert!(headers.contains(&format!("Authorization: Bearer {}", config.api_secret)));
        let data: Value = serde_json::from_slice(&request[end + 4..]).unwrap();
        assert_eq!(data["messages"][0]["content"], config.prompt);
        assert_eq!(data["messages"][1]["content"], diff);
        assert_eq!(data["model"], "test-model");
    }
    #[test]
    fn local_transport_errors_are_bounded_and_never_echo_service_secrets() {
        for (status, body) in [
            (401, "fixture-token secret body".into()),
            (302, "redirect".into()),
            (200, "not json fixture-token".into()),
            (200, json!({"choices":[]}).to_string()),
            (
                200,
                json!({"choices":[{"message":{"content":" "}}]}).to_string(),
            ),
            (200, "x".repeat(1_100_000)),
        ] {
            let (url, task) = server(status, body, Duration::ZERO);
            let error = generate(&config(url), "diff").unwrap_err().to_string();
            if status != 200 {
                assert!(error.contains(&format!("HTTP {status}")));
            }
            assert!(!error.contains("fixture-token"));
            assert!(error.len() < 256);
            task.join().unwrap();
        }
    }
    #[test]
    fn local_transport_timeout_and_cancellation_close_the_request() {
        let (url, task) = server(200, "{}".into(), Duration::from_millis(150));
        let error =
            generate_with_timeout(&config(url), "diff", Duration::from_millis(50)).unwrap_err();
        assert!(error.to_string().contains("超时"));
        task.join().unwrap();
        let (url, task) = server(200, "{}".into(), Duration::from_millis(150));
        let token = crate::process::Cancellation::default();
        let cancel = token.clone();
        let signal = thread::spawn(move || {
            thread::sleep(Duration::from_millis(50));
            cancel.cancel();
        });
        let error = crate::process::scope(token, || generate(&config(url), "diff")).unwrap_err();
        assert!(error.to_string().contains("取消"));
        signal.join().unwrap();
        task.join().unwrap();
    }
}
