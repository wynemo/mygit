import time
from functools import wraps
from typing import Optional

from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget


def get_main_window():
    main_window = QApplication.instance().activeWindow()
    return main_window


def get_main_window_by_parent(parent: QWidget) -> Optional[QMainWindow]:
    while parent:
        if isinstance(parent, QMainWindow):
            return parent
        parent = parent.parent()
    return None


def timeit(func):
    """装饰器，用于测量函数执行时间

    Args:
        func: 被装饰的函数

    Returns:
        wrapper: 包装后的函数
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()  # 记录开始时间
        result = func(*args, **kwargs)  # 执行原函数
        end_time = time.time()  # 记录结束时间
        print(f"函数 {func.__name__} 执行耗时：{end_time - start_time:.4f}秒")
        return result

    return wrapper
