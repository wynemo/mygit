from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem


class CommitGraphView(QTreeWidget):
    COMMIT_DOT_RADIUS = 5
    COLUMN_WIDTH = 20
    ROW_HEIGHT = 30

    def __init__(self, parent=None):
        super().__init__(parent)
        self.commits = []
        self.branch_colors = {}
        self.commit_positions = {}  # 存储每个提交的位置

    def set_commit_data(self, graph_data):
        """Sets the commit data for the graph and populates tree widget items."""
        # Ensure the widget is properly configured for columns if not done elsewhere.
        # This is typically done once after __init__. For example:
        # self.setColumnCount(5)
        # self.setHeaderLabels(["Graph", "Description", "Author", "Date", "SHA"])
        # However, this setup is done in CommitHistoryView.py for history_graph_list.

        self.clear() # Clear existing items from the QTreeWidget (itself)
        
        self.commits = graph_data.get("commits", [])
        self.branch_colors = graph_data.get("branch_colors", {})

        if not self.commits:
            self.calculate_positions() # Recalculate (empty) positions
            self.update()
            return

        for commit_dict in self.commits:
            item = QTreeWidgetItem(self) # 'self' is the CommitGraphView (QTreeWidget)
            # Column 0 is where the graph is drawn by paintEvent.
            # We can leave item text for col 0 empty or put a minimal indicator.
            item.setText(0, "") # Graph column - text is not primary content here.
            item.setText(1, commit_dict.get("message", ""))    # Description
            item.setText(2, commit_dict.get("author", ""))     # Author
            item.setText(3, commit_dict.get("date", ""))       # Date
            item.setText(4, commit_dict.get("hash", ""))       # Full SHA

        self.calculate_positions() # Calculate positions based on the new self.commits list
        self.update() # Trigger repaint to draw the graph

    def calculate_positions(self):
        self.commit_positions.clear()
        if not self.commits:
            return

        # Assign a preferred column index to each branch
        # Sort branch names to ensure consistent column assignment if order changes between calls
        sorted_branch_names = sorted(list(self.branch_colors.keys()))
        branch_to_column_idx = {branch_name: i for i, branch_name in enumerate(sorted_branch_names)}
        
        # Keep track of occupied columns at each y-level to avoid visual overlap of commit dots
        # This maps y_index to a set of column indices that are already taken at that y_level
        occupied_columns_at_y = {}

        max_observed_column = 0

        for y_idx, commit in enumerate(self.commits):
            y_coord = y_idx * self.ROW_HEIGHT + self.ROW_HEIGHT // 2

            # Determine the initial target column for this commit
            target_column = 0 # Default for commits not on a named branch tip
            if commit["branches"]:
                # This commit is a head of one or more branches. Use its primary branch's preferred column.
                # Sort branches to get a consistent primary branch if multiple are listed
                sorted_commit_branches = sorted(commit["branches"])
                primary_branch_name = sorted_commit_branches[0]
                
                # Get column for this branch, use a fallback if branch somehow not in pre-calculated map
                target_column = branch_to_column_idx.get(primary_branch_name, len(branch_to_column_idx))
            else:
                # This commit is not a direct head of a branch.
                # Start it at column 0 and let collision avoidance move it.
                target_column = 0

            # Resolve collisions: find the next available column at this y_idx if target_column is taken
            if y_idx not in occupied_columns_at_y:
                occupied_columns_at_y[y_idx] = set()

            check_col = target_column
            while check_col in occupied_columns_at_y[y_idx]:
                check_col += 1
            final_assigned_column = check_col
            
            occupied_columns_at_y[y_idx].add(final_assigned_column)
            
            if final_assigned_column > max_observed_column:
                max_observed_column = final_assigned_column

            x_coord = final_assigned_column * self.COLUMN_WIDTH + (self.COLUMN_WIDTH // 2) 

            self.commit_positions[commit["hash"]] = QPoint(x_coord, y_coord)

    def paintEvent(self, event):
        """重写绘制事件"""
        super().paintEvent(event)

        if not self.commits:
            return

        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Get current scroll offsets
        v_scroll = self.verticalScrollBar().value()
        h_scroll = self.horizontalScrollBar().value()

        # Draw lines and commit dots
        for commit in self.commits:
            # Apply scroll offset to the current commit's position
            current_pos_abs = self.commit_positions[commit["hash"]]
            current_pos = QPoint(
                current_pos_abs.x() - h_scroll,
                current_pos_abs.y() - v_scroll,
            )

            # Skip drawing if the commit is not vertically visible
            if not (0 <= current_pos.y() <= self.viewport().height() + self.ROW_HEIGHT): # Add ROW_HEIGHT to avoid clipping lines to commits just off screen
                # Consider also checking horizontal visibility if it becomes an issue
                continue

            # Draw lines to parent commits
            for parent_hash in commit["parents"]:
                if parent_hash in self.commit_positions:
                    parent_pos_abs = self.commit_positions[parent_hash] # Absolute position of the parent
                    # Apply scroll offset to the parent commit's position
                    parent_pos = QPoint(
                        parent_pos_abs.x() - h_scroll,
                        parent_pos_abs.y() - v_scroll,
                    )

                    # Determine line color
                    line_color = QColor("#cccccc")  # Default color for non-branch lines or general connections
                    if commit["branches"]:
                        # If the child commit is a head of a branch, color the line with that branch's color
                        # Sort for deterministic color choice if a commit is head of multiple branches simultaneously
                        sorted_commit_branches = sorted(commit["branches"])
                        primary_branch_name = sorted_commit_branches[0]
                        if primary_branch_name in self.branch_colors:
                             line_color = QColor(self.branch_colors[primary_branch_name])

                    # Draw the line
                    pen = QPen(line_color, 2)  # Line thickness 2
                    painter.setPen(pen)
                    painter.drawLine(current_pos, parent_pos)

            # Draw commit dots
            # Ensure commit dots are drawn for commits that might be slightly off-screen but have visible lines
            if not (0 <= current_pos.y() <= self.viewport().height()):
                 # This check is slightly different from line visibility; dot is smaller.
                 # Re-evaluate if this shorter check is ideal or should match line visibility.
                 pass # Potentially continue if precise dot visibility culling is needed

            for branch_name in commit["branches"]: # Primary dot color from its branches
                if branch_name in self.branch_colors: # Check if branch_name is valid
                    color = QColor(self.branch_colors[branch_name])
                else: # Fallback color if branch_name is not in branch_colors (should not happen with current data model)
                    color = QColor("#888888") 
            # Draw the commit dot(s)
            # If a commit belongs to multiple branches, it will be drawn multiple times,
            # with the last one on top. This is usually fine.
            # Alternatively, pick a primary branch for the dot color as well.
            # For now, let's use the color of the first branch associated with the commit for its dot.
            dot_color = QColor("#808080") # Default dot color if no branches or no color found
            if commit["branches"]:
                sorted_dot_branches = sorted(commit["branches"])
                primary_dot_branch = sorted_dot_branches[0]
                if primary_dot_branch in self.branch_colors:
                    dot_color = QColor(self.branch_colors[primary_dot_branch])
            
            painter.setBrush(dot_color)
            painter.setPen(Qt.PenStyle.NoPen) # No border for the dot
            painter.drawEllipse(
                current_pos.x() - self.COMMIT_DOT_RADIUS,
                current_pos.y() - self.COMMIT_DOT_RADIUS,
                self.COMMIT_DOT_RADIUS * 2,
                self.COMMIT_DOT_RADIUS * 2,
            )

            # Draw branch names next to commit heads
            if commit["branches"]:
                # Settings for drawing branch names
                font = painter.font() # Get current font
                # font.setPointSize(font.pointSize() - 1) # Optionally make font slightly smaller
                painter.setFont(font)
                fm = painter.fontMetrics()
                line_height = fm.height()
                
                # Base X position for branch names (right of the commit dot)
                base_x = current_pos.x() + self.COMMIT_DOT_RADIUS + 5 # 5px padding

                # Sort branches for consistent display order
                sorted_branch_names = sorted(commit["branches"])
                
                # Limit number of displayed branches (e.g., max 3)
                max_branches_to_display = 3
                display_branches = sorted_branch_names[:max_branches_to_display]
                
                # Calculate initial Y to center the block of names vertically against the dot.
                # current_pos.y() is the center of the dot.
                # fm.ascent() is height from baseline to top of char.
                # line_height is approx ascent + descent.
                # For a single line, its baseline y should be: current_pos.y() - line_height/2 + fm.ascent()
                # This formula generalizes for multiple lines:
                num_display_branches = len(display_branches)
                y_of_first_baseline = current_pos.y() - (num_display_branches * line_height / 2) + fm.ascent()

                for idx, branch_name in enumerate(display_branches):
                    text_y = y_of_first_baseline + (idx * line_height)
                    
                    branch_text_color = QColor(self.branch_colors.get(branch_name, Qt.GlobalColor.black)) # Fallback to black
                    painter.setPen(branch_text_color)
                    
                    painter.drawText(int(base_x), int(text_y), branch_name)

                if len(sorted_branch_names) > max_branches_to_display:
                    # Indicate more branches exist
                    text_y = y_of_first_baseline + (num_display_branches * line_height)
                    painter.setPen(QColor(Qt.GlobalColor.gray)) # Ellipsis in gray
                    painter.drawText(int(base_x), int(text_y), "...")
