//! Bounded, cancellable child execution. Each UI job gets its own cancellation scope.
use anyhow::{Context, Result, bail};
use std::{
    cell::RefCell,
    io::{BufRead, BufReader, Read, Write},
    process::{Command, Output, Stdio},
    sync::{
        Arc, Mutex,
        atomic::{AtomicBool, Ordering},
    },
    time::{Duration, Instant},
};

/// Stable error identity, independent of the language used to display it.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Failure {
    Cancelled,
    GitTimeout,
    SubprocessTimeout,
}
impl std::fmt::Display for Failure {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(crate::i18n::text(match self {
            Self::Cancelled => "任务已取消",
            Self::GitTimeout => "Git 操作超时，请重试",
            Self::SubprocessTimeout => "子进程操作超时，请重试",
        }))
    }
}
impl std::error::Error for Failure {}

#[derive(Clone, Default)]
pub struct Cancellation(Arc<AtomicBool>);
impl Cancellation {
    pub fn cancel(&self) {
        self.0.store(true, Ordering::Relaxed);
    }
    pub fn cancelled(&self) -> bool {
        self.0.load(Ordering::Relaxed)
    }
}
pub fn display_diagnostic(text: String) -> String {
    if text.len() <= 8192 {
        return text;
    }
    let mut first = 4096;
    let mut last = text.len() - 4096;
    while !text.is_char_boundary(first) {
        first -= 1;
    }
    while !text.is_char_boundary(last) {
        last += 1;
    }
    crate::localized_format!(
        "{}\n…输出较长，显示首尾…\n{}",
        "{}\n…Long output; showing the beginning and end…\n{}",
        &text[..first],
        &text[last..]
    )
}
#[derive(Clone, Default)]
pub struct Progress(Arc<Mutex<Vec<u8>>>);
impl Progress {
    pub fn append(&self, bytes: &[u8]) {
        let mut output = self.0.lock().unwrap_or_else(|e| e.into_inner());
        output.extend_from_slice(bytes);
        let excess = output.len().saturating_sub(8192);
        if excess > 0 {
            output.drain(..excess);
        }
    }
    pub fn text(&self) -> String {
        String::from_utf8_lossy(&self.0.lock().unwrap_or_else(|e| e.into_inner()))
            .replace('\r', "\n")
    }
}
thread_local! { static PROGRESS: RefCell<Option<Progress>> = const { RefCell::new(None) }; }
pub fn with_progress<T>(progress: Progress, job: impl FnOnce() -> T) -> T {
    struct Restore(Option<Progress>);
    impl Drop for Restore {
        fn drop(&mut self) {
            PROGRESS.with(|slot| *slot.borrow_mut() = self.0.take());
        }
    }
    let previous = PROGRESS.with(|slot| slot.replace(Some(progress)));
    let _restore = Restore(previous);
    job()
}
thread_local! { static CURRENT: RefCell<Cancellation> = RefCell::new(Cancellation::default()); }
pub fn scope<T>(token: Cancellation, job: impl FnOnce() -> T) -> T {
    struct Restore(Option<Cancellation>);
    impl Drop for Restore {
        fn drop(&mut self) {
            CURRENT.with(|c| *c.borrow_mut() = self.0.take().unwrap());
        }
    }
    let previous = CURRENT.with(|c| c.replace(token));
    let _restore = Restore(Some(previous));
    job()
}
pub fn check() -> Result<()> {
    if CURRENT.with(|c| c.borrow().cancelled()) {
        return Err(Failure::Cancelled.into());
    }
    Ok(())
}
fn drain(mut reader: impl Read, progress: Option<Progress>) -> std::io::Result<(Vec<u8>, bool)> {
    let mut bytes = vec![];
    let mut buf = [0u8; 8192];
    let mut exceeded = false;
    loop {
        let n = reader.read(&mut buf)?;
        if n == 0 {
            break;
        }
        if let Some(progress) = &progress {
            progress.append(&buf[..n]);
        }
        if bytes.len() + n <= 64 * 1024 * 1024 {
            bytes.extend_from_slice(&buf[..n]);
        } else {
            exceeded = true;
        }
    }
    Ok((bytes, exceeded))
}
pub fn output(command: &mut Command, timeout: Duration) -> Result<Output> {
    check()?;
    command
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .stdin(Stdio::null());
    #[cfg(unix)]
    {
        use std::os::unix::process::CommandExt;
        command.process_group(0);
    }
    let mut child = command
        .spawn()
        .context(crate::i18n::text("无法启动子进程"))?;
    let stdout = child.stdout.take().unwrap();
    let stderr = child.stderr.take().unwrap();
    let started = Instant::now();
    // Scoped readers always finish after the child/process group is reaped.
    std::thread::scope(|scope| {
        let progress = PROGRESS.with(|slot| slot.borrow().clone());
        let out = scope.spawn(move || drain(stdout, None));
        let err = scope.spawn(move || drain(stderr, progress));
        let mut reason = None;
        let status = loop {
            match child.try_wait() {
                Ok(Some(status)) => break Ok(status),
                Ok(None) => {}
                Err(error) => break Err(error),
            }
            if check().is_err() || started.elapsed() >= timeout {
                reason = Some(if started.elapsed() >= timeout {
                    Failure::GitTimeout
                } else {
                    Failure::Cancelled
                });
                #[cfg(unix)]
                unsafe {
                    libc::kill(-(child.id() as i32), libc::SIGKILL);
                }
                let _ = child.kill();
                break child.wait();
            }
            std::thread::sleep(Duration::from_millis(10));
        };
        // A hook may leave descendants holding the pipe after its parent exits.
        #[cfg(unix)]
        unsafe {
            libc::kill(-(child.id() as i32), libc::SIGKILL);
        }
        if status.is_err() {
            let _ = child.kill();
            let _ = child.wait();
        }
        let (stdout, stdout_exceeded) = out.join().map_err(|_| {
            anyhow::anyhow!(crate::localized_format!(
                "读取标准输出失败",
                "Unable to read standard output"
            ))
        })??;
        let (stderr, stderr_exceeded) = err.join().map_err(|_| {
            anyhow::anyhow!(crate::localized_format!(
                "读取错误输出失败",
                "Unable to read standard error"
            ))
        })??;
        if let Some(reason) = reason {
            return Err(reason.into());
        }
        if stdout_exceeded || stderr_exceeded {
            bail!(crate::localized_format!(
                "Git 输出超过 64 MB 上限",
                "Git output exceeds the 64 MB limit"
            ));
        }
        Ok(Output {
            status: status?,
            stdout,
            stderr,
        })
    })
}
/// Line-by-line output with consumer backpressure. A false return stops and
/// reaps the process group, while retaining the already consumed records.
pub struct LineOutput {
    pub status: std::process::ExitStatus,
    pub stderr: Vec<u8>,
    pub stopped: bool,
    pub record_exceeded: bool,
}
pub fn lines(
    command: &mut Command,
    timeout: Duration,
    max_record: usize,
    consume: impl FnMut(&[u8]) -> Result<bool> + Send,
) -> Result<LineOutput> {
    lines_with_input(command, timeout, max_record, None, consume)
}
/// Input is piped concurrently with reading, so secrets need not appear in
/// process arguments or temporary files. Cancellation closes blocked writers.
pub fn lines_with_input(
    command: &mut Command,
    timeout: Duration,
    max_record: usize,
    input: Option<&[u8]>,
    mut consume: impl FnMut(&[u8]) -> Result<bool> + Send,
) -> Result<LineOutput> {
    check()?;
    command
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .stdin(if input.is_some() {
            Stdio::piped()
        } else {
            Stdio::null()
        });
    #[cfg(unix)]
    {
        use std::os::unix::process::CommandExt;
        command.process_group(0);
    }
    let mut child = command
        .spawn()
        .context(crate::i18n::text("无法启动子进程"))?;
    let stdin = child.stdin.take();
    let stdout = child.stdout.take().unwrap();
    let stderr = child.stderr.take().unwrap();
    let stop = AtomicBool::new(false);
    let started = Instant::now();
    std::thread::scope(|scope| {
        let writer = scope.spawn(move || -> std::io::Result<()> {
            if let (Some(mut stdin), Some(input)) = (stdin, input) {
                stdin.write_all(input)?;
            }
            Ok(())
        });
        let stop_ref = &stop;
        let out = scope.spawn(move || -> Result<(bool, bool)> {
            let result = (|| {
                let mut reader = BufReader::new(stdout);
                let mut record = vec![];
                loop {
                    let buffer = reader.fill_buf()?;
                    if buffer.is_empty() {
                        if !record.is_empty() && !consume(&record)? {
                            return Ok((true, false));
                        }
                        return Ok((false, false));
                    }
                    let length = buffer
                        .iter()
                        .position(|byte| *byte == b'\n')
                        .map_or(buffer.len(), |i| i + 1);
                    if record.len().saturating_add(length) > max_record {
                        return Ok((true, true));
                    }
                    record.extend_from_slice(&buffer[..length]);
                    let complete = record.last() == Some(&b'\n');
                    reader.consume(length);
                    if complete {
                        if !consume(&record)? {
                            return Ok((true, false));
                        }
                        record.clear();
                    }
                }
            })();
            if !matches!(&result, Ok((false, false))) {
                stop_ref.store(true, Ordering::Release);
            }
            result
        });
        let err = scope.spawn(move || drain(stderr, None));
        let mut reason = None;
        let status = loop {
            match child.try_wait() {
                Ok(Some(status)) => break Ok(status),
                Ok(None) => {}
                Err(error) => break Err(error),
            }
            if check().is_err() || started.elapsed() >= timeout || stop.load(Ordering::Acquire) {
                if check().is_err() {
                    reason = Some(Failure::Cancelled);
                } else if started.elapsed() >= timeout {
                    reason = Some(Failure::SubprocessTimeout);
                }
                #[cfg(unix)]
                unsafe {
                    libc::kill(-(child.id() as i32), libc::SIGKILL);
                }
                let _ = child.kill();
                break child.wait();
            }
            std::thread::sleep(Duration::from_millis(10));
        };
        #[cfg(unix)]
        unsafe {
            libc::kill(-(child.id() as i32), libc::SIGKILL);
        }
        if status.is_err() {
            let _ = child.kill();
            let _ = child.wait();
        }
        let read = out.join().map_err(|_| {
            anyhow::anyhow!(crate::localized_format!(
                "读取标准输出失败",
                "Unable to read standard output"
            ))
        })?;
        let (stderr, exceeded) = err.join().map_err(|_| {
            anyhow::anyhow!(crate::localized_format!(
                "读取错误输出失败",
                "Unable to read standard error"
            ))
        })??;
        let written = writer.join().map_err(|_| {
            anyhow::anyhow!(crate::localized_format!(
                "写入标准输入失败",
                "Unable to write standard input"
            ))
        })?;
        if let Some(reason) = reason {
            return Err(reason.into());
        }
        check()?;
        let (stopped, record_exceeded) = read?;
        // BrokenPipe is expected when a child rejects input or output hits a limit.
        if let Err(error) = written
            && error.kind() != std::io::ErrorKind::BrokenPipe
        {
            return Err(error.into());
        }
        if exceeded {
            bail!(crate::localized_format!(
                "错误输出超过 64 MB 上限",
                "Error output exceeds the 64 MB limit"
            ));
        }
        Ok(LineOutput {
            status: status?,
            stderr,
            stopped,
            record_exceeded,
        })
    })
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    #[cfg(unix)]
    fn piped_input_roundtrips_and_blocked_writer_is_cancelled() {
        let input = "中文🙂\n".repeat(20_000);
        let mut output = Vec::new();
        let result = lines_with_input(
            &mut Command::new("cat"),
            Duration::from_secs(2),
            1024,
            Some(input.as_bytes()),
            |record| {
                output.extend_from_slice(record);
                Ok(true)
            },
        )
        .unwrap();
        assert!(result.status.success());
        assert_eq!(output, input.as_bytes());
        let input = vec![b'x'; 256_000];
        let started = Instant::now();
        let error = lines_with_input(
            Command::new("sh").args(["-c", "sleep 20"]),
            Duration::from_millis(30),
            1024,
            Some(&input),
            |_| Ok(true),
        )
        .err()
        .unwrap();
        assert!(error.to_string().contains("超时"));
        assert!(started.elapsed() < Duration::from_secs(1));
    }
    #[test]
    #[cfg(unix)]
    fn streaming_consumer_limits_records_and_reaps_early_or_failed_consumers() {
        let started = Instant::now();
        let mut records = vec![];
        let output = lines(
            Command::new("sh").args(["-c", "printf 'one\ntwo\n'; sleep 20"]),
            Duration::from_secs(2),
            1024,
            |line| {
                records.push(line.to_vec());
                Ok(false)
            },
        )
        .unwrap();
        assert!(output.stopped);
        assert_eq!(records, vec![b"one\n".to_vec()]);
        assert!(started.elapsed() < Duration::from_secs(1));
        let output = lines(
            Command::new("sh").args(["-c", "printf abcdef"]),
            Duration::from_secs(2),
            3,
            |_| panic!("oversized record must not be delivered"),
        )
        .unwrap();
        assert!(output.record_exceeded);
        let error = lines(
            Command::new("sh").args(["-c", "printf 'bad\n'; sleep 20"]),
            Duration::from_secs(2),
            1024,
            |_| bail!("invalid record"),
        )
        .err()
        .unwrap();
        assert!(error.to_string().contains("invalid record"));
        let mut bytes = vec![];
        let output = lines(
            Command::new("sh").args(["-c", "printf final"]),
            Duration::from_secs(2),
            1024,
            |line| {
                bytes.extend_from_slice(line);
                Ok(true)
            },
        )
        .unwrap();
        assert!(!output.stopped);
        assert!(output.status.success());
        assert_eq!(bytes, b"final");
    }
    #[test]
    #[cfg(unix)]
    fn streaming_timeout_and_cancellation_finish_without_open_pipes() {
        let error = lines(
            Command::new("sh").args(["-c", "sleep 20"]),
            Duration::from_millis(30),
            1024,
            |_| Ok(true),
        )
        .err()
        .unwrap();
        assert!(error.to_string().contains("超时"));
        let token = Cancellation::default();
        let trigger = token.clone();
        let cancel = std::thread::spawn(move || {
            std::thread::sleep(Duration::from_millis(30));
            trigger.cancel();
        });
        let error = scope(token, || {
            lines(
                Command::new("sh").args(["-c", "sleep 20"]),
                Duration::from_secs(2),
                1024,
                |_| Ok(true),
            )
        })
        .err()
        .unwrap();
        cancel.join().unwrap();
        assert!(error.to_string().contains("取消"));
    }
    #[test]
    fn diagnostic_display_bounds_large_unicode_output() {
        let source = format!("first\n{}\nlast", "🙂你".repeat(3000));
        let shown = display_diagnostic(source);
        assert!(shown.starts_with("first"));
        assert!(shown.ends_with("last"));
        assert!(shown.len() < 8300);
        assert_eq!(display_diagnostic("short".into()), "short");
    }
    #[test]
    #[cfg(unix)]
    fn progress_is_bounded_stderr_only_and_scope_does_not_leak() {
        let progress = Progress::default();
        progress.append(&vec![b'a'; 10000]);
        assert_eq!(progress.text().len(), 8192);
        let progress = Progress::default();
        let output = with_progress(progress.clone(), || {
            output(
                Command::new("sh").args(["-c", "printf private; printf progress >&2"]),
                Duration::from_secs(2),
            )
        })
        .unwrap();
        assert_eq!(output.stdout, b"private");
        assert_eq!(progress.text(), "progress");
        super::output(
            Command::new("sh").args(["-c", "printf later >&2"]),
            Duration::from_secs(2),
        )
        .unwrap();
        assert_eq!(progress.text(), "progress");
    }
    #[test]
    fn already_cancelled_scope_does_not_launch_and_restores_previous() {
        let token = Cancellation::default();
        token.cancel();
        assert!(scope(token, check).is_err());
        assert!(check().is_ok());
    }
    #[test]
    #[cfg(unix)]
    fn timeout_and_cancellation_reap_child_group() {
        let start = Instant::now();
        let error = output(
            Command::new("sh").args(["-c", "sleep 10 & wait"]),
            Duration::from_millis(30),
        )
        .unwrap_err();
        assert!(error.to_string().contains("超时"));
        assert!(start.elapsed() < Duration::from_secs(2));
        let token = Cancellation::default();
        let other = token.clone();
        let trigger = std::thread::spawn(move || {
            std::thread::sleep(Duration::from_millis(30));
            other.cancel();
        });
        let error = scope(token, || {
            output(
                Command::new("sh").args(["-c", "sleep 10 & wait"]),
                Duration::from_secs(20),
            )
        })
        .unwrap_err();
        trigger.join().unwrap();
        assert!(error.to_string().contains("取消"));
    }
}
