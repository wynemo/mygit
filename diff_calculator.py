import difflib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List


@dataclass
class InlineDiff:
    """行内差异数据类"""

    start: int  # 差异开始位置
    end: int  # 差异结束位置
    type: str  # 差异类型：'equal', 'insert', 'delete', 'replace'


@dataclass
class DiffChunk:
    """差异块数据类"""

    left_start: int
    left_end: int
    right_start: int
    right_end: int
    type: str  # 'equal', 'insert', 'delete', 'replace'
    inline_diffs: List[InlineDiff] = field(default_factory=list)  # 行内差异列表


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
        """使用 difflib 计算文本差异

        Args:
            left_text: 左侧文本
            right_text: 右侧文本

        Returns:
            包含行内差异的 DiffChunk 列表
        """
        left_lines = left_text.splitlines()
        right_lines = right_text.splitlines()

        matcher = difflib.SequenceMatcher(None, left_lines, right_lines)
        chunks = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            chunk = DiffChunk(left_start=i1, left_end=i2, right_start=j1, right_end=j2, type=tag, inline_diffs=[])

            # 对于替换类型的差异块，计算行内差异
            if tag == "replace" and i2 - i1 == j2 - j1:
                for left_line, right_line in zip(left_lines[i1:i2], right_lines[j1:j2], strict=False):
                    self._compute_inline_diff(left_line, right_line, chunk)

            chunks.append(chunk)

        return chunks

    def _compute_inline_diff(self, left_line: str, right_line: str, chunk: DiffChunk):
        """计算单行的行内差异

        Args:
            left_line: 左侧行文本
            right_line: 右侧行文本
            chunk: 要填充行内差异的 DiffChunk 对象
        """
        matcher = difflib.SequenceMatcher(None, left_line, right_line)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag != "equal":
                chunk.inline_diffs.append(InlineDiff(start=j1, end=j2, type=tag))

    def get_diff(self, left_text: str, right_text: str) -> dict:
        """获取文件差异（转换为 git_manager 格式）

        返回：
            {行号：修改类型} 的字典，修改类型为 "added", "modified", "deleted"
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
