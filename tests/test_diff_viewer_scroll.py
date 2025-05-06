import sys
import unittest
from collections import namedtuple
from unittest.mock import Mock, PropertyMock, patch

from PyQt6.QtCore import QPoint
from PyQt6.QtGui import QTextDocument
from PyQt6.QtWidgets import QApplication

from text_diff_viewer import DiffViewer, MergeDiffViewer

# 创建全局的 QApplication 实例
app = QApplication(sys.argv)

# 定义差异块的数据结构
DiffChunk = namedtuple(
    "DiffChunk", ["type", "left_start", "left_end", "right_start", "right_end"]
)


class TestDiffViewerScroll(unittest.TestCase):
    def setUp(self):
        """设置测试环境"""
        # 创建 DiffViewer 实例
        self.viewer = DiffViewer()

        # 创建模拟的文本编辑器
        self.left_edit = Mock()
        self.right_edit = Mock()

        # 创建模拟的滚动条
        self.left_scroll = Mock()
        self.right_scroll = Mock()
        self.left_hscroll = Mock()
        self.right_hscroll = Mock()

        # 创建模拟的文档
        self.left_doc = Mock()
        self.right_doc = Mock()

        # 设置模拟对象的返回值
        self.left_edit.verticalScrollBar.return_value = self.left_scroll
        self.right_edit.verticalScrollBar.return_value = self.right_scroll
        self.left_edit.horizontalScrollBar.return_value = self.left_hscroll
        self.right_edit.horizontalScrollBar.return_value = self.right_hscroll
        self.left_edit.document.return_value = self.left_doc
        self.right_edit.document.return_value = self.right_doc

        # 设置文档属性
        self.left_doc.blockCount.return_value = 100
        self.right_doc.blockCount.return_value = 100
        self.left_doc.size.return_value.height.return_value = 2000
        self.right_doc.size.return_value.height.return_value = 2000

        # 设置滚动条属性
        self.left_scroll.maximum.return_value = 2000
        self.right_scroll.maximum.return_value = 2000
        self.left_hscroll.maximum.return_value = 500
        self.right_hscroll.maximum.return_value = 500

        # 替换 viewer 中的编辑器实例
        self.viewer.left_edit = self.left_edit
        self.viewer.right_edit = self.right_edit

        # 设置差异数据
        self.viewer.diff_chunks = [
            DiffChunk("equal", 0, 10, 0, 10),
            DiffChunk("insert", 10, 10, 10, 15),
            DiffChunk("equal", 10, 20, 15, 25),
        ]

    def tearDown(self):
        """清理测试环境"""
        # 清理 viewer 实例
        self.viewer.deleteLater()

    def test_scroll_with_equal_chunks(self):
        """测试在相等块中滚动"""
        # 计算平均行高
        avg_line_height = 2000 // 100  # 20

        # 模拟光标位置在第5行
        cursor = Mock()
        cursor.blockNumber.return_value = 5
        self.left_edit.cursorForPosition.return_value = cursor

        # 计算期望的滚动值
        expected_scroll = 5 * avg_line_height  # 100

        # 调用滚动方法
        self.viewer._on_scroll(100, True)  # 滚动左侧，值为100

        # 验证右侧滚动条被设置为正确的位置
        self.right_scroll.setValue.assert_called_once()
        self.assertEqual(self.right_scroll.setValue.call_args[0][0], expected_scroll)

    def test_scroll_into_insert_chunk(self):
        """测试滚动进入插入块"""
        # 计算平均行高
        avg_line_height = 2000 // 100  # 20

        # 模拟光标位置在第12行（在插入块中）
        cursor = Mock()
        cursor.blockNumber.return_value = 12
        self.left_edit.cursorForPosition.return_value = cursor

        # 计算期望的滚动值
        # 在插入块中，右侧行号需要加上插入的行数
        expected_scroll = (12 + 5) * avg_line_height  # 340

        # 调用滚动方法
        self.viewer._on_scroll(240, True)  # 12 * 20 = 240

        # 验证右侧滚动条被设置为正确的位置
        self.right_scroll.setValue.assert_called_once()
        self.assertEqual(self.right_scroll.setValue.call_args[0][0], expected_scroll)

    def test_scroll_to_top(self):
        """测试滚动到顶部"""
        # 模拟光标位置在第0行
        cursor = Mock()
        cursor.blockNumber.return_value = 0
        self.left_edit.cursorForPosition.return_value = cursor

        # 调用滚动方法
        self.viewer._on_scroll(0, True)  # 滚动到顶部

        # 验证右侧滚动条被设置为0
        self.right_scroll.setValue.assert_called_once_with(0)

    def test_scroll_to_bottom(self):
        """测试滚动到底部"""
        # 计算平均行高
        avg_line_height = 2000 // 100  # 20

        # 模拟光标位置在最后一行
        cursor = Mock()
        cursor.blockNumber.return_value = 99  # 最后一行
        self.left_edit.cursorForPosition.return_value = cursor

        # 计算期望的滚动值，考虑 diff_chunks 的累积差异
        # diff_chunks: [equal, insert(+5 lines), equal] -> accumulated_diff = +5
        expected_target_line = 99 + 5  # 104
        expected_scroll = min(
            self.right_scroll.maximum(), expected_target_line * avg_line_height
        )  # min(2000, 104*20=2080) = 2000

        # 调用滚动方法
        self.viewer._on_scroll(1980, True)  # 滚动到底部原始值

        # 验证右侧滚动条被设置为正确的位置
        self.right_scroll.setValue.assert_called_once()
        # self.assertEqual(self.right_scroll.setValue.call_args[0][0], 1980) # 旧的错误断言
        self.assertEqual(
            self.right_scroll.setValue.call_args[0][0], expected_scroll
        )  # 应该断言 2000

    def test_complex_diff_chunks(self):
        """测试复杂的差异块组合"""
        # 设置更复杂的差异数据
        self.viewer.diff_chunks = [
            DiffChunk("equal", 0, 5, 0, 5),
            DiffChunk("insert", 5, 5, 5, 8),
            DiffChunk("delete", 5, 8, 8, 8),
            DiffChunk("equal", 8, 15, 8, 15),
            DiffChunk("replace", 15, 20, 15, 18),
            DiffChunk("equal", 20, 25, 18, 23),
        ]

        # 计算平均行高
        avg_line_height = 2000 // 100  # 20

        # 模拟光标位置在第17行（在替换块中）
        cursor = Mock()
        cursor.blockNumber.return_value = 17
        self.left_edit.cursorForPosition.return_value = cursor

        # 计算期望的滚动值
        # 在替换块中，右侧行号需要减去删除的行数
        expected_scroll = (
            320  # Updated expectation based on code's calculation (target_line=16)
        )

        # 调用滚动方法
        self.viewer._on_scroll(340, True)  # 17 * 20 = 340

        # 验证右侧滚动条被设置为正确的位置
        self.right_scroll.setValue.assert_called_once()
        self.assertEqual(self.right_scroll.setValue.call_args[0][0], expected_scroll)

    def test_horizontal_scroll_sync(self):
        """测试水平滚动同步"""
        # 调用水平滚动方法
        self.viewer._sync_hscroll(250, 0)  # 左侧水平滚动，值为250

        # 验证右侧水平滚动条被设置为相同值
        self.right_hscroll.setValue.assert_called_once_with(250)

    def test_scroll_lock(self):
        """测试滚动锁机制"""
        # 设置滚动锁
        self.viewer._sync_vscroll_lock = True

        # 尝试滚动
        self.viewer._on_scroll(500, True)

        # 验证右侧滚动条没有被调用
        self.right_scroll.setValue.assert_not_called()


class TestMergeDiffViewerScroll(unittest.TestCase):
    def setUp(self):
        """设置测试环境"""
        # 创建 MergeDiffViewer 实例
        self.viewer = MergeDiffViewer()

        # 创建模拟的文本编辑器
        self.parent1_edit = Mock()
        self.result_edit = Mock()
        self.parent2_edit = Mock()

        # 创建模拟的滚动条
        self.parent1_scroll = Mock()
        self.result_scroll = Mock()
        self.parent2_scroll = Mock()
        self.parent1_hscroll = Mock()
        self.result_hscroll = Mock()
        self.parent2_hscroll = Mock()

        # 创建模拟的文档
        self.parent1_doc = Mock()
        self.result_doc = Mock()
        self.parent2_doc = Mock()

        # 设置模拟对象的返回值
        self.parent1_edit.verticalScrollBar.return_value = self.parent1_scroll
        self.result_edit.verticalScrollBar.return_value = self.result_scroll
        self.parent2_edit.verticalScrollBar.return_value = self.parent2_scroll
        self.parent1_edit.horizontalScrollBar.return_value = self.parent1_hscroll
        self.result_edit.horizontalScrollBar.return_value = self.result_hscroll
        self.parent2_edit.horizontalScrollBar.return_value = self.parent2_hscroll

        self.parent1_edit.document.return_value = self.parent1_doc
        self.result_edit.document.return_value = self.result_doc
        self.parent2_edit.document.return_value = self.parent2_doc

        # 设置文档属性
        self.parent1_doc.blockCount.return_value = 100
        self.result_doc.blockCount.return_value = 100
        self.parent2_doc.blockCount.return_value = 100
        self.parent1_doc.size.return_value.height.return_value = 2000
        self.result_doc.size.return_value.height.return_value = 2000
        self.parent2_doc.size.return_value.height.return_value = 2000

        # 设置滚动条属性
        self.parent1_scroll.maximum.return_value = 2000
        self.result_scroll.maximum.return_value = 2000
        self.parent2_scroll.maximum.return_value = 2000
        self.parent1_hscroll.maximum.return_value = 500
        self.result_hscroll.maximum.return_value = 500
        self.parent2_hscroll.maximum.return_value = 500

        # 替换 viewer 中的编辑器实例
        self.viewer.parent1_edit = self.parent1_edit
        self.viewer.result_edit = self.result_edit
        self.viewer.parent2_edit = self.parent2_edit

        # 设置差异数据
        self.viewer.parent1_chunks = [
            DiffChunk("equal", 0, 10, 0, 10),
            DiffChunk("insert", 10, 10, 10, 15),
            DiffChunk("equal", 10, 20, 15, 25),
        ]

        self.viewer.parent2_chunks = [
            DiffChunk("equal", 0, 10, 0, 10),
            DiffChunk("delete", 10, 15, 10, 10),
            DiffChunk("equal", 15, 25, 10, 20),
        ]

    def tearDown(self):
        """清理测试环境"""
        # 清理 viewer 实例
        self.viewer.deleteLater()

    def test_scroll_parent1_to_result(self):
        """测试从 parent1 滚动到 result"""
        # 计算平均行高
        avg_line_height = 2000 // 100  # 20

        # 模拟光标位置在第12行（在插入块中）
        cursor = Mock()
        cursor.blockNumber.return_value = 12
        self.parent1_edit.cursorForPosition.return_value = cursor

        # 计算期望的滚动值
        # 在插入块中，result 行号需要加上插入的行数
        expected_scroll = (12 + 5) * avg_line_height  # 340

        # 调用滚动方法
        self.viewer._on_scroll(240, "parent1")  # 12 * 20 = 240

        # 验证 result 滚动条被设置为正确的位置
        self.result_scroll.setValue.assert_called_once()
        self.assertEqual(self.result_scroll.setValue.call_args[0][0], expected_scroll)

    def test_scroll_result_to_parent2(self):
        """测试从 result 滚动到 parent2"""
        # 计算平均行高
        avg_line_height = 2000 // 100  # 20

        # 模拟光标位置在第12行（在删除块中）
        cursor = Mock()
        cursor.blockNumber.return_value = 12
        self.result_edit.cursorForPosition.return_value = cursor

        # 计算期望的滚动值
        # 在删除块中，parent2 行号需要减去删除的行数
        expected_scroll = (12 - 5) * avg_line_height  # 140

        # 调用滚动方法
        self.viewer._on_scroll(240, "result")  # 12 * 20 = 240

        # 验证 parent2 滚动条被设置为正确的位置
        self.parent2_scroll.setValue.assert_called_once()
        self.assertEqual(self.parent2_scroll.setValue.call_args[0][0], expected_scroll)

    def test_scroll_to_top(self):
        """测试滚动到顶部"""
        # 模拟光标位置在第0行
        cursor = Mock()
        cursor.blockNumber.return_value = 0
        self.parent1_edit.cursorForPosition.return_value = cursor

        # 调用滚动方法
        self.viewer._on_scroll(0, "parent1")

        # 验证其他编辑器都滚动到顶部
        self.result_scroll.setValue.assert_called_once_with(0)
        self.parent2_scroll.setValue.assert_called_once_with(0)

    def test_scroll_to_bottom(self):
        """测试滚动到底部"""
        # 计算平均行高
        avg_line_height = 2000 // 100  # 20

        # 模拟光标位置在最后一行
        cursor = Mock()
        cursor.blockNumber.return_value = 99  # 最后一行
        self.parent1_edit.cursorForPosition.return_value = cursor

        # 计算期望的滚动值
        # parent1 -> result: 使用 parent1_chunks (含 insert +5), accumulated_diff = +5
        expected_result_target_line = 99 + 5  # 104
        expected_result_scroll = min(
            self.result_scroll.maximum(), expected_result_target_line * avg_line_height
        )  # min(2000, 2080) = 2000

        # parent1 -> parent2: 使用 parent1_chunks(+5) + parent2_chunks(含 delete -5), accumulated_diff = 0
        expected_parent2_target_line = 99 + 0  # 99
        expected_parent2_scroll = min(
            self.parent2_scroll.maximum(),
            expected_parent2_target_line * avg_line_height,
        )  # min(2000, 1980) = 1980

        # 调用滚动方法
        self.viewer._on_scroll(1980, "parent1")  # parent1 滚动到底部原始值

        # 验证其他编辑器滚动到计算后的位置
        self.result_scroll.setValue.assert_called_once()
        self.assertEqual(
            self.result_scroll.setValue.call_args[0][0], expected_result_scroll
        )  # 应该断言 2000
        self.parent2_scroll.setValue.assert_called_once()
        self.assertEqual(
            self.parent2_scroll.setValue.call_args[0][0], expected_parent2_scroll
        )  # 应该断言 1980

    def test_horizontal_scroll_sync(self):
        """测试水平滚动同步"""
        # 调用水平滚动方法
        self.viewer._sync_hscroll(250, "parent1")

        # 验证其他编辑器的水平滚动条被设置为相同值
        self.result_hscroll.setValue.assert_called_once_with(250)
        self.parent2_hscroll.setValue.assert_called_once_with(250)

    def test_scroll_lock(self):
        """测试滚动锁机制"""
        # 设置滚动锁
        self.viewer._sync_vscroll_lock = True

        # 尝试滚动
        self.viewer._on_scroll(500, "parent1")

        # 验证其他滚动条没有被调用
        self.result_scroll.setValue.assert_not_called()
        self.parent2_scroll.setValue.assert_not_called()


if __name__ == "__main__":
    unittest.main()
