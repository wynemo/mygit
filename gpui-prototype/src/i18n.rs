//! Application text only. Language is selected at startup; user and Git content are never translated.
use std::sync::atomic::{AtomicBool, Ordering};
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum Language {
    #[default]
    Chinese,
    English,
}
impl Language {
    pub fn from_saved(value: &str) -> Self {
        if value == "English" {
            Self::English
        } else {
            Self::Chinese
        }
    }
    pub fn saved(self) -> &'static str {
        match self {
            Self::Chinese => "中文",
            Self::English => "English",
        }
    }
}
static ENGLISH: AtomicBool = AtomicBool::new(false);
/// Call once at application startup. Preference edits take effect on restart.
pub fn initialize(language: Language) {
    ENGLISH.store(language == Language::English, Ordering::Relaxed);
}
pub fn is_english() -> bool {
    ENGLISH.load(Ordering::Relaxed)
}
pub fn text(value: &'static str) -> &'static str {
    translate(
        if is_english() {
            Language::English
        } else {
            Language::Chinese
        },
        value,
    )
}
pub fn translate(language: Language, value: &str) -> &str {
    if language == Language::Chinese {
        return value;
    }
    match value {
        "提交信息 · 仅提交暂存区内容，未保存编辑不包含在内" => {
            "Commit message · Only staged changes are committed; unsaved edits are excluded"
        }
        "AI 配置" => "AI settings",
        "生成中…" => "Generating…",
        "AI 生成" => "Generate with AI",
        "取消 AI" => "Cancel AI",
        "执行中…" => "Running…",
        "提交暂存内容" => "Commit staged changes",
        "AI 生成草稿（可编辑）" => "AI draft (editable)",
        "应用到提交信息（替换）" => "Replace commit message with draft",
        "提交信息（手动草稿）" => "Commit message (manual draft)",
        "分支 · {} 个引用" => "Branches · {} refs",
        "显示所有分支" => "Show all branches",
        "建立跟踪并切换" => "Track and switch",
        "切换选中分支" => "Switch to selected branch",
        "关闭" => "Close",
        "远程 " => "Remote ",
        "本地 " => "Local ",
        "没有分支引用；空仓库可输入新分支名，起点用 HEAD。" => {
            "No branch refs. For an empty repository, enter a new branch name with HEAD as its base."
        }
        "新分支名 / 远程本地名" => "New branch / local tracking name",
        "新分支起点 / Reset 目标" => "New branch base / reset target",
        "创建并切换" => "Create and switch",
        "远程" => "Remote",
        "合并选中到当前" => "Merge selected into current",
        "Reset 至上方目标：" => "Reset to the target above:",
        "选择引用可设为新分支起点。切换沿用 Git 对未提交内容的保护；远程检出建立本地跟踪分支。" => {
            "Select a ref to use as the new branch base. Git protects uncommitted changes when switching; remote checkout creates a local tracking branch."
        }
        "关闭其他" => "Close others",
        "关闭全部" => "Close all",
        "全部变更 · HEAD ↔ 工作区" => "All changes · HEAD ↔ worktree",
        "已暂存 · HEAD ↔ index" => "Staged · HEAD ↔ index",
        "未暂存 · index ↔ 工作区" => "Unstaged · index ↔ worktree",
        "{} · 已加载 {count} 条" => "{} · {count} loaded",
        "查询结果" => "Search results",
        "提交 DAG" => "Commit DAG",
        "短灰线：父提交未包含在结果中" => {
            "Short gray lines: parent commits outside the results"
        }
        "正在加载历史…" => "Loading history…",
        "加载更多" => "Load more",
        "选中提交 ↔ 工作区" => "Selected commit ↔ worktree",
        "合并提交三栏查看" => "Three-column merge view",
        "复制 SHA" => "Copy SHA",
        "复制信息" => "Copy message",
        "提交者：{} <{}>\n{}" => "Committer: {} <{}>\n{}",
        "父提交：{}" => "Parents: {}",
        "当前文件历史" => "Current file history",
        "暂存选中" => "Stage selected",
        "取消暂存" => "Unstage selected",
        "暂存全部" => "Stage all",
        "取消全部" => "Unstage all",
        "无末尾换行" => "No newline at end of file",
        "隐藏 Blame" => "Hide Blame",
        "正在读取三侧 Blame…" => "Loading Blame for three sides…",
        "首父双栏" => "First-parent split view",
        "上一处" => "Previous change",
        "下一处" => "Next change",
        "合并提交历史 · 紫色：结果与双方不同；绿色/蓝色：与父 1/父 2 不同 · 右键复制原始行" => {
            "Merge history · Purple: differs from both parents; green/blue: differs from parent 1/2 · Right-click to copy original lines"
        }
        "父提交 1" => "Parent 1",
        "合并结果" => "Merge result",
        "父提交 2" => "Parent 2",
        "该版本中不存在此文件" => "This file does not exist in this revision",
        "复制内容" => "Copy content",
        "父 1 ↔ 结果：{}；父 2 ↔ 结果：{}" => {
            "Parent 1 ↔ result: {}; parent 2 ↔ result: {}"
        }
        "预览上限" => "Preview limit",
        "按需查看（最高 20 MB）" => "Load on demand (up to 20 MB)",
        "三侧文件均为空" => "All three files are empty",
        "工作区文件树" => "Worktree files",
        "历史" => "History",
        "刷新" => "Refresh",
        "正在读取目录…" => "Loading directory…",
        "输入提交 SHA/分支/标签；EMPTY 表示空内容，右侧可用 WORKTREE。比较视图只读。" => {
            "Enter a commit SHA, branch or tag; EMPTY means empty content. The right side also accepts WORKTREE. This comparison is read-only."
        }
        "左侧" => "Left",
        "右侧" => "Right",
        "开始比较" => "Compare",
        "打开仓库" => "Open repository",
        "撤销还原" => "Undo restore",
        "项目搜索" => "Project search",
        "文件定位" => "Quick open",
        "历史搜索" => "History search",
        "分支" => "Branches",
        "比较版本" => "Compare revisions",
        "提交面板" => "Commit panel",
        "文件树" => "File tree",
        "设置 / 最近仓库" => "Settings / Recent repositories",
        "取消加载" => "Cancel loading",
        "字体：{} · {}" => "Font: {} · {}",
        "切换字体" => "Cycle font",
        "历史 −" => "History −",
        "历史 +" => "History +",
        "文件 −" => "Files −",
        "文件 +" => "Files +",
        "AI API 配置" => "AI API settings",
        "代码配色" => "Code palette",
        "字体名称" => "Font family",
        "字号" => "Font size",
        "应用字体" => "Apply font",
        "清空最近仓库" => "Clear recent repositories",
        "隐藏文件栏" => "Hide file panel",
        "显示文件栏" => "Show file panel",
        "{}：{} → 工作区磁盘\n目标：{}{}\nindex 保持原样；先保存恢复记录，可用“撤销还原”恢复。" => {
            "{}: {} → worktree on disk\nTarget: {}{}\nThe index is preserved. Recovery data is saved first; use Undo restore to recover."
        }
        "还原当前差异块" => "Restore current change block",
        "还原整文件" => "Restore entire file",
        "{}\n目标提交：{}\n当前 HEAD：{}\n当前分支：{}\n这是本地操作，不会推送远程。已提交内容可从 reflog 查找。" => {
            "{}\nTarget commit: {}\nCurrent HEAD: {}\nCurrent branch: {}\nThis is a local operation; it does not push. Committed content can be found in the reflog."
        }
        "空仓库" => "Empty repository",
        "确认 Reset" => "Confirm reset",
        "确认还原" => "Confirm restore",
        "存在未保存内容" => "Unsaved changes",
        "保存失败时会保留编辑器内容，并停止关闭或切换。" => {
            "If saving fails, editor content is preserved and closing or switching stops."
        }
        "保存并继续" => "Save and continue",
        "放弃修改并继续" => "Discard changes and continue",
        "取消" => "Cancel",
        "AI API 配置 · 基础 URL 自动追加 /chat/completions" => {
            "AI API settings · /chat/completions is appended to the base URL"
        }
        "API 密钥" => "API key",
        "模型名称" => "Model name",
        "提示词" => "Prompt",
        "密钥保存在兼容 JSON 中；Unix 文件权限 0600。MYGIT_AI_API_SECRET 可覆盖密钥且无需写入配置。" => {
            "The key is stored in compatible JSON with Unix permissions 0600. MYGIT_AI_API_SECRET overrides the key without saving it to settings."
        }
        "保存 AI 配置" => "Save AI settings",
        "历史搜索 · 消息全文 / SHA / 作者" => {
            "History search · Full message / SHA / author"
        }
        "搜索" => "Search",
        "恢复普通历史" => "Reset history search",
        "关闭面板" => "Close panel",
        "查询" => "Query",
        "范围（HEAD / 分支 / 标签 / ALL）" => "Scope (HEAD / branch / tag / ALL)",
        "作者过滤" => "Author filter",
        "开始日期 YYYY-MM-DD" => "Start date YYYY-MM-DD",
        "结束日期 YYYY-MM-DD" => "End date YYYY-MM-DD",
        "{}历史：{}" => "{} history: {}",
        "目录" => "Directory",
        "跟随重命名的文件" => "File with rename tracking",
        "请先完成输入法组合" => "Finish composing text first",
        "已保存" => "Saved",
        "当前内容未保存，请先保存或关闭后重新打开" => {
            "Unsaved content. Save first, or close and reopen the editor."
        }
        "文件目标已变化或正在输入，请关闭后重新打开" => {
            "The file target changed or text is being composed. Close and reopen the editor."
        }
        "保存" => "Save",
        "重新加载" => "Reload",
        "撤销" => "Undo",
        "重做" => "Redo",
        "提交信息" => "Commit message",
        "未保存" => "Unsaved",
        "磁盘文件已变化。保存会检查冲突；无未保存修改时可重新加载。" => {
            "The file changed on disk. Saving checks for conflicts; reload is available when there are no unsaved edits."
        }
        "关闭查找" => "Close find",
        "文件快速定位 · Cmd/Ctrl+P · ↑↓ 选择 · Enter 打开 · Esc 关闭" => {
            "Quick open · Cmd/Ctrl+P · ↑↓ select · Enter open · Esc close"
        }
        "刷新索引" => "Refresh index",
        "打开" => "Open",
        "正在更新文件索引…" => "Updating file index…",
        "正在匹配…" => "Matching…",
        "索引 {} 个文件 · 匹配 {} 项 · 显示 {} 项" => {
            "{} indexed files · {} matches · {} displayed"
        }
        "没有匹配文件" => "No matching files",
        "未提交" => "Uncommitted",
        "来源：{} : {}" => "Source: {} : {}",
        "该行尚无提交归属" => "This line has not been committed",
        "单击查看历史，右击复制 SHA" => "Click to view history; right-click to copy SHA",
        "选择文件查看差异" => "Select a file to view differences",
        "查看 Diff" => "View Diff",
        "编辑工作区" => "Edit worktree",
        "还原文件" => "Restore file",
        "还原当前块" => "Restore current block",
        "双栏" => "Split view",
        "统一视图" => "Unified view",
        "全选" => "Select all",
        "复制" => "Copy",
        "{} · {} · 选区 {} 字节" => "{} · {} · {} selected bytes",
        "字号 −" => "Font −",
        "字号 +" => "Font +",
        "2 MB 预览上限" => "2 MB preview limit",
        "按需预览（最高 20 MB）" => "Load preview (up to 20 MB)",
        "正在读取两侧 Blame…" => "Loading Blame for both sides…",
        "正在加载…" => "Loading…",
        "{}：没有变更文件" => "{}: no changed files",
        "打开一个 Git 仓库开始浏览" => "Open a Git repository to start browsing",
        "项目内容搜索 · Cmd/Ctrl+Shift+F · ↑↓ 选择 · Enter 打开" => {
            "Project search · Cmd/Ctrl+Shift+F · ↑↓ select · Enter open"
        }
        "重新搜索" => "Search again",
        "包含 glob（例如 *.rs）" => "Include glob (e.g. *.rs)",
        "排除 glob（例如 target/**）" => "Exclude glob (e.g. target/**)",
        "大小写" => "Case sensitive",
        "✓ 大小写" => "✓ Case sensitive",
        "正则" => "Regex",
        "✓ 正则" => "✓ Regex",
        "整词" => "Whole word",
        "✓ 整词" => "✓ Whole word",
        "隐藏文件" => "Hidden files",
        "✓ 隐藏文件" => "✓ Hidden files",
        "正在搜索磁盘内容…" => "Searching disk contents…",
        "显示 {} 个文件 / {} 个匹配行 / {} 处匹配{} · 跳过编码 {} 项" => {
            "{} files / {} matching lines / {} matches{} · {} skipped for encoding"
        }
        "（已达上限，请缩小范围）" => " (limit reached; narrow the scope)",
        "遵循 rg 忽略规则 · 单文件 ≤20 MB · 最多 2,000 行 · 搜索磁盘内容" => {
            "Uses rg ignore rules · Files ≤20 MB · Up to 2,000 lines · Searches disk contents"
        }
        "请输入查询；没有匹配结果" => "Enter a query; no matches",
        "{}:{} · {} 处" => "{}:{} · {} matches",
        "设置" => "Settings",
        "退出" => "Quit",
        "仓库" => "Repository",
        "分支管理" => "Manage branches",
        "项目内容搜索" => "Project content search",
        "文件快速定位" => "Quick open",
        "显示 / 隐藏文件栏" => "Show / hide file panel",
        "全部变更" => "All changes",
        "已暂存" => "Staged",
        "未暂存" => "Unstaged",
        "复制提交 SHA" => "Copy commit SHA",
        "工作区" => "Worktree",
        "暂存选中文件" => "Stage selected files",
        "取消暂存选中文件" => "Unstage selected files",
        "暂存全部文件" => "Stage all files",
        "取消全部暂存" => "Unstage all files",
        "编辑" => "Edit",
        "差异" => "Diff",
        "无法创建窗口" => "Unable to create window",
        "选择 Git 仓库" => "Select Git repository",
        "无法打开目录选择器：{other:?}" => "Unable to open directory picker: {other:?}",
        "Git 写操作正在执行，请等待完成后再切换或刷新仓库" => {
            "A Git write operation is running. Wait before switching or refreshing repositories."
        }
        "正在读取仓库…" => "Loading repository…",
        "正在读取{}…" => "Loading {}…",
        "{} · {} 个文件" => "{} · {} files",
        "正在比较 {}…" => "Comparing {}…",
        "合并文件不再存在" => "The merge file no longer exists",
        "正在加载编辑器 {path}…" => "Loading editor for {path}…",
        "编辑器已打开，点击文本开始输入" => {
            "Editor opened; click the text to start typing"
        }
        "正在按需读取大文件（最高 20 MB）…" => {
            "Loading large file on demand (up to 20 MB)…"
        }
        "正在更新已保存 Diff…" => "Updating saved Diff…",
        "还原涉及未保存文件，请先保存或关闭编辑器修改" => {
            "Restore affects unsaved files. Save or close the edited files first."
        }
        "请先定位要还原的差异块" => "Select a change block to restore first",
        "正在保存恢复记录并还原…" => "Saving recovery data and restoring…",
        "还原来源已变化，请刷新 Diff 后重新选择块" => {
            "The restore source changed. Refresh the Diff and select a block again."
        }
        "已还原，index 保持原样；恢复记录：{}" => {
            "Restored; index preserved. Recovery data: {}"
        }
        "请先保存未保存的编辑，再撤销还原" => {
            "Save unsaved edits before undoing restore"
        }
        "正在撤销最近还原…" => "Undoing the last restore…",
        "已撤销还原：{}" => "Restore undone: {}",
        "Git 写操作执行中，请等待完成后退出" => {
            "A Git write operation is running. Wait before quitting."
        }
        "仍有文件未保存，请处理保存错误或取消关闭" => {
            "Some files are still unsaved. Resolve saving errors or cancel closing."
        }
        "所选文件有未保存修改，请先保存后再暂存" => {
            "Selected files have unsaved edits. Save them before staging."
        }
        "正在暂存…" => "Staging…",
        "正在取消暂存…" => "Unstaging…",
        "index 已更新" => "Index updated",
        "正在解析比较版本…" => "Resolving comparison revisions…",
        "正在提交暂存内容…" => "Committing staged changes…",
        "Git 操作失败：{error:#}" => "Git operation failed: {error:#}",
        "正在打开 {path}…" => "Opening {path}…",
        "{message}；请使用文件预览入口" => "{message}; use the file preview action",
        "文件已打开，但无法定位：{error}" => {
            "File opened, but unable to navigate: {error}"
        }
        "加载历史失败：{e:#}" => "Unable to load history: {e:#}",
        "Git 写操作执行中，请等待结果" => {
            "A Git write operation is running. Wait for the result."
        }
        "AI 任务已取消，手动草稿保留" => "AI task cancelled; manual draft preserved",
        "已取消搜索，可修改查询或点击重新搜索重试" => {
            "Search cancelled. Change the query or search again to retry."
        }
        "已取消文件定位任务，可刷新索引重试" => {
            "Quick open cancelled. Refresh the index to retry."
        }
        "已取消 Blame，可隐藏后重新显示重试" => {
            "Blame cancelled. Hide and show it again to retry."
        }
        "已取消，可刷新或重新选择" => "Cancelled. Refresh or select again to retry.",
        "无法保存设置：{e:#}" => "Unable to save settings: {e:#}",
        "请先完成字体设置输入" => "Finish composing the font settings first",
        "字体设置已应用" => "Font settings applied",
        "正在按当前暂存 Diff 生成…（15 秒超时）" => {
            "Generating from the current staged Diff… (15-second timeout)"
        }
        "生成草稿可编辑；点击应用将替换手动草稿，可撤销" => {
            "The generated draft is editable. Applying it replaces the manual draft and can be undone."
        }
        "AI 生成失败：{error:#}；可继续手动提交" => {
            "AI generation failed: {error:#}; you can still commit manually"
        }
        "请先完成输入法组合，再应用草稿" => {
            "Finish composing text before applying the draft"
        }
        "暂存区或 HEAD 已改变，请重新生成；当前草稿保留" => {
            "The index or HEAD changed. Generate again; the current draft is preserved."
        }
        "校验期间草稿有修改，请再次点击应用" => {
            "The draft changed during validation. Click apply again."
        }
        "已应用 AI 草稿，可继续编辑或撤销；尚未提交" => {
            "AI draft applied. You can edit or undo it; no commit has been made."
        }
        "无法应用草稿：{error:#}" => "Unable to apply draft: {error:#}",
        "无法校验暂存区：{error:#}" => "Unable to validate index: {error:#}",
        "无法加载 AI 配置：{error:#}" => "Unable to load AI settings: {error:#}",
        "请先完成输入法组合，再保存配置" => {
            "Finish composing text before saving settings"
        }
        "AI 配置无效：{error:#}" => "Invalid AI settings: {error:#}",
        "AI 配置已保存；尚未发送请求" => "AI settings saved; no request has been sent",
        "无法保存 AI 配置，请检查文件权限；输入保留" => {
            "Unable to save AI settings. Check file permissions; input is preserved."
        }
        "AI 任务已取消，草稿保留" => "AI task cancelled; draft preserved",
        "请先保存或关闭未保存的编辑内容，再执行此 Git 操作" => {
            "Save or close unsaved edits before running this Git operation"
        }
        "正在切换分支…" => "Switching branches…",
        "正在创建分支…" => "Creating branch…",
        "正在 Fetch…" => "Fetching…",
        "正在 Pull…" => "Pulling…",
        "正在 Push…" => "Pushing…",
        "正在合并分支…" => "Merging branch…",
        "正在检查 Reset 目标…" => "Checking reset target…",
        "正在 Reset…" => "Resetting…",
        "历史查询失败：{error:#}" => "History search failed: {error:#}",
        "历史分页失败：{error:#}" => "Unable to load more history: {error:#}",
        "文件监听不可用，将定期刷新：{error:#}" => {
            "File watching unavailable; periodic refresh enabled: {error:#}"
        }
        "刷新失败：{error:#}" => "Refresh failed: {error:#}",
        "父提交 2 Blame：{error:#}" => "Parent 2 Blame: {error:#}",
        "打开一个 Git 仓库" => "Open a Git repository",
        "无内容差异" => "No content differences",
        "{} 行 · {} 处差异" => "{} lines · {} changes",
        "旧版本" => "Old revision",
        "新版本" => "New revision",
        "提交 · {}" => "Commit · {}",
        "暂存区（index）" => "Staging area (index)",
        "工作区（磁盘）" => "Worktree (disk)",
        "空内容" => "Empty content",
        "提交变更" => "Commit changes",
        "合并提交三栏" => "Three-column merge",
        "自定义比较" => "Custom comparison",
        "界面语言" => "Interface language",
        "保存后重启生效" => "Takes effect after restarting",
        "语言设置已保存，请重启应用生效" => {
            "Language preference saved. Restart the app to apply it."
        }
        "无法读取 AI 配置 JSON" => "Unable to read AI settings JSON",
        "无法读取 AI 配置" => "Unable to read AI settings",
        "AI 配置超过长度上限" => "AI settings exceed the length limit",
        "AI 密钥或模型名称含不支持的控制字符" => {
            "AI key or model name contains unsupported control characters"
        }
        "请先配置 AI 模型名称" => "Configure the AI model name first",
        "请配置有效的 AI API 基础 URL" => "Configure a valid AI API base URL",
        "AI API URL 需为 HTTP/HTTPS 基础地址，不能包含登录信息、查询或片段" => {
            "The AI API URL must use HTTP/HTTPS and contain no credentials, query or fragment"
        }
        "暂存区存在未解决冲突，无法生成提交信息" => {
            "The index has unresolved conflicts; unable to generate a commit message"
        }
        "没有已暂存的变更" => "No staged changes",
        "暂存 Diff 超过 1 MB，未发送请求；请拆分提交" => {
            "Staged Diff exceeds 1 MB; no request was sent. Split the commit."
        }
        "暂存 Diff 不是 UTF-8，无法生成提交信息" => {
            "The staged Diff is not UTF-8; unable to generate a commit message"
        }
        "暂存区或 HEAD 在读取期间改变，请重试" => {
            "The index or HEAD changed while reading; retry"
        }
        "暂存区或 HEAD 在生成期间改变，未应用结果，请重试" => {
            "The index or HEAD changed during generation; the result was not applied. Retry."
        }
        "AI 请求需要 1 MB 以内的非空暂存 Diff" => {
            "AI requests require a nonempty staged Diff within 1 MB"
        }
        "AI 请求已取消" => "AI request cancelled",
        "AI 请求超时" => "AI request timed out",
        "无法执行 AI 请求，请检查 curl 安装与网络" => {
            "Unable to run AI request; check curl installation and network"
        }
        "AI 响应超过 1 MB 上限" => "AI response exceeds the 1 MB limit",
        "AI 请求超时（15 秒）" => "AI request timed out (15 seconds)",
        "AI 请求失败，请检查网络、证书与 API 配置" => {
            "AI request failed; check the network, certificates and API settings"
        }
        "AI 响应缺少 HTTP 状态" => "AI response is missing the HTTP status",
        "AI API 调用失败：HTTP {status}" => "AI API request failed: HTTP {status}",
        "AI API 返回无效 JSON" => "AI API returned invalid JSON",
        "AI API 未返回文本提交信息" => "AI API did not return a text commit message",
        "AI 提交信息为空、过长或包含 NUL" => {
            "AI commit message is empty, too long or contains NUL"
        }
        "缺少父目录" => "Missing parent directory",
        "缺少有效父目录" => "Missing valid parent directory",
        "路径的父目录位于仓库外，停止还原" => {
            "The parent directory is outside the repository; restore stopped"
        }
        "链接目标不是 UTF-8" => "The link target is not UTF-8",
        "目录/特殊文件不能使用文件还原操作" => {
            "Directories and special files cannot be restored as files"
        }
        "文件超过 20 MB 恢复记录上限" => "File exceeds the 20 MB recovery limit",
        "特殊文件不能还原" => "Special files cannot be restored",
        "文件在读取期间超过上限" => "File exceeded the size limit while reading",
        "此平台不能恢复符号链接" => "This platform cannot restore symbolic links",
        "恢复记录数据路径无效" => "Invalid recovery data path",
        "恢复记录数据无效或超过上限" => {
            "Recovery data is invalid or exceeds the size limit"
        }
        "本次还原超过 64 MB 恢复记录上限，请分批操作" => {
            "Restore exceeds the 64 MB recovery limit; restore in smaller batches"
        }
        "磁盘文件在准备还原时变化，未执行还原" => {
            "The disk file changed while preparing; restore was not performed"
        }
        "磁盘文件在还原期间变化" => "The disk file changed during restore",
        "{p} 已变化，保留现场" => "{p} changed; its current state is preserved",
        "{error:#}；恢复记录位于 {}；回退结果：{}" => {
            "{error:#}; recovery data: {}; rollback result: {}"
        }
        "已回退" => "Rolled back",
        "请选择还原文件" => "Select a file to restore",
        "请先选择差异块" => "Select a change block first",
        "差异块还原仅支持已存在的普通文本文件" => {
            "Change block restore requires an existing regular text file"
        }
        "磁盘内容已偏离当前 Diff，请刷新后再还原" => {
            "Disk content no longer matches the Diff; refresh before restoring"
        }
        "当前文件不是 UTF-8" => "The current file is not UTF-8",
        "没有可撤销的还原记录" => "No restore record to undo",
        "{} 已在还原后改变，撤销不会覆盖新内容" => {
            "{} changed after restore; undo will not overwrite new content"
        }
        "文件在撤销期间变化，停止操作" => {
            "The file changed during undo; operation stopped"
        }
        "当前仓库没有可撤销的还原记录" => {
            "This repository has no restore record to undo"
        }
        "分支引用不是 UTF-8" => "Branch ref is not UTF-8",
        "无法读取完整分支引用" => "Unable to read complete branch refs",
        "未知分支引用" => "Unknown branch ref",
        "请输入有效分支名" => "Enter a valid branch name",
        "目标分支已不存在，请刷新列表" => {
            "The target branch no longer exists; refresh the list"
        }
        "远程配置已不存在，请先检查远程" => {
            "The remote configuration no longer exists; check remotes first"
        }
        "已建立跟踪分支 {name} → {}" => "Created tracking branch {name} → {}",
        "已切换到 {}" => "Switched to {}",
        "新分支起点必须是提交/分支/标签" => {
            "The branch base must be a commit, branch or tag"
        }
        "已创建并切换到 {name}" => "Created and switched to {name}",
        "三栏历史查看需要恰好两个父提交；当前提交有 {} 个父提交" => {
            "Three-column history requires exactly two parents; this commit has {} parents"
        }
        "三栏历史查看需要恰好两个父提交" => {
            "Three-column history requires exactly two parents"
        }
        "三侧内容合计超过 {} MB 预览上限" => {
            "Total content across three sides exceeds the {} MB preview limit"
        }
        "合并结果行映射无效" => "Invalid merge-result line mapping",
        "合并结果行映射不完整" => "Incomplete merge-result line mapping",
        "父提交 1：{l}\n父提交 2：{r}" => "Parent 1: {l}\nParent 2: {r}",
        "父提交 1：{l}" => "Parent 1: {l}",
        "父提交 2：{r}" => "Parent 2: {r}",
        "两侧比较的合并结果不一致" => {
            "The merge results in the two comparisons do not match"
        }
        "Git 返回非 UTF-8 文本，暂不支持该路径或编码" => {
            "Git returned non-UTF-8 text; this path or encoding is not supported"
        }
        "HEAD 在刷新期间改变，稍后重试" => "HEAD changed during refresh; retry later",
        "引用标签格式无效" => "Invalid ref label format",
        "提交历史格式无效" => "Invalid commit history format",
        "提交详情格式无效" => "Invalid commit detail format",
        "文件路径不是 UTF-8，暂不支持预览" => {
            "The file path is not UTF-8; preview is unavailable"
        }
        "Git 文件列表缺少路径" => "Git file list is missing a path",
        "重命名记录缺少目标路径" => "Rename record is missing the destination path",
        "未跟踪文件路径不是 UTF-8" => "Untracked file path is not UTF-8",
        "比较版本不能为空" => "Comparison revisions cannot be empty",
        "自定义比较左侧必须是提交或 EMPTY，右侧可用提交或 WORKTREE" => {
            "The left revision must be a commit or EMPTY; the right may be a commit or WORKTREE"
        }
        "文件路径必须位于当前仓库" => {
            "The file path must be inside the current repository"
        }
        "请选择要暂存的文件" => "Select files to stage",
        "所选路径已不存在，请刷新状态" => {
            "The selected path no longer exists; refresh status"
        }
        "请选择要取消暂存的文件" => "Select files to unstage",
        "提交信息不能为空" => "Commit message cannot be empty",
        "仍有未解决的冲突，不能提交" => "Unresolved conflicts remain; cannot commit",
        "暂存区为空，请先暂存文件" => "The index is empty; stage files first",
        "状态路径不是 UTF-8" => "Status path is not UTF-8",
        "状态记录无效" => "Invalid status record",
        "重命名缺少原路径" => "Rename is missing its original path",
        "无法读取工作区 {}" => "Unable to read worktree {}",
        "符号链接" => "Symbolic link",
        "子模块未检出" => "Submodule not checked out",
        "子模块" => "Submodule",
        "目录不是普通文件或已登记的子模块" => {
            "The directory is not a regular file or registered submodule"
        }
        "特殊文件不支持预览" => "Special files cannot be previewed",
        "文本/二进制文件" => "Text/binary file",
        "缺少对象信息" => "Missing object information",
        "对象模式无效" => "Invalid object mode",
        "缺少对象 ID" => "Missing object ID",
        "不支持的 Git 对象模式：{mode}" => "Unsupported Git object mode: {mode}",
        "缺少 blob ID" => "Missing blob ID",
        "还原来源必须是提交、index 或空内容" => {
            "The restore source must be a commit, index or empty content"
        }
        "还原来源缺少模式" => "Restore source is missing its mode",
        "未合并 index 不能作为还原来源" => {
            "An unmerged index cannot be used as a restore source"
        }
        "子模块目录不能使用文件还原操作" => {
            "Submodule directories cannot be restored as files"
        }
        "还原文件超过 20 MB 恢复记录上限" => {
            "Restore file exceeds the 20 MB recovery limit"
        }
        "逐行归属仅支持普通文本文件" => "Blame requires a regular text file",
        "文件超过逐行归属读取上限" => "File exceeds the Blame size limit",
        "冲突文件：暂不支持预览未合并的 index 内容" => {
            "Conflicted file: preview of unmerged index content is not supported"
        }
        "左侧：{} · {} 字节；右侧：{} · {} 字节" => {
            "Left: {} · {} bytes; right: {} · {} bytes"
        }
        "子模块提交引用\n左侧：{}\n右侧：{}\n目录内容不作为普通文本读取" => {
            "Submodule commit refs\nLeft: {}\nRight: {}\nDirectory content is not read as ordinary text"
        }
        "空/未检出" => "Empty/not checked out",
        "文件超过 {} MB 预览上限；{description}" => {
            "File exceeds the {} MB preview limit; {description}"
        }
        "日期请使用 YYYY-MM-DD" => "Use YYYY-MM-DD for dates",
        "日期无效" => "Invalid date",
        "搜索内容超过 4096 字节上限" => "Search text exceeds the 4096-byte limit",
        "开始日期不能晚于结束日期" => "Start date cannot be after end date",
        "历史范围必须是提交/分支/标签或 ALL" => {
            "History scope must be a commit, branch, tag or ALL"
        }
        "历史包含非 UTF-8 文本" => "History contains non-UTF-8 text",
        "历史记录格式无效" => "Invalid history record format",
        "无法读取目录 {parent}" => "Unable to read directory {parent}",
        "目录存在非 UTF-8 文件名" => "Directory contains a non-UTF-8 file name",
        "变更" => "Changes",
        "编辑文件超过 2 MB 上限" => "Editable file exceeds the 2 MB limit",
        "二进制文件不可编辑" => "Binary files cannot be edited",
        "编辑仅支持 UTF-8 文本" => "Editing requires UTF-8 text",
        "输入范围无效" => "Invalid input range",
        "缓冲区没有文件路径" => "Buffer has no file path",
        "磁盘文件已被外部修改，未覆盖；请重新加载或另存内容" => {
            "The disk file changed externally and was not overwritten; reload or save the content elsewhere"
        }
        "文件路径缺少目录" => "File path is missing its directory",
        "保存期间文件发生外部修改，未覆盖" => {
            "The file changed externally during save and was not overwritten"
        }
        "无法读取 {}" => "Unable to read {}",
        "仅可编辑普通文件，符号链接及目录保持只读" => {
            "Only regular files can be edited; symbolic links and directories are read-only"
        }
        "仅可编辑普通文件" => "Only regular files can be edited",
        "文件索引超过 200000 项或 16 MB 路径上限" => {
            "File index exceeds 200000 entries or the 16 MB path limit"
        }
        "文件查询最多支持 256 个字符" => "File queries support up to 256 characters",
        "文件索引包含非 UTF-8 路径" => "File index contains a non-UTF-8 path",
        "文件缺少父目录" => "File is missing its parent directory",
        "当前文件尚无提交归属" => "This file has not been committed",
        "{}\n…输出较长，显示首尾…\n{}" => {
            "{}\n…Long output; showing the beginning and end…\n{}"
        }
        "任务已取消" => "Task cancelled",
        "无法启动子进程" => "Unable to start subprocess",
        "Git 操作超时，请重试" => "Git operation timed out; retry",
        "读取标准输出失败" => "Unable to read standard output",
        "读取错误输出失败" => "Unable to read standard error",
        "Git 输出超过 64 MB 上限" => "Git output exceeds the 64 MB limit",
        "子进程操作超时，请重试" => "Subprocess operation timed out; retry",
        "写入标准输入失败" => "Unable to write standard input",
        "错误输出超过 64 MB 上限" => "Error output exceeds the 64 MB limit",
        "二进制文件：暂不提供内容预览" => {
            "Binary file: content preview is unavailable"
        }
        "文件超过 {} MB 预览上限" => "File exceeds the {} MB preview limit",
        "文本超过 200000 行预览上限，暂不支持分段预览" => {
            "Text exceeds the 200000-line preview limit; partial preview is unavailable"
        }
        "旧版本不是 UTF-8 文本" => "Old revision is not UTF-8 text",
        "新版本不是 UTF-8 文本" => "New revision is not UTF-8 text",
        "匹配行已不存在，请重新搜索" => {
            "The matching line no longer exists; search again"
        }
        "文件内容在搜索后改变，请重新搜索" => {
            "The file changed after searching; search again"
        }
        "ripgrep 返回无效 JSON" => "ripgrep returned invalid JSON",
        "搜索结果缺少行号" => "Search result is missing the line number",
        "搜索行号超出范围" => "Search line number is out of range",
        "搜索行号必须从 1 开始" => "Search line numbers must start at 1",
        "搜索结果缺少匹配范围" => "Search result is missing the match range",
        "匹配起点无效" => "Invalid match start",
        "匹配终点无效" => "Invalid match end",
        "匹配范围不在 UTF-8 文本边界内" => "Match range is not on UTF-8 text boundaries",
        "查询最多 4096 字符，查询与过滤不能含 NUL" => {
            "Queries support up to 4096 characters; queries and filters cannot contain NUL"
        }
        "项目搜索失败（需要可执行的 ripgrep/rg）" => {
            "Project search failed (an executable ripgrep/rg is required)"
        }
        "ripgrep 搜索失败：{}" => "ripgrep search failed: {}",
        "\n单条搜索输出超过 64 MB，已停止读取" => {
            "\nA search record exceeds 64 MB; reading stopped"
        }
        "soft：移动 HEAD，保留暂存区及工作区内容。" => {
            "soft: Move HEAD; preserve the index and worktree."
        }
        "mixed：移动 HEAD 并重置暂存区，保留工作区磁盘内容。" => {
            "mixed: Move HEAD and reset the index; preserve worktree files."
        }
        "hard：移动 HEAD、重置暂存区及工作区；丢弃未提交的 tracked 修改，并可能删除妨碍检出的未跟踪文件。未提交内容无法用 Git reflog 恢复。" => {
            "hard: Move HEAD and reset the index and worktree; discard uncommitted tracked changes and possibly delete untracked files that block checkout. Git reflog cannot recover uncommitted content."
        }
        "远程 {name} 不存在，请检查仓库配置" => {
            "Remote {name} does not exist; check repository configuration"
        }
        "当前没有已提交的本地分支，detached HEAD/空仓库不能 Pull 或 Push" => {
            "No committed local branch; Pull and Push are unavailable with detached HEAD or an empty repository"
        }
        "{verb} 完成 · {name}\n{}" => "{verb} complete · {name}\n{}",
        "合并目标分支已不存在，请刷新" => {
            "The merge target branch no longer exists; refresh"
        }
        "合并完成 · {}\n{}" => "Merge complete · {}\n{}",
        "Reset 目标必须是提交/分支/标签" => {
            "Reset target must be a commit, branch or tag"
        }
        "HEAD 或当前分支在确认后改变，请重新选择 Reset 目标" => {
            "HEAD or the current branch changed after confirmation; select the reset target again"
        }
        "Reset 完成 · {} · {}\n{}" => "Reset complete · {} · {}\n{}",
        "字体名称必须为 1–255 字节且不含控制字符" => {
            "Font family must be 1–255 bytes without control characters"
        }
        "字号必须为数字" => "Font size must be a number",
        "字号必须为 10–22" => "Font size must be between 10 and 22",
        "配置损坏，已使用默认设置；保存时保留原文件备份" => {
            "Settings are corrupt; defaults are used and the original file is backed up when saving"
        }
        "无法读取配置，已使用默认设置" => "Unable to read settings; using defaults",
        "配置路径缺少目录" => "Settings path is missing its directory",
        "无法备份损坏配置，未覆盖原文件" => {
            "Unable to back up corrupt settings; the original was not overwritten"
        }
        "隐藏 Git 面板" => "Hide Git panel",
        "显示 Git 面板" => "Show Git panel",
        "显示 / 隐藏 Git 面板" => "Show / hide Git panel",
        "隐藏文件树" => "Hide file tree",
        "显示文件树" => "Show file tree",
        "工作区编辑器" => "Worktree editor",
        "当前标签是只读比较，显示 Git 面板查看" => {
            "This tab is a read-only comparison. Show the Git panel to view it."
        }
        "Git 面板已隐藏，选择工作区文件继续编辑" => {
            "Git panel hidden. Select a worktree file to continue editing."
        }
        "工作区内容已变化或正在输入，保留编辑器位置" => {
            "Worktree content changed or text is being composed; editor position preserved."
        }
        _ => value,
    }
}

/// Select the application's format template before formatting raw arguments.
/// Both branches are compile-checked by Rust; arguments are evaluated once.
#[macro_export]
macro_rules! localized_format {
    ($chinese:literal, $english:literal $(, $($args:tt)*)?) => {
        if $crate::i18n::is_english() {
            format!($english $(, $($args)*)?)
        } else {
            format!($chinese $(, $($args)*)?)
        }
    };
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn language_defaults_and_application_text_do_not_translate_user_content() {
        assert_eq!(Language::from_saved("English"), Language::English);
        for value in ["", "中文", "invalid", "english"] {
            assert_eq!(Language::from_saved(value), Language::Chinese);
        }
        assert_eq!(Language::English.saved(), "English");
        assert_eq!(Language::Chinese.saved(), "中文");
        assert_eq!(translate(Language::English, "打开仓库"), "Open repository");
        assert_eq!(translate(Language::Chinese, "打开仓库"), "打开仓库");
        let raw = "打开仓库/中文🙂 file.rs";
        assert_eq!(translate(Language::English, raw), raw);
        assert!(translate(Language::English, "hard：移动 HEAD、重置暂存区及工作区；丢弃未提交的 tracked 修改，并可能删除妨碍检出的未跟踪文件。未提交内容无法用 Git reflog 恢复。").contains("cannot recover uncommitted content"));
    }
}
