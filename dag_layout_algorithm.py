class DAGLayoutAlgorithm:
    def __init__(self):
        self.column_assignments = {}  # 分支到列的映射
        self.color_assignments = {}   # 分支到颜色的映射

    def calculate_layout(self, commits):
        """计算所有提交的DAG布局信息"""
        # 1. 分析分支结构
        # 2. 分配列位置
        # 3. 计算连接路径
        # 4. 分配颜色

        # Build children mapping
        children_map = {commit['hash']: [] for commit in commits}
        for commit in commits:
            for parent in commit['parents']:
                if parent in children_map:
                    children_map[parent].append(commit['hash'])

        for commit in commits:
            commit['children'] = children_map[commit['hash']]

        layouts = {}
        for commit in commits:
            layouts[commit['hash']] = {
                'column': 0,
                'color_index': 0,
                'is_merge': len(commit['parents']) > 1,
                'is_branch_start': False, # to be implemented
                'connections': [], # to be implemented
                'has_children': len(children_map[commit['hash']]) > 0
            }

        self.assign_columns(commits, layouts)
        self.calculate_connections(commits, layouts)

        return layouts

    def assign_columns(self, commits, layouts):
        """为每个提交分配列位置"""
        # This is a simplified column assignment. A more sophisticated
        # algorithm would be needed for complex branch structures.
        lanes = {}  # lane -> commit_hash
        commit_to_lane = {}

        for i, commit in enumerate(commits):
            # Find an available lane
            lane_idx = 0
            while lane_idx in lanes and lanes[lane_idx] is not None:
                # Check if the commit in the lane is a parent of the current commit
                # If so, we can't reuse this lane yet.
                if lanes[lane_idx] in commit['parents']:
                    lane_idx += 1
                    continue

                # Check if the commit in the lane has the current commit as a child.
                # If not, we can't reuse this lane.
                lane_commit = next((c for c in commits if c['hash'] == lanes[lane_idx]), None)
                if lane_commit and commit['hash'] not in lane_commit['children']:
                     # If the lane is occupied by a commit that is not a direct parent,
                     # and the current commit is not a child of it, we should look for another lane
                     # to avoid incorrect line drawing.
                     is_parent = False
                     for p_hash in commit['parents']:
                         if p_hash == lanes[lane_idx]:
                             is_parent = True
                             break
                     if not is_parent:
                        lane_idx += 1
                        continue

            lanes[lane_idx] = commit['hash']
            commit_to_lane[commit['hash']] = lane_idx
            layouts[commit['hash']]['column'] = lane_idx
            layouts[commit['hash']]['color_index'] = lane_idx

            # Free up lanes from parents that are now handled
            for parent_hash in commit['parents']:
                if parent_hash in commit_to_lane:
                    parent_lane = commit_to_lane[parent_hash]
                    parent_commit = next((c for c in commits if c['hash'] == parent_hash), None)
                    if parent_commit:
                        # Check if all children of the parent have been processed
                        all_children_processed = True
                        for child_hash in parent_commit['children']:
                            # Check if the child is in the processed part of the list
                            child_processed = any(c['hash'] == child_hash for c in commits[:i+1])
                            if not child_processed:
                                all_children_processed = False
                                break
                        if all_children_processed:
                            lanes[parent_lane] = None


    def calculate_connections(self, commits, layouts):
        """计算提交间的连接路径"""
        for commit in commits:
            commit_layout = layouts[commit['hash']]
            for parent_hash in commit['parents']:
                if parent_hash in layouts:
                    parent_layout = layouts[parent_hash]
                    connection = {
                        'from_col': parent_layout['column'],
                        'to_col': commit_layout['column'],
                        'color_index': parent_layout['color_index']
                    }
                    commit_layout['connections'].append(connection)
