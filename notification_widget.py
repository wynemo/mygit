from PyQt6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QSizePolicy
from PyQt6.QtCore import QTimer, Qt

class NotificationWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setFixedWidth(300)
        self.setMinimumHeight(50)
        self.setStyleSheet("""
            NotificationWidget {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 5px;
            }
        """)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.hide()

        layout = QVBoxLayout(self)
        self.setLayout(layout)

        self.message_label = QLabel()
        self.message_label.setWordWrap(True)
        self.message_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.hide_widget)
        self.close_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)


        layout.addWidget(self.message_label)
        layout.addWidget(self.close_button, alignment=Qt.AlignmentFlag.AlignRight)

        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide_widget)

    def show_message(self, message: str):
        self.message_label.setText(message)
        self.adjustSize() # Adjust size based on content first
        # Ensure the widget is positioned correctly, e.g., top-right of parent
        if self.parentWidget():
            parent_rect = self.parentWidget().rect()
            self.move(parent_rect.right() - self.width() - 10, 10) # 10px margin
        self.show()
        self.hide_timer.start(7000) # 7 seconds
        self.raise_()

    def hide_widget(self):
        self.hide()
        if self.hide_timer.isActive():
            self.hide_timer.stop()

if __name__ == '__main__':
    from PyQt6.QtWidgets import QApplication, QMainWindow
    import sys

    app = QApplication(sys.argv)
    main_window = QMainWindow()
    main_window.setWindowTitle("Notification Test")
    main_window.setGeometry(100, 100, 600, 400)

    notification_widget = NotificationWidget(main_window)

    # Button to trigger notification (for testing)
    test_button = QPushButton("Show Notification", main_window)
    test_button.setGeometry(50, 50, 150, 30)
    test_button.clicked.connect(lambda: notification_widget.show_message(
        "This is a test notification! It should disappear after 7 seconds or if you click close."
    ))

    main_window.show()
    sys.exit(app.exec())
