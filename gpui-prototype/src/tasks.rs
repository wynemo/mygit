use crate::app::MyGit;
use anyhow::Result;
use gpui::Context;

/// Every background result is checked against the current selection before applying it.
pub fn run<T: Send + 'static>(
    cx: &mut Context<MyGit>,
    generation: u64,
    token: mygit_gpui::process::Cancellation,
    job: impl FnOnce() -> Result<T> + Send + 'static,
    apply: impl FnOnce(&mut MyGit, T, &mut Context<MyGit>) + 'static,
) {
    let task = cx
        .background_executor()
        .spawn(async move { mygit_gpui::process::scope(token, job) });
    cx.spawn(async move |this, cx| {
        let result = task.await;
        let _ = this.update(cx, |this, cx| {
            if this.state.generation != generation {
                return;
            }
            this.state.loading = false;
            match result {
                Ok(value) => apply(this, value, cx),
                Err(error) => {
                    this.state.message = format!("{error:#}");
                    if error.downcast_ref::<mygit_gpui::process::Failure>()
                        != Some(&mygit_gpui::process::Failure::Cancelled)
                    {
                        this.notify_result(
                            mygit_gpui::notifications::Kind::Error,
                            this.state.message.clone(),
                            cx,
                        );
                    }
                }
            }
            cx.notify();
        });
    })
    .detach();
}
