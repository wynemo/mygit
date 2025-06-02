from PyQt6.QtCore import QThread, pyqtSignal  # Added QEvent and threading


class PullThread(QThread):
    """用于在后台执行pull操作的线程"""

    finished = pyqtSignal(bool, str)  # (success, error_message)

    def __init__(self, git_manager):
        super().__init__()
        self.git_manager = git_manager

    def run(self):
        """执行pull操作"""
        try:
            self.git_manager.pull()
            self.finished.emit(True, "")
        except Exception as e:
            self.finished.emit(False, str(e))
