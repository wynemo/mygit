# git_graph_layout.py

from git_graph_data import CommitNode
from git_graph_items import HORIZONTAL_SPACING, VERTICAL_SPACING, COLOR_PALETTE

# More spacing to make graph less dense initially
LAYOUT_HORIZONTAL_SPACING = HORIZONTAL_SPACING * 1.5
LAYOUT_VERTICAL_SPACING = VERTICAL_SPACING * 1.5

def calculate_commit_positions(commits: list[CommitNode]):
    """
    Calculates and assigns x, y, column, and color_idx attributes for each CommitNode.
    The input `commits` list is expected to be ordered (e.g., reverse chronological from git log).
    Commits at the beginning of the list are considered "newer".
    Y-coordinates will be assigned sequentially based on this order (newer at top, y=0).
    X-coordinates are based on column assignment.
    Column assignment is heuristic to try and represent branches.
    Color index is assigned to help distinguish branches.
    """
    if not commits:
        return

    commits_map = {c.sha: c for c in commits}

    # `lane_occupied_until_y` tracks how far down a column (lane) is occupied by a branch segment.
    # Key: column index, Value: y-coordinate until which this lane is considered "busy".
    # This helps in deciding if a new branch needs to find a new lane or can reuse one.
    lane_occupied_until_y: dict[int, float] = {}

    # `lane_colors` tracks the color index for each active lane.
    # Key: column index, Value: color_idx
    lane_colors: dict[int, int] = {}

    next_global_color_idx = 0

    # Assign Y coordinates and perform initial column/color assignment.
    # Commits are processed from newest to oldest (as per typical git log --all order).
    for i, commit_node in enumerate(commits):
        commit_node.y = i * LAYOUT_VERTICAL_SPACING

        parent_nodes = [commits_map[p_sha] for p_sha in commit_node.parents if p_sha in commits_map]
        parent_nodes.sort(key=lambda p: p.y) # Oldest parent first

        if not parent_nodes:
            # Root commit (or oldest in the current log view)
            # Place in the first available column.
            col = 0
            while lane_occupied_until_y.get(col, -1) >= commit_node.y:
                col += 1

            commit_node.column = col
            commit_node.color_idx = lane_colors.get(col)
            if commit_node.color_idx is None:
                commit_node.color_idx = next_global_color_idx
                next_global_color_idx = (next_global_color_idx + 1) % len(COLOR_PALETTE)
            lane_colors[col] = commit_node.color_idx

        elif len(parent_nodes) == 1:
            # Single parent: try to follow parent's lane and color.
            parent = parent_nodes[0]
            commit_node.column = parent.column
            commit_node.color_idx = parent.color_idx # Inherit color

            # Check if this commit is starting a new branch relative to its parent's other children.
            # If the parent has multiple children, and this commit is not the "primary" one
            # (primary assumed to be the one that continues the lane, often the one with smallest y diff or processed first),
            # then this commit might need a new lane.

            # A simple heuristic: if parent's lane is already taken by another child of the same parent
            # that is *newer* than this commit, then this commit needs a new lane.
            # This means we need to know the layout of newer items first.
            # The current loop (newest to oldest) helps here.

            # If this commit's chosen column is already occupied by a line segment that isn't its direct parent's,
            # or if the parent has other children that are "straighter" in this lane, find a new column.
            is_branching_off = False
            if len(parent.children) > 1:
                # Find this commit in parent's children list (mapped to nodes)
                parent_children_nodes = sorted(
                    [commits_map[c_sha] for c_sha in parent.children if c_sha in commits_map],
                    key=lambda c: c.y # Sort children by y (newest first)
                )
                if parent_children_nodes and commit_node.sha != parent_children_nodes[0].sha:
                    # This is not the first (newest) child, so it's a branch-off.
                    is_branching_off = True

            current_occupant_y = lane_occupied_until_y.get(commit_node.column, -1)
            # If column is busy *at or above* parent's Y, AND it's not parent itself, or if it's a clear branch-off:
            if is_branching_off or \
                (current_occupant_y >= parent.y and current_occupant_y != parent.y ) : # Simplified check
                # Need a new column for this branch
                new_col = commit_node.column + 1 # Try right first
                while lane_occupied_until_y.get(new_col, -1) >= commit_node.y:
                    new_col += 1
                commit_node.column = new_col
                commit_node.color_idx = next_global_color_idx # New branch, new color
                next_global_color_idx = (next_global_color_idx + 1) % len(COLOR_PALETTE)

            lane_colors[commit_node.column] = commit_node.color_idx

        else: # Merge commit (multiple parents)
            # Merge into the lane of the first parent (typically the main branch being merged into).
            # First parent by convention in `git log` output is the one on the current branch.
            # Our `parent_nodes` are sorted by y, so `parent_nodes[0]` is the newest parent.
            # Let's try to align with the *oldest* parent's column if possible, or first parent.

            # Heuristic: merge into the column of the parent that is "most mainline"
            # For now, use the column of the first parent in the list (newest `y` value).
            first_parent = parent_nodes[0] # Parent with smallest y (newest)
            commit_node.column = first_parent.column
            commit_node.color_idx = first_parent.color_idx # Inherit color from this parent

            # Ensure this chosen column is not "over-occupied" by something else unexpected.
            # (Similar check to single-parent case, but less likely for merges to shift columns often)
            # For now, we assume the first parent's column is the target.

            lane_colors[commit_node.column] = commit_node.color_idx

            # The lines from other parents will visually merge.
            # Mark those other parent lanes as "ending" or "merging" at this commit's Y.
            # This means their `lane_occupied_until_y` should be updated to `commit_node.y`.
            for p_node in parent_nodes[1:]:
                if p_node.column != commit_node.column: # If in a different lane
                    # This lane is merging. If no other branches continue in p_node.column below this y,
                    # it could be considered free. For now, just ensure it's marked up to here.
                    lane_occupied_until_y[p_node.column] = max(lane_occupied_until_y.get(p_node.column, -1), commit_node.y)


        # Update how far this lane is occupied.
        # A lane is occupied by this commit's line segment continuing from its parent(s) to itself.
        # Or, if it's a root, it starts here.
        # The critical thing is that `lane_occupied_until_y[col]` should reflect the
        # y-level of the *newest* commit currently defining the bottom of a segment in that lane.
        lane_occupied_until_y[commit_node.column] = commit_node.y

        # Assign X coordinate
        commit_node.x = commit_node.column * LAYOUT_HORIZONTAL_SPACING

    # Post-layout adjustments (optional but good)
    # 1. Normalize X coordinates: find min_x and shift all if min_x is not 0 (or some padding)
    if commits:
        min_x_coord = min(c.x for c in commits)
        if min_x_coord != 0:
            for c in commits:
                c.x -= min_x_coord

    # 2. Detect max column to help view scaling later
    max_column = 0
    if commits:
        max_column = max((c.column for c in commits), default=0)

    # The layout is now stored in commit_node.x, commit_node.y, commit_node.column, commit_node.color_idx
    # print(f"Layout calculated. Max column: {max_column}")
    # for c in commits[:5]:
    #     print(f"  SHA: {c.sha[:7]}, X: {c.x}, Y: {c.y}, Col: {c.column}, ColorIdx: {c.color_idx}")


if __name__ == '__main__':
    print("git_graph_layout.py - Contains logic for calculating commit positions.")
    # To test this, you'd typically:
    # 1. Parse a real git log using git_log_parser.py into CommitNode objects.
    # from git_log_parser import parse_git_log
    # current_repo_commits = parse_git_log(".")
    # if current_repo_commits:
    #     calculate_commit_positions(current_repo_commits)
    #     print(f"Layout calculated for {len(current_repo_commits)} commits.")
    #     for i, node in enumerate(current_repo_commits):
    #         if i < 15: # Print details for first 15
    #             print(f"Commit SHA: {node.sha}, X: {node.x}, Y: {node.y}, Column: {node.column}, Color: {node.color_idx}, Parents: {node.parents}, Children: {node.children}")
    #         if i == 0: # Max values from the first commit (newest)
    #             max_y = max(c.y for c in current_repo_commits)
    #             max_x = max(c.x for c in current_repo_commits)
    #             print(f"Max Y: {max_y}, Max X: {max_x}")
    # else:
    #     print("No commits found to test layout.")
