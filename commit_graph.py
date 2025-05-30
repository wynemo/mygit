from PyQt6.QtCore import QPoint, Qt, QRect # QRect was added previously
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem # Added QTreeWidgetItem
from typing import List, Optional, Any, Dict 


# --- Data Structures for Graph Elements ---

class RefInfo:
    """Base class for information about a Git reference (branch or tag)."""
    def __init__(self, name: str):
        self.name: str = name

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}('{self.name}')"


class BranchInfo(RefInfo):
    """Information about a Git branch."""
    def __init__(self, name: str, is_local: bool, is_current: bool, commit_hash: str):
        super().__init__(name)
        self.is_local: bool = is_local
        self.is_current: bool = is_current
        self.commit_hash: str = commit_hash  # Hash of the commit this branch points to

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}('{self.name}', local={self.is_local}, current={self.is_current}, commit='{self.commit_hash}')"


class TagInfo(RefInfo):
    """Information about a Git tag."""
    def __init__(self, name: str, commit_hash: str):
        super().__init__(name)
        self.commit_hash: str = commit_hash  # Hash of the commit this tag points to

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}('{self.name}', commit='{self.commit_hash}')"


class NodeDescriptor:
    """Base class for all nodes in the visual tree of the commit graph."""
    q_tree_widget_item: Optional['QTreeWidgetItem'] = None # Class attribute for type hinting

    def __init__(self, display_name: str):
        self.display_name: str = display_name
        self.q_tree_widget_item: Optional['QTreeWidgetItem'] = None # Instance attribute
        self.children: List['NodeDescriptor'] = [] # Forward reference for type hint

    def add_child(self, child: 'NodeDescriptor'):
        self.children.append(child)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}('{self.display_name}', children={len(self.children)})"


class CommitNode(NodeDescriptor):
    """Represents a commit in the graph."""
    # Using Any for commit_data as its structure is not yet fully defined
    def __init__(self, commit_data: Dict[str, Any], display_name_override: Optional[str] = None):
        # Potentially use commit hash or a shortened version for display_name if not overridden
        super().__init__(display_name_override or commit_data.get("hash", "Unknown Commit"))
        self.commit_data: Dict[str, Any] = commit_data
        # Parents in terms of NodeDescriptors will be set during graph construction
        self.parent_nodes: List[NodeDescriptor] = []

    def __repr__(self) -> str:
        return f"CommitNode('{self.commit_data.get('hash', 'Unknown')}', children={len(self.children)})"


class BranchNode(NodeDescriptor):
    """Represents a branch in the visual tree."""
    def __init__(self, branch_info: BranchInfo):
        super().__init__(branch_info.name)
        self.branch_info: BranchInfo = branch_info

    def __repr__(self) -> str:
        return f"BranchNode(info={self.branch_info}, children={len(self.children)})"


class TagNode(NodeDescriptor):
    """Represents a tag in the visual tree."""
    def __init__(self, tag_info: TagInfo):
        super().__init__(tag_info.name)
        self.tag_info: TagInfo = tag_info

    def __repr__(self) -> str:
        return f"TagNode(info={self.tag_info}, children={len(self.children)})"


class RemoteNode(NodeDescriptor):
    """Represents a remote in the visual tree."""
    def __init__(self, name: str):
        super().__init__(name)
        # Children will be BranchNodes under this remote

    def __repr__(self) -> str:
        return f"RemoteNode('{self.display_name}', children={len(self.children)})"


class GroupNode(NodeDescriptor):
    """Represents a group of branches (e.g., 'feature/', 'bugfix/')."""
    def __init__(self, group_prefix: str):
        super().__init__(group_prefix)
        # Children will be BranchNodes or other GroupNodes

    def __repr__(self) -> str:
        return f"GroupNode('{self.display_name}', children={len(self.children)})"


# --- Commit Graph Widget ---

class CommitGraphView(QTreeWidget):
    COMMIT_DOT_RADIUS = 5
    COLUMN_WIDTH = 15 # For lane spacing within the graph area
    ROW_HEIGHT = 20   # For fallback Y, and vertical spacing of topological levels
    GRAPH_X_OFFSET = 20 # Initial X offset for the graph drawing area from the tree items

    def __init__(self, parent=None):
        super().__init__(parent)
        self.commits_data = [] # Raw commit data list
        self.branch_colors = {}
        self.commit_positions: Dict[str, QPoint] = {}  # Stores QPoint for each commit hash for drawing
        # self.node_positions is removed as QTreeWidget handles label positions.
        # CommitNode positions will be stored directly in self.commit_positions.
        self.branch_x_lanes: Dict[str, int] = {} # Stores X-coordinate for branch "lanes"
        self.root_node: Optional[NodeDescriptor] = None # Root of our structured tree
        self.commit_nodes_map: Dict[str, CommitNode] = {} # Map hash to CommitNode
        self.raw_graph_data: Dict[str, Any] = {} # To store the original graph_data if needed
        self.branch_name_to_node_map: Dict[str, BranchNode] = {}

    def _find_or_create_group_node(self, parent_node: NodeDescriptor, group_name: str) -> GroupNode:
        """Finds an existing GroupNode or creates and adds a new one."""
        for child in parent_node.children:
            if isinstance(child, GroupNode) and child.display_name == group_name:
                return child
        new_group_node = GroupNode(group_name)
        parent_node.add_child(new_group_node)
        return new_group_node

    def _find_or_create_remote_node(self, parent_node: NodeDescriptor, remote_name: str) -> RemoteNode:
        """Finds an existing RemoteNode or creates and adds a new one."""
        for child in parent_node.children:
            if isinstance(child, RemoteNode) and child.display_name == remote_name:
                return child
        new_remote_node = RemoteNode(remote_name)
        parent_node.add_child(new_remote_node)
        return new_remote_node

    def _build_branch_tree(self, graph_data: Dict[str, Any]) -> NodeDescriptor:
        """
        Transforms raw commit data into a structured tree of NodeDescriptors.
        """
        root = GroupNode("root")
        local_branches_group = GroupNode("Local Branches")
        remotes_group = GroupNode("Remotes")
        tags_group = GroupNode("Tags")
        root.add_child(local_branches_group)
        root.add_child(remotes_group)
        root.add_child(tags_group)

        self.commit_nodes_map.clear()
        if "commits" not in graph_data:
            return root # Return empty structure if no commits

        # 1. Create CommitNode for all commits
        for commit_data_item in graph_data["commits"]:
            commit_hash = commit_data_item["hash"]
            self.commit_nodes_map[commit_hash] = CommitNode(commit_data_item)

        # 2. Process branches and tags from commit data
        # head_hash helps determine the current branch.
        # The head_hash from graph_data might be a commit hash if HEAD is detached,
        # or a ref name like 'refs/heads/main'.
        raw_head_ref = graph_data.get("head_ref", "") # e.g., "refs/heads/main"
        current_branch_name = ""
        if raw_head_ref.startswith("refs/heads/"):
            current_branch_name = raw_head_ref[len("refs/heads/"):]

        all_branch_infos: List[BranchInfo] = []
        all_tag_infos: List[TagInfo] = []

        for commit_data_item in graph_data["commits"]:
            commit_hash = commit_data_item["hash"]
            
            # Process branches associated with this commit
            for branch_name_full in commit_data_item.get("branches", []):
                is_local = not branch_name_full.startswith("refs/remotes/")
                is_current = False
                
                if is_local:
                    # Simple name like "main" or "feature/foo"
                    actual_branch_name = branch_name_full
                    if actual_branch_name == current_branch_name:
                        is_current = True
                    all_branch_infos.append(BranchInfo(actual_branch_name, True, is_current, commit_hash))
                else:
                    # Remote branch like "refs/remotes/origin/main"
                    # Format is usually refs/remotes/<remote_name>/<branch_name_on_remote>
                    parts = branch_name_full.split('/', 4)
                    if len(parts) >= 4 and parts[0] == "refs" and parts[1] == "remotes":
                        remote_name = parts[2]
                        branch_name_on_remote = "/".join(parts[3:])
                        # For current purposes, remote branches are not "current" in the local repo sense
                        all_branch_infos.append(BranchInfo(f"{remote_name}/{branch_name_on_remote}", False, False, commit_hash))

            # Process tags associated with this commit
            for tag_name in commit_data_item.get("tags", []):
                all_tag_infos.append(TagInfo(tag_name, commit_hash))
        
        # Deduplicate BranchInfo and TagInfo (preferring current branch if duplicates exist)
        # A commit can be pointed to by multiple refs, but we want unique BranchInfo/TagInfo for tree
        unique_branch_infos: Dict[str, BranchInfo] = {}
        for bi in all_branch_infos:
            key = bi.name # Using full name for uniqueness (e.g. "origin/main")
            if key not in unique_branch_infos or (bi.is_current and not unique_branch_infos[key].is_current) :
                 unique_branch_infos[key] = bi
        
        unique_tag_infos: Dict[str, TagInfo] = {ti.name: ti for ti in all_tag_infos}


        # 3. Build tree structure for local branches
        for branch_info in unique_branch_infos.values():
            if not branch_info.is_local:
                continue

            parts = branch_info.name.split('/')
            current_parent_node: NodeDescriptor = local_branches_group
            for i, part_name in enumerate(parts):
                if i == len(parts) - 1: # Last part is the branch name itself
                    branch_node = BranchNode(branch_info)
                    current_parent_node.add_child(branch_node)
                else: # Intermediate parts are group names
                    current_parent_node = self._find_or_create_group_node(current_parent_node, part_name)
        
        # 4. Build tree structure for remote branches
        for branch_info in unique_branch_infos.values():
            if branch_info.is_local:
                continue

            # Name is already "remote/branch" e.g. "origin/main" or "origin/feature/foo"
            remote_and_branch_name = branch_info.name 
            parts = remote_and_branch_name.split('/', 1)
            remote_name = parts[0]
            branch_path = parts[1] if len(parts) > 1 else "" # Should always have a branch path

            remote_node = self._find_or_create_remote_node(remotes_group, remote_name)
            
            branch_parts = branch_path.split('/')
            current_parent_node: NodeDescriptor = remote_node
            for i, part_name in enumerate(branch_parts):
                if i == len(branch_parts) - 1: # Last part is the branch name
                    # We need to create a new BranchInfo here that reflects the "display name" within the remote
                    # The original branch_info.name is "origin/main", but in the tree, we want "main" under "origin"
                    # For now, reuse existing branch_info, but ideally BranchInfo.name would be the short name
                    # and it would have a separate `remote_name` attribute.
                    # Let's adjust BranchNode's display name for now.
                    # Create a new BranchInfo for this context
                    # The 'branch_info' (from unique_branch_infos) has the full correct name like "origin/main".
                    # We want the BranchNode to store this BranchInfo.
                    # The display name for the node in the tree should be the short part_name (e.g., "main").
                    bn = BranchNode(branch_info) 
                    bn.display_name = part_name # Set display name to the short name
                    current_parent_node.add_child(bn)
                else: # Intermediate parts are group names under the remote
                    current_parent_node = self._find_or_create_group_node(current_parent_node, part_name)

        # 5. Build tree structure for tags
        for tag_info in unique_tag_infos.values():
            # Tags are generally not namespaced in the same way as branches,
            # but some projects might use '/' in tag names. For now, treat them as flat.
            # If namespacing for tags (e.g. "release/v1.0") is needed, similar logic to branches applies.
            tag_node = TagNode(tag_info)
            tags_group.add_child(tag_node)
            
        return root

    def set_commit_data(self, graph_data: Dict[str, Any]):
        """设置提交数据 and build the branch tree."""
        self.raw_graph_data = graph_data # Store raw graph data
        self.commits_data = graph_data.get("commits", [])
        self.branch_colors = graph_data.get("branch_colors", {})
        
        self.root_node = self._build_branch_tree(graph_data)
        
        self.calculate_positions() 
        self.update() # Triggers repaint

    def _assign_branch_lanes_recursive(self, node: NodeDescriptor, current_x_ref: List[int], current_remote_name: Optional[str] = None):
        """ Helper to assign X-coordinates (lanes) to branches. """
        if isinstance(node, RemoteNode):
            # Update current_remote_name for children of this RemoteNode
            for child in node.children:
                self._assign_branch_lanes_recursive(child, current_x_ref, node.display_name)
            return # RemoteNode itself doesn't get a lane, its branches do

        if isinstance(node, BranchNode):
            # After fixes to _build_branch_tree, node.branch_info.name is already the correct
            # full key, e.g., "main" for local, "origin/main" for remote.
            branch_key = node.branch_info.name
            
            if branch_key not in self.branch_x_lanes:
                self.branch_x_lanes[branch_key] = current_x_ref[0]
                current_x_ref[0] += self.COLUMN_WIDTH * 2 # Increment X for the next distinct branch lane

        # For GroupNodes, continue traversal with the same remote_name context
        elif isinstance(node, GroupNode):
            for child in node.children:
                self._assign_branch_lanes_recursive(child, current_x_ref, current_remote_name)
            return # GroupNode itself doesn't get a lane

        # Default traversal for other node types if necessary (though primarily targeting BranchNodes)
        # This path should ideally not be hit if structure is as expected (Group or Remote as parents of Branches)
        else:
            for child in node.children:
                 self._assign_branch_lanes_recursive(child, current_x_ref, current_remote_name)


    # _calculate_label_positions_recursive is removed. QTreeWidget handles label positions.

    def _collect_branch_nodes_recursive(self, node: NodeDescriptor):
        if isinstance(node, BranchNode):
            self.branch_name_to_node_map[node.branch_info.name] = node
        for child in node.children:
            self._collect_branch_nodes_recursive(child)

    def calculate_positions(self):
        """Calculates positions for commit dots, now relative to QTreeWidgetItems."""
        self.commit_positions.clear()
        # self.node_positions.clear() # No longer used for labels
        self.branch_x_lanes.clear()
        self.branch_name_to_node_map.clear()

        if not self.root_node or not self.commits_data:
            self.update() # Ensure repaint even if no data
            return

        # Populate branch_name_to_node_map
        if self.root_node:
            self._collect_branch_nodes_recursive(self.root_node)
            
        # Step 1: Assign X "lanes" to branches by traversing the NodeDescriptor tree
        # These lanes are for the commit graph part.
        initial_x_lane = self.COLUMN_WIDTH
        # We want to iterate through Local, then Remotes for lane assignment order.
        if self.root_node.children:
            local_branches_node = next((n for n in self.root_node.children if n.display_name == "Local Branches"), None)
            remote_branches_node = next((n for n in self.root_node.children if n.display_name == "Remotes"), None)
            
            current_x_ref = [initial_x_lane]
            if local_branches_node:
                self._assign_branch_lanes_recursive(local_branches_node, current_x_ref, None) # No remote name for local branches
            
            # Reset X slightly or continue for remotes, ensuring they don't overlap too much if desired
            # For now, remotes will continue from where local branches left off.
            if remote_branches_node:
                 self._assign_branch_lanes_recursive(remote_branches_node, current_x_ref, None) # Start with no remote, it will be set by RemoteNode


        # Step 2: Determine topological levels for Y-ordering of commits.
        # This remains crucial for drawing lines and as a fallback Y.
        children_map: Dict[str, List[str]] = {commit_hash: [] for commit_hash in self.commit_nodes_map.keys()}
        in_degree: Dict[str, int] = {commit_hash: 0 for commit_hash in self.commit_nodes_map.keys()}
        
        all_present_commit_hashes = set(self.commit_nodes_map.keys())

        for commit_hash, commit_node in self.commit_nodes_map.items():
            num_present_parents = 0
            for parent_hash in commit_node.commit_data.get("parents", []):
                if parent_hash in all_present_commit_hashes:
                    children_map.setdefault(parent_hash, []).append(commit_hash)
                    num_present_parents += 1
            in_degree[commit_hash] = num_present_parents

        # Initialize queue with root nodes (in_degree == 0)
        # These are nodes without parents within the current commits_data set
        current_level_queue: List[str] = [commit_hash for commit_hash, degree in in_degree.items() if degree == 0]
        
        commit_levels: Dict[str, int] = {}
        level = 0
        
        processed_commits_count = 0
        while current_level_queue:
            next_level_queue: List[str] = []
            for commit_hash_u in current_level_queue:
                commit_levels[commit_hash_u] = level
                processed_commits_count +=1
                
                for child_hash_v in children_map.get(commit_hash_u, []):
                    in_degree[child_hash_v] -= 1
                    if in_degree[child_hash_v] == 0:
                        next_level_queue.append(child_hash_v)
            
            # For commits on the same level, sort them by original index (approximating date)
            # to maintain some visual consistency if graph_data was date-sorted.
            # This helps make layout more deterministic if multiple orders are possible.
            original_indices = {chash: i for i, cdata in enumerate(self.commits_data) for chash in [cdata["hash"]]}
            next_level_queue.sort(key=lambda ch: original_indices.get(ch, float('inf')))

            current_level_queue = next_level_queue
            level += 1
        
        if processed_commits_count < len(all_present_commit_hashes):
            # This indicates a cycle in the graph or commits with missing (but expected) parents.
            # Assign remaining commits to a default level or handle as an error.
            # For now, assign them to a high level to make them visible.
            print(f"Warning: Cycle detected or missing parents. {len(all_present_commit_hashes) - processed_commits_count} commits not leveled.")
            for chash in all_present_commit_hashes:
                if chash not in commit_levels:
                    commit_levels[chash] = level # Place them at the next available level
            level +=1


        # Step 3: Assign X and Y positions to commits
        
        # Build a map of tip commit hashes to their branch names (keys from self.branch_x_lanes)
        tip_commit_to_branch_names: Dict[str, List[str]] = {}
        # Inner helper function for recursion within calculate_positions context
        def _collect_branch_tips_recursive_inner(node: NodeDescriptor):
            if isinstance(node, BranchNode):
                tip_hash = node.branch_info.commit_hash
                tip_commit_to_branch_names.setdefault(tip_hash, []).append(node.branch_info.name)
            for child_node in node.children:
                _collect_branch_tips_recursive_inner(child_node)

        if self.root_node:
            _collect_branch_tips_recursive_inner(self.root_node)

        head_ref_full = self.raw_graph_data.get("head_ref", "")
        current_head_branch_key: Optional[str] = None
        if head_ref_full.startswith("refs/heads/"):
            current_head_branch_key = head_ref_full[len("refs/heads/"):]
        elif head_ref_full.startswith("refs/remotes/"):
            parts = head_ref_full.split('/', 3)
            if len(parts) == 4: current_head_branch_key = f"{parts[2]}/{parts[3]}"

        # Determine a base X for the graph drawing area, right of the tree items.
        # This might need adjustment based on actual QTreeWidget column 0 width.
        # For now, using a fixed offset from the viewport, plus self.indentation for some padding.
        # A more robust way might involve self.header().sectionViewportPosition(0) + self.header().sectionSize(0)
        # if the header is visible and sections are well-defined.
        # Let's assume column 0 is where items are, and graph starts after it.
        # This is a placeholder; a more robust calculation might be needed.
        # Effective indentation for items in column 0. Max depth of visible tree could be used.
        # For simplicity, let's use a fixed offset.
        # If header is not visible, sectionSize(0) might be entire viewport.
        # self.indentation() is the per-level indent.
        base_x_for_graph = self.indentation() * 3 + self.GRAPH_X_OFFSET # Approx 3 levels of indent + offset
        if self.header().isVisible():
             base_x_for_graph = self.header().sectionSize(0) + self.GRAPH_X_OFFSET


        for commit_data_item in self.commits_data:
            commit_hash = commit_data_item["hash"]
            
            topo_level = commit_levels.get(commit_hash)
            if topo_level is None: 
                print(f"Warning: Commit {commit_hash} was not assigned a topological level.")
                topo_level = level 
            
            owning_branch_name: Optional[str] = None
            owning_branch_node: Optional[BranchNode] = None
            
            commit_branch_full_refs = commit_data_item.get("branches", [])
            commit_branch_keys: List[str] = []
            for b_full_ref in commit_branch_full_refs:
                if b_full_ref.startswith("refs/heads/"):
                    commit_branch_keys.append(b_full_ref[len("refs/heads/"):])
                elif b_full_ref.startswith("refs/remotes/"):
                    parts = b_full_ref.split('/', 3)
                    if len(parts) == 4: commit_branch_keys.append(f"{parts[2]}/{parts[3]}")
            
            if current_head_branch_key and current_head_branch_key in commit_branch_keys:
                owning_branch_name = current_head_branch_key
            
            if not owning_branch_name:
                branches_where_this_is_tip = tip_commit_to_branch_names.get(commit_hash, [])
                if branches_where_this_is_tip:
                    branches_where_this_is_tip.sort(key=lambda bn: self.branch_x_lanes.get(bn, float('inf')))
                    owning_branch_name = branches_where_this_is_tip[0]
            
            if not owning_branch_name and commit_branch_keys:
                valid_branches_with_lanes = [
                    bn_key for bn_key in commit_branch_keys if bn_key in self.branch_x_lanes
                ]
                if valid_branches_with_lanes:
                    valid_branches_with_lanes.sort(key=lambda bn_key: self.branch_x_lanes[bn_key])
                    owning_branch_name = valid_branches_with_lanes[0]

            # Determine X and Y for the commit dot
            assigned_x = base_x_for_graph + self.COLUMN_WIDTH # Default lane X within graph area
            y_pos = topo_level * self.ROW_HEIGHT + self.ROW_HEIGHT // 2 # Fallback Y based on topo level

            if owning_branch_name:
                owning_branch_node = self.branch_name_to_node_map.get(owning_branch_name)
                if owning_branch_node:
                    if not hasattr(owning_branch_node, 'q_tree_widget_item'):
                        print(f"CRITICAL_DEBUG: BranchNode {owning_branch_node.display_name} ({owning_branch_node.branch_info.name}) LACKS q_tree_widget_item attribute!")
                        # y_pos remains topo_level based (already set)
                        # X can use lane if available, else default
                        assigned_x = base_x_for_graph + self.branch_x_lanes.get(owning_branch_name, self.COLUMN_WIDTH)
                    elif owning_branch_node.q_tree_widget_item is None:
                        print(f"CRITICAL_DEBUG: BranchNode {owning_branch_node.display_name} ({owning_branch_node.branch_info.name}) has q_tree_widget_item=None!")
                        # y_pos remains topo_level based
                        assigned_x = base_x_for_graph + self.branch_x_lanes.get(owning_branch_name, self.COLUMN_WIDTH)
                    else: # Attribute exists and is not None
                        q_item = owning_branch_node.q_tree_widget_item
                        item_rect = self.visualItemRect(q_item)
                        # Check if item_rect is valid (not empty, not (0,0,0,0) if that's an invalid state)
                        if item_rect and item_rect.isValid() and not (item_rect.width() == 0 and item_rect.height() == 0 and item_rect.x() == 0 and item_rect.y() == 0) :
                            y_pos = item_rect.top() + item_rect.height() // 2
                            assigned_x = base_x_for_graph + self.branch_x_lanes.get(owning_branch_name, self.COLUMN_WIDTH)
                        else: # visualItemRect not valid, use fallback for Y
                            if item_rect is not None:
                                print(f"DEBUG: visualItemRect for {owning_branch_node.display_name} is invalid/empty: x={item_rect.x()},y={item_rect.y()},w={item_rect.width()},h={item_rect.height()}")
                            else: # visualItemRect may have returned None
                                print(f"DEBUG: visualItemRect for {owning_branch_node.display_name} returned None")
                            # y_pos remains topo_level based
                            assigned_x = base_x_for_graph + self.branch_x_lanes.get(owning_branch_name, self.COLUMN_WIDTH)
                elif owning_branch_name in self.branch_x_lanes: # Owning branch node not found in map, but lane exists
                    print(f"DEBUG: Owning branch node for {owning_branch_name} not in branch_name_to_node_map, but lane exists.")
                    assigned_x = base_x_for_graph + self.branch_x_lanes[owning_branch_name]
                    # y_pos remains topo_level based
                else: # Owning branch completely unknown for X
                    print(f"DEBUG: Owning branch {owning_branch_name} has no node or lane.")
                    # y_pos remains topo_level based, assigned_x remains default graph area X + COLUMN_WIDTH
            elif commit_branch_keys: # Fallback if no specific owning_branch_name, use first known branch
                for bn_key in commit_branch_keys:
                    if bn_key in self.branch_x_lanes:
                        assigned_x = base_x_for_graph + self.branch_x_lanes[bn_key]
                        break
                # y_pos remains topo_level based
            else: # No owning branch and no associated branches with lanes
                print(f"DEBUG: Commit {commit_hash} has no owning branch or known branch lanes.")
                # y_pos remains topo_level based, assigned_x remains default
            
            self.commit_positions[commit_hash] = QPoint(assigned_x, y_pos)
            # No need to update self.node_positions for CommitNodes if paintEvent uses commit_positions

        # NO LONGER NEEDED: Step 3: Position labels for Groups, Branches, Tags in the tree hierarchy
        # QTreeWidget handles this.
        
        self.update()

    def _get_branch_color(self, branch_name_full_or_simple: str) -> QColor:
        """Gets color for a branch, handling full ref or simple name."""
        # self.branch_colors keys are simple for local (main), remote/branch for remote (origin/main)
        
        if branch_name_full_or_simple.startswith("refs/heads/"):
            key = branch_name_full_or_simple[len("refs/heads/"):]
        elif branch_name_full_or_simple.startswith("refs/remotes/"):
            parts = branch_name_full_or_simple.split('/', 3)
            if len(parts) == 4: # refs/remotes/origin/main -> origin/main
                key = f"{parts[2]}/{parts[3]}"
            else: # Should not happen if format is correct
                key = branch_name_full_or_simple 
        else: # Already a simple name
            key = branch_name_full_or_simple
            
        return QColor(self.branch_colors.get(key, "#cccccc")) # Default color if not found

    def _get_commit_color(self, commit_data_item: Dict[str, Any]) -> QColor:
        """Determines the color for a commit dot or line based on its branches."""
        if not commit_data_item:
            return QColor("#cccccc") # Default
            
        commit_branches = commit_data_item.get("branches", [])
        if not commit_branches:
            return QColor("#cccccc") # Default for commits with no branch association (e.g., detached)

        head_ref = self.raw_graph_data.get("head_ref", "") # e.g. "refs/heads/main"
        
        # Priority 1: Current checked-out branch
        if head_ref:
            simple_head_ref = ""
            if head_ref.startswith("refs/heads/"):
                simple_head_ref = head_ref[len("refs/heads/"):]
            elif head_ref.startswith("refs/remotes/"): # Should not be primary for local commit color
                parts = head_ref.split('/',3)
                if len(parts) == 4: simple_head_ref = f"{parts[2]}/{parts[3]}"

            if simple_head_ref and simple_head_ref in commit_branches : # commit_branches are simple names for local, full for remote
                 # Need to check if simple_head_ref (if local) is in commit_branches (which are full names)
                 # Or if simple_head_ref (if remote, e.g. "origin/main") is in commit_branches (which are full names)
                if head_ref in commit_branches: # commit_branches from item are full "refs/..." names
                    return self._get_branch_color(head_ref)


        # Priority 2: First local branch
        for b_name_full in commit_branches: # e.g. "main" or "refs/remotes/origin/main"
            if not b_name_full.startswith("refs/remotes/"):
                # It's a local branch name, already simple like "main" or "feature/foo"
                return self._get_branch_color(b_name_full)
        
        # Priority 3: First remote branch
        for b_name_full in commit_branches:
            if b_name_full.startswith("refs/remotes/"):
                 return self._get_branch_color(b_name_full) # _get_branch_color handles parsing "refs/remotes/..."

        return QColor("#cccccc") # Fallback

    def paintEvent(self, event):
        """Draws the commit graph and branch/tag labels."""
        super().paintEvent(event)
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if not self.root_node or not self.commits_data:
            return

        v_scroll = self.verticalScrollBar().value()
        h_scroll = self.horizontalScrollBar().value()

        # 1. Draw Commit Graph Lines (Connections)
        for commit_data_item in self.commits_data: # Iterate raw commit data for parent info
            commit_hash = commit_data_item["hash"]
            original_child_pos = self.commit_positions.get(commit_hash)
            if not original_child_pos:
                continue

            child_pos = QPoint(original_child_pos.x() - h_scroll, original_child_pos.y() - v_scroll)
            
            # Determine line color based on the child commit
            line_color = self._get_commit_color(commit_data_item)
            pen = QPen(line_color, 2)
            painter.setPen(pen)

            for parent_hash in commit_data_item.get("parents", []):
                original_parent_pos = self.commit_positions.get(parent_hash)
                if not original_parent_pos:
                    continue
                
                parent_pos = QPoint(original_parent_pos.x() - h_scroll, original_parent_pos.y() - v_scroll)
                
                # Check visibility for lines (optional, can be expensive)
                # For simplicity, draw if either end is visible or near visible.
                # A more robust check would involve line clipping algorithms.
                line_rect = QRect(child_pos, parent_pos).normalized()
                if not self.viewport().rect().intersects(line_rect.adjusted(-20,-20,20,20)): # Add some margin
                    # continue # This might be too aggressive, let's draw for now
                    pass


                painter.drawLine(child_pos, parent_pos)

        # 2. Draw Commit Dots
        # Need commit_data_item again for coloring, so iterate self.commits_data
        commit_data_map = {c["hash"]: c for c in self.commits_data}

        for commit_hash, original_pos in self.commit_positions.items():
            pos = QPoint(original_pos.x() - h_scroll, original_pos.y() - v_scroll)

            if not (0 <= pos.y() <= self.viewport().height() + self.COMMIT_DOT_RADIUS * 2): # Check Y visibility
                 if not (-self.COMMIT_DOT_RADIUS*2 <= pos.y() <= self.viewport().height() + self.COMMIT_DOT_RADIUS*2): # Check Y visibility
                    continue


            commit_data_item = commit_data_map.get(commit_hash)
            dot_color = self._get_commit_color(commit_data_item)

            painter.setBrush(dot_color)
            painter.setPen(Qt.PenStyle.NoPen) # No border for dots typically
            painter.drawEllipse(
                pos.x() - self.COMMIT_DOT_RADIUS,
                pos.y() - self.COMMIT_DOT_RADIUS,
                self.COMMIT_DOT_RADIUS * 2,
                self.COMMIT_DOT_RADIUS * 2,
            )

        # 3. Draw Node Labels (Branches, Groups, Tags)
        font = painter.font()
        font_metrics = painter.fontMetrics()

        for node, original_pos in self.node_positions.items():
            if isinstance(node, CommitNode): # Commit dots already drawn
                continue

            pos = QPoint(original_pos.x() - h_scroll, original_pos.y() - v_scroll)

            # Check Y visibility for labels
            # Approximate height of text for visibility check
            text_height = font_metrics.height()
            if not (-text_height <= pos.y() <= self.viewport().height() + text_height):
                continue
            
            display_name = node.display_name
            label_color = QColor(Qt.GlobalColor.black) # Default label color

            if isinstance(node, BranchNode):
                # node.display_name is short name for remote, full for local
                # node.branch_info.name is short for remote, full for local
                # This is due to how BranchNode was constructed for remotes.
                # For coloring with self.branch_colors, we need the key that matches.
                # node.branch_info.name should already be correctly formatted by _build_branch_tree
                # (e.g., "main" for local, "origin/main" for remote branches).
                branch_key_for_color = node.branch_info.name
                
                label_color = self._get_branch_color(branch_key_for_color)
                
                if node.branch_info.is_current:
                    font.setBold(True)
                    # Add a visual marker like '*' or 'HEAD ->'
                    # display_name = f"* {display_name}" # Simple star
                else:
                    font.setBold(False)
            elif isinstance(node, TagNode):
                label_color = QColor("#FFA500") # Orange for tags
                font.setBold(False)
            else: # GroupNode, RemoteNode
                font.setBold(True) # Make group names bold

            painter.setFont(font)
            painter.setPen(label_color)
            
            # Adjust text position for better alignment with the point
            # Point is typically middle-left or top-left for the label.
            # Let's assume point is middle-left of where text should start.
            text_x = pos.x() + self.COMMIT_DOT_RADIUS # Start text slightly to the right of where a dot might be
            text_y = pos.y() + font_metrics.ascent() // 2 # Align text vertically centered
            
            painter.drawText(text_x, text_y, display_name)
            font.setBold(False) # Reset bold for next iteration
        painter.setFont(font) # Ensure font is reset finally
