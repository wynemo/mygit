//! Workspace files open in the editor, independently of the selected Git commit.
use crate::{app::MyGit, views::tabs};
use gpui::{prelude::*, *};
pub fn pane(this: &MyGit, cx: &mut Context<MyGit>) -> impl IntoElement {
    div()
        .id("workspace-editor-pane")
        .flex()
        .flex_col()
        .flex_1()
        .min_w_0()
        .min_h_0()
        .child(tabs::bar(this, cx))
        .when_some(this.current_editor(), |s, editor| s.child(editor))
}
