## todos

1. ~~仓库所有文件视图~~
2. ~~编辑器代码语法高亮，多种语言支持;完成一半了~~
3. ~~对比工作区，可以修改工作区文件；现在加入了编辑功能~~ 编辑功能不太符合使用习惯 特别是这个确定保存
4. ~~工作区文件，右键点击，可以查看单个文件历史；放到提交历史旁边，这里要弄一个 tab，也就是说，有多个 tab，一个是提交历史，其他的是单个文件的历史~~
5. ~~现有的点击提交历史的文件，比较视图弄到工作区右边的 tab_widget 里面，现在是视图下方~~
6. 把字符串抽离出来，后续做国际化
7. ~~多分支视图的绘制~~ 还不够完善
8. 在完成 7 以后，可以进行 git 3-ways merge
9. ~~接 4 的改动，点击文件历史，在右侧显示文件变化，现在放到下面的 tab 里确实好像不好用，一个文件出现那么多 tab~~
10. ~~提交历史现在只显示了一部分，需要支持拖动，加载更多~~
11. ~~提交信息太长，或者有换行时，界面上显示不出来~~
12. ~~标签页，增加关闭其他标签页的功能~~
13. ~~把提交历史、文件历史，文件差异的视图，现在是在上方，需要放到下方，并且可以隐藏与显示~~
14. ~~工作区的更改，可以在文件编辑器中显示，比如删除了一行，修改了几行，都需要显示出来~~
15. ~~commit_dialog.py 添加 git push 好像没有必要了~~
16. ~~在“提交历史”标签右边，增加 git push 按钮~~
17. ~~在 git commit 以后更新提交历史 CommitDialog.accept() commit_history_view update_history()~~
18. ~~工作区文件按字母顺序排序~~
19. ~~多行 commit 信息换行显示，参考 jetbrains ide，放在文件变化下面~~
20. ~~接 11 的改动，在鼠标移动到提交历史上时，完整显示单行提交信息~~
21. ~~“提交历史”标签，不可关闭，那么样式不需要一个“x“的关闭按钮~~
22. ~~仓库需要优先显示默认分支~~
23. ~~工作区的文件，右键菜单，加入 git annoation 支持;完成一半了~~
24. ~~git push 以后，需要有点提示；或者说界面上有点不同；同时增加推送中的交互，添加一个旋转图标，后续 git fetch/pull 也需要有这个交互~~
25. ~~CommitHistoryView 的 history_list (CustomTreeWidget) 需要显示 remote 与 local，现在只显示了 local, remote 可加 emoji ☁️~~
26. ~~点击 git annoation 单行的区域时，根据 commit 信息，需要选中 commit_history_view history_list 的相应的 item，然后 on_commit_clicked 触发~~
27. ~~git annoation 宽度不一致 希望能计算出最宽的宽度 然后合理的显示~~
28. ~~接 26 的改动，点击 git annoation 单行的区域时，现在 commit_history_view histroy_list 如果没有相应的 item 就触发不了 on_commit_clicked 这是因为 histroy_list 还没有加载，因为是滚动触发的，所以需要加载更多，这需要合理的处理~~
29. ~~CompareView, 也就是比较的时候也支持 git annotation 的显示~~
30. ~~接 29 的改动，也像 26 说的那样触发 on_commit_clicked~~
31. ~~工作区文件有修改，左边树形列表（FileTreeWidget）相应的文件显示有变化，颜色可变为棕色，表示修改了次文件~~
32. ~~GitManagerWindow 中的元素 窗口布局的大小，需要根据屏幕大小，自动调整，现在是固定大小; 比如 CommitDetailView 提交详情这个页面，需要根据内容大小，自动调整高度，现在完全挤在一起了~~
33. ~~接 31 的改动，文件视图，需要显示修改的地方~~
34. ~~set_texts 有的地方参数不对，git 短 hash 的，现在设置的为 None~~
35. ~~SyncedTextEdit 上添加上、下两个按钮，快速定位到上一个差异，下一个差异~~ 还有些问题，滚动不够灵敏，~~然后当前差异的处的行号显示应该不同，要不然以为点击上一个下一个没有反应~~
36. ~~Refresh 按钮占用太大空间了 另外想一个图标~~
37. ~~重构：GitManagerWindow top_widget top_layout 的东西能否抽离出去~~
38. ~~bug：点击“show blame” - 弹出的菜单与鼠标右键点击的地方隔太远了~~
39. bug: 文件差异的换行没有显示
40. ~~impovement: 2025-05-25 22:30:04,384 - ERROR - root - 拉取仓库时发生错误 -  出现 git pull 异常时要提示~~
41. ~~feature: 在 synced_text_edit 上添加查找功能 ctrl/command + f 可以触发~~
42. ~~接 41 的改动，ctrl + f，如果有选中的文字，那么查找的文字就是选中的文字；此外，高亮的效果太差了，需要弄成蓝色背景~~
43. ~~text_edit.py/FindDialog 换成浮动的 widget, 查找的过程浮动在 SyncedTextEdit 之上，然后 SyncedTextEdit 不会失焦~~
44. ~~git push 以后，需要更新分支的 remote 提示~~
45. ~~SyncedTextEdit 字体大小是硬编码的~~
46. ~~比较页面，也需要有代码语法高亮的支持~~
47. ~~untracked files 在 workspace_explorer FileTreeWidget 需要显示状态 可显示为灰色~~
48. ~~修复 git push 时的动画 bug: QPropertyAnimation: you're trying to animate a non-existing property _rotation_angle of your QObject~~
49. ~~windows 阶段测试 没有明显问题~~
50. linux 阶段测试
60. ~~与工作区比较，加入编辑功能~~
61. 将 fetch pull push 等按钮放到左下角
62. macOS 失焦问题，对话框灰色，输入法无效，要切换到别的窗口再切换回来才正常；打包成 app 试试还有没有这个问题
63. 大仓库加载慢，需要懒加载，或者说分批加载
64. ~~各种情况下，比如打开了模态对话框，都需要支持直接退出~~
65. ~~添加切换分支的功能~~
66. ~~https://github.com/wynemo/mygit/issues/25~~
67. 文件内容变更了 一些状态没刷新 比如行号旁边的修改状态
68. show all affected files 功能，需要支持，但界面要很多功能，比如侧边栏
69. 搜索查找历史，现在只能搜索已经加载出来的记录，需要支持搜索未加载出来的记录
70. ~~侧边栏：工作区、提交~~
71. ~~有修改的文件夹也要显示颜色，目前只是文件显示了颜色~~
72. 图标美化，现在图标太丑了
73. ~~editors/text_edit.py - 行号旁边的绘制修改状态竖线，在窗口重新获得焦点后，需要刷新~~ 倒是修改好了，但会滚动到第一行
74. ~~侧边栏的文件夹也需要右键菜单~~
75. ~~commit_detail_view.py 如果超过 MAX_BRANCHES_TO_SHOW 想想该怎么交互~~
76. ~~侧边栏的文件夹需要拷贝完整路径的菜单~~
77. ~~侧边栏两个按钮不要边框~~
78. 侧边栏两个按钮，选中的效果，选中但失去焦距的效果；ai 给加上了，但效果不太好，等待界面调整了以后再说
79. ~~工作区文件编辑了以后，没有保存到磁盘前，标记一下，文件名上*~~
80. ~~提交对话框换成标签页~~
81. ~~CommitDialog 太大了，超出框体，需要调整，需要重新设计，名字也得改下，现在容易误会，已经不是对话框了~~
82. ~~CommitDialog 获得焦点时，需要刷新~~
83. ~~file_history_view.py 需要处理 git mv 的情况，没有正确获取到历史~~
84. ~~file_changes_view.py 里面对于 git mv 的情况，是显示了 R 的情况，但没有显示移动为什么新文件了~~
85. ~~WorkspaceExplorer.file_changes_view 处理信号 点击文件 没有处理~~
86. WorkspaceExplorer.file_changes_view 处理信号 与工作区比较 没有处理