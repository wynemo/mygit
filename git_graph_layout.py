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

    # Initialize is_on_mainline for all commits
    for commit in commits:
        commit.is_on_mainline = False

    # --- Mainline Identification Logic ---
    preferred_mainline_names = ['main', 'master']
    mainline_tip_sha = None

    # Try to find HEAD and its target branch first
    head_ref_commit_sha = None
    head_target_branch_name = None

    for commit_node in commits: # Newest first
        for ref in commit_node.references:
            if ref.startswith("HEAD -> "):
                head_target_branch_name = ref.split("HEAD -> ")[1].strip()
                head_ref_commit_sha = commit_node.sha # This commit is where HEAD points
                break
        if head_target_branch_name:
            break

    # 1. Check preferred mainline names if HEAD points to one of them
    if head_target_branch_name and head_target_branch_name in preferred_mainline_names:
        mainline_tip_sha = head_ref_commit_sha

    # 2. If not, check other preferred mainline names (e.g. main or master might exist even if HEAD is elsewhere)
    if not mainline_tip_sha:
        for commit_node in commits: # Newest first
            for ref in commit_node.references:
                ref_name_part = ref.split("tag: ", 1)[-1] # Get ref name, strip "tag: " if present
                if ref_name_part in preferred_mainline_names or \
                   any(f"refs/heads/{name}" == ref_name_part for name in preferred_mainline_names):
                    mainline_tip_sha = commit_node.sha
                    break
            if mainline_tip_sha:
                break

    # 3. If still no mainline tip from preferred names, use the branch HEAD points to (if any)
    if not mainline_tip_sha and head_ref_commit_sha and head_target_branch_name:
        # We need the actual tip of head_target_branch_name, which might be newer than head_ref_commit_sha
        # if HEAD was checked out earlier and not at the tip.
        # Iterate again to find the commit that *is* the tip of head_target_branch_name
        for commit_node in commits:
            for ref in commit_node.references:
                ref_name_part = ref.split("tag: ", 1)[-1]
                if ref_name_part == head_target_branch_name or ref == f"refs/heads/{head_target_branch_name}":
                    mainline_tip_sha = commit_node.sha
                    break
            if mainline_tip_sha and commits_map[mainline_tip_sha].references:  # ensure it's a branch tip
               and any(r == head_target_branch_name or r == f"refs/heads/{head_target_branch_name}" for r in commits_map[mainline_tip_sha].references):
                break # Found the actual tip of the branch HEAD was pointing to
        if not mainline_tip_sha : # fallback if loop above didnt find a better one.
             mainline_tip_sha = head_ref_commit_sha


    # 4. If no mainline tip from branch names, and HEAD is detached, use the commit HEAD points to
    if not mainline_tip_sha and head_ref_commit_sha and "HEAD" in commits_map[head_ref_commit_sha].references and not head_target_branch_name: # Detached HEAD
        mainline_tip_sha = head_ref_commit_sha

    # Traverse up from mainline_tip_sha setting is_on_mainline
    if mainline_tip_sha and mainline_tip_sha in commits_map:
        current_sha = mainline_tip_sha
        while current_sha:
            commit = commits_map[current_sha]
            commit.is_on_mainline = True
            if commit.parents:
                # Follow first parent for mainline path
                # Check if parent is in the current list of commits
                if commit.parents[0] in commits_map:
                    current_sha = commit.parents[0]
                else: # Parent not in map (e.g. shallow clone)
                    current_sha = None
            else:
                current_sha = None
    # --- End Mainline Identification ---

    # `lane_occupied_until_y` tracks how far down a column (lane) is occupied by a branch segment.
    # Key: column index, Value: y-coordinate (newest commit y in that lane).
    # Key: column index, Value: y-coordinate (newest commit y in that lane).
    # This helps in deciding if a new branch needs to find a new lane or can reuse one.
    lane_occupied_until_y: dict[int, float] = {}

    # `lane_colors` tracks the color index for each active lane.
    # Key: column index, Value: color_idx
    lane_colors: dict[int, int] = {}

    next_global_color_idx = 0
    mainline_col = 0
    # Assign mainline_color_idx based on the first color or a specific choice
    mainline_color_idx = 0 if COLOR_PALETTE else 0


    # Assign Y coordinates and perform column/color assignment.
    # Commits are processed from newest to oldest.
    for i, commit_node in enumerate(commits):
        commit_node.y = i * LAYOUT_VERTICAL_SPACING
        parent_nodes = [commits_map[p_sha] for p_sha in commit_node.parents if p_sha in commits_map]
        # Sort parents: mainline parent first (if any), then by y-coordinate (newest first)
        parent_nodes.sort(key=lambda p: (not p.is_on_mainline, p.y))


        if commit_node.is_on_mainline:
            commit_node.column = mainline_col
            commit_node.color_idx = mainline_color_idx
            lane_colors[mainline_col] = mainline_color_idx
        else:
            # This commit is NOT on the identified mainline
            assigned_col = False
            if parent_nodes:
                first_parent = parent_nodes[0] # Primary parent to consider for lane continuation

                if first_parent.is_on_mainline:
                    # Branching directly from mainline
                    commit_node.color_idx = (mainline_color_idx + 1 + next_global_color_idx) % len(COLOR_PALETTE)
                    next_global_color_idx = (next_global_color_idx + 1) % (len(COLOR_PALETTE) -1 if len(COLOR_PALETTE) > 1 else 1) # ensure it cycles through non-mainline colors
                    if next_global_color_idx == mainline_color_idx and len(COLOR_PALETTE) > 1: # Avoid reusing mainline color immediately
                         next_global_color_idx = (next_global_color_idx + 1) % len(COLOR_PALETTE)


                    # Find a new column to the right of mainline (simplification)
                    new_col = mainline_col + 1
                    while lane_occupied_until_y.get(new_col, -1) >= commit_node.y :
                        new_col += 1
                    commit_node.column = new_col
                    assigned_col = True
                else:
                    # Continuing an existing non-mainline branch
                    commit_node.column = first_parent.column
                    commit_node.color_idx = first_parent.color_idx # Inherit color

                    # Check if this lane is already occupied by a newer commit from a different branch,
                    # or if this commit is a secondary branch from its non-mainline parent.
                    is_secondary_branch = False
                    if len(first_parent.children) > 1:
                        parent_children_nodes = sorted(
                            [commits_map[c_sha] for c_sha in first_parent.children if c_sha in commits_map],
                            key=lambda c: c.y # Newest first
                        )
                        if parent_children_nodes and commit_node.sha != parent_children_nodes[0].sha:
                            is_secondary_branch = True

                    current_occupant_y = lane_occupied_until_y.get(commit_node.column, -1)
                    if is_secondary_branch or \
                       (current_occupant_y >= commit_node.y and current_occupant_y != first_parent.y and commits_map.get(current_occupant_y_sha_placeholder, {}).get('column') == commit_node.column) : # Placeholder for actual check
                        # Lane taken or secondary branch, find new column
                        new_col = commit_node.column + 1
                        while lane_occupied_until_y.get(new_col, -1) >= commit_node.y or new_col == mainline_col:
                            new_col += 1
                        commit_node.column = new_col
                        commit_node.color_idx = (first_parent.color_idx + 1 + next_global_color_idx) % len(COLOR_PALETTE) # New color
                        next_global_color_idx = (next_global_color_idx + 1) % (len(COLOR_PALETTE) -1 if len(COLOR_PALETTE) > 1 else 1)
                        if next_global_color_idx == mainline_color_idx and len(COLOR_PALETTE) >1 : next_global_color_idx = (next_global_color_idx + 1) % len(COLOR_PALETTE)

                    assigned_col = True

            if not assigned_col: # No parents in view or other complex cases (e.g. root of a non-mainline branch)
                new_col = mainline_col + 1
                while lane_occupied_until_y.get(new_col, -1) >= commit_node.y:
                    new_col += 1
                commit_node.column = new_col
                commit_node.color_idx = (mainline_color_idx + 1 + next_global_color_idx) % len(COLOR_PALETTE)
                next_global_color_idx = (next_global_color_idx + 1) % (len(COLOR_PALETTE) -1 if len(COLOR_PALETTE) > 1 else 1)
                if next_global_color_idx == mainline_color_idx and len(COLOR_PALETTE) > 1 : next_global_color_idx = (next_global_color_idx + 1) % len(COLOR_PALETTE)

            lane_colors[commit_node.column] = commit_node.color_idx

            # Merge commit specific: ensure other parent lanes are marked up to this commit_node.y
            if len(parent_nodes) > 1:
                 for p_node in parent_nodes[1:]: # Other parents
                    if p_node.column != commit_node.column:
                         lane_occupied_until_y[p_node.column] = max(lane_occupied_until_y.get(p_node.column, -1), commit_node.y)


        # Update lane occupancy for the commit's final column
        lane_occupied_until_y[commit_node.column] = commit_node.y

        # Assign X coordinate based on final column
        commit_node.x = commit_node.column * LAYOUT_HORIZONTAL_SPACING

    # Post-layout adjustments
    # Normalize X coordinates: find min_x and shift all if min_x is not 0 (or some padding)
    # This is important if branches can go to the left of mainline_col (e.g. col -1, -2)
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
