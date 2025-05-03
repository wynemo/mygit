from PyQt6.QtWidgets import QWidget, QVBoxLayout
from text_diff_viewer import DiffViewer, MergeDiffViewer
from diff_calculator import GitDiffCalculator

class CompareView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        
        self.diff_viewer = DiffViewer()
        self.merge_diff_viewer = MergeDiffViewer()
        self.merge_diff_viewer.hide()
        
        layout.addWidget(self.diff_viewer)
        layout.addWidget(self.merge_diff_viewer)
        
    def show_diff(self, git_manager, commit, file_path):
        """显示文件差异"""
        try:
            parents = commit.parents
            
            # 获取当前提交的文件内容
            try:
                current_content = (
                    commit.tree[file_path]
                    .data_stream.read()
                    .decode("utf-8", errors="replace")
                )
            except KeyError:
                current_content = ""
                
            # 获取父提交的文件内容
            parent_content = ""
            if parents:
                try:
                    parent_content = (
                        parents[0]
                        .tree[file_path]
                        .data_stream.read()
                        .decode("utf-8", errors="replace")
                    )
                except KeyError:
                    pass
                    
            # 根据父提交数量选择显示模式
            if len(parents) <= 1:
                self.diff_viewer.show()
                self.merge_diff_viewer.hide()
                self.diff_viewer.set_texts(parent_content, current_content)
            else:
                self.diff_viewer.hide()
                self.merge_diff_viewer.show()
                
                # 获取第二个父提交的内容
                parent2_content = ""
                try:
                    parent2_content = (
                        parents[1]
                        .tree[file_path]
                        .data_stream.read()
                        .decode("utf-8", errors="replace")
                    )
                except KeyError:
                    pass
                    
                self.merge_diff_viewer.set_texts(
                    parent_content, current_content, parent2_content
                )
                
        except Exception as e:
            print(f"Error displaying file diff: {e}") 