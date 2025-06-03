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
