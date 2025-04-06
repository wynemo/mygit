import sys
from PyQt6.QtWidgets import QApplication
from git_manager_window import GitManagerWindow


def main():
    app = QApplication(sys.argv)
    window = GitManagerWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
