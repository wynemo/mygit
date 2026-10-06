use gpui::{prelude::*, *};
pub struct Hint(pub SharedString);
impl Render for Hint {
    fn render(&mut self, _: &mut Window, _: &mut Context<Self>) -> impl IntoElement {
        div()
            .max_w(px(400.))
            .p_2()
            .rounded_md()
            .bg(rgb(crate::views::theme::CHROME))
            .text_color(rgb(crate::views::theme::TEXT))
            .text_size(px(12.))
            .child(self.0.clone())
    }
}
pub fn button_hint(id: &str) -> Option<&'static str> {
    let (zh, en) = match id {
        "tree-actions" => (
            "选中文件的历史、路径、显示位置和还原操作 · Shift+F10",
            "History, paths, reveal and restore for the selected file · Shift+F10",
        ),
        "current-file-history" | "workspace-history" => (
            "查看当前完整路径的历史，跟随文件重命名",
            "View history for the current full path, following file renames",
        ),
        "workspace-blame" => (
            "显示或隐藏当前编辑缓冲区的逐行归属",
            "Show or hide line attribution for the current editing buffer",
        ),
        "edit-current-worktree" => (
            "打开同一路径的磁盘文件编辑；历史版本保持只读",
            "Edit the file at the same path on disk; historical versions remain read-only",
        ),
        "compare-current-worktree" => (
            "当前已提交文件版本与磁盘内容比较；不改写文件",
            "Compare this committed file version with its content on disk without writing files",
        ),
        "open" => (
            "打开本地 Git 仓库 · Cmd/Ctrl+O",
            "Open a local Git repository · Cmd/Ctrl+O",
        ),
        "refresh" => (
            "重新读取仓库状态 · Cmd/Ctrl+R",
            "Refresh repository status · Cmd/Ctrl+R",
        ),
        "project-search" => (
            "搜索磁盘文件内容 · Cmd/Ctrl+Shift+F",
            "Search file contents on disk · Cmd/Ctrl+Shift+F",
        ),
        "quick-open" => (
            "按文件名定位工作区文件 · Cmd/Ctrl+P",
            "Find a worktree file by name · Cmd/Ctrl+P",
        ),
        "show-commit" => (
            "打开提交草稿；仅提交已暂存内容 · Cmd/Ctrl+K",
            "Open the commit draft; only staged changes are committed · Cmd/Ctrl+K",
        ),
        "toggle-git-panel" | "settings-toggle-git" | "workspace-show-git" => (
            "显示或隐藏 Git 区域，保留工作区编辑内容 · Cmd/Ctrl+J",
            "Show or hide Git views while preserving worktree edits · Cmd/Ctrl+J",
        ),
        "toggle-files-panel" => (
            "显示或隐藏文件栏 · Cmd/Ctrl+B",
            "Show or hide the file panel · Cmd/Ctrl+B",
        ),
        "notifications" => (
            "查看最近 16 条操作通知 · Cmd/Ctrl+Shift+M",
            "View the last 16 operation notifications · Cmd/Ctrl+Shift+M",
        ),
        "clear-notifications" => (
            "清空本次运行的通知记录，不影响任务或仓库",
            "Clear this session's notifications without affecting jobs or the repository",
        ),
        "copy-notice" => (
            "复制通知详情及所属仓库路径",
            "Copy notification details and the associated repository path",
        ),
        "cancel-task" => (
            "取消读取任务；Git 写操作需等待完成 · Esc",
            "Cancel read tasks; Git writes must finish · Esc",
        ),
        "edit-file" | "workspace-edit-file" => (
            "编辑磁盘上的工作区文本；保存时检查外部修改",
            "Edit worktree text on disk; saving checks for external changes",
        ),
        "save-editor" => (
            "保存当前文件，检测外部修改冲突 · Cmd/Ctrl+S",
            "Save this file and check for external changes · Cmd/Ctrl+S",
        ),
        "reload-editor" => (
            "从磁盘重新加载；未保存编辑不会被覆盖",
            "Reload from disk; unsaved edits will not be overwritten",
        ),
        "undo-editor" => ("撤销编辑 · Cmd/Ctrl+Z", "Undo edit · Cmd/Ctrl+Z"),
        "redo-editor" => (
            "重做编辑 · Cmd/Ctrl+Shift+Z",
            "Redo edit · Cmd/Ctrl+Shift+Z",
        ),
        "previous-diff" | "merge-prev" => ("定位上一处差异", "Navigate to the previous change"),
        "next-diff" | "merge-next" => ("定位下一处差异", "Navigate to the next change"),
        "scroll-left" | "merge-left" => ("向左横向滚动", "Scroll horizontally to the left"),
        "scroll-right" | "merge-right" => ("向右横向滚动", "Scroll horizontally to the right"),
        "font-smaller" | "merge-smaller" => ("减小代码字号", "Decrease code font size"),
        "font-larger" | "merge-larger" => ("增大代码字号", "Increase code font size"),
        "restore-file" => (
            "还原所选文件到比较左侧版本；不改 index，可撤销",
            "Restore this file to the left revision; preserve the index and allow undo",
        ),
        "restore-block" => (
            "还原当前差异块到左侧版本；先保存未保存编辑",
            "Restore the current block from the left revision; save unsaved edits first",
        ),
        "undo-restore" => (
            "撤销最近的还原；文件有后续修改时停止覆盖",
            "Undo the last restore; stop if files changed afterward",
        ),
        "stage-selected" => (
            "将选中文件的磁盘内容加入暂存区",
            "Stage selected files' contents from disk",
        ),
        "unstage-selected" => (
            "取消选中文件的暂存，保留工作区内容",
            "Unstage selected files and preserve worktree contents",
        ),
        "stage-all" => (
            "暂存全部文件；未保存编辑不在磁盘中",
            "Stage all files; unsaved edits are not on disk",
        ),
        "unstage-all" => (
            "取消全部暂存，保留工作区内容",
            "Unstage all files and preserve worktree contents",
        ),
        "commit-index" => (
            "仅提交暂存区内容；未暂存或未保存内容不包含在内",
            "Commit only the index; unstaged and unsaved contents are excluded",
        ),
        "switch-branch" => (
            "切换所选分支；远程引用会建立本地跟踪分支",
            "Switch to the selected branch; a remote ref creates a local tracking branch",
        ),
        "create-branch" => (
            "从指定起点创建分支并切换",
            "Create a branch from the specified base and switch to it",
        ),
        "fetch-remote" => (
            "更新指定远程的引用，不合并工作区",
            "Update refs from the specified remote without merging the worktree",
        ),
        "pull-remote" => (
            "拉取并整合当前分支；沿用仓库的 Git 配置",
            "Pull and integrate the current branch using repository Git configuration",
        ),
        "push-remote" => (
            "推送当前本地分支；首次推送会建立上游关系",
            "Push the current local branch; its first push sets an upstream",
        ),
        "merge-branch" => (
            "将所选分支合并到当前分支",
            "Merge the selected branch into the current branch",
        ),
        "reset-soft" => (
            "移动 HEAD，保留暂存区和工作区；执行前确认",
            "Move HEAD, preserving the index and worktree; confirm before execution",
        ),
        "reset-mixed" => (
            "移动 HEAD 并重置暂存区，保留磁盘文件；执行前确认",
            "Move HEAD and reset the index, preserving disk files; confirm before execution",
        ),
        "reset-hard" => (
            "重置 HEAD、暂存区和工作区；丢弃未提交修改，执行前确认",
            "Reset HEAD, index and worktree; discard uncommitted changes and confirm before execution",
        ),
        "ai-generate" => (
            "使用当前全部文件变更生成可编辑草稿，无需暂存；5 分钟超时",
            "Generate an editable draft from all current changes without staging; 5-minute timeout",
        ),
        "ai-apply" => (
            "替换手动草稿，可撤销；不会自动提交",
            "Replace the manual draft with undo support; no automatic commit",
        ),
        "preview-large-file" | "merge-large-preview" => (
            "扩大预览读取范围，最高 20 MB",
            "Expand the preview read limit up to 20 MB",
        ),
        "clear-recent" => (
            "清空最近仓库及下次自动恢复路径，保留当前仓库",
            "Clear recent repositories and the next startup path, preserving the current repository",
        ),
        "language-zh" | "language-en" => (
            "语言选择保存后重启生效",
            "Restart after saving the language preference",
        ),
        _ => return None,
    };
    Some(if mygit_gpui::i18n::is_english() {
        en
    } else {
        zh
    })
}
