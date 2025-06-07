from typing import Optional

from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget


def get_main_window():
    main_window = QApplication.instance().activeWindow()
    return main_window


def get_main_window_by_parent(parent: QWidget) -> Optional[QMainWindow]:
    while parent:
        if isinstance(parent, QMainWindow):
            return parent
        parent = parent.parent()
    return None
