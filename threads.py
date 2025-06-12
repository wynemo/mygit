import asyncio

import aiohttp
from PyQt6.QtCore import QThread, pyqtSignal


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

    def __init__(self, git_manager):
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
