use super::*;
use mygit_gpui::notifications::{Kind, TOAST_SECONDS};
impl MyGit {
    pub fn notify_result(&mut self, kind: Kind, message: String, cx: &mut Context<Self>) {
        let repository = self
            .state
            .repo
            .as_ref()
            .map(|r| r.root.clone())
            .or_else(|| self.last_path.clone());
        let id = self.notifications.push(kind, message, repository);
        cx.spawn(async move |this, cx| {
            Timer::after(std::time::Duration::from_secs(TOAST_SECONDS)).await;
            let _ = this.update(cx, |this, cx| {
                if this.notifications.dismiss(id) {
                    cx.notify();
                }
            });
        })
        .detach();
        cx.notify();
    }
    pub fn toggle_notifications(&mut self, cx: &mut Context<Self>) {
        if self.confirmation.is_some() {
            return;
        }
        self.show_notifications = !self.show_notifications;
        self.restore_main_focus = true;
        cx.notify();
    }
    pub fn copy_notification(&mut self, id: u64, cx: &mut Context<Self>) {
        if let Some(notice) = self.notifications.entries().iter().find(|n| n.id == id) {
            cx.write_to_clipboard(ClipboardItem::new_string(notice.copy_text()));
        }
    }
}
