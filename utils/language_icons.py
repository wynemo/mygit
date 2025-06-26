import os

from PyQt6.QtGui import QIcon

from .language_map import LANGUAGE_MAP

# 语言图标映射，将语言类型映射到图标文件名
LANGUAGE_ICON_MAP = {
    "python": "python.svg",
    "javascript": "javascript.svg",
    "typescript": "typescript.svg",
    "java": "java.svg",
    "c": "c.svg",
    "cpp": "cpp.svg",
    "go": "go.svg",
    "rust": "rust.svg",
    "php": "php.svg",
    "ruby": "ruby.svg",
    "swift": "swift.svg",
    "kotlin": "kotlin.svg",
    "dart": "dart.svg",
    "vue": "vue.svg",
    "html": "html.svg",
    "css": "css.svg",
    "json": "json.svg",
    "xml": "xml.svg",
    "yaml": "yaml.svg",
    "markdown": "markdown.svg",
    "md": "markdown.svg",
    "shell": "shell.svg",
    "text": "file.svg",  # 默认文件图标
}


def get_language_icon(file_name: str) -> QIcon:
    """
    根据文件名获取对应的语言图标

    Args:
        file_name: 文件名

    Returns:
        QIcon: 对应的图标对象，如果没有找到则返回默认图标
    """
    # 获取文件扩展名
    file_ext = file_name.split(".")[-1].lower() if "." in file_name else ""

    # 从 LANGUAGE_MAP 获取语言类型
    language = LANGUAGE_MAP.get(file_ext, "text")

    # 获取图标文件名
    icon_filename = LANGUAGE_ICON_MAP.get(language, "file.svg")

    # 构建图标文件路径
    icon_path = os.path.join("icons", "languages", icon_filename)

    # 如果图标文件不存在，使用默认图标
    if not os.path.exists(icon_path):
        icon_path = os.path.join("icons", "languages", "file.svg")
        # 如果默认图标也不存在，返回空图标
        if not os.path.exists(icon_path):
            return QIcon()

    return QIcon(icon_path)


def get_folder_icon() -> QIcon:
    """
    获取文件夹图标

    Returns:
        QIcon: 文件夹图标
    """
    icon_path = os.path.join("icons", "folder.svg")
    if os.path.exists(icon_path):
        return QIcon(icon_path)
    return QIcon()
