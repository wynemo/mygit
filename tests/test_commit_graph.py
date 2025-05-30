import unittest
from PyQt6.QtCore import QPoint

# Assuming CommitGraphView and its Node types are in app.commit_graph
# Adjust this import path based on your project structure.
# For this environment, let's assume commit_graph.py is in the root or accessible directly.
from commit_graph import (
    CommitGraphView,
    NodeDescriptor,
    CommitNode,
    BranchNode,
    TagNode,
    GroupNode,
    RemoteNode,
    BranchInfo,
    TagInfo
)

# Helper to find a node in the tree via a path of display names
def find_node_by_path(start_node: NodeDescriptor, path: list[str]) -> Optional[NodeDescriptor]:
    current_node = start_node
    for part_name in path:
        found_child = None
        for child in current_node.children:
            if child.display_name == part_name:
                found_child = child
                break
        if not found_child:
            return None
        current_node = found_child
    return current_node

class TestCommitGraphView(unittest.TestCase):
    def setUp(self):
        self.view = CommitGraphView() # Create a new view for each test

    # --- Test Data Scenarios ---
    @staticmethod
    def get_scenario_linear_data():
        return {
            "commits": [ # Newest first
                {"hash": "c3", "parents": ["c2"], "branches": ["refs/heads/main"], "tags": [], "subject": "Commit 3"},
                {"hash": "c2", "parents": ["c1"], "branches": [], "tags": [], "subject": "Commit 2"},
                {"hash": "c1", "parents": [], "branches": [], "tags": ["refs/tags/v1.0"], "subject": "Commit 1"},
            ],
            "branch_colors": {"main": "#FF0000", "v1.0": "#00FF00"}, # Tag colors not directly used by branch_colors
            "head_ref": "refs/heads/main"
        }

    @staticmethod
    def get_scenario_fork_data():
        return {
            "commits": [ # Newest first
                {"hash": "c4", "parents": ["c2"], "branches": ["refs/heads/develop"], "tags": [], "subject": "Commit 4 (dev)"},
                {"hash": "c3", "parents": ["c2"], "branches": ["refs/heads/main"], "tags": [], "subject": "Commit 3 (main)"},
                {"hash": "c2", "parents": ["c1"], "branches": [], "tags": [], "subject": "Commit 2 (common)"},
                {"hash": "c1", "parents": [], "branches": [], "tags": ["refs/tags/v0.9"], "subject": "Commit 1 (init)"},
            ],
            "branch_colors": {"main": "#FF0000", "develop": "#00FF00"},
            "head_ref": "refs/heads/develop"
        }

    @staticmethod
    def get_scenario_remote_branches_data():
        return {
            "commits": [ # Newest first
                {"hash": "c4", "parents": ["c3"], "branches": ["refs/remotes/origin/feature-x"], "tags": [], "subject": "Commit 4 (remote feature)"},
                {"hash": "c3", "parents": ["c2"], "branches": ["refs/heads/main", "refs/remotes/origin/main"], "tags": [], "subject": "Commit 3 (main sync)"},
                {"hash": "c2", "parents": ["c1"], "branches": ["refs/remotes/origin/main"], "tags": [], "subject": "Commit 2 (origin main old)"}, # Simulating local main not yet at c2
                {"hash": "c1", "parents": [], "branches": [], "tags": [], "subject": "Commit 1 (init)"},
            ],
            "branch_colors": {"main": "#FF0000", "origin/main": "#AA0000", "origin/feature-x": "#00AA00"},
            "head_ref": "refs/heads/main"
        }
        
    @staticmethod
    def get_scenario_namespaced_branches_data():
        return {
            "commits": [
                {"hash": "c4", "parents": ["c1"], "branches": ["refs/heads/feature/new-ux"], "tags":[]},
                {"hash": "c3", "parents": ["c1"], "branches": ["refs/heads/feature/sidebar"], "tags":[]},
                {"hash": "c2", "parents": ["c1"], "branches": ["refs/heads/bugfix/login-issue"], "tags":[]},
                {"hash": "c1", "parents": [], "branches": ["refs/heads/main"], "tags":[]},
            ],
            "branch_colors": {
                "main": "#FF0000", 
                "feature/new-ux": "#00FF00", 
                "feature/sidebar": "#00AAFF",
                "bugfix/login-issue": "#FFAA00"
            },
            "head_ref": "refs/heads/feature/new-ux"
        }

    # --- Tests for _build_branch_tree ---

    def test_build_tree_linear(self):
        graph_data = self.get_scenario_linear_data()
        self.view.set_commit_data(graph_data)

        self.assertIsNotNone(self.view.root_node)
        self.assertEqual(len(self.view.root_node.children), 3) # Local, Remotes, Tags

        # Local Branches
        local_branches_node = find_node_by_path(self.view.root_node, ["Local Branches"])
        self.assertIsNotNone(local_branches_node)
        self.assertIsInstance(local_branches_node, GroupNode)
        
        main_branch_node = find_node_by_path(local_branches_node, ["main"])
        self.assertIsNotNone(main_branch_node)
        self.assertIsInstance(main_branch_node, BranchNode)
        self.assertEqual(main_branch_node.branch_info.name, "main")
        self.assertTrue(main_branch_node.branch_info.is_local)
        self.assertTrue(main_branch_node.branch_info.is_current) # head_ref is main
        self.assertEqual(main_branch_node.branch_info.commit_hash, "c3")

        # Tags
        tags_node = find_node_by_path(self.view.root_node, ["Tags"])
        self.assertIsNotNone(tags_node)
        self.assertIsInstance(tags_node, GroupNode)

        tag_v1_node = find_node_by_path(tags_node, ["v1.0"])
        self.assertIsNotNone(tag_v1_node)
        self.assertIsInstance(tag_v1_node, TagNode)
        self.assertEqual(tag_v1_node.tag_info.name, "v1.0")
        self.assertEqual(tag_v1_node.tag_info.commit_hash, "c1")
        
        # Commit Nodes Map
        self.assertIn("c1", self.view.commit_nodes_map)
        self.assertIn("c2", self.view.commit_nodes_map)
        self.assertIn("c3", self.view.commit_nodes_map)
        self.assertIsInstance(self.view.commit_nodes_map["c1"], CommitNode)

    def test_build_tree_fork(self):
        graph_data = self.get_scenario_fork_data()
        self.view.set_commit_data(graph_data)

        local_branches_node = find_node_by_path(self.view.root_node, ["Local Branches"])
        self.assertIsNotNone(local_branches_node)

        main_node = find_node_by_path(local_branches_node, ["main"])
        self.assertIsNotNone(main_node)
        self.assertIsInstance(main_node, BranchNode)
        self.assertEqual(main_node.branch_info.commit_hash, "c3")
        self.assertFalse(main_node.branch_info.is_current)

        develop_node = find_node_by_path(local_branches_node, ["develop"])
        self.assertIsNotNone(develop_node)
        self.assertIsInstance(develop_node, BranchNode)
        self.assertEqual(develop_node.branch_info.commit_hash, "c4")
        self.assertTrue(develop_node.branch_info.is_current) # head_ref is develop

    def test_build_tree_remote_branches(self):
        graph_data = self.get_scenario_remote_branches_data()
        self.view.set_commit_data(graph_data)

        remotes_node = find_node_by_path(self.view.root_node, ["Remotes"])
        self.assertIsNotNone(remotes_node)
        origin_node = find_node_by_path(remotes_node, ["origin"])
        self.assertIsNotNone(origin_node)
        self.assertIsInstance(origin_node, RemoteNode)

        origin_main_node = find_node_by_path(origin_node, ["main"]) # Find by display name "main"
        self.assertIsNotNone(origin_main_node)
        self.assertIsInstance(origin_main_node, BranchNode)
        self.assertEqual(origin_main_node.branch_info.name, "origin/main") # branch_info.name is full "origin/main"
        self.assertEqual(origin_main_node.display_name, "main") # display_name is short "main"
        self.assertFalse(origin_main_node.branch_info.is_local)
        self.assertEqual(origin_main_node.branch_info.commit_hash, "c3")

        origin_feature_x_node = find_node_by_path(origin_node, ["feature-x"]) # Find by display name "feature-x"
        self.assertIsNotNone(origin_feature_x_node)
        self.assertIsInstance(origin_feature_x_node, BranchNode)
        self.assertEqual(origin_feature_x_node.branch_info.name, "origin/feature-x") # branch_info.name is full "origin/feature-x"
        self.assertEqual(origin_feature_x_node.display_name, "feature-x") # display_name is short "feature-x"
        self.assertFalse(origin_feature_x_node.branch_info.is_local)
        self.assertEqual(origin_feature_x_node.branch_info.commit_hash, "c4")

    def test_build_tree_namespaced_branches(self):
        graph_data = self.get_scenario_namespaced_branches_data()
        self.view.set_commit_data(graph_data)

        local_branches_node = find_node_by_path(self.view.root_node, ["Local Branches"])
        self.assertIsNotNone(local_branches_node)

        feature_group_node = find_node_by_path(local_branches_node, ["feature"])
        self.assertIsNotNone(feature_group_node)
        self.assertIsInstance(feature_group_node, GroupNode)

        new_ux_node = find_node_by_path(feature_group_node, ["new-ux"])
        self.assertIsNotNone(new_ux_node)
        self.assertIsInstance(new_ux_node, BranchNode)
        self.assertEqual(new_ux_node.branch_info.name, "feature/new-ux") # Full name in info
        self.assertTrue(new_ux_node.branch_info.is_current)

        sidebar_node = find_node_by_path(feature_group_node, ["sidebar"])
        self.assertIsNotNone(sidebar_node)
        self.assertIsInstance(sidebar_node, BranchNode)
        self.assertEqual(sidebar_node.branch_info.name, "feature/sidebar")

        bugfix_group_node = find_node_by_path(local_branches_node, ["bugfix"])
        self.assertIsNotNone(bugfix_group_node)
        login_issue_node = find_node_by_path(bugfix_group_node, ["login-issue"])
        self.assertIsNotNone(login_issue_node)
        self.assertEqual(login_issue_node.branch_info.name, "bugfix/login-issue")


    # --- Tests for calculate_positions ---

    def test_positions_linear(self):
        graph_data = self.get_scenario_linear_data()
        self.view.set_commit_data(graph_data) # calculate_positions is called inside

        # Commit positions (Y based on reverse chronological index)
        self.assertEqual(self.view.commit_positions["c3"].y(), self.view.ROW_HEIGHT // 2 + 0 * self.view.ROW_HEIGHT)
        self.assertEqual(self.view.commit_positions["c2"].y(), self.view.ROW_HEIGHT // 2 + 1 * self.view.ROW_HEIGHT)
        self.assertEqual(self.view.commit_positions["c1"].y(), self.view.ROW_HEIGHT // 2 + 2 * self.view.ROW_HEIGHT)

        # All commits on 'main' should have same X from branch_x_lanes
        main_lane_x = self.view.branch_x_lanes.get("main")
        self.assertIsNotNone(main_lane_x)
        self.assertEqual(self.view.commit_positions["c3"].x(), main_lane_x)
        # c1 and c2 are not directly on main branch tip, their X might be default or based on 'main' if no other branch.
        # The current logic for X assignment in calculate_positions gives them main_lane_x
        # because 'main' is the only branch and it's the current branch.
        self.assertEqual(self.view.commit_positions["c2"].x(), main_lane_x)
        self.assertEqual(self.view.commit_positions["c1"].x(), main_lane_x)


        # Node positions (labels)
        local_branches_node = find_node_by_path(self.view.root_node, ["Local Branches"])
        main_branch_node = find_node_by_path(local_branches_node, ["main"])
        tags_node = find_node_by_path(self.view.root_node, ["Tags"])
        tag_v1_node = find_node_by_path(tags_node, ["v1.0"])

        self.assertIn(local_branches_node, self.view.node_positions)
        self.assertIn(main_branch_node, self.view.node_positions)
        self.assertIn(tags_node, self.view.node_positions)
        self.assertIn(tag_v1_node, self.view.node_positions)

        # Check Y order for labels (approximated)
        self.assertTrue(self.view.node_positions[local_branches_node].y() < self.view.node_positions[main_branch_node].y())
        self.assertTrue(self.view.node_positions[main_branch_node].y() < self.view.node_positions[tags_node].y())
        self.assertTrue(self.view.node_positions[tags_node].y() < self.view.node_positions[tag_v1_node].y())
        
        # Check X indentation for labels
        self.assertEqual(self.view.node_positions[local_branches_node].x(), self.view.COLUMN_WIDTH) # Level 0
        self.assertEqual(self.view.node_positions[main_branch_node].x(), self.view.COLUMN_WIDTH + self.view.COLUMN_WIDTH) # Level 1
        self.assertEqual(self.view.node_positions[tags_node].x(), self.view.COLUMN_WIDTH) # Level 0
        self.assertEqual(self.view.node_positions[tag_v1_node].x(), self.view.COLUMN_WIDTH + self.view.COLUMN_WIDTH) # Level 1


    def test_positions_fork(self):
        graph_data = self.get_scenario_fork_data()
        self.view.set_commit_data(graph_data)

        develop_lane_x = self.view.branch_x_lanes.get("develop")
        main_lane_x = self.view.branch_x_lanes.get("main")
        self.assertIsNotNone(develop_lane_x)
        self.assertIsNotNone(main_lane_x)
        self.assertNotEqual(develop_lane_x, main_lane_x)

        self.assertEqual(self.view.commit_positions["c4"].x(), develop_lane_x) # on develop
        self.assertEqual(self.view.commit_positions["c3"].x(), main_lane_x)    # on main
        
        # c2 is parent of both, should be on current branch (develop) lane due to fallback logic
        # or based on how it's associated. Current logic: head_ref is develop.
        # commit_branches for c2 is empty. Falls back to 'master' or default.
        # This highlights a need for better X for commits not on a current branch tip.
        # For now, let's assume it might get a default or the 'develop' lane if it's current.
        # The current logic for commit X position:
        # c2 has no branches. head_ref is "refs/heads/develop" (simple "develop").
        # "develop" is not in c2's branches. No local branches. No remote.
        # Fallback: self.branch_x_lanes.get("master", self.COLUMN_WIDTH)
        # Let's make "master" a default lane for testing this, or ensure "develop" is chosen if it's HEAD
        # The current code will use `self.branch_x_lanes.get("master", self.COLUMN_WIDTH)`
        # This could be improved in calculate_positions, but for now, test current behavior.
        # To make it predictable, if "master" is not in branch_x_lanes, it gets self.COLUMN_WIDTH.
        expected_c2_x = self.view.branch_x_lanes.get("master", self.view.COLUMN_WIDTH)
        if "develop" in self.view.branch_x_lanes and not graph_data["commits"][2].get("branches"): # If c2 has no branches
             # And develop is current HEAD, current logic might try to assign to develop's lane if it's the only context
             # However, the code explicitly checks if current_commit_branch_name in commit_branches.
             # So it will go to fallback.
             pass

        self.assertEqual(self.view.commit_positions["c2"].x(), expected_c2_x)


    # TODO: Add more scenarios for tree building and positions:
    # - Merge commits (parents list has 2 hashes)
    # - More complex remote branch structures (e.g. origin/feature/subfeature)
    # - Tags on merge commits, tags on branch tips
    # - Detached HEAD scenarios (head_ref is a commit hash or a tag ref)

# To run tests from command line if this file is executed:
# if __name__ == '__main__':
#    unittest.main()
