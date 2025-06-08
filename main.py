import logging
import os
import sys

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from git_manager_window import GitManagerWindow


def main():
    app = QApplication(sys.argv)

    # 设置应用图标
    app.setWindowIcon(QIcon("icons/mygit.icns"))

    window = GitManagerWindow()
    window.show()

    # 尝试解决失焦问题，启动后，窗口灰色，使用“打开文件夹”也是灰色;切换到别的程序再切回来会变好
    window.activateWindow()
    window.raise_()

    sys.exit(app.exec())


if __name__ == "__main__":
    # 根据环境变量设置日志级别
    log_level = logging.DEBUG if os.getenv("DEBUG") == "1" else logging.INFO

    # 配置日志
    logging.basicConfig(
        level=log_level, format="%(asctime)s - %(levelname)s - %(name)s - %(filename)s:%(lineno)d - %(message)s"
    )
    main()
