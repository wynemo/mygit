import json
import os
from pathlib import Path

from PyQt6.QtGui import QColor


class Settings:
    def __init__(self):
        # 获取用户主目录
        home = str(Path.home())
        # 创建配置目录
        self.config_dir = os.path.join(home, ".git_manager")
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)

        # 配置文件路径
        self.config_file = os.path.join(self.config_dir, "settings.json")

        # 默认设置
        self.settings = {
            "recent_folders": [],  # 最近打开的文件夹列表
            "last_folder": None,  # 上次打开的文件夹
            "max_recent": 10,  # 最大记录数
            "font_family": "Courier New",  # 默认字体
            "font_size": 12,  # 默认字体大小
            "code_style": "friendly",  # 代码风格设置
        }

        # 加载已有设置
        self.load_settings()

    def load_settings(self):
        """加载设置"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r", encoding="utf-8") as f:
                    saved_settings = json.load(f)
                    self.settings.update(saved_settings)
        except Exception as e:
            print(f"加载设置失败：{e!s}")

    def save_settings(self):
        """保存设置"""
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存设置失败：{e!s}")

    def add_recent_folder(self, folder_path):
        """添加最近打开的文件夹"""
        # 更新最后打开的文件夹
        self.settings["last_folder"] = folder_path

        # 更新最近文件夹列表
        recent = self.settings["recent_folders"]

        # 如果已经在列表中，先移除
        if folder_path in recent:
            recent.remove(folder_path)

        # 添加到列表开头
        recent.insert(0, folder_path)

        # 保持列表在最大长度以内
        self.settings["recent_folders"] = recent[: self.settings["max_recent"]]

        # 保存设置
        self.save_settings()

    def get_recent_folders(self):
        """获取最近文件夹列表"""
        return self.settings["recent_folders"]

    def get_last_folder(self):
        """获取上次打开的文件夹"""
        return self.settings["last_folder"]

    def get_font_family(self):
        """获取字体设置"""
        return self.settings.get("font_family", "Courier New")

    def set_font_family(self, font_family):
        """设置字体"""
        self.settings["font_family"] = font_family
        self.save_settings()

    def get_font_size(self):
        """获取字体大小设置"""
        return self.settings.get("font_size", 12)

    def set_font_size(self, font_size):
        """设置字体大小"""
        self.settings["font_size"] = font_size
        self.save_settings()

    def get_code_style(self):
        """获取代码风格设置"""
        return self.settings.get("code_style", "friendly")

    def set_code_style(self, code_style):
        """设置代码风格"""
        self.settings["code_style"] = code_style
        self.save_settings()


BLAME_COLOR_PALETTE = [
    QColor(192, 203, 229),  # light blue
    QColor(222, 228, 240),  # lighter blue
    QColor(235, 235, 255),  # lightest blue
    QColor(255, 255, 255),  # white
]

# icons folder
ICONS_FOLDER = os.path.join(os.path.dirname(__file__), "icons")
