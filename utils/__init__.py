from PyQt6.QtWidgets import QApplication


def get_main_window():
    main_window = QApplication.instance().activeWindow()
    return main_window
