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
            chunk = DiffChunk(
                left_start=i1, left_end=i2, right_start=j1, right_end=j2, type=tag
            )
            chunks.append(chunk)

        return chunks


# todo 似乎这个用不到了，git diff，就直接用文本的差异来实现吧
class GitDiffCalculator(DiffCalculator):
    """基于 git diff 输出的差异计算器"""

    def __init__(self, git_diff_output: str = None):
        """初始化差异计算器

        Args:
            git_diff_output: git diff 命令的原始输出，如果提供则使用它来计算差异
        """
        self.git_diff_output = git_diff_output

    def compute_diff(self, left_text: str, right_text: str) -> List[DiffChunk]:
        """计算文本差异

        如果提供了 git_diff_output，则使用它来计算差异；
        否则回退到使用 difflib 计算差异。

        Args:
            left_text: 父提交的文件内容
            right_text: 当前提交的文件内容

        Returns:
            差异块列表
        """
        if self.git_diff_output:
            return self._parse_git_diff(self.git_diff_output)
        else:
            return self._compute_diff_with_difflib(left_text, right_text)

    def _compute_diff_with_difflib(
        self, left_text: str, right_text: str
    ) -> List[DiffChunk]:
        """使用 difflib 计算差异"""
        left_lines = left_text.splitlines()
        right_lines = right_text.splitlines()

        chunks = []
        matcher = difflib.SequenceMatcher(None, left_lines, right_lines)

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            diff_type = {
                "equal": "equal",
                "insert": "insert",
                "delete": "delete",
                "replace": "replace",
            }[tag]

            chunk = DiffChunk(
                left_start=i1, left_end=i2, right_start=j1, right_end=j2, type=diff_type
            )
            chunks.append(chunk)

        return chunks

    def _parse_git_diff(self, diff_output: str) -> List[DiffChunk]:
        """解析 git diff 输出

        Args:
            diff_output: git diff 命令的原始输出

        Returns:
            差异块列表
        """
        chunks = []
        current_chunk = None
        left_line = 0
        right_line = 0

        for line in diff_output.splitlines():
            if line.startswith("@@"):
                # 新的差异块开始
                if current_chunk:
                    chunks.append(current_chunk)

                # 解析块头信息
                # 格式如: @@ -1,3 +1,4 @@
                import re

                match = re.match(r"@@ -(\d+),?(\d+)? \+(\d+),?(\d+)? @@", line)
                if match:
                    left_start = int(match.group(1))
                    left_count = int(match.group(2) or 1)
                    right_start = int(match.group(3))
                    right_count = int(match.group(4) or 1)

                    current_chunk = DiffChunk(
                        left_start=left_start - 1,  # 转换为0-based索引
                        left_end=left_start + left_count - 1,
                        right_start=right_start - 1,
                        right_end=right_start + right_count - 1,
                        type="replace",  # 默认类型，后续会根据内容调整
                    )
                    left_line = left_start - 1
                    right_line = right_start - 1

            elif current_chunk and line.startswith(" "):
                # 未修改的行
                left_line += 1
                right_line += 1

            elif current_chunk and line.startswith("-"):
                # 删除的行
                if current_chunk.type == "replace":
                    current_chunk.type = "delete"
                left_line += 1

            elif current_chunk and line.startswith("+"):
                # 新增的行
                if current_chunk.type == "delete":
                    current_chunk.type = "replace"
                elif current_chunk.type == "equal":
                    current_chunk.type = "insert"
                right_line += 1

        # 添加最后一个块
        if current_chunk:
            chunks.append(current_chunk)

        return chunks
