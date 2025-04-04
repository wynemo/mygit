import json
import os
from pathlib import Path

class Settings:
    def __init__(self):
        # 获取用户主目录
        home = str(Path.home())
        # 创建配置目录
        self.config_dir = os.path.join(home, '.git_manager')
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)
            
        # 配置文件路径
        self.config_file = os.path.join(self.config_dir, 'settings.json')
        
        # 默认设置
        self.settings = {
            'recent_folders': [],  # 最近打开的文件夹列表
            'last_folder': None,   # 上次打开的文件夹
            'max_recent': 10       # 最大记录数
        }
        
        # 加载已有设置
        self.load_settings()
        
    def load_settings(self):
        """加载设置"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    saved_settings = json.load(f)
                    self.settings.update(saved_settings)
        except Exception as e:
            print(f"加载设置失败: {str(e)}")
            
    def save_settings(self):
        """保存设置"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存设置失败: {str(e)}")
            
    def add_recent_folder(self, folder_path):
        """添加最近打开的文件夹"""
        # 更新最后打开的文件夹
        self.settings['last_folder'] = folder_path
        
        # 更新最近文件夹列表
        recent = self.settings['recent_folders']
        
        # 如果已经在列表中，先移除
        if folder_path in recent:
            recent.remove(folder_path)
            
        # 添加到列表开头
        recent.insert(0, folder_path)
        
        # 保持列表在最大长度以内
        self.settings['recent_folders'] = recent[:self.settings['max_recent']]
        
        # 保存设置
        self.save_settings()
        
    def get_recent_folders(self):
        """获取最近文件夹列表"""
        return self.settings['recent_folders']
        
    def get_last_folder(self):
        """获取上次打开的文件夹"""
        return self.settings['last_folder'] 