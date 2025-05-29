from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QTreeWidget


class CommitGraphView(QTreeWidget):
    COMMIT_DOT_RADIUS = 5
    COLUMN_WIDTH = 20
    ROW_HEIGHT = 30

    def __init__(self, parent=None):
        super().__init__(parent)
        self.commits_data = [] # Renamed from self.commits
        self.branch_colors = {}
        self.commit_positions = {}  # 存储每个提交的位置
        self.branch_lanes = {} # To store lane assignments for branches
        self.next_lane = 0     # To assign new lanes

    def set_commit_data(self, graph_data):
        """设置提交数据"""
        self.commits_data = graph_data["commits"]
        self.branch_colors = graph_data["branch_colors"]
        # Ensure branch_colors has all branches encountered in commits_data
        for commit in self.commits_data:
            for branch_name in commit.get("branches", []):
                if branch_name not in self.branch_colors:
                    # Assign a default color or handle as an error/warning
                    # For now, let's assume graph_data["branch_colors"] is comprehensive
                    # or GitManager.get_commit_graph() handles this.
                    pass
        self.calculate_positions()
        self.update() # Request a repaint

    def calculate_positions(self):
        """计算每个提交的位置 (Refactored)"""
        self.commit_positions.clear()
        self.branch_lanes.clear()
        self.next_lane = 0
        
        # First pass: assign lanes to branches based on their first appearance
        # This helps in keeping branch lines somewhat consistent.
        # This assumes commits are roughly in chronological or topological order.
        temp_branch_first_occurrence_y = {}
        for idx, commit in enumerate(self.commits_data):
            y = idx * self.ROW_HEIGHT + self.ROW_HEIGHT // 2
            for branch_name in commit.get("branches", []):
                if branch_name not in self.branch_lanes:
                    if branch_name not in temp_branch_first_occurrence_y:
                        temp_branch_first_occurrence_y[branch_name] = y

        # Sort branches by their first occurrence to assign lanes more logically
        # Branches appearing earlier get lanes first.
        sorted_branches_by_occurrence = sorted(
            temp_branch_first_occurrence_y.keys(),
            key=lambda b: temp_branch_first_occurrence_y[b]
        )

        for branch_name in sorted_branches_by_occurrence:
            if branch_name not in self.branch_lanes: # Should always be true here
                self.branch_lanes[branch_name] = self.next_lane
                self.next_lane += 1
        
        # Second pass: calculate positions
        for idx, commit in enumerate(self.commits_data):
            y = idx * self.ROW_HEIGHT + self.ROW_HEIGHT // 2
            
            commit_lane = -1

            # Try to place commit in a lane of one of its branches.
            # Prioritize branches that have already been assigned a lane.
            # If multiple branches of this commit have lanes, pick the one with the smallest lane index.
            min_lane_idx = float('inf')
            assigned_branch_for_commit = None

            for branch_name in commit.get("branches", []):
                if branch_name in self.branch_lanes:
                    if self.branch_lanes[branch_name] < min_lane_idx:
                        min_lane_idx = self.branch_lanes[branch_name]
                        assigned_branch_for_commit = branch_name
            
            if assigned_branch_for_commit:
                commit_lane = self.branch_lanes[assigned_branch_for_commit]
            else:
                # This case should ideally not happen if all branches are processed in the first pass.
                # Or, if a commit has no branches listed (e.g. a detached commit).
                # Assign it to a new lane or a default lane (e.g., 0 or self.next_lane).
                # For now, if it has branches but none were known, it's an issue.
                # If it truly has no branches in its data, it could be a new lane.
                if commit.get("branches"): # Has branches, but none known. This is unexpected.
                    # Fallback: use the first branch and assign it a new lane if really necessary.
                    # This indicates an issue with pre-assigning lanes or data consistency.
                    # For robustness, let's ensure even unknown branches get some lane.
                    primary_branch_name = commit["branches"][0]
                    if primary_branch_name not in self.branch_lanes:
                        self.branch_lanes[primary_branch_name] = self.next_lane
                        self.next_lane += 1
                    commit_lane = self.branch_lanes[primary_branch_name]
                else: # Commit has no branches (e.g. old commit, detached HEAD state)
                    commit_lane = 0 # Default to lane 0 or handle as a special case

            x = commit_lane * self.COLUMN_WIDTH + (self.COLUMN_WIDTH // 2) # Center in the lane
            self.commit_positions[commit["hash"]] = QPoint(x, y)

    def paintEvent(self, event):
        """重写绘制事件"""
        super().paintEvent(event)

        if not self.commits_data: # Updated to use self.commits_data
            return

        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 获取滚动条位置
        v_scroll = self.verticalScrollBar().value()
        h_scroll = self.horizontalScrollBar().value()

        # 绘制连线和提交点
        for commit in self.commits_data:
            if commit["hash"] not in self.commit_positions:
                continue # Should not happen if calculate_positions is called correctly

            current_pos_unscrolled = self.commit_positions[commit["hash"]]
            current_pos = QPoint(
                current_pos_unscrolled.x() - h_scroll,
                current_pos_unscrolled.y() - v_scroll,
            )

            # Improved visibility check
            if not (current_pos.y() + self.COMMIT_DOT_RADIUS >= 0 and \
                    current_pos.y() - self.COMMIT_DOT_RADIUS <= self.viewport().height()):
                continue

            # Determine the 'display_branch' for this commit (branch whose lane it's in)
            display_branch_name = None
            min_lane_val = float('inf')
            if commit.get("branches"):
                for branch_name in commit["branches"]:
                    if branch_name in self.branch_lanes and self.branch_lanes[branch_name] < min_lane_val:
                        min_lane_val = self.branch_lanes[branch_name]
                        display_branch_name = branch_name
            
            if not display_branch_name and commit.get("branches"):
                # Fallback if no branch associated or no branch has a lane (should be rare after calculate_positions)
                display_branch_name = commit["branches"][0] 

            # --- Drawing parent lines ---
            for parent_hash in commit["parents"]:
                if parent_hash in self.commit_positions:
                    parent_pos_unscrolled = self.commit_positions[parent_hash]
                    parent_pos = QPoint(
                        parent_pos_unscrolled.x() - h_scroll,
                        parent_pos_unscrolled.y() - v_scroll,
                    )
                    
                    line_color = QColor("#cccccc") # Default
                    if display_branch_name and display_branch_name in self.branch_colors:
                        line_color = QColor(self.branch_colors[display_branch_name])
                    
                    pen = QPen(line_color, 2)
                    painter.setPen(pen)
                    painter.drawLine(current_pos, parent_pos)

            # --- Drawing commit dot ---
            dot_color = QColor("#cccccc") # Default
            if display_branch_name and display_branch_name in self.branch_colors:
                dot_color = QColor(self.branch_colors[display_branch_name])
            
            painter.setBrush(dot_color)
            painter.setPen(Qt.PenStyle.NoPen) # No border for the dot
            painter.drawEllipse(
                current_pos, # QPoint version for center
                self.COMMIT_DOT_RADIUS,
                self.COMMIT_DOT_RADIUS
            )
