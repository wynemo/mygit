# dag_item_delegate.py

from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import QModelIndex, QRect, Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QWidget

from git_graph_data import CommitNode
from git_graph_items import COLOR_PALETTE
from git_graph_layout import calculate_commit_positions

if TYPE_CHECKING:
    from git_manager import GitManager


class DAGItemDelegate(QStyledItemDelegate):
    """
    自定义委托，用于在树形控件的第一列绘制 DAG 图形
    """
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.git_manager: Optional["GitManager"] = None
        self.commits_data: list[CommitNode] = []
        self.commit_positions: dict[str, tuple[int, int]] = {}  # sha -> (x, y)
        self.row_commit_map: dict[int, str] = {}  # row_index -> commit_sha
        
        # 绘制参数
        self.commit_radius = 4
        self.column_width = 15
        self.left_margin = 10
        
    def set_git_manager(self, git_manager: "GitManager"):
        """设置 Git 管理器"""
        self.git_manager = git_manager
        
    def update_commits_data(self, tree_widget):
        """从树形控件更新提交数据"""
        if not self.git_manager or not self.git_manager.repo:
            self.commits_data.clear()
            self.commit_positions.clear()
            self.row_commit_map.clear()
            return
            
        # 收集所有可见的提交信息
        commits = []
        self.row_commit_map.clear()
        
        for i in range(tree_widget.topLevelItemCount()):
            item = tree_widget.topLevelItem(i)
            if item and not item.isHidden():
                commit_hash = item.data(1, Qt.ItemDataRole.UserRole)
                if commit_hash:
                    # 创建 CommitNode
                    commit_node = CommitNode(
                        sha=commit_hash,
                        message=item.text(1),
                        author_name=item.text(3),
                        author_email="",
                        author_date=item.text(4)
                    )
                    
                    # 从 Git 仓库获取父提交信息和引用信息
                    try:
                        repo_commit = self.git_manager.repo.commit(commit_hash)
                        commit_node.parents = [parent.hexsha for parent in repo_commit.parents]
                        
                        # 获取引用信息（分支和标签）
                        refs = []
                        for ref in self.git_manager.repo.refs:
                            if ref.commit.hexsha == commit_hash:
                                refs.append(ref.name)
                        commit_node.references = refs
                        
                        print(f"提交 {commit_hash[:7]}: {len(commit_node.parents)} 个父提交, {len(refs)} 个引用")
                        
                    except Exception as e:
                        print(f"获取提交信息失败 {commit_hash[:7]}: {e}")
                        commit_node.parents = []
                    
                    commits.append(commit_node)
                    
                    # 记录行索引到提交的映射
                    visual_row = len([c for c in commits])  # 当前可见的行数
                    self.row_commit_map[visual_row - 1] = commit_hash
        
        # 建立子提交关系
        commits_map = {c.sha: c for c in commits}
        for commit in commits:
            for parent_sha in commit.parents:
                if parent_sha in commits_map:
                    commits_map[parent_sha].children.append(commit.sha)
        
        print(f"总共 {len(commits)} 个提交")
        
        # 计算布局
        if commits:
            calculate_commit_positions(commits)
            print("布局计算完成")
            for i, commit in enumerate(commits[:5]):  # 只打印前5个
                print(f"  {commit.sha[:7]}: column={commit.column}, color_idx={commit.color_idx}, parents={len(commit.parents)}")
            
        self.commits_data = commits
        self._calculate_positions()
        
    def _calculate_positions(self):
        """计算每个提交的绘制位置"""
        self.commit_positions.clear()
        
        for i, commit in enumerate(self.commits_data):
            # X 位置：根据分支列计算
            x = self.left_margin + commit.column * self.column_width
            
            # Y 位置：在行的中央
            y = 0  # 将在绘制时根据行高计算
            
            self.commit_positions[commit.sha] = (x, y)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        """绘制 DAG 图形"""
        # 如果不是第一列，使用默认绘制
        if index.column() != 0:
            super().paint(painter, option, index)
            return
            
        # 获取当前行对应的提交
        row = index.row()
        if row not in self.row_commit_map:
            super().paint(painter, option, index)
            return
            
        commit_sha = self.row_commit_map[row]
        if commit_sha not in self.commit_positions:
            super().paint(painter, option, index)
            return
            
        # 获取对应的提交数据
        commit_node = None
        for commit in self.commits_data:
            if commit.sha == commit_sha:
                commit_node = commit
                break
                
        if not commit_node:
            super().paint(painter, option, index)
            return
            
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 计算绘制区域
        rect = option.rect
        
        # 更新 Y 位置为行的中央
        pos_x, _ = self.commit_positions[commit_sha]
        pos_y = rect.center().y()
        
        # 绘制连接线
        self._draw_edges_for_commit(painter, commit_node, pos_x, pos_y, rect)
        
        # 绘制提交圆圈
        self._draw_commit_circle(painter, commit_node, pos_x, pos_y)
        
        painter.restore()

    def _draw_edges_for_commit(self, painter: QPainter, commit_node: CommitNode, 
                              pos_x: int, pos_y: int, rect: QRect):
        """绘制当前提交的连接线"""
        row_height = rect.height()
        
        # 为每个父提交绘制连接线
        for parent_sha in commit_node.parents:
            if parent_sha not in self.commit_positions:
                continue
                
            parent_pos_x, _ = self.commit_positions[parent_sha]
            
            # 查找父提交在可见行中的位置
            parent_row = -1
            current_row = -1
            
            for row_idx, sha in self.row_commit_map.items():
                if sha == parent_sha:
                    parent_row = row_idx
                elif sha == commit_node.sha:
                    current_row = row_idx
                    
            if parent_row >= 0 and current_row >= 0:
                # 计算父提交的实际 Y 位置
                parent_pos_y = pos_y + (parent_row - current_row) * row_height
                
                # 确定线条颜色 - 使用子提交的颜色
                color_idx = (
                    commit_node.branch_color_idx if commit_node.branch_color_idx is not None 
                    else commit_node.color_idx
                )
                color = COLOR_PALETTE[color_idx % len(COLOR_PALETTE)]
                pen = QPen(color, 1.5)
                painter.setPen(pen)
                
                # 如果父子在同一列，直接绘制直线
                if abs(parent_pos_x - pos_x) < 5:  # 基本在同一列
                    painter.drawLine(int(pos_x), int(pos_y), int(parent_pos_x), int(parent_pos_y))
                else:
                    # 如果在不同列，绘制弯曲线（简单的折线）
                    mid_y = pos_y + (parent_pos_y - pos_y) / 2
                    
                    # 先向上到中点
                    painter.drawLine(int(pos_x), int(pos_y), int(pos_x), int(mid_y))
                    # 然后水平连接
                    painter.drawLine(int(pos_x), int(mid_y), int(parent_pos_x), int(mid_y))
                    # 最后到父提交
                    painter.drawLine(int(parent_pos_x), int(mid_y), int(parent_pos_x), int(parent_pos_y))

    def _draw_commit_circle(self, painter: QPainter, commit_node: CommitNode, 
                           pos_x: int, pos_y: int):
        """绘制提交圆圈"""
        # 确定圆圈颜色
        color_idx = (
            commit_node.branch_color_idx if commit_node.branch_color_idx is not None 
            else commit_node.color_idx
        )
        color = COLOR_PALETTE[color_idx % len(COLOR_PALETTE)]
        
        # 绘制圆圈
        painter.setBrush(color)
        painter.setPen(QPen(QColor(0, 0, 0), 1))
        painter.drawEllipse(
            pos_x - self.commit_radius,
            pos_y - self.commit_radius,
            self.commit_radius * 2,
            self.commit_radius * 2
        )