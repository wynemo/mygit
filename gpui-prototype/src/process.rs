//! Bounded, cancellable child execution. Each UI job gets its own cancellation scope.
use anyhow::{Context, Result, bail};
use std::{
    cell::RefCell,
    io::Read,
    process::{Command, Output, Stdio},
    sync::{
        Arc,
        atomic::{AtomicBool, Ordering},
    },
    time::{Duration, Instant},
};

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
        bail!("任务已取消");
    }
    Ok(())
}
fn drain(mut reader: impl Read) -> std::io::Result<(Vec<u8>, bool)> {
    let mut bytes = vec![];
    let mut buf = [0u8; 8192];
    let mut exceeded = false;
    loop {
        let n = reader.read(&mut buf)?;
        if n == 0 {
            break;
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
    let mut child = command.spawn().context("无法启动子进程")?;
    let stdout = child.stdout.take().unwrap();
    let stderr = child.stderr.take().unwrap();
    let started = Instant::now();
    // Scoped readers always finish after the child/process group is reaped.
    std::thread::scope(|scope| {
        let out = scope.spawn(|| drain(stdout));
        let err = scope.spawn(|| drain(stderr));
        let mut reason = None;
        let status = loop {
            match child.try_wait() {
                Ok(Some(status)) => break Ok(status),
                Ok(None) => {}
                Err(error) => break Err(error),
            }
            if check().is_err() || started.elapsed() >= timeout {
                reason = Some(if started.elapsed() >= timeout {
                    "Git 操作超时，请重试"
                } else {
                    "任务已取消"
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
        let (stdout, stdout_exceeded) = out
            .join()
            .map_err(|_| anyhow::anyhow!("读取标准输出失败"))??;
        let (stderr, stderr_exceeded) = err
            .join()
            .map_err(|_| anyhow::anyhow!("读取错误输出失败"))??;
        if let Some(reason) = reason {
            bail!("{reason}");
        }
        if stdout_exceeded || stderr_exceeded {
            bail!("Git 输出超过 64 MB 上限");
        }
        Ok(Output {
            status: status?,
            stdout,
            stderr,
        })
    })
}
#[cfg(test)]
mod tests {
    use super::*;
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
