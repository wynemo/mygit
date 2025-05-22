import os
from PyQt6.QtWidgets import (
    QWidget,
    QPlainTextEdit,
    QHBoxLayout,
    QVBoxLayout,
    QScrollBar,
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt


class BlameViewWidget(QWidget):
    def __init__(self, blame_data: list, file_content: str, parent=None):
        super().__init__(parent)
        self.blame_data = blame_data
        self.file_content = file_content # Stored for potential future use, though blame_data['content'] is primary

        self.annotation_area = QPlainTextEdit()
        self.code_area = QPlainTextEdit()

        self.setup_ui()

    def setup_ui(self):
        # Main layout for the widget itself
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0) # Use full space

        # Configure Annotation Area
        self.annotation_area.setReadOnly(True)
        # Use a monospaced font
        font = QFont("Monospace")
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.annotation_area.setFont(font)
        self.annotation_area.setMaximumWidth(300) # Fixed width for annotations
        self.annotation_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff) # No horizontal scroll
        self.annotation_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff) # Hide by default, sync handles it

        # Configure Code Area
        self.code_area.setReadOnly(True)
        self.code_area.setFont(font) # Use the same monospaced font
        self.code_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn) # Main scrollbar visible here

        # Add widgets to layout
        main_layout.addWidget(self.annotation_area)
        main_layout.addWidget(self.code_area)
        
        self.setLayout(main_layout)

        self.load_data()
        self.synchronize_scrollbars()

    def load_data(self):
        annotation_lines = []
        code_lines = []

        if not self.blame_data:
            # If blame_data is empty, display the file_content directly in code_area
            # and leave annotation_area empty or with a placeholder.
            self.code_area.setPlainText(self.file_content)
            self.annotation_area.setPlainText("No blame data available.")
            return

        for blame_entry in self.blame_data:
            commit_hash_short = blame_entry.get("commit_hash", "N/A")[:7]
            author_name = blame_entry.get("author_name", "N/A")
            # Truncate author name if too long to fit well
            if len(author_name) > 15:
                author_name = author_name[:12] + "..."
            committed_date = blame_entry.get("committed_date", "N/A")
            content = blame_entry.get("content", "") # This is the line from the file

            annotation_str = f"{commit_hash_short} {author_name} {committed_date}"
            annotation_lines.append(annotation_str)
            code_lines.append(content)
        
        self.annotation_area.setPlainText("\n".join(annotation_lines))
        self.code_area.setPlainText("\n".join(code_lines))

    def synchronize_scrollbars(self):
        # Get the scrollbars
        anno_scrollbar = self.annotation_area.verticalScrollBar()
        code_scrollbar = self.code_area.verticalScrollBar()

        # Connect the valueChanged signals
        # When annotation_area is scrolled, scroll code_area
        anno_scrollbar.valueChanged.connect(code_scrollbar.setValue)
        # When code_area is scrolled, scroll annotation_area
        code_scrollbar.valueChanged.connect(anno_scrollbar.setValue)

        # Also synchronize horizontal scrollbars if they were enabled,
        # but for annotations, it's usually better to have a fixed width
        # and wrap or truncate text.

    def wheelEvent(self, event):
        # Forward wheel events from annotation_area to code_area to ensure
        # scrolling works even if mouse is over annotation_area (which has scrollbars off)
        # This is a common pattern when one widget's scrollbar is hidden but should follow another.
        if self.annotation_area.rect().contains(event.position().toPoint()):
            self.code_area.verticalScrollBar().setValue(
                self.code_area.verticalScrollBar().value() - (event.angleDelta().y() // 120) * self.code_area.verticalScrollBar().singleStep()
            )
            event.accept()
        else:
            super().wheelEvent(event)

if __name__ == '__main__':
    from PyQt6.QtWidgets import QApplication
    import sys

    # Dummy data for testing
    dummy_blame_data = [
        {"commit_hash": "a1b2c3d4e5f6", "author_name": "John Doe VeryLongName", "committed_date": "2023-01-01", "content": "Line 1: This is the first line of the file."},
        {"commit_hash": "f6e5d4c3b2a1", "author_name": "Jane Smith", "committed_date": "2023-01-02", "content": "Line 2: And this is the second line."},
        {"commit_hash": "a1b2c3d4e5f6", "author_name": "John Doe VeryLongName", "committed_date": "2023-01-01", "content": "Line 3: Followed by a third."},
        {"commit_hash": "1234567890ab", "author_name": "Another Dev", "committed_date": "2023-01-03", "content": "Line 4: The fourth line is here."},
    ]
    for i in range(5, 50):
        dummy_blame_data.append(
             {"commit_hash": f"fedcba{i:02x}", "author_name": "Automated Commit", "committed_date": f"2023-02-{i%28+1:02d}", "content": f"Line {i}: This is an auto-generated line number {i}."}
        )

    dummy_file_content = "\n".join([item['content'] for item in dummy_blame_data])
    
    app = QApplication(sys.argv)
    # Test with empty blame data
    # window = BlameViewWidget([], "This is file content if blame fails.")
    # Test with blame data
    window = BlameViewWidget(dummy_blame_data, dummy_file_content)
    window.setWindowTitle("Blame View Test")
    window.resize(800, 600)
    window.show()
    sys.exit(app.exec())
