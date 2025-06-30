"""
文件索引管理器 - 提供高效的文件搜索索引和缓存机制
"""

import logging
import os
import threading
import time
from collections import defaultdict
from typing import Dict, List, Set

# 常量定义
MIN_SUBSTRING_LENGTH = 2


class TrieNode:
    """前缀树节点"""

    def __init__(self):
        self.children: Dict[str, "TrieNode"] = {}
        self.file_paths: Set[str] = set()  # 存储匹配此前缀的文件路径
        self.is_end = False


class FileIndexManager:
    """文件索引管理器 - 提供高效的文件搜索功能"""

    def __init__(self):
        self.index = {
            "files": {},  # 文件详情: {path: {name, relative_path, mtime}}
            "name_trie": TrieNode(),  # 文件名前缀树索引
            "path_trie": TrieNode(),  # 路径前缀树索引
            "fuzzy_map": defaultdict(set),  # 模糊匹配映射
            "last_updated": 0,  # 最后更新时间戳
            "is_building": False,  # 是否正在构建索引
        }
        self.search_cache = {}  # LRU缓存搜索结果
        self.cache_size = 100
        self._update_lock = threading.Lock()

    def add_file(self, file_path: str, base_path: str | None = None) -> None:
        """添加文件到索引"""
        if not os.path.isfile(file_path):
            return

        try:
            stat = os.stat(file_path)
            filename = os.path.basename(file_path)

            relative_path = os.path.relpath(file_path, base_path) if base_path else file_path

            # 更新文件详情
            self.index["files"][file_path] = {"name": filename, "relative_path": relative_path, "mtime": stat.st_mtime}

            # 添加到文件名前缀树
            self._add_to_trie(self.index["name_trie"], filename.lower(), file_path)

            # 添加到路径前缀树
            self._add_to_trie(self.index["path_trie"], relative_path.lower(), file_path)

            # 构建模糊匹配映射
            self._build_fuzzy_mapping(filename.lower(), file_path)

            self.index["last_updated"] = time.time()

            # 清空搜索缓存
            self.search_cache.clear()

        except (OSError, IOError):
            logging.exception("添加文件到索引时出错")

    def remove_file(self, file_path: str) -> None:
        """从索引中移除文件"""
        if file_path not in self.index["files"]:
            return

        try:
            file_info = self.index["files"][file_path]
            filename = file_info["name"]
            relative_path = file_info["relative_path"]

            # 从文件名前缀树移除
            self._remove_from_trie(self.index["name_trie"], filename.lower(), file_path)

            # 从路径前缀树移除
            self._remove_from_trie(self.index["path_trie"], relative_path.lower(), file_path)

            # 从模糊匹配映射移除
            self._remove_fuzzy_mapping(filename.lower(), file_path)

            # 删除文件记录
            del self.index["files"][file_path]

            self.index["last_updated"] = time.time()

            # 清空搜索缓存
            self.search_cache.clear()

        except Exception:
            logging.exception("从索引移除文件时出错")

    def update_file(self, file_path: str, base_path: str | None = None) -> None:
        """更新文件在索引中的信息"""
        if file_path in self.index["files"]:
            self.remove_file(file_path)
        self.add_file(file_path, base_path)

    def search_files(self, query: str, max_results: int = 50) -> List[str]:
        """多层次搜索策略"""
        if not query:
            return list(self.index["files"].keys())[:max_results]

        # 检查缓存
        cache_key = f"{query}_{max_results}"
        if cache_key in self.search_cache:
            return self.search_cache[cache_key]

        query_lower = query.lower()
        results = []

        # 1. 精确文件名前缀匹配（最高权重）
        exact_matches = self._search_by_prefix(query_lower, self.index["name_trie"])

        # 2. 路径前缀匹配（中等权重）
        path_matches = self._search_by_prefix(query_lower, self.index["path_trie"])

        # 3. 模糊匹配（最低权重）
        fuzzy_matches = self._fuzzy_search(query_lower)

        # 4. 智能排序和去重
        results = self._rank_and_dedupe(exact_matches, path_matches, fuzzy_matches, query_lower)

        # 限制结果数量
        results = results[:max_results]

        # 缓存结果
        self._cache_search_result(cache_key, results)

        return results

    def get_all_files(self) -> List[str]:
        """获取所有文件路径列表"""
        return list(self.index["files"].keys())

    def get_file_count(self) -> int:
        """获取索引中的文件数量"""
        return len(self.index["files"])

    def clear_index(self) -> None:
        """清空索引"""
        with self._update_lock:
            self.index = {
                "files": {},
                "name_trie": TrieNode(),
                "path_trie": TrieNode(),
                "fuzzy_map": defaultdict(set),
                "last_updated": 0,
                "is_building": False,
            }
            self.search_cache.clear()

    def clear(self) -> None:
        """清空所有索引数据（clear_index的别名）"""
        self.clear_index()

    def _add_to_trie(self, trie_root: TrieNode, text: str, file_path: str) -> None:
        """添加文本到前缀树"""
        node = trie_root
        for char in text:
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
            node.file_paths.add(file_path)
        node.is_end = True

    def _remove_from_trie(self, trie_root: TrieNode, text: str, file_path: str) -> None:
        """从前缀树移除文本"""

        def _remove_recursive(node: TrieNode, text: str, index: int) -> bool:
            if index == len(text):
                node.is_end = False
                node.file_paths.discard(file_path)
                return len(node.children) == 0 and not node.is_end and len(node.file_paths) == 0

            char = text[index]
            if char not in node.children:
                return False

            child_node = node.children[char]
            should_delete_child = _remove_recursive(child_node, text, index + 1)

            if should_delete_child:
                del node.children[char]

            child_node.file_paths.discard(file_path)

            return len(node.children) == 0 and not node.is_end and len(node.file_paths) == 0 and node != trie_root

        _remove_recursive(trie_root, text, 0)

    def _search_by_prefix(self, prefix: str, trie_root: TrieNode) -> Set[str]:
        """通过前缀搜索文件"""
        node = trie_root
        for char in prefix:
            if char not in node.children:
                return set()
            node = node.children[char]

        return node.file_paths.copy()

    def _build_fuzzy_mapping(self, filename: str, file_path: str) -> None:
        """构建模糊匹配映射"""
        # 为文件名的每个字符组合建立映射
        for i in range(len(filename)):
            for j in range(i + 1, min(i + 4, len(filename) + 1)):  # 限制子字符串长度
                substring = filename[i:j]
                if len(substring) >= MIN_SUBSTRING_LENGTH:  # 只索引长度>=2的子字符串
                    self.index["fuzzy_map"][substring].add(file_path)

    def _remove_fuzzy_mapping(self, filename: str, file_path: str) -> None:
        """移除模糊匹配映射"""
        for i in range(len(filename)):
            for j in range(i + 1, min(i + 4, len(filename) + 1)):
                substring = filename[i:j]
                if len(substring) >= MIN_SUBSTRING_LENGTH:
                    self.index["fuzzy_map"][substring].discard(file_path)
                    if not self.index["fuzzy_map"][substring]:
                        del self.index["fuzzy_map"][substring]

    def _fuzzy_search(self, query: str) -> Set[str]:
        """模糊搜索"""
        if len(query) < MIN_SUBSTRING_LENGTH:
            return set()

        matches = set()
        for i in range(len(query) - 1):
            substring = query[i : i + 2]
            if substring in self.index["fuzzy_map"]:
                if not matches:
                    matches = self.index["fuzzy_map"][substring].copy()
                else:
                    matches &= self.index["fuzzy_map"][substring]

        return matches

    def _rank_and_dedupe(
        self, exact_matches: Set[str], path_matches: Set[str], fuzzy_matches: Set[str], query: str
    ) -> List[str]:
        """智能排序和去重"""
        scored_files = []
        all_matches = exact_matches | path_matches | fuzzy_matches

        for file_path in all_matches:
            if file_path not in self.index["files"]:
                continue

            match_type = self._get_match_type(file_path, exact_matches, path_matches, fuzzy_matches)
            score = self._calculate_score(file_path, query, match_type)
            scored_files.append((score, file_path))

        # 按分数降序排序
        scored_files.sort(key=lambda x: x[0], reverse=True)

        return [file_path for _, file_path in scored_files]

    def _get_match_type(
        self, file_path: str, exact_matches: Set[str], path_matches: Set[str], fuzzy_matches: Set[str]
    ) -> str:
        """获取匹配类型"""
        if file_path in exact_matches:
            return "exact"
        elif file_path in path_matches:
            return "path"
        elif file_path in fuzzy_matches:
            return "fuzzy"
        return "unknown"

    def _calculate_score(self, file_path: str, query: str, match_type: str) -> float:
        """计算文件匹配分数"""
        score = 0.0

        # 匹配类型权重
        type_weights = {"exact": 100, "path": 80, "fuzzy": 60}
        score += type_weights.get(match_type, 0)

        # 文件名匹配优于路径匹配
        filename = os.path.basename(file_path).lower()
        if query in filename:
            score += 50

        # 查询在文件名开头的加权更高
        if filename.startswith(query):
            score += 30

        # 路径深度权重（浅层文件优先）
        depth = file_path.count(os.sep)
        score -= depth * 2

        # 最近修改时间权重
        file_info = self.index["files"].get(file_path, {})
        mtime = file_info.get("mtime", 0)
        age_bonus = max(0, 10 - (time.time() - mtime) / 86400)  # 10天内的文件有加分
        score += age_bonus

        return score

    def _cache_search_result(self, cache_key: str, results: List[str]) -> None:
        """缓存搜索结果"""
        if len(self.search_cache) >= self.cache_size:
            # 移除最旧的缓存项
            oldest_key = next(iter(self.search_cache))
            del self.search_cache[oldest_key]

        self.search_cache[cache_key] = results
