# DAG图形化展示实现计划

## 项目背景

基于现有的CommitHistoryView和CustomTreeWidget实现，在列表视图中添加DAG（有向无环图）图形化展示功能，用于可视化Git提交的分支和合并关系。

## 技术分析

### 现有架构分析

#### CommitHistoryView结构
- 使用CustomTreeWidget作为主要列表组件
- 当前列结构：`["提交信息", "Branches", "作者", "日期"]`
- 支持分页加载和搜索过滤功能
- 集成GitGraphView但当前隐藏状态

#### CustomTreeWidget功能
- 继承自HoverRevealTreeWidget
- 支持悬停文本显示
- 集成Git操作上下文菜单
- 支持无限滚动加载

#### 数据流分析
```python
# 当前提交数据结构
commit = {
    "hash": "full_commit_hash",
    "message": "commit_message", 
    "author": "author_name",
    "date": "commit_date",
    "decorations": ["branch1", "tag1", ...]  # 分支和标签信息
}
```

## 实现方案

### 第1阶段：数据结构扩展

#### 1.1 扩展GitManager提交数据获取
- 修改`git_manager.py`中的`get_commit_history()`方法
- 添加父子关系信息获取：
```python
# 扩展后的数据结构
commit_data = {
    'hash': 'commit_hash',
    'message': 'commit_message',
    'author': 'author_name', 
    'date': 'commit_date',
    'decorations': [...],
    'parents': ['parent1_hash', 'parent2_hash'],  # 新增父提交信息
    'children': ['child1_hash', 'child2_hash'],   # 新增子提交信息
    'dag_info': {                                 # DAG布局信息
        'column': 2,                             # 所在列位置
        'color_index': 1,                        # 颜色索引
        'is_merge': True,                        # 是否为合并提交
        'is_branch_start': False,                # 是否为分支起点
        'connections': [...]                     # 连接路径信息
    }
}
```

#### 1.2 实现DAG布局算法
创建新文件`dag_layout_algorithm.py`：
```python
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
        pass
        
    def assign_columns(self, commits):
        """为每个提交分配列位置"""
        pass
        
    def calculate_connections(self, commits):
        """计算提交间的连接路径"""
        pass
```

### 第2阶段：自定义绘制实现

#### 2.1 创建DAG绘制委托
创建`dag_item_delegate.py`：
```python
from PyQt6.QtWidgets import QStyledItemDelegate
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QPen, QBrush

class DAGItemDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.colors = [
            '#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A',
            '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9'
        ]
    
    def paint(self, painter, option, index):
        """绘制DAG图形列"""
        if index.column() == 0:  # DAG图形列
            self.paint_dag_cell(painter, option, index)
        else:
            super().paint(painter, option, index)
    
    def paint_dag_cell(self, painter, option, index):
        """绘制DAG单元格内容"""
        dag_info = index.data(Qt.ItemDataRole.UserRole + 1)
        if not dag_info:
            return
            
        # 绘制连接线
        self.draw_connections(painter, option.rect, dag_info)
        
        # 绘制提交节点
        self.draw_commit_node(painter, option.rect, dag_info)
    
    def draw_connections(self, painter, rect, dag_info):
        """绘制分支连接线"""
        pass
    
    def draw_commit_node(self, painter, rect, dag_info):
        """绘制提交节点"""
        pass
```

#### 2.2 扩展CustomTreeWidget
在`custom_tree_widget.py`中添加DAG功能：
```python
class CustomTreeWidget(HoverRevealTreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # 现有代码...
        
        # 新增DAG功能
        self.dag_delegate = DAGItemDelegate(self)
        self.setItemDelegateForColumn(0, self.dag_delegate)  # DAG列使用自定义委托
        
    def setup_dag_column(self):
        """设置DAG图形列"""
        # 插入DAG列作为第一列
        header_labels = self.headerItem()
        current_labels = [header_labels.text(i) for i in range(header_labels.columnCount())]
        new_labels = ["DAG"] + current_labels
        self.setHeaderLabels(new_labels)
        
        # 设置DAG列宽度
        self.setColumnWidth(0, 100)  # DAG列宽度
```

### 第3阶段：布局算法核心实现

#### 3.1 分支跟踪算法
```python
def track_branches(self, commits):
    """跟踪分支的创建、合并和演变"""
    active_branches = {}  # 当前活跃的分支
    branch_columns = {}   # 分支到列的映射
    
    for commit in commits:
        # 处理合并提交
        if len(commit['parents']) > 1:
            self.handle_merge_commit(commit, active_branches, branch_columns)
        
        # 处理普通提交
        else:
            self.handle_regular_commit(commit, active_branches, branch_columns)
```

#### 3.2 连接路径计算
```python
def calculate_connection_paths(self, parent_commit, child_commit):
    """计算两个提交间的连接路径"""
    parent_col = parent_commit['dag_info']['column']
    child_col = child_commit['dag_info']['column']
    
    if parent_col == child_col:
        # 直线连接
        return [{'type': 'vertical', 'from': parent_col, 'to': child_col}]
    else:
        # 弯曲连接（用于分支合并）
        return [
            {'type': 'vertical', 'from': parent_col, 'to': parent_col},
            {'type': 'horizontal', 'from': parent_col, 'to': child_col},
            {'type': 'vertical', 'from': child_col, 'to': child_col}
        ]
```

### 第4阶段：集成和优化

#### 4.1 修改CommitHistoryView
在`commit_history_view.py`中集成DAG功能：
```python
def load_more_commits(self):
    """加载更多提交历史（修改版本）"""
    # 现有代码...
    
    # 计算DAG布局
    dag_algorithm = DAGLayoutAlgorithm()
    dag_layouts = dag_algorithm.calculate_layout(commits)
    
    for i, commit in enumerate(commits):
        item = QTreeWidgetItem(self.history_list)
        
        # DAG信息存储
        item.setData(0, Qt.ItemDataRole.UserRole + 1, dag_layouts[i])
        
        # 现有列数据（索引需要+1因为添加了DAG列）
        item.setData(1, Qt.ItemDataRole.UserRole, commit["hash"])
        item.setText(1, commit["message"])  # 提交信息列
        item.setText(2, decoration_text)    # 分支列  
        item.setText(3, commit["author"])   # 作者列
        item.setText(4, commit["date"])     # 日期列
```

#### 4.2 性能优化
```python
class OptimizedDAGDelegate(DAGItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.path_cache = {}  # 缓存连接路径
        self.visible_range = (0, 0)  # 可见范围
    
    def paint(self, painter, option, index):
        """优化的绘制方法"""
        # 只绘制可见区域
        if self.is_in_visible_range(index.row()):
            super().paint(painter, option, index)
```

## 技术要点

### 绘制技术细节

#### 节点绘制
```python
def draw_commit_node(self, painter, rect, dag_info):
    """绘制提交节点"""
    column = dag_info['column']
    color_index = dag_info['color_index']
    
    # 计算节点位置
    node_x = rect.x() + column * 20 + 10
    node_y = rect.center().y()
    
    # 设置颜色和样式
    color = self.colors[color_index % len(self.colors)]
    painter.setBrush(QBrush(QColor(color)))
    painter.setPen(QPen(Qt.black, 2))
    
    # 绘制节点
    if dag_info['is_merge']:
        # 合并节点：菱形
        painter.drawPolygon(self.create_diamond_polygon(node_x, node_y, 6))
    else:
        # 普通节点：圆形
        painter.drawEllipse(node_x - 4, node_y - 4, 8, 8)
```

#### 连接线绘制
```python
def draw_connections(self, painter, rect, dag_info):
    """绘制分支连接线"""
    painter.setRenderHint(QPainter.Antialiasing)
    
    for connection in dag_info['connections']:
        color = self.colors[connection['color_index']]
        painter.setPen(QPen(QColor(color), 2))
        
        if connection['type'] == 'vertical':
            # 绘制垂直线
            self.draw_vertical_line(painter, rect, connection)
        elif connection['type'] == 'curve':
            # 绘制弯曲线
            self.draw_curve_line(painter, rect, connection)
```

### 数据同步策略

#### 增量更新
```python
def update_dag_data(self, new_commits):
    """增量更新DAG数据"""
    # 只重新计算新增提交的布局
    # 保持现有提交的布局不变
    existing_layout = self.get_existing_layout()
    new_layout = self.calculate_incremental_layout(new_commits, existing_layout)
    self.merge_layouts(existing_layout, new_layout)
```

## 预期效果

### 视觉效果
1. **分支可视化**：不同分支用不同颜色的线条表示
2. **合并点标识**：合并提交使用菱形节点，普通提交使用圆形节点
3. **连接清晰**：分支间的连接关系一目了然
4. **风格统一**：与现有UI风格保持一致

### 功能特性
1. **交互支持**：点击DAG节点选择提交
2. **悬停提示**：鼠标悬停显示分支信息
3. **上下文菜单**：与现有Git操作菜单集成
4. **性能优化**：大型仓库下流畅的滚动和绘制

### 用户体验
1. **直观理解**：快速理解分支结构和合并历史
2. **导航便利**：通过图形化界面快速定位特定提交
3. **信息丰富**：在有限空间内展示最大化的版本控制信息

## 开发时间估算

### 详细分工
- **第1阶段（数据结构扩展）**：2-3天
  - GitManager扩展：1天
  - DAG算法设计：1-2天

- **第2阶段（绘制实现）**：2-3天  
  - 委托类实现：1-2天
  - TreeWidget集成：1天

- **第3阶段（算法实现）**：2天
  - 布局算法：1天
  - 路径计算：1天

- **第4阶段（集成优化）**：1-2天
  - CommitHistoryView修改：0.5天
  - 性能优化和测试：0.5-1.5天

### 总计：7-10天

## 风险评估

### 技术风险
1. **性能问题**：大型仓库可能导致绘制卡顿
   - **缓解措施**：实现可视区域绘制和路径缓存

2. **算法复杂性**：复杂的分支合并可能导致布局混乱
   - **缓解措施**：参考成熟Git工具的布局算法

### 兼容性风险
1. **现有功能影响**：修改可能影响现有列表功能
   - **缓解措施**：渐进式开发，保持向后兼容

## 后续扩展

### 可能的功能增强
1. **缩放功能**：支持DAG图形的缩放显示
2. **折叠功能**：支持分支的展开/折叠
3. **主题支持**：支持明暗主题切换
4. **导出功能**：支持将DAG图导出为图片

### 维护考虑
1. **代码模块化**：保持良好的代码结构便于维护
2. **单元测试**：为核心算法添加测试用例
3. **文档完善**：维护详细的API文档和使用说明