use crate::app::MyGit;
use anyhow::Result;
use gpui::Context;

/// Every background result is checked against the current selection before applying it.
pub fn run<T: Send + 'static>(
    cx: &mut Context<MyGit>,
    generation: u64,
    job: impl FnOnce() -> Result<T> + Send + 'static,
    apply: impl FnOnce(&mut MyGit, T, &mut Context<MyGit>) + 'static,
) {
    let task = cx.background_executor().spawn(async move { job() });
    cx.spawn(async move |this, cx| {
        let result = task.await;
        let _ = this.update(cx, |this, cx| {
            if this.state.generation != generation {
                return;
            }
            this.state.loading = false;
            match result {
                Ok(value) => apply(this, value, cx),
                Err(error) => this.state.message = format!("{error:#}"),
            }
            cx.notify();
        });
    })
    .detach();
}
