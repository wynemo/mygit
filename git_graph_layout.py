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

    lane_occupied_until_y: dict[int, float] = {}
    lane_branch_color_used: dict[int, int] = {} # Tracks which branch_color_idx is using a column

    mainline_col = 0
    mainline_color_idx = 0 if COLOR_PALETTE else 0 # Mainline uses the first color

    branch_name_to_color_map: dict[str, int] = {}
    # Start assigning new branch colors from index 1 (or after mainline_color_idx)
    next_branch_color_assign_idx = (mainline_color_idx + 1) % len(COLOR_PALETTE) if COLOR_PALETTE else 0


    # Reverse commits for child-to-parent color propagation (older to newer)
    # This pass is primarily for establishing branch_color_idx
    for commit_node in reversed(commits):
        if commit_node.is_on_mainline:
            commit_node.branch_color_idx = mainline_color_idx
        else:
            # Try to identify branch color from its references (if it's a branch tip)
            found_branch_ref = False
            for ref in commit_node.references:
                branch_name = None
                if ref.startswith("HEAD -> "):
                    branch_name = ref.split("HEAD -> ")[1].strip()
                elif ref.startswith("refs/heads/"):
                    branch_name = ref.split("refs/heads/")[1].strip()
                elif "origin/" in ref and not ref.startswith("tag:"): # Simple check for remote branches
                    branch_name = ref

                if branch_name:
                    found_branch_ref = True
                    if branch_name not in branch_name_to_color_map:
                        branch_name_to_color_map[branch_name] = next_branch_color_assign_idx
                        commit_node.branch_color_idx = next_branch_color_assign_idx
                        next_branch_color_assign_idx = (next_branch_color_assign_idx + 1)
                        if next_branch_color_assign_idx == mainline_color_idx and len(COLOR_PALETTE) > 1:
                             next_branch_color_assign_idx = (next_branch_color_assign_idx + 1)
                        if next_branch_color_assign_idx >= len(COLOR_PALETTE): # Wrap around
                            next_branch_color_assign_idx = (mainline_color_idx +1) % len(COLOR_PALETTE) if len(COLOR_PALETTE) > 1 else 0
                    else:
                        commit_node.branch_color_idx = branch_name_to_color_map[branch_name]
                    break # Found a branch name, use it

            # If not a named tip, try to inherit from children (processed commits)
            if commit_node.branch_color_idx is None:
                children_nodes = [commits_map[c_sha] for c_sha in commit_node.children if c_sha in commits_map]
                # Filter children that have a branch_color_idx and are not mainline, or if this commit is clearly off-mainline
                valid_children_for_color = [
                    c for c in children_nodes
                    if c.branch_color_idx is not None and
                       (c.branch_color_idx != mainline_color_idx or not commit_node.is_on_mainline)
                ]
                if len(valid_children_for_color) == 1: # Only inherit if one child dictates a clear branch path
                     # Check if this commit is a merge point from mainline to this child's branch
                    is_merge_to_child_branch = False
                    if len(commit_node.parents)>1:
                        parent_is_mainline = any(p_sha in commits_map and commits_map[p_sha].is_on_mainline for p_sha in commit_node.parents)
                        if parent_is_mainline and valid_children_for_color[0].branch_color_idx != mainline_color_idx:
                            is_merge_to_child_branch = True # Don't inherit color if this commit merges mainline into a branch

                    if not is_merge_to_child_branch :
                        commit_node.branch_color_idx = valid_children_for_color[0].branch_color_idx


    # Main layout loop (newest to oldest)
    for i, commit_node in enumerate(commits):
        commit_node.y = i * LAYOUT_VERTICAL_SPACING

        # Assign final drawing color (color_idx) based on branch_color_idx or fallback
        if commit_node.branch_color_idx is not None:
            commit_node.color_idx = commit_node.branch_color_idx
        # If branch_color_idx is None, color_idx will be assigned by lane logic or default to mainline if it's a mainline commit without branch color (should not happen)
        # For commits on mainline, color_idx should already be mainline_color_idx from branch_color_idx
        if commit_node.is_on_mainline and commit_node.branch_color_idx is None: # Should be set already
             commit_node.branch_color_idx = mainline_color_idx
             commit_node.color_idx = mainline_color_idx


        parent_nodes = [commits_map[p_sha] for p_sha in commit_node.parents if p_sha in commits_map]
        parent_nodes.sort(key=lambda p: (not p.is_on_mainline, p.branch_color_idx == commit_node.branch_color_idx, p.y))


        if commit_node.is_on_mainline:
            commit_node.column = mainline_col
        else:
            # Non-mainline commit column assignment
            assigned_column = False
            if parent_nodes:
                first_parent = parent_nodes[0]
                # Try to inherit column from the first parent if on the same branch
                if commit_node.branch_color_idx is not None and commit_node.branch_color_idx == first_parent.branch_color_idx:
                    # Check if column is free or occupied by the same branch
                    # A column is free if no newer commit is in it, OR if the newer commit is part of the same branch.
                    occupant_y = lane_occupied_until_y.get(first_parent.column, -1)
                    occupant_branch_color = lane_branch_color_used.get(first_parent.column, -1) # -1 if no color

                    if occupant_y < commit_node.y or occupant_branch_color == commit_node.branch_color_idx :
                        commit_node.column = first_parent.column
                        assigned_column = True

                # If not assigned (e.g. different branch, or parent column taken by different branch)
                if not assigned_column:
                    # Branching from mainline or another branch, or parent's column is taken by a different branch.
                    # Find a new column. Try to the right of the first parent's column or mainline.
                    start_col_search = mainline_col + 1
                    if not first_parent.is_on_mainline and first_parent.column >= mainline_col :
                        start_col_search = first_parent.column + 1

                    new_col = start_col_search
                    while True:
                        occupant_y = lane_occupied_until_y.get(new_col, -1)
                        occupant_branch_color = lane_branch_color_used.get(new_col, -1)
                        if new_col != mainline_col and \
                           (occupant_y < commit_node.y or occupant_branch_color == commit_node.branch_color_idx):
                            commit_node.column = new_col
                            assigned_column = True
                            break
                        new_col += 1
                        if new_col > max((c.column for c in commits if hasattr(c, 'column')), default=0) + 5 : # Safety break
                             commit_node.column = new_col # Failsafe
                             assigned_column = True
                             break

            if not assigned_column: # Root of a non-mainline branch (no parents in view)
                new_col = mainline_col + 1
                while True:
                    occupant_y = lane_occupied_until_y.get(new_col, -1)
                    occupant_branch_color = lane_branch_color_used.get(new_col, -1)
                    if new_col != mainline_col and \
                       (occupant_y < commit_node.y or occupant_branch_color == commit_node.branch_color_idx) :
                        commit_node.column = new_col
                        break
                    new_col +=1
                    if new_col > max((c.column for c in commits if hasattr(c, 'column')), default=0) + 5 : # Safety break
                         commit_node.column = new_col
                         break


        # Fallback for color_idx if somehow still not set (e.g. non-mainline, no branch_color_idx)
        if commit_node.color_idx is None:
            if parent_nodes and parent_nodes[0].color_idx is not None:
                 commit_node.color_idx = parent_nodes[0].color_idx # Inherit from first parent as last resort
            else:
                 commit_node.color_idx = (mainline_color_idx + 1) % len(COLOR_PALETTE) if COLOR_PALETTE else 0


        lane_occupied_until_y[commit_node.column] = commit_node.y
        if commit_node.branch_color_idx is not None:
            lane_branch_color_used[commit_node.column] = commit_node.branch_color_idx
        else: # Should ideally not happen if color_idx is now based on branch_color_idx
            lane_branch_color_used[commit_node.column] = commit_node.color_idx


        commit_node.x = commit_node.column * LAYOUT_HORIZONTAL_SPACING

    # Post-layout adjustments (Normalization)
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
