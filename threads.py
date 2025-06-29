import asyncio
import os
from typing import TYPE_CHECKING

import aiohttp
from PyQt6.QtCore import QThread, pyqtSignal

if TYPE_CHECKING:
    from git_manager import GitManager


class FetchThread(QThread):
    finished = pyqtSignal(bool, str)

    def __init__(self, git_manager):
        super().__init__()
        self.git_manager = git_manager

    def run(self):
        try:
            self.git_manager.fetch()
            self.finished.emit(True, "")
        except Exception as e:
            self.finished.emit(False, str(e))


class PullThread(QThread):
    """用于在后台执行 pull 操作的线程"""

    finished = pyqtSignal(bool, str)  # (success, error_message)

    def __init__(self, git_manager):
        super().__init__()
        self.git_manager = git_manager

    def run(self):
        """执行 pull 操作"""
        try:
            self.git_manager.pull()
            self.finished.emit(True, "")
        except Exception as e:
            self.finished.emit(False, str(e))


class PushThread(QThread):
    """用于在后台执行 push 操作的线程"""

    finished = pyqtSignal(bool, str)  # (success, error_message)

    def __init__(self, git_manager: "GitManager"):
        super().__init__()
        self.git_manager = git_manager

    def run(self):
        """执行 push 操作"""
        try:
            self.git_manager.push()
            self.finished.emit(True, "")
        except Exception as e:
            self.finished.emit(False, str(e))


class AIGeneratorThread(QThread):
    finished = pyqtSignal(str)  # 成功信号
    error = pyqtSignal(str)  # 错误信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self.diff_content = None
        self.settings = None

    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self._call_ai_api())
            loop.close()
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))

    async def _call_ai_api(self):
        """调用 AI API 生成提交信息"""
        api_url = self.settings.get("api_url", "").rstrip("/") + "/chat/completions"
        api_secret = self.settings.get("api_secret", "")
        model_name = self.settings.get("model_name", "")
        prompt = self.settings.get("prompt", "请根据以下 Git 变更生成一个简洁的提交信息：")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_secret}",
        }

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": self.diff_content},
        ]

        data = {"model": model_name, "messages": messages}

        timeout = aiohttp.ClientTimeout(total=15)  # 15 秒超时

        try:
            async with (
                aiohttp.ClientSession(timeout=timeout) as session,
                session.post(api_url, headers=headers, json=data) as response,
            ):
                if response.status == 200:
                    result = await response.json()
                    return result["choices"][0]["message"]["content"]
                else:
                    error_text = await response.text()
                    raise Exception(f"API 调用失败：{response.status} - {error_text}")
        except asyncio.TimeoutError as e:
            raise Exception("API 调用超时（15 秒）") from e
        except aiohttp.ClientError as e:
            raise Exception("API 调用错误") from e


class FileIndexThread(QThread):
    """用于在后台建立文件索引的线程"""

    finished = pyqtSignal()  # 索引建立完成信号
    error = pyqtSignal(str)  # 错误信号

    def __init__(self, workspace_path, git_manager, file_index_manager, parent=None):
        super().__init__(parent)
        self.workspace_path = workspace_path
        self.git_manager = git_manager
        self.file_index_manager = file_index_manager

    def run(self):
        """在后台线程中执行索引建立"""
        try:
            def _is_dir_ignored(path: str) -> bool:
                # 确保路径是相对的
                if os.path.isabs(path):
                    _path = os.path.relpath(path, self.git_manager.repo_path)
                else:
                    _path = path
                return self.git_manager.is_ignored(_path) or _path.startswith(".git")

            for root, dirs, files in os.walk(self.workspace_path, topdown=True):
                # 过滤被忽略的文件夹
                # 使用索引和切片来修改 dirs
                dirs[:] = [d for d in dirs if not _is_dir_ignored(os.path.join(root, d))]

                for f in files:
                    file_path = os.path.join(root, f)
                    # 确保文件路径是相对的
                    relative_file_path = os.path.relpath(file_path, self.git_manager.repo_path)
                    if not self.git_manager.is_ignored(relative_file_path):
                        self.file_index_manager.add_file(file_path, self.workspace_path)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))
