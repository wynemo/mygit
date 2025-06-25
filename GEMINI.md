+ 使用中文注释
+ 这是用 pyqt6 的工程
+ 专注于当前的功能，不要修改无关的代码
+ 抛错记录异常使用 logging.exception 不要使用 logging.error 里面再格式化一个异常对象，比如 logging.error(f"Failed to compare commit changes with workspace for {commit_hash}: {e}"),正确的方式是 logging.exception("Failed to compare commit changes with workspace")
+ logging 不要使用 f-string, 用格式化字符串 比如 logging.error(f"切换分支 {branch_name} 失败：{e!s}") 应该使用 logging.error("切换分支 %s 失败", branch_name)
+ edit the file in small chunks
