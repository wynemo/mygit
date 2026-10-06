use gpui::{prelude::*, *};

pub fn icon(path: &'static str) -> Svg {
    svg()
        .path(path)
        .size(px(16.))
        .flex_shrink_0()
        .text_color(rgb(0x202020))
}
pub fn file(path: &str) -> Img {
    img(ImageSource::Resource(Resource::Embedded(
        mygit_gpui::resources::file_icon(path).into(),
    )))
    .size(px(16.))
    .flex_shrink_0()
}
pub fn button_icon(id: &str) -> Option<&'static str> {
    Some(match id {
        "open" => "icons/folder.svg",
        "refresh" | "refresh-tree" | "refresh-branches" => "icons/refresh.svg",
        "settings" => "icons/settings.svg",
        "project-search" | "quick-open" | "history-search" => "icons/search.svg",
        "show-branches" | "switch-branch" | "create-branch" => "icons/git_branch.svg",
        "show-commit" | "commit-index" => "icons/commit_icon.svg",
        "fetch-remote" => "icons/fetch.svg",
        "pull-remote" => "icons/pull.svg",
        "push-remote" => "icons/push.svg",
        "previous-diff" | "merge-prev" => "icons/up.svg",
        "next-diff" | "merge-next" => "icons/down.svg",
        _ => return None,
    })
}
