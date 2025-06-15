import os
import tempfile
import unittest

from ripgrepy import Ripgrepy


class TestRipgrepyFeatures(unittest.TestCase):
    def setUp(self):
        # 创建临时目录
        self.temp_dir = tempfile.mkdtemp()
        # 创建测试文件
        self.test_file = os.path.join(self.temp_dir, "test.txt")
        with open(self.test_file, "w") as f:
            f.write("apple\napplesauce\nPython python PYTHON\n123-4567")
        # 创建排除文件夹
        self.excluded_dir = os.path.join(self.temp_dir, "excluded_dir")
        os.makedirs(self.excluded_dir)
        with open(os.path.join(self.excluded_dir, "excluded.txt"), "w") as f:
            f.write("This file should be excluded.")

    def tearDown(self):
        # 清理临时目录
        for root, dirs, files in os.walk(self.temp_dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(self.temp_dir)

    def test_exclude_folder(self):
        # 测试排除文件夹功能
        print("------------- excluded_dir", os.path.basename(self.excluded_dir))
        results = Ripgrepy(".", path=self.temp_dir).glob(f"!{os.path.basename(self.excluded_dir)}/").run()
        self.assertNotIn("excluded.txt", str(results))

    def test_whole_words(self):
        # 测试全词匹配功能（使用 word_regexp() 方法）
        results = Ripgrepy("apple", path=self.temp_dir).word_regexp().run()
        self.assertNotIn("applesauce", str(results))
        results = Ripgrepy("applesauce", path=self.temp_dir).word_regexp().run()
        self.assertIn("applesauce", str(results))

    def test_ignore_case(self):
        # 测试忽略大小写功能（使用 ignore_case() 方法）
        results = Ripgrepy("python", path=self.temp_dir).ignore_case().run()
        self.assertIn("Python", str(results))
        self.assertIn("python", str(results))
        self.assertIn("PYTHON", str(results))

    def test_regex_search(self):
        # 测试正则表达式搜索功能
        results = Ripgrepy(r"\d{3}-\d{4}", path=self.temp_dir).run()
        self.assertIn("123-4567", str(results))


if __name__ == "__main__":
    unittest.main()
