import difflib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List


@dataclass
class DiffChunk:
    left_start: int
    left_end: int
    right_start: int
    right_end: int
    type: str  # 'equal', 'insert', 'delete', 'replace'


class DiffCalculator(ABC):
    """差异计算器基类"""

    @abstractmethod
    def compute_diff(self, left_text: str, right_text: str) -> List[DiffChunk]:
        """计算两个文本之间的差异

        Args:
            left_text: 左侧文本
            right_text: 右侧文本

        Returns:
            差异块列表
        """
        pass


class DifflibCalculator(DiffCalculator):
    """基于 difflib 的差异计算器"""

    def compute_diff(self, left_text: str, right_text: str) -> List[DiffChunk]:
        """使用 difflib 计算文本差异"""
        left_lines = left_text.splitlines()
        right_lines = right_text.splitlines()

        matcher = difflib.SequenceMatcher(None, left_lines, right_lines)
        chunks = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            chunk = DiffChunk(left_start=i1, left_end=i2, right_start=j1, right_end=j2, type=tag)
            chunks.append(chunk)

        return chunks

    def get_diff(self, left_text: str, right_text: str) -> dict:
        """获取文件差异（转换为git_manager格式）

        返回:
            {行号: 修改类型} 的字典，修改类型为 "added", "modified", "deleted"
        """
        chunks = self.compute_diff(left_text, right_text)
        diff_dict = {}

        for chunk in chunks:
            if chunk.type == "insert":
                # 新增行：行号范围 [right_start+1, right_end]
                for line in range(chunk.right_start, chunk.right_end):
                    diff_dict[line + 1] = "added"

            elif chunk.type == "delete":
                # 删除行：行号对应删除位置（使用新文件行号）
                # 删除发生在当前行号位置（新文件中的行号）
                diff_dict[chunk.right_start + 1] = "deleted"

            elif chunk.type == "replace":
                # 修改行：行号范围 [right_start+1, right_end]
                for line in range(chunk.right_start, chunk.right_end):
                    diff_dict[line + 1] = "modified"

        return diff_dict
