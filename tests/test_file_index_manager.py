"""
文件索引管理器的单元测试
"""

import os
import tempfile
import unittest
from unittest.mock import patch

from utils.file_index_manager import FileIndexManager, TrieNode


class TestTrieNode(unittest.TestCase):
    """前缀树节点测试"""
    
    def test_trie_node_creation(self):
        """测试前缀树节点创建"""
        node = TrieNode()
        self.assertEqual(len(node.children), 0)
        self.assertEqual(len(node.file_paths), 0)
        self.assertFalse(node.is_end)
    
    def test_trie_node_children(self):
        """测试前缀树节点子节点"""
        node = TrieNode()
        node.children['a'] = TrieNode()
        self.assertIn('a', node.children)
        self.assertIsInstance(node.children['a'], TrieNode)


class TestFileIndexManager(unittest.TestCase):
    """文件索引管理器测试"""
    
    def setUp(self):
        """测试前准备"""
        self.manager = FileIndexManager()
        # 创建临时目录和文件用于测试
        self.temp_dir = tempfile.mkdtemp()
        self.test_files = []
        
        # 创建测试文件
        test_filenames = [
            'test.py',
            'main.js',
            'config.json',
            'readme.md',
            'utils.py'
        ]
        
        for filename in test_filenames:
            file_path = os.path.join(self.temp_dir, filename)
            with open(file_path, 'w') as f:
                f.write(f"# Test content for {filename}")
            self.test_files.append(file_path)
    
    def tearDown(self):
        """测试后清理"""
        # 清理临时文件
        for file_path in self.test_files:
            try:
                os.remove(file_path)
            except FileNotFoundError:
                pass
        try:
            os.rmdir(self.temp_dir)
        except OSError:
            pass
    
    def test_manager_initialization(self):
        """测试管理器初始化"""
        self.assertIsInstance(self.manager.index['files'], dict)
        self.assertIsInstance(self.manager.index['name_trie'], TrieNode)
        self.assertIsInstance(self.manager.index['path_trie'], TrieNode)
        self.assertIsInstance(self.manager.search_cache, dict)
        self.assertEqual(self.manager.cache_size, 100)
    
    def test_add_file(self):
        """测试添加文件到索引"""
        test_file = self.test_files[0]  # test.py
        self.manager.add_file(test_file, self.temp_dir)
        
        # 检查文件是否被添加到索引
        self.assertIn(test_file, self.manager.index['files'])
        
        # 检查文件信息
        file_info = self.manager.index['files'][test_file]
        self.assertEqual(file_info['name'], 'test.py')
        self.assertEqual(file_info['relative_path'], 'test.py')
        self.assertIsInstance(file_info['mtime'], float)
    
    def test_remove_file(self):
        """测试从索引中移除文件"""
        test_file = self.test_files[0]
        
        # 先添加文件
        self.manager.add_file(test_file, self.temp_dir)
        self.assertIn(test_file, self.manager.index['files'])
        
        # 移除文件
        self.manager.remove_file(test_file)
        self.assertNotIn(test_file, self.manager.index['files'])
    
    def test_update_file(self):
        """测试更新文件索引"""
        test_file = self.test_files[0]
        
        # 添加文件
        self.manager.add_file(test_file, self.temp_dir)
        self.assertIn(test_file, self.manager.index['files'])
        
        # 更新文件（这会重新读取文件信息）
        self.manager.update_file(test_file, self.temp_dir)
        
        # 检查文件仍在索引中
        self.assertIn(test_file, self.manager.index['files'])
    
    def test_search_exact_match(self):
        """测试精确文件名搜索"""
        # 添加测试文件到索引
        for file_path in self.test_files:
            self.manager.add_file(file_path, self.temp_dir)
        
        # 搜索 "test"
        results = self.manager.search_files("test")
        test_files = [f for f in results if 'test.py' in f]
        self.assertTrue(len(test_files) > 0)
    
    def test_search_prefix_match(self):
        """测试前缀匹配搜索"""
        # 添加测试文件到索引
        for file_path in self.test_files:
            self.manager.add_file(file_path, self.temp_dir)
        
        # 搜索 "te" (应该匹配 test.py)
        results = self.manager.search_files("te")
        test_files = [f for f in results if 'test.py' in f]
        self.assertTrue(len(test_files) > 0)
    
    def test_search_fuzzy_match(self):
        """测试模糊匹配搜索"""
        # 添加测试文件到索引
        for file_path in self.test_files:
            self.manager.add_file(file_path, self.temp_dir)
        
        # 搜索 "py" (应该匹配 .py 文件)
        results = self.manager.search_files("py")
        py_files = [f for f in results if f.endswith('.py')]
        self.assertTrue(len(py_files) >= 2)  # test.py 和 utils.py
    
    def test_search_cache(self):
        """测试搜索缓存机制"""
        # 添加测试文件到索引
        for file_path in self.test_files:
            self.manager.add_file(file_path, self.temp_dir)
        
        # 首次搜索
        query = "test"
        results1 = self.manager.search_files(query)
        
        # 检查缓存是否被创建
        cache_key = f"{query}_50"
        self.assertIn(cache_key, self.manager.search_cache)
        
        # 第二次搜索（应该从缓存获取）
        results2 = self.manager.search_files(query)
        self.assertEqual(results1, results2)
    
    def test_get_file_count(self):
        """测试获取文件数量"""
        self.assertEqual(self.manager.get_file_count(), 0)
        
        # 添加文件
        for file_path in self.test_files[:3]:
            self.manager.add_file(file_path, self.temp_dir)
        
        self.assertEqual(self.manager.get_file_count(), 3)
    
    def test_clear_index(self):
        """测试清空索引"""
        # 添加文件
        for file_path in self.test_files:
            self.manager.add_file(file_path, self.temp_dir)
        
        self.assertTrue(self.manager.get_file_count() > 0)
        
        # 清空索引
        self.manager.clear_index()
        self.assertEqual(self.manager.get_file_count(), 0)
        self.assertEqual(len(self.manager.search_cache), 0)
    
    def test_add_nonexistent_file(self):
        """测试添加不存在的文件"""
        nonexistent_file = os.path.join(self.temp_dir, "nonexistent.txt")
        
        # 添加不存在的文件应该不会出错，但也不会被添加到索引
        self.manager.add_file(nonexistent_file, self.temp_dir)
        self.assertNotIn(nonexistent_file, self.manager.index['files'])
    
    def test_empty_search(self):
        """测试空搜索查询"""
        # 添加测试文件到索引
        for file_path in self.test_files:
            self.manager.add_file(file_path, self.temp_dir)
        
        # 空搜索应该返回所有文件
        results = self.manager.search_files("")
        self.assertEqual(len(results), len(self.test_files))
        
        # None 搜索应该返回所有文件
        results = self.manager.search_files(None)
        self.assertEqual(len(results), len(self.test_files))


if __name__ == '__main__':
    unittest.main()