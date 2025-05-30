import unittest
from unittest.mock import patch, MagicMock
from PyQt6.QtCore import QPoint, QRect
from PyQt6.QtWidgets import QApplication, QTreeWidgetItem # Added QApplication, QTreeWidgetItem

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
    TagInfo,
    # Optional needed for type hint if NodeDescriptor.q_tree_widget_item type hinted
)
from typing import Optional # Added for Optional type hint

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


    @classmethod
    def setUpClass(cls):
        # QApplication is needed for QWidget-based tests, even if not showing UI
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    @classmethod
    def tearDownClass(cls):
        cls.app = None

    # --- Tests for calculate_positions ---

    def test_positions_linear(self):
        graph_data = self.get_scenario_linear_data()
        
        # Mocking visualItemRect and header properties
        mock_item_height = self.view.ROW_HEIGHT # Or any desired mock height
        mock_main_branch_item_y = 30 # Arbitrary Y for the main branch item in the tree
        
        # These mocks need to be active when set_commit_data -> calculate_positions is called
        # And when we access branch_name_to_node_map later.
        # So, call set_commit_data first to build the node structure and qitems
        self.view.set_commit_data(graph_data)

        main_branch_node = self.view.branch_name_to_node_map.get("main")
        self.assertIsNotNone(main_branch_node)
        self.assertIsNotNone(main_branch_node.q_tree_widget_item)

        mock_rects = {
            main_branch_node.q_tree_widget_item: QRect(0, mock_main_branch_item_y, 100, mock_item_height)
        }
        
        mock_header_size = 120

        def side_effect_visualItemRect(item):
            return mock_rects.get(item, QRect()) 

        # Patching before re-running calculate_positions (or make sure set_commit_data is within patch)
        # For simplicity, we can re-run calculate_positions after mocks are set if needed,
        # but set_commit_data already calls it. So, we need to patch before set_commit_data.
        # Let's re-structure: patch, then set_commit_data.

        with patch.object(self.view, 'visualItemRect', side_effect=side_effect_visualItemRect), \
             patch.object(self.view.header(), 'sectionSize', return_value=mock_header_size), \
             patch.object(self.view.header(), 'isVisible', return_value=True):
            
            # Re-call set_commit_data to ensure calculate_positions runs with mocks
            self.view.set_commit_data(graph_data) 

            # Y-coordinates for commits on 'main' should align with main_branch_node's item center
            expected_y_main = mock_main_branch_item_y + mock_item_height // 2
            
            # c3 is tip of main, should use main_qitem's Y
            self.assertEqual(self.view.commit_positions["c3"].y(), expected_y_main)
            # c1 and c2 are also on main by current logic, should also align if main is owning branch.
            # The owning branch logic will pick 'main' for c1, c2, c3.
            self.assertEqual(self.view.commit_positions["c2"].y(), expected_y_main)
            self.assertEqual(self.view.commit_positions["c1"].y(), expected_y_main)


            # X-coordinates
            expected_base_x = mock_header_size + self.view.GRAPH_X_OFFSET
            main_lane_x_offset = self.view.branch_x_lanes.get("main")
            self.assertIsNotNone(main_lane_x_offset)
            expected_x_main_commits = expected_base_x + main_lane_x_offset

            self.assertEqual(self.view.commit_positions["c3"].x(), expected_x_main_commits)
            self.assertEqual(self.view.commit_positions["c2"].x(), expected_x_main_commits)
            self.assertEqual(self.view.commit_positions["c1"].x(), expected_x_main_commits)


        # Assertions for self.view.node_positions for labels are removed as QTreeWidget handles them.

    def test_positions_linear_fallback_y(self):
        graph_data = self.get_scenario_linear_data()
        
        # Mock visualItemRect to return invalid QRect for main branch item
        # to test fallback Y logic (topo-level based)
        mock_header_size = 120

        with patch.object(self.view, 'visualItemRect', return_value=QRect()), \
             patch.object(self.view.header(), 'sectionSize', return_value=mock_header_size), \
             patch.object(self.view.header(), 'isVisible', return_value=True):
            
            self.view.set_commit_data(graph_data)

            # Y-coordinates should now use fallback (topo_level * ROW_HEIGHT + ROW_HEIGHT // 2)
            # c1: level 0, c2: level 1, c3: level 2 (based on current topo sort)
            # ROW_HEIGHT is 20
            self.assertEqual(self.view.commit_positions["c1"].y(), 0 * 20 + 20 // 2) # 10
            self.assertEqual(self.view.commit_positions["c2"].y(), 1 * 20 + 20 // 2) # 30
            self.assertEqual(self.view.commit_positions["c3"].y(), 2 * 20 + 20 // 2) # 50

            # X-coordinates should still be based on lanes
            expected_base_x = mock_header_size + self.view.GRAPH_X_OFFSET
            main_lane_x_offset = self.view.branch_x_lanes.get("main")
            self.assertIsNotNone(main_lane_x_offset)
            expected_x_main_commits = expected_base_x + main_lane_x_offset
            
            self.assertEqual(self.view.commit_positions["c3"].x(), expected_x_main_commits)
            self.assertEqual(self.view.commit_positions["c2"].x(), expected_x_main_commits)
            self.assertEqual(self.view.commit_positions["c1"].x(), expected_x_main_commits)


    def test_positions_fork(self):
        graph_data = self.get_scenario_fork_data()

        mock_item_height = self.view.ROW_HEIGHT
        mock_main_item_y = 30
        mock_develop_item_y = 50 
        mock_header_size = 120

        # Call set_commit_data once to build nodes and allow q_tree_widget_item access
        self.view.set_commit_data(graph_data) 
        
        main_branch_node = self.view.branch_name_to_node_map.get("main")
        develop_branch_node = self.view.branch_name_to_node_map.get("develop")
        self.assertIsNotNone(main_branch_node)
        self.assertIsNotNone(develop_branch_node)
        self.assertIsNotNone(main_branch_node.q_tree_widget_item)
        self.assertIsNotNone(develop_branch_node.q_tree_widget_item)

        mock_rects = {
            main_branch_node.q_tree_widget_item: QRect(0, mock_main_item_y, 100, mock_item_height),
            develop_branch_node.q_tree_widget_item: QRect(0, mock_develop_item_y, 100, mock_item_height)
        }
        def side_effect_visualItemRect(item):
            return mock_rects.get(item, QRect())

        with patch.object(self.view, 'visualItemRect', side_effect=side_effect_visualItemRect), \
             patch.object(self.view.header(), 'sectionSize', return_value=mock_header_size), \
             patch.object(self.view.header(), 'isVisible', return_value=True):
            
            # Re-run set_commit_data to apply mocks during calculate_positions
            self.view.set_commit_data(graph_data)

            expected_base_x = mock_header_size + self.view.GRAPH_X_OFFSET
            develop_lane_x_offset = self.view.branch_x_lanes.get("develop")
            main_lane_x_offset = self.view.branch_x_lanes.get("main")
            self.assertIsNotNone(develop_lane_x_offset)
            self.assertIsNotNone(main_lane_x_offset)
            self.assertNotEqual(develop_lane_x_offset, main_lane_x_offset)

            expected_x_develop = expected_base_x + develop_lane_x_offset
            expected_x_main = expected_base_x + main_lane_x_offset

            # Y-coordinates
            # c4 (develop tip) & c3 (main tip) should align with their respective mocked item centers
            self.assertEqual(self.view.commit_positions["c4"].y(), mock_develop_item_y + mock_item_height // 2)
            self.assertEqual(self.view.commit_positions["c3"].y(), mock_main_item_y + mock_item_height // 2)

            # X-coordinates
            self.assertEqual(self.view.commit_positions["c4"].x(), expected_x_develop)
            self.assertEqual(self.view.commit_positions["c3"].x(), expected_x_main)
            
            # c2 (common ancestor) - owning branch is 'develop' (current HEAD)
            self.assertEqual(self.view.commit_positions["c2"].x(), expected_x_develop)
            # Y for c2: 'develop' is owning branch.
            self.assertEqual(self.view.commit_positions["c2"].y(), mock_develop_item_y + mock_item_height // 2)

            # c1 (oldest) - owning branch is 'develop' (current HEAD, as c1 is ancestor of develop)
            self.assertEqual(self.view.commit_positions["c1"].x(), expected_x_develop)
             # Y for c1: 'develop' is owning branch.
            self.assertEqual(self.view.commit_positions["c1"].y(), mock_develop_item_y + mock_item_height // 2)

    def test_qtree_item_population_and_styling(self):
        graph_data = self.get_scenario_linear_data() # main is current
        self.view.set_commit_data(graph_data)

        # Check main branch
        main_node = self.view.branch_name_to_node_map.get("main")
        self.assertIsNotNone(main_node)
        self.assertIsNotNone(main_node.q_tree_widget_item)
        self.assertIsInstance(main_node.q_tree_widget_item, QTreeWidgetItem)
        self.assertEqual(main_node.q_tree_widget_item.text(0), main_node.display_name)
        self.assertTrue(main_node.q_tree_widget_item.font(0).bold()) # main is current
        
        expected_color_main = self.view._get_branch_color("main")
        self.assertEqual(main_node.q_tree_widget_item.foreground(0).color(), expected_color_main)

        # Check a tag
        tags_root_node = find_node_by_path(self.view.root_node, ["Tags"])
        tag_v1_node = find_node_by_path(tags_root_node, ["v1.0"]) # display_name is "v1.0"
        self.assertIsNotNone(tag_v1_node)
        self.assertIsInstance(tag_v1_node, TagNode)
        self.assertIsNotNone(tag_v1_node.q_tree_widget_item)
        self.assertIsInstance(tag_v1_node.q_tree_widget_item, QTreeWidgetItem)
        self.assertEqual(tag_v1_node.q_tree_widget_item.text(0), tag_v1_node.display_name)
        # Tags are not currently bolded unless they are also current branch (not possible for tags)
        # Tags don't have branch_colors, _populate_tree_items doesn't color them.

    # TODO: Add more scenarios for tree building and positions:
    # - Merge commits (parents list has 2 hashes)
    # - More complex remote branch structures (e.g. origin/feature/subfeature)
    # - Tags on merge commits, tags on branch tips
    # - Detached HEAD scenarios (head_ref is a commit hash or a tag ref)

# To run tests from command line if this file is executed:
# if __name__ == '__main__':
#    unittest.main()
