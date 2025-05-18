import sys

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from git_manager_window import GitManagerWindow


def main():
    app = QApplication(sys.argv)

    # 设置应用图标
    app.setWindowIcon(QIcon("mygit.icns"))

    window = GitManagerWindow()
    window.show()

    # 尝试解决失焦问题,启动后,窗口灰色,使用“打开文件夹”也是灰色;切换到别的程序再切回来会变好
    window.activateWindow()
    window.raise_()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
