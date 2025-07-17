# UnifiedDiffViewer 实现计划

## 概述
基于现有的 `text_diff_viewer.py` 中的 side-by-side diff viewer，创建一个统一的 diff 查看器，将左右两侧的内容合并在单个编辑器中显示。

## 分析结果

### 现有代码结构
- `DiffViewer` 类使用两个 `SyncedTextEdit` 实例并排显示
- 使用 `DiffCalculator` 计算差异块，`MultiHighlighter` 处理语法高亮
- 有 Previous/Next Change 导航功能
- 包含 `MergeDiffViewer` 用于三方合并查看

### 统一查看器需求（基于提供的图片）
- 单个编辑器窗格显示统一格式
- 行号格式：`"left_line_num right_line_num"` 用于未变更行
- 添加行：`"     right_line_num"` 绿色高亮
- 删除行：`"left_line_num     "` 灰色高亮
- 内容在行号后缩进显示
- 保持变更导航功能

## 实现计划

### 1. 创建 UnifiedDiffViewer 类
- 继承自 `QWidget`
- 使用单个 `SyncedTextEdit` 实例
- 复用现有的导航按钮布局
- 保持与 `DiffViewer` 相同的公共接口

```python
class UnifiedDiffViewer(QWidget):
    def __init__(self, diff_calculator: DiffCalculator | None = None):
        super().__init__()
        self.actual_diff_chunks = []
        self.current_diff_index = -1
        self.unified_line_mapping = {}  # 映射统一行号到原始行号
        self.setup_ui()
        self.diff_calculator = diff_calculator or DifflibCalculator()
```

### 2. 实现统一格式文本渲染
- 创建 `_format_unified_text()` 方法
- 处理不同类型的差异块（equal, insert, delete, replace）
- 生成正确的行号格式
- 创建行映射表用于导航

```python
def _format_unified_text(self, left_text: str, right_text: str) -> str:
    """将左右文本格式化为统一格式"""
    left_lines = left_text.splitlines()
    right_lines = right_text.splitlines()
    unified_lines = []
    self.unified_line_mapping = {}
    
    unified_line_num = 0
    
    for chunk in self.diff_chunks:
        if chunk.type == "equal":
            # 未变更行：显示左右行号
            for i in range(chunk.left_start, chunk.left_end):
                left_line_num = i + 1
                right_line_num = chunk.right_start + (i - chunk.left_start) + 1
                line_content = left_lines[i] if i < len(left_lines) else ""
                formatted_line = f"{left_line_num:>4} {right_line_num:>4}    {line_content}"
                unified_lines.append(formatted_line)
                self.unified_line_mapping[unified_line_num] = ('equal', chunk, i)
                unified_line_num += 1
                
        elif chunk.type == "delete":
            # 删除行：只显示左行号
            for i in range(chunk.left_start, chunk.left_end):
                left_line_num = i + 1
                line_content = left_lines[i] if i < len(left_lines) else ""
                formatted_line = f"{left_line_num:>4}         {line_content}"
                unified_lines.append(formatted_line)
                self.unified_line_mapping[unified_line_num] = ('delete', chunk, i)
                unified_line_num += 1
                
        elif chunk.type == "insert":
            # 添加行：只显示右行号
            for i in range(chunk.right_start, chunk.right_end):
                right_line_num = i + 1
                line_content = right_lines[i] if i < len(right_lines) else ""
                formatted_line = f"     {right_line_num:>4}    {line_content}"
                unified_lines.append(formatted_line)
                self.unified_line_mapping[unified_line_num] = ('insert', chunk, i)
                unified_line_num += 1
                
        elif chunk.type == "replace":
            # 替换：先显示删除的行，再显示添加的行
            for i in range(chunk.left_start, chunk.left_end):
                left_line_num = i + 1
                line_content = left_lines[i] if i < len(left_lines) else ""
                formatted_line = f"{left_line_num:>4}         {line_content}"
                unified_lines.append(formatted_line)
                self.unified_line_mapping[unified_line_num] = ('delete', chunk, i)
                unified_line_num += 1
                
            for i in range(chunk.right_start, chunk.right_end):
                right_line_num = i + 1
                line_content = right_lines[i] if i < len(right_lines) else ""
                formatted_line = f"     {right_line_num:>4}    {line_content}"
                unified_lines.append(formatted_line)
                self.unified_line_mapping[unified_line_num] = ('insert', chunk, i)
                unified_line_num += 1
    
    return "\n".join(unified_lines)
```

### 3. 实现统一查看器的语法高亮
- 创建 `UnifiedHighlighter` 类继承自 `MultiHighlighter`
- 处理统一格式的差异高亮（绿色添加，灰色删除）
- 保持原有的语法高亮功能
- 正确处理行号区域和内容区域的分离

```python
class UnifiedHighlighter(MultiHighlighter):
    def __init__(self, document, unified_line_mapping):
        super().__init__(document, "unified", None)
        self.unified_line_mapping = unified_line_mapping
        
    def highlightBlock(self, text):
        # 先应用语法高亮
        super().highlightBlock(text)
        
        # 再应用差异高亮
        block_number = self.currentBlock().blockNumber()
        if block_number in self.unified_line_mapping:
            line_type, chunk, original_line = self.unified_line_mapping[block_number]
            
            if line_type == 'insert':
                # 绿色背景用于添加行
                format = QTextCharFormat()
                format.setBackground(QColor(200, 255, 200))  # 浅绿色
                self.setFormat(0, len(text), format)
            elif line_type == 'delete':
                # 灰色背景用于删除行
                format = QTextCharFormat()
                format.setBackground(QColor(255, 200, 200))  # 浅红色
                self.setFormat(0, len(text), format)
```

### 4. 适配导航功能
- 修改 `_scroll_to_current_diff()` 方法适配统一格式
- 维护差异块到统一行的映射关系
- 保持 Previous/Next Change 按钮功能
- 正确高亮当前查看的差异

```python
def _scroll_to_current_diff(self):
    """滚动到当前差异位置"""
    if 0 <= self.current_diff_index < len(self.actual_diff_chunks):
        chunk = self.actual_diff_chunks[self.current_diff_index]
        
        # 找到该差异块在统一视图中的第一行
        target_line = -1
        for unified_line, (line_type, mapped_chunk, original_line) in self.unified_line_mapping.items():
            if mapped_chunk == chunk:
                target_line = unified_line
                break
        
        if target_line != -1:
            # 清除之前的高亮
            self.unified_edit.clear_highlighted_line()
            self.unified_edit.clear_block_background()
            
            # 设置新高亮
            self.unified_edit.set_highlighted_line(target_line)
            
            # 滚动到目标行
            self.unified_edit.scroll_to_line(target_line)
```

### 5. 完善UI和用户体验
- 设置合适的字体（等宽字体）
- 优化行号对齐
- 添加差异统计信息显示
- 支持文件路径和提交哈希显示

```python
def setup_ui(self):
    # 按钮布局
    button_layout = QHBoxLayout()
    self.prev_diff_button = QPushButton("Previous Change")
    self.next_diff_button = QPushButton("Next Change")
    self.prev_diff_button.setEnabled(False)
    self.next_diff_button.setEnabled(False)
    self.prev_diff_button.clicked.connect(self.navigate_to_previous_diff)
    self.next_diff_button.clicked.connect(self.navigate_to_next_diff)
    button_layout.addWidget(self.prev_diff_button)
    button_layout.addWidget(self.next_diff_button)
    
    # 统一编辑器
    self.unified_edit = SyncedTextEdit()
    self.unified_edit.setObjectName("unified_edit")
    self.unified_edit.setReadOnly(True)
    
    # 设置等宽字体
    font = QFont("Consolas", 10)
    font.setStyleHint(QFont.StyleHint.Monospace)
    self.unified_edit.setFont(font)
    
    # 主布局
    main_layout = QVBoxLayout()
    main_layout.addLayout(button_layout)
    main_layout.addWidget(self.unified_edit)
    self.setLayout(main_layout)
```

## 主要文件修改
- 在 `text_diff_viewer.py` 中添加 `UnifiedDiffViewer` 类
- 创建 `UnifiedHighlighter` 类
- 保持现有 `DiffViewer` 类不变以确保向后兼容

## 集成方式
- 可以作为 `DiffViewer` 的替代品使用
- 保持相同的公共接口：`set_texts()` 方法
- 支持相同的差异计算器和文件路径参数

## 预期效果
创建一个功能完整的统一 diff 查看器，提供：
- 清晰的统一格式差异显示
- 正确的语法高亮
- 流畅的导航体验
- 与现有代码的良好集成

## 注意事项
1. 确保行号格式与参考图片一致
2. 处理长行的显示和滚动
3. 优化大文件的性能
4. 测试各种边界情况（空文件、单行文件等）
5. 保持与现有UI风格的一致性

## 后续扩展
- 支持内联编辑功能
- 添加搜索和过滤功能
- 支持更多的差异显示选项
- 集成到主应用程序的界面中